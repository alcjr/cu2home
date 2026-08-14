from django.core.management.base import BaseCommand
from django.db import transaction
from apps.properties.models import Province, Municipality
from apps.properties.data.cuba_geography import CUBA_PROVINCES


class Command(BaseCommand):
    help = "Populate provinces and municipalities of Cuba"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Creando provincias y municipios de Cuba...")

        for province_data in CUBA_PROVINCES:
            province_name = province_data["name"]
            province, created = Province.objects.get_or_create(name=province_name)
            if created:
                self.stdout.write(f"  Provincia creada: {province_name}")
            else:
                self.stdout.write(f"  Provincia existente: {province_name}")

            for mun_name in province_data["municipalities"]:
                mun, created = Municipality.objects.get_or_create(
                    province=province,
                    name=mun_name
                )
                if created:
                    self.stdout.write(f"    Municipio creado: {mun_name}")
                else:
                    self.stdout.write(f"    Municipio existente: {mun_name}")

        self.stdout.write(self.style.SUCCESS("¡Datos de geografía de Cuba cargados correctamente!"))