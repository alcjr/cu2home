"""
Management command para poblar Province y Municipality con la división
político-administrativa vigente de la República de Cuba (15 provincias +
el municipio especial Isla de la Juventud, 168 municipios en total).

Ubicación sugerida dentro de la app 'properties':
    apps/properties/management/__init__.py            (vacío)
    apps/properties/management/commands/__init__.py    (vacío)
    apps/properties/management/commands/populate_cuba_locations.py  (este archivo)

Uso:
    python manage.py populate_cuba_locations
    python manage.py populate_cuba_locations --flush   # borra y repuebla

Notas:
- Es idempotente: usa get_or_create, así que se puede correr varias veces
  sin duplicar registros.
- No se pasan slugs: Province.save() y Municipality.save() ya generan el
  slug automáticamente con slugify(name) si no se provee uno.
- Isla de la Juventud es, en la realidad, un "municipio especial" que no
  pertenece a ninguna provincia. Como Municipality.province es obligatorio
  en el modelo actual, se representa aquí como una Province propia
  ("Isla de la Juventud") con un único Municipality homónimo. Si en el
  futuro se quiere modelar esto de forma más fiel (province nullable +
  flag is_special), habría que migrar el esquema.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.properties.models import Municipality, Province

# Orden oficial ONEI, de oeste a este.
CUBA_LOCATIONS = {
    "Pinar del Río": [
        "Sandino", "Mantua", "Minas de Matahambre", "Viñales", "La Palma",
        "Consolación del Sur", "Pinar del Río", "San Luis", "San Juan y Martínez",
        "Guane", "Los Palacios",
    ],
    "Artemisa": [
        "Bahía Honda", "Mariel", "Guanajay", "Caimito", "Bauta",
        "San Antonio de los Baños", "Güira de Melena", "Alquízar",
        "Artemisa", "Candelaria", "San Cristóbal",
    ],
    "La Habana": [
        "Playa", "Plaza de la Revolución", "Centro Habana", "La Habana Vieja",
        "Regla", "Habana del Este", "Guanabacoa", "San Miguel del Padrón",
        "Diez de Octubre", "Cerro", "Marianao", "La Lisa", "Boyeros",
        "Arroyo Naranjo", "Cotorro",
    ],
    "Mayabeque": [
        "Bejucal", "San José de las Lajas", "Jaruco", "Santa Cruz del Norte",
        "Madruga", "Nueva Paz", "San Nicolás", "Güines", "Melena del Sur",
        "Batabanó", "Quivicán",
    ],
    "Matanzas": [
        "Martí", "Colón", "Perico", "Jovellanos", "Pedro Betancourt",
        "Limonar", "Unión de Reyes", "Ciénaga de Zapata", "Jagüey Grande",
        "Calimete", "Los Arabos", "Matanzas", "Cárdenas",
    ],
    "Cienfuegos": [
        "Aguada de Pasajeros", "Rodas", "Palmira", "Cienfuegos", "Cruces",
        "Cumanayagua", "Lajas", "Abreus",
    ],
    "Villa Clara": [
        "Corralillo", "Quemado de Güines", "Sagua la Grande", "Encrucijada",
        "Camajuaní", "Caibarién", "Remedios", "Placetas", "Santa Clara",
        "Cifuentes", "Ranchuelo", "Santo Domingo", "Manicaragua",
    ],
    "Sancti Spíritus": [
        "Yaguajay", "Jatibonico", "Taguasco", "Cabaiguán", "Fomento",
        "Sancti Spíritus", "Trinidad", "La Sierpe",
    ],
    "Ciego de Ávila": [
        "Chambas", "Morón", "Bolivia", "Ciro Redondo", "Primero de Enero",
        "Ciego de Ávila", "Venezuela", "Florencia", "Majagua", "Baraguá",
    ],
    "Camagüey": [
        "Nuevitas", "Minas", "Sierra de Cubitas", "Esmeralda", "Camagüey",
        "Carlos Manuel de Céspedes", "Vertientes", "Florida", "Guáimaro",
        "Sibanicú", "Najasa", "Jimaguayú", "Santa Cruz del Sur",
    ],
    "Las Tunas": [
        "Manatí", "Puerto Padre", "Jesús Menéndez", "Majibacoa", "Las Tunas",
        "Jobabo", "Colombia", "Amancio",
    ],
    "Holguín": [
        "Rafael Freyre", "Gibara", "Banes", "Antilla", "Báguanos", "Holguín",
        "Calixto García", "Cacocum", "Urbano Noris", "Cueto", "Mayarí",
        "Frank País", "Sagua de Tánamo", "Moa",
    ],
    "Granma": [
        "Río Cauto", "Cauto Cristo", "Jiguaní", "Bayamo", "Yara", "Manzanillo",
        "Campechuela", "Media Luna", "Niquero", "Pilón", "Bartolomé Masó",
        "Buey Arriba", "Guisa",
    ],
    "Santiago de Cuba": [
        "Contramaestre", "Mella", "San Luis", "Songo-La Maya",
        "Santiago de Cuba", "Segundo Frente", "Guamá", "Tercer Frente",
        "Palma Soriano",
    ],
    "Guantánamo": [
        "El Salvador", "Manuel Tames", "Yateras", "Baracoa", "Maisí", "Imías",
        "San Antonio del Sur", "Guantánamo", "Caimanera", "Niceto Pérez",
    ],
    # Municipio especial, sin provincia real. Se modela como "provincia" de
    # un solo municipio homónimo por la restricción province NOT NULL.
    "Isla de la Juventud": [
        "Isla de la Juventud",
    ],
}


class Command(BaseCommand):
    help = (
        "Puebla Province y Municipality con la división político-administrativa "
        "actual de Cuba (15 provincias + Isla de la Juventud, 168 municipios)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Elimina todas las Province/Municipality existentes antes de poblar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write(self.style.WARNING(
                "Eliminando Municipality y Province existentes..."
            ))
            Municipality.objects.all().delete()
            Province.objects.all().delete()

        provinces_created = municipalities_created = 0
        provinces_existing = municipalities_existing = 0

        for province_name, municipality_names in CUBA_LOCATIONS.items():
            province, created = Province.objects.get_or_create(name=province_name)
            if created:
                provinces_created += 1
            else:
                provinces_existing += 1

            for municipality_name in municipality_names:
                _, m_created = Municipality.objects.get_or_create(
                    province=province, name=municipality_name
                )
                if m_created:
                    municipalities_created += 1
                else:
                    municipalities_existing += 1

        self.stdout.write(self.style.SUCCESS(
            f"Provincias: {provinces_created} creadas, {provinces_existing} ya existían."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Municipios: {municipalities_created} creados, {municipalities_existing} ya existían."
        ))
