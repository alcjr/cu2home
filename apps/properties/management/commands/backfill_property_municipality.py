"""
Management command para rellenar `Property.municipality` en los registros
que quedaron con municipality_id NULL tras la importación inicial.

Motivo: properties_property.csv trae `city` como texto libre con el nombre
del municipio (o de una localidad/barrio conocida dentro de él), pero nunca
trajo el `municipality_id` real -- por eso el filtro de municipio siempre
devolvía 0 resultados aunque el código (form/vista/HTMX) es correcto.

Ubicación sugerida:
    apps/properties/management/commands/backfill_property_municipality.py

Uso:
    python manage.py backfill_property_municipality            # aplica los cambios
    python manage.py backfill_property_municipality --dry-run  # solo reporta, no guarda
"""

from django.core.management.base import BaseCommand

from apps.properties.models import Municipality, Property


class Command(BaseCommand):
    help = (
        "Rellena Property.municipality cruzando el campo 'city' con "
        "Municipality.name (dentro de la misma provincia), con un mapa de "
        "alias para barrios/localidades conocidas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué se cambiaría sin guardar nada en la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        qs = Property.objects.filter(municipality__isnull=True).select_related("province")
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No hay propiedades con municipality_id NULL."))
            return

        matched_exact = matched_alias = 0
        unresolved = []

        for prop in qs:
            if prop.province_id is None or not prop.city:
                unresolved.append(prop)
                continue

            

            municipality = Municipality.objects.filter(
                province_id=prop.province_id, name__iexact=prop.city.strip()
            ).first()
            is_alias = False

            if municipality is None and city_key in CITY_ALIASES:
                municipality = Municipality.objects.filter(
                    province_id=prop.province_id, name=CITY_ALIASES[city_key]
                ).first()
                is_alias = True

            if municipality is None:
                unresolved.append(prop)
                continue

            if is_alias:
                matched_alias += 1
            else:
                matched_exact += 1

            self.stdout.write(
                f"  [{'DRY-RUN' if dry_run else 'OK'}] Property #{prop.pk} "
                f"city={prop.city!r} (provincia={prop.province.name}) -> "
                f"municipio={municipality.name!r}{' (alias)' if is_alias else ''}"
            )

            if not dry_run:
                prop.municipality = municipality
                prop.save(update_fields=["municipality"])

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Coincidencia exacta: {matched_exact} | Por alias: {matched_alias} | "
            f"Sin resolver: {len(unresolved)} (de {total} totales)"
        ))

        if unresolved:
            self.stdout.write(self.style.WARNING(
                "\nRevisar manualmente (city/province_id no cuadran con ningún "
                "municipio ni alias conocido):"
            ))
            for prop in unresolved:
                province_name = prop.province.name if prop.province_id else "—"
                self.stdout.write(f"  - Property #{prop.pk}: city={prop.city!r}, provincia={province_name!r}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nModo --dry-run: no se guardó ningún cambio."))
