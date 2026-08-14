import os
import random
import tempfile
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.files import File
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

from apps.properties.models import MAX_IMAGES_PER_PROPERTY, Property, PropertyImage, PropertyStatus


class Command(BaseCommand):
    help = "Populate the database with sample properties for all Cuban provinces."

    # Datos de provincias y municipios (coordenadas aproximadas en EPSG:4326)
    CUBAN_DATA = {
        "Pinar del Río": {
            "municipios": [
                ("Pinar del Río", 22.4175, -83.6981),
                ("Viñales", 22.6185, -83.7512),
                ("San Luis", 22.2830, -83.7570),
            ]
        },
        "Artemisa": {
            "municipios": [
                ("Artemisa", 22.8137, -82.7619),
                ("Güira de Melena", 22.8003, -82.5068),
                ("Bauta", 22.9821, -82.5478),
            ]
        },
        "La Habana": {
            "municipios": [
                ("Playa", 23.0944, -82.4482),
                ("Centro Habana", 23.1336, -82.3638),
                ("Vedado", 23.1172, -82.3970),
                ("Miramar", 23.1106, -82.4298),
            ]
        },
        "Mayabeque": {
            "municipios": [
                ("San José de las Lajas", 22.9683, -82.1559),
                ("Jaruco", 23.0422, -82.0126),
                ("Madruga", 22.9147, -81.8582),
            ]
        },
        "Matanzas": {
            "municipios": [
                ("Matanzas", 23.0494, -81.5766),
                ("Varadero", 23.1422, -81.2861),
                ("Cárdenas", 23.0361, -81.2056),
            ]
        },
        "Villa Clara": {
            "municipios": [
                ("Santa Clara", 22.4069, -79.9647),
                ("Placetas", 22.3172, -79.6477),
                ("Remedios", 22.4928, -79.5458),
            ]
        },
        "Cienfuegos": {
            "municipios": [
                ("Cienfuegos", 22.1456, -80.4521),
                ("Abreus", 22.2783, -80.5686),
                ("Cruces", 22.3403, -80.2708),
            ]
        },
        "Sancti Spíritus": {
            "municipios": [
                ("Sancti Spíritus", 21.9322, -79.4425),
                ("Trinidad", 21.8067, -79.9847),
                ("Yaguajay", 22.3311, -79.2367),
            ]
        },
        "Ciego de Ávila": {
            "municipios": [
                ("Ciego de Ávila", 21.8400, -78.7619),
                ("Morón", 22.1094, -78.6267),
                ("Chambas", 22.1958, -78.4917),
            ]
        },
        "Camagüey": {
            "municipios": [
                ("Camagüey", 21.3789, -77.9186),
                ("Florida", 21.5256, -78.2272),
                ("Nuevitas", 21.5461, -77.2644),
            ]
        },
        "Las Tunas": {
            "municipios": [
                ("Las Tunas", 20.9608, -76.9511),
                ("Puerto Padre", 21.1958, -76.5886),
                ("Amancio", 20.8197, -77.5794),
            ]
        },
        "Holguín": {
            "municipios": [
                ("Holguín", 20.8881, -76.2606),
                ("Gibara", 21.1097, -76.1328),
                ("Banes", 20.9694, -75.7186),
            ]
        },
        "Granma": {
            "municipios": [
                ("Bayamo", 20.3769, -76.6436),
                ("Manzanillo", 20.3403, -77.1167),
                ("Jiguaní", 20.3775, -76.4250),
            ]
        },
        "Santiago de Cuba": {
            "municipios": [
                ("Santiago de Cuba", 20.0247, -75.8219),
                ("San Luis", 20.1883, -75.8508),
                ("El Cobre", 20.0486, -75.9461),
            ]
        },
        "Guantánamo": {
            "municipios": [
                ("Guantánamo", 20.1453, -75.2039),
                ("Baracoa", 20.3478, -74.4961),
                ("Maisí", 20.2469, -74.1517),
            ]
        },
        "Isla de la Juventud": {
            "municipios": [
                ("Nueva Gerona", 21.8867, -82.8008),
                ("San Fe", 21.7833, -82.8833),
            ]
        },
    }

    # Tipos de propiedad (coinciden con PROPERTY_TYPES en constants)
    PROPERTY_TYPES = ["apartment", "house", "villa", "commercial", "land", "other"]

    # Palabras para generar títulos y descripciones
    ADJECTIVES = ["Cómodo", "Luminoso", "Amplio", "Moderno", "Acogedor", "Exclusivo", "Céntrico", "Tranquilo"]
    NOUNS = ["apartamento", "casa", "villa", "local", "terreno", "chalet", "dúplex", "ático"]
    FEATURES = ["con vistas al mar", "cerca del centro", "totalmente reformado", "con piscina",
                "con jardín", "en urbanización privada", "ideal para familias", "rentabilidad asegurada"]

    def add_arguments(self, parser):
        parser.add_argument(
            "--total",
            type=int,
            default=50,
            help="Número total de propiedades a crear (se distribuyen entre todas las provincias).",
        )
        parser.add_argument(
            "--images-per-property",
            type=int,
            default=5,
            help="Número de imágenes por propiedad (máximo {MAX_IMAGES_PER_PROPERTY}).",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Si existe alguna propiedad, no crea nuevas (evita duplicados).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        total = options["total"]
        images_per_prop = min(options["images_per_property"], MAX_IMAGES_PER_PROPERTY)
        skip_existing = options["skip_existing"]

        if skip_existing and Property.objects.exists():
            self.stdout.write(self.style.WARNING("Ya existen propiedades. Saltando creación."))
            return

        # Recolectar todos los municipios con sus coordenadas
        locations = []
        for province, data in self.CUBAN_DATA.items():
            for mun, lat, lng in data["municipios"]:
                locations.append((province, mun, lat, lng))

        # Distribuir propiedades uniformemente
        num_provinces = len(self.CUBAN_DATA)
        per_province = max(1, total // num_provinces)
        extra = total - (per_province * num_provinces)

        created = 0
        for province, data in self.CUBAN_DATA.items():
            mun_list = data["municipios"]
            count = per_province + (1 if extra > 0 else 0)
            extra -= 1
            self.stdout.write(f"Creando {count} propiedades en {province}...")

            for i in range(count):
                mun, lat, lng = random.choice(mun_list)
                prop = self._create_property(province, mun, lat, lng)
                if prop:
                    # Crear las imágenes
                    for img_idx in range(images_per_prop):
                        self._create_image(prop, img_idx)
                    created += 1

        self.stdout.write(
            self.style.SUCCESS(f"✅ Se crearon {created} propiedades con {images_per_prop} imágenes cada una.")
        )

    def _create_property(self, province, city, lat, lng):
        """Crea una propiedad con datos realistas."""
        ptype = random.choice(self.PROPERTY_TYPES)
        # Generar título
        adj = random.choice(self.ADJECTIVES)
        noun = random.choice(self.NOUNS)
        feature = random.choice(self.FEATURES)
        title = f"{adj} {noun} en {city}, {province} - {feature}"

        # Slug único
        base_slug = slugify(title)[:80]
        slug = base_slug
        counter = 1
        while Property.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Precio en CUP (rango 5000 - 500000)
        price = Decimal(random.randint(5000, 500000))
        surface = random.randint(40, 400)
        rooms = random.randint(1, 5)
        bathrooms = random.randint(1, 3)

        # Booleanos aleatorios
        has_elevator = random.choice([True, False])
        has_heating = random.choice([True, False])
        has_air_conditioning = random.choice([True, False])

        # Estado: mayormente disponibles
        status = random.choices(
            [PropertyStatus.AVAILABLE, PropertyStatus.RESERVED, PropertyStatus.SOLD],
            weights=[0.8, 0.1, 0.1],
        )[0]

        # Descripción más detallada
        desc = (
            f"Excelente {noun} en {city}, provincia de {province}. "
            f"Superficie de {surface} m², {rooms} habitaciones y {bathrooms} baños. "
            f"{'Cuenta con ascensor. ' if has_elevator else ''}"
            f"{'Calefacción central. ' if has_heating else ''}"
            f"{'Aire acondicionado en todas las estancias. ' if has_air_conditioning else ''}"
            f"Precio: {price} CUP. {feature}. "
            "Ideal para inversión o residencia familiar."
        )

        # Crear el objeto (sin guardar aún)
        prop = Property(
            property_type=ptype,
            city=city,
            province=province,
            address=f"Calle {random.randint(1, 100)} #{random.randint(1, 50)}",
            location=Point(lng, lat, srid=4326),  # OJO: Point(lng, lat)
            price=price,
            surface=surface,
            rooms=rooms,
            bathrooms=bathrooms,
            has_elevator=has_elevator,
            has_heating=has_heating,
            has_air_conditioning=has_air_conditioning,
            slug=slug,
            is_active=True,
            views_count=random.randint(0, 500),
            status=status,
            # agent se deja NULL (o se podría crear un usuario de prueba)
        )

        # Ahora guardamos la traducción (parler)
        prop.set_current_language('es')
        prop.title = title
        prop.description = desc
        prop.save()

        return prop

    def _create_image(self, property_obj, index):
        """Genera una imagen ficticia y la asocia a la propiedad."""
        # Crear imagen en memoria
        width, height = 800, 600
        color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
        img = Image.new('RGB', (width, height), color=color)
        draw = ImageDraw.Draw(img)

        # Texto indicando la propiedad
        text = f"Propiedad #{property_obj.id} - Imagen {index+1}"
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
            font = ImageFont.load_default()

        # Calcular posición centrada
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # Dibujar sombra blanca y texto negro
        draw.text((x+2, y+2), text, fill=(255, 255, 255), font=font)
        draw.text((x, y), text, fill=(0, 0, 0), font=font)

        # Guardar en BytesIO
        img_io = BytesIO()
        img.save(img_io, format='JPEG', quality=90)
        img_io.seek(0)

        # Crear el objeto ImageFile
        filename = f"property_{property_obj.id}_img_{index+1}.jpg"
        image_file = ImageFile(img_io, name=filename)

        # Crear PropertyImage
        PropertyImage.objects.create(
            property=property_obj,
            image=image_file,
            order=index,
            is_cover=(index == 0),
        )