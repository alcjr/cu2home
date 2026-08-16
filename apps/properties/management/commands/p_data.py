"""
Management command para cargar/actualizar Province, Municipality, Property
y PropertyImage a partir de los CSV exportados (properties_province.csv,
properties_municipality.csv, properties_property.csv,
properties_propertyimage.csv).

Ubicación sugerida:
    apps/properties/management/commands/import_property_data.py

Uso:
    python manage.py import_property_data \
        --province-csv /ruta/properties_province.csv \
        --municipality-csv /ruta/properties_municipality.csv \
        --property-csv /ruta/properties_property.csv \
        --image-csv /ruta/properties_propertyimage.csv

Por defecto busca los 4 archivos en ./data/ con esos mismos nombres.

QUÉ RESUELVE ESTE COMANDO
--------------------------
1. Los `province_id` dentro de properties_property.csv (valores 1-16) NO
   corresponden a los id reales de la tabla Province en tu base de datos
   (17-32 según properties_province.csv). Vienen numerados por posición
   (1=Pinar del Río ... 16=Isla de la Juventud) en vez de usar el id real.
   Este comando construye el mapeo posición -> id real a partir del propio
   properties_province.csv (ordenado por id) y remapea cada `province_id`
   de Property antes de guardarlo.
2. properties_municipality.csv SÍ usa los id reales de provincia
   (17-32), así que se importa tal cual.
3. `municipality_id` viene NULL en las 120 propiedades del CSV: se
   respeta ese NULL, no se inventa un municipio.
4. `location` viene en WKB hexadecimal (formato nativo de PostGIS/Django);
   se reconstruye con GEOSGeometry directamente desde el hex.
5. Los id de Property (1-120) se preservan, porque
   properties_propertyimage.csv referencia `property_id` con esos mismos
   valores (no están remapeados, y no lo necesitan).

6. properties_property_translation.csv trae title/description (django-parler,
   language_code='es', master_id = id de Property, coincide 1:1 con las 120
   propiedades). Se importa con update_or_create por id, igual que el resto.

LO QUE ESTE COMANDO **NO** HACE
--------------------------------
- No copia los binarios de imagen: `properties_propertyimage.csv` sólo
  trae las rutas (properties/<id>/images/<archivo>.jpg); el ImageField
  quedará apuntando a esa ruta dentro de MEDIA_ROOT/tu storage, pero el
  archivo en sí debe subirse aparte si no existe ya ahí.
"""

import csv
import re
from pathlib import Path

from django.apps import apps as django_apps
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.properties.models import Municipality, Property, PropertyImage, Province

PropertyTranslation = django_apps.get_model("properties", "PropertyTranslation")

NULL = "NULL"


def clean(value):
    """Convierte el literal 'NULL' del CSV en None; deja el resto igual."""
    return None if value == NULL else value


def to_bool(value):
    return str(value).strip().lower() == "true"


def to_datetime(value):
    """Postgres exporta offsets tipo '+02' (sin minutos); parse_datetime
    de Django exige '+02:00'. Se normaliza antes de parsear."""
    value = value.strip()
    value = re.sub(r"([+-]\d{2})$", r"\1:00", value)
    dt = parse_datetime(value)
    if dt is None:
        raise ValueError(f"No se pudo parsear la fecha: {value!r}")
    return dt


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = (
        "Importa/actualiza Province, Municipality, Property y PropertyImage "
        "desde los CSV properties_province.csv, properties_municipality.csv, "
        "properties_property.csv y properties_propertyimage.csv."
    )

    def add_arguments(self, parser):
        parser.add_argument("--province-csv", default="data/properties_province.csv")
        parser.add_argument("--municipality-csv", default="data/properties_municipality.csv")
        parser.add_argument("--property-csv", default="data/properties_property.csv")
        parser.add_argument("--image-csv", default="data/properties_propertyimage.csv")
        parser.add_argument(
            "--translation-csv",
            default="data/properties_property_translation.csv",
            help="Opcional: si no existe, se omite sin error (title/description quedarán vacíos).",
        )

    def handle(self, *args, **options):
        paths = {
            key: Path(options[key])
            for key in ("province_csv", "municipality_csv", "property_csv", "image_csv")
        }
        for key, path in paths.items():
            if not path.exists():
                raise CommandError(f"No se encontró el archivo para --{key.replace('_', '-')}: {path}")

        translation_path = Path(options["translation_csv"])
        has_translations = translation_path.exists()
        if not has_translations:
            self.stdout.write(self.style.WARNING(
                f"No se encontró {translation_path}; se omite la importación de "
                "title/description (quedarán vacíos en las propiedades nuevas)."
            ))

        with transaction.atomic():
            province_id_map = self.import_provinces(paths["province_csv"])
            self.import_municipalities(paths["municipality_csv"])
            self.import_properties(paths["property_csv"], province_id_map)
            self.import_property_images(paths["image_csv"])
            if has_translations:
                self.import_translations(translation_path)

        self.stdout.write(self.style.SUCCESS("Importación completada."))

    # ------------------------------------------------------------------
    def import_provinces(self, path):
        rows = sorted(read_csv(path), key=lambda r: int(r["id"]))
        created = updated = 0
        for row in rows:
            _, was_created = Province.objects.update_or_create(
                pk=int(row["id"]),
                defaults={"name": row["name"], "slug": row["slug"]},
            )
            created += was_created
            updated += not was_created
        self.stdout.write(f"Province: {created} creadas, {updated} actualizadas.")

        # Mapea la posición ordinal (1-based, en el orden del CSV real)
        # al id real de esa provincia. Esto es lo que arregla el
        # desfase de province_id en properties_property.csv.
        return {position: int(row["id"]) for position, row in enumerate(rows, start=1)}

    def import_municipalities(self, path):
        rows = read_csv(path)
        created = updated = 0
        missing_provinces = set()
        for row in rows:
            province_id = int(row["province_id"])
            if not Province.objects.filter(pk=province_id).exists():
                missing_provinces.add(province_id)
                continue
            _, was_created = Municipality.objects.update_or_create(
                pk=int(row["id"]),
                defaults={
                    "name": row["name"],
                    "slug": row["slug"],
                    "province_id": province_id,
                },
            )
            created += was_created
            updated += not was_created
        self.stdout.write(f"Municipality: {created} creadas, {updated} actualizadas.")
        if missing_provinces:
            self.stdout.write(self.style.WARNING(
                f"Municipios omitidos por province_id inexistente: {sorted(missing_provinces)}"
            ))

    def import_properties(self, path, province_id_map):
        rows = read_csv(path)
        created = updated = 0
        remap_warnings = 0

        for row in rows:
            raw_province_id = int(row["province_id"])
            real_province_id = province_id_map.get(raw_province_id)
            if real_province_id is None:
                # El valor ya era un id real (o no se pudo mapear); se usa tal cual.
                real_province_id = raw_province_id
                remap_warnings += 1

            municipality_id = clean(row["municipality_id"])
            agent_id = clean(row["agent_id"])

            defaults = {
                "property_type": row["property_type"],
                "price": row["price"],
                "surface": clean(row["surface"]),
                "rooms": clean(row["rooms"]),
                "bathrooms": clean(row["bathrooms"]),
                "has_elevator": to_bool(row["has_elevator"]),
                "has_heating": to_bool(row["has_heating"]),
                "has_air_conditioning": to_bool(row["has_air_conditioning"]),
                "city": row["city"],
                "is_active": to_bool(row["is_active"]),
                "views_count": int(row["views_count"]),
                "created_at": to_datetime(row["created_at"]),
                "updated_at": to_datetime(row["updated_at"]),
                "agent_id": int(agent_id) if agent_id is not None else None,
                "location": GEOSGeometry(row["location"]) if row["location"] else None,
                "slug": row["slug"],
                "address": clean(row["address"]),
                "status": row["status"],
                "province_id": real_province_id,
                "municipality_id": int(municipality_id) if municipality_id is not None else None,
            }

            _, was_created = Property.objects.update_or_create(
                pk=int(row["id"]), defaults=defaults
            )
            created += was_created
            updated += not was_created

        self.stdout.write(f"Property: {created} creadas, {updated} actualizadas.")
        if remap_warnings:
            self.stdout.write(self.style.WARNING(
                f"{remap_warnings} filas tenían un province_id que no se pudo remapear "
                "por posición; se usó el valor tal cual venía en el CSV."
            ))
        self.stdout.write(self.style.WARNING(
            "Nota: title/description no se importaron (viven en la tabla de "
            "traducciones de django-parler, no incluida en properties_property.csv)."
        ))

    def import_property_images(self, path):
        rows = read_csv(path)
        created = updated = 0
        missing_properties = set()
        for row in rows:
            property_id = int(row["property_id"])
            if not Property.objects.filter(pk=property_id).exists():
                missing_properties.add(property_id)
                continue
            _, was_created = PropertyImage.objects.update_or_create(
                pk=int(row["id"]),
                defaults={
                    "image": row["image"],
                    "is_cover": to_bool(row["is_cover"]),
                    "order": int(row["order"]),
                    "created_at": to_datetime(row["created_at"]),
                    "property_id": property_id,
                },
            )
            created += was_created
            updated += not was_created
        self.stdout.write(f"PropertyImage: {created} creadas, {updated} actualizadas.")
        if missing_properties:
            self.stdout.write(self.style.WARNING(
                f"Imágenes omitidas por property_id inexistente: {sorted(missing_properties)}"
            ))
        self.stdout.write(self.style.WARNING(
            "Nota: sólo se importaron las rutas de imagen; sube los archivos "
            "binarios a tu storage/MEDIA_ROOT bajo esas mismas rutas si aún no están."
        ))

    def import_translations(self, path):
        rows = read_csv(path)
        created = updated = 0
        missing_properties = set()
        for row in rows:
            master_id = int(row["master_id"])
            if not Property.objects.filter(pk=master_id).exists():
                missing_properties.add(master_id)
                continue
            _, was_created = PropertyTranslation.objects.update_or_create(
                pk=int(row["id"]),
                defaults={
                    "language_code": row["language_code"],
                    "title": row["title"],
                    "description": row["description"],
                    "master_id": master_id,
                },
            )
            created += was_created
            updated += not was_created
        self.stdout.write(f"PropertyTranslation: {created} creadas, {updated} actualizadas.")
        if missing_properties:
            self.stdout.write(self.style.WARNING(
                f"Traducciones omitidas por master_id (property) inexistente: {sorted(missing_properties)}"
            ))
