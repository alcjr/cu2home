# -*- coding: utf-8 -*-
"""
properties/management/commands/p_property_images.py
=====================================================

Management command de Django que puebla `properties_propertyimage` con
fotos para los inmuebles ya existentes en `properties_property`.

Fuente de las fotos: Lorem Picsum (https://picsum.photos), servicio
gratuito pensado para datos de demo/desarrollo, sin API key. Se usa el
modo "seed" (https://picsum.photos/seed/{seed}/{ancho}/{alto}) con una
seed determinista por imagen (f"property-{property_id}-{n}"), de forma
que relanzar el comando con la misma --seed reproduce exactamente el
mismo set de imágenes.

Cantidad de imágenes por inmueble: aleatoria entre --min-per-property y
--max-per-property (por defecto, este último es MAX_IMAGES_PER_PROPERTY
de settings, leído de config.ini). La primera imagen de cada inmueble
(order=0) se marca is_cover=True.

Requiere el paquete `requests` (no viene con Django). Si no está
instalado en el entorno: pip install requests

UBICACIÓN DEL ARCHIVO (requerida por Django para que se reconozca como
comando):
    properties/
        management/
            __init__.py
            commands/
                __init__.py
                p_property_images.py   <-- este archivo

USO:
    python manage.py p_property_images
    python manage.py p_property_images --dry-run
    python manage.py p_property_images --only-missing          (default)
    python manage.py p_property_images --flush                 (borra y regenera todo)
    python manage.py p_property_images --min-per-property 5 --max-per-property 10
    python manage.py p_property_images --seed 42
    python manage.py p_property_images --width 1200 --height 800
    python manage.py p_property_images --delay 0.05
    python manage.py p_property_images --property-type apartment
    python manage.py p_property_images --limit 50               (solo pruebas)
"""

import random
import time
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

# Imports relativos al propio app: funcionan sin importar si el app está
# declarado en INSTALLED_APPS como "properties" o como "apps.properties"
# (mismo criterio que p_properties.py).
from ...models import Property, PropertyImage

PICSUM_SEED_URL = "https://picsum.photos/seed/{seed}/{width}/{height}"

DEFAULT_MIN_PER_PROPERTY = 3
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
DEFAULT_TIMEOUT = 15  # segundos por descarga
DEFAULT_RETRIES = 3
DEFAULT_DELAY = 0.0  # pausa entre descargas, por si el servicio rate-limita


class Command(BaseCommand):
    help = (
        "Puebla properties_propertyimage descargando fotos deterministas "
        "(picsum.photos, modo seed) para cada inmueble de properties_property "
        "que aún no tenga imágenes (o todos, con --flush)."
    )

    # ------------------------------------------------------------------ #
    # CLI
    # ------------------------------------------------------------------ #
    def add_arguments(self, parser):
        parser.add_argument(
            "--min-per-property", type=int, default=DEFAULT_MIN_PER_PROPERTY,
            help=f"Mínimo de imágenes por inmueble (default {DEFAULT_MIN_PER_PROPERTY}).",
        )
        parser.add_argument(
            "--max-per-property", type=int, default=None,
            help="Máximo de imágenes por inmueble (default: MAX_IMAGES_PER_PROPERTY de settings).",
        )
        parser.add_argument(
            "--width", type=int, default=DEFAULT_WIDTH,
            help=f"Ancho en px de cada imagen (default {DEFAULT_WIDTH}).",
        )
        parser.add_argument(
            "--height", type=int, default=DEFAULT_HEIGHT,
            help=f"Alto en px de cada imagen (default {DEFAULT_HEIGHT}).",
        )
        parser.add_argument(
            "--seed", type=int, default=None,
            help="Semilla para random (reparto de cantidades por inmueble). No afecta "
                 "al contenido de cada foto, que ya es determinista por su propia seed.",
        )
        parser.add_argument(
            "--flush", action="store_true",
            help="Elimina las imágenes existentes de los inmuebles afectados antes de poblar.",
        )
        parser.add_argument(
            "--only-missing", action="store_true", default=True,
            help="(Default) Salta inmuebles que ya tengan al menos una imagen.",
        )
        parser.add_argument(
            "--property-type", type=str, default=None,
            help="Filtra por un property_type concreto (por defecto, todos).",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Procesa como máximo N inmuebles (útil para probar antes de lanzar todo).",
        )
        parser.add_argument(
            "--delay", type=float, default=DEFAULT_DELAY,
            help=f"Pausa en segundos entre descargas (default {DEFAULT_DELAY}).",
        )
        parser.add_argument(
            "--timeout", type=int, default=DEFAULT_TIMEOUT,
            help=f"Timeout en segundos por descarga (default {DEFAULT_TIMEOUT}).",
        )
        parser.add_argument(
            "--retries", type=int, default=DEFAULT_RETRIES,
            help=f"Reintentos por imagen si falla la descarga (default {DEFAULT_RETRIES}).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo muestra el plan de generación, no descarga ni escribe nada.",
        )

    # ------------------------------------------------------------------ #
    # ENTRY POINT
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        if requests is None and not options["dry_run"]:
            raise CommandError(
                "Falta el paquete 'requests' (pip install requests). "
                "Añádelo a requirements.txt."
            )

        if options["seed"] is not None:
            random.seed(options["seed"])

        min_per = options["min_per_property"]
        max_per = options["max_per_property"] or getattr(settings, "MAX_IMAGES_PER_PROPERTY", 10)

        if min_per < 1:
            raise CommandError("--min-per-property debe ser >= 1.")
        if max_per < min_per:
            raise CommandError("--max-per-property debe ser >= --min-per-property.")
        if max_per > getattr(settings, "MAX_IMAGES_PER_PROPERTY", max_per):
            self.stdout.write(self.style.WARNING(
                f"[aviso] --max-per-property ({max_per}) supera "
                f"MAX_IMAGES_PER_PROPERTY ({settings.MAX_IMAGES_PER_PROPERTY}) de settings."
            ))

        properties = self._load_target_properties(options)
        if not properties:
            self.stdout.write(self.style.WARNING("No hay inmuebles que coincidan con los filtros. Nada que hacer."))
            return

        plan = self._plan_counts(properties, min_per, max_per)
        self._print_plan_summary(plan, options)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\n[dry-run] No se ha descargado ni escrito nada."))
            return

        if options["flush"]:
            target_ids = [p.id for p in properties]
            deleted, _ = PropertyImage.objects.filter(property_id__in=target_ids).delete()
            self.stdout.write(self.style.WARNING(f"[flush] Se eliminaron {deleted} imágenes existentes."))

        stats = self._populate_images(plan, options)
        self._print_result_summary(stats)

    # ------------------------------------------------------------------ #
    # CARGA / FILTRADO DE INMUEBLES OBJETIVO
    # ------------------------------------------------------------------ #
    def _load_target_properties(self, options):
        qs = Property.objects.all().order_by("id")

        if options["property_type"]:
            qs = qs.filter(property_type=options["property_type"])

        if options["only_missing"] and not options["flush"]:
            qs = qs.filter(images__isnull=True)

        qs = qs.distinct()

        if options["limit"]:
            qs = qs[: options["limit"]]

        return list(qs)

    # ------------------------------------------------------------------ #
    # PLANIFICACIÓN: cuántas imágenes por inmueble
    # ------------------------------------------------------------------ #
    def _plan_counts(self, properties, min_per, max_per):
        """Devuelve lista de tuplas (property, n_imagenes)."""
        return [(p, random.randint(min_per, max_per)) for p in properties]

    def _print_plan_summary(self, plan, options):
        total_images = sum(n for _, n in plan)
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"PLAN: {len(plan)} inmuebles -> {total_images} imágenes a generar "
            f"({options['width']}x{options['height']}px, picsum.photos)"
        )
        self.stdout.write("=" * 60)

    # ------------------------------------------------------------------ #
    # DESCARGA + GUARDADO
    # ------------------------------------------------------------------ #
    def _download_image_bytes(self, seed, width, height, timeout, retries):
        url = PICSUM_SEED_URL.format(seed=seed, width=width, height=height)
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                return response.content
            except requests.RequestException as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2 ** attempt, 10))  # backoff exponencial simple
        raise last_error

    def _populate_images(self, plan, options):
        width, height = options["width"], options["height"]
        timeout, retries, delay = options["timeout"], options["retries"], options["delay"]

        created = 0
        failed_properties = []
        processed_properties = 0
        total = len(plan)

        for property_obj, n_images in plan:
            try:
                with transaction.atomic():
                    for i in range(n_images):
                        seed = f"property-{property_obj.id}-{i + 1}"
                        image_bytes = self._download_image_bytes(seed, width, height, timeout, retries)

                        filename = f"{property_obj.id}_{i + 1}.jpg"
                        img = PropertyImage(
                            property=property_obj,
                            order=i,
                            is_cover=(i == 0),
                        )
                        img.image.save(filename, ContentFile(image_bytes), save=True)
                        created += 1

                        if delay:
                            time.sleep(delay)
            except Exception as exc:  # noqa: BLE001 - queremos seguir con el resto de inmuebles
                failed_properties.append((property_obj.id, str(exc)))
                self.stdout.write(self.style.ERROR(
                    f"  [error] inmueble {property_obj.id}: {exc} -- se omite, sigue con el resto"
                ))

            processed_properties += 1
            if processed_properties % 25 == 0 or processed_properties == total:
                self.stdout.write(f"  progreso: {processed_properties}/{total} inmuebles procesados...")

        return {
            "created": created,
            "processed_properties": processed_properties,
            "failed_properties": failed_properties,
        }

    # ------------------------------------------------------------------ #
    # REPORTE FINAL
    # ------------------------------------------------------------------ #
    def _print_result_summary(self, stats):
        self.stdout.write("=" * 60)
        self.stdout.write(f"RESULTADO: {stats['created']} imágenes creadas "
                           f"para {stats['processed_properties']} inmuebles procesados")
        if stats["failed_properties"]:
            self.stdout.write(self.style.WARNING(
                f"\n{len(stats['failed_properties'])} inmuebles con fallos de descarga (omitidos, relanzables):"
            ))
            for property_id, error in stats["failed_properties"][:20]:
                self.stdout.write(f"  - inmueble {property_id}: {error}")
            if len(stats["failed_properties"]) > 20:
                self.stdout.write(f"  ... y {len(stats['failed_properties']) - 20} más.")
            self.stdout.write(
                "\nPuedes relanzar el comando (sin --flush) para completar solo los que faltan: "
                "--only-missing es el comportamiento por defecto."
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nSin fallos de descarga."))
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("¡Listo! Tabla properties_propertyimage poblada."))
