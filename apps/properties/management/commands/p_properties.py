import random
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

from apps.properties.constants import PROPERTY_TYPES
from apps.properties.models import (
    Municipality,
    Property,
    PropertyImage,
    PropertyOfferType,
    PropertyStatus,
    Province,
)


MAX_IMAGES_PER_PROPERTY = settings.MAX_IMAGES_PER_PROPERTY


class Command(BaseCommand):
    help = (
        "Populate the database with sample properties "
        "for all Cuban provinces."
    )

    CUBAN_DATA = {
        "Pinar del Río": {
            "municipios": [
                ("Pinar del Río", 22.4175, -83.6981),
                ("Viñales", 22.6185, -83.7512),
                ("San Luis", 22.2830, -83.7570),
            ],
        },
        "Artemisa": {
            "municipios": [
                ("Artemisa", 22.8137, -82.7619),
                ("Güira de Melena", 22.8003, -82.5068),
                ("Bauta", 22.9821, -82.5478),
            ],
        },
        "La Habana": {
            "municipios": [
                ("Playa", 23.0944, -82.4482),
                ("Centro Habana", 23.1336, -82.3638),
                ("Vedado", 23.1172, -82.3970),
                ("Miramar", 23.1106, -82.4298),
            ],
        },
        "Mayabeque": {
            "municipios": [
                ("San José de las Lajas", 22.9683, -82.1559),
                ("Jaruco", 23.0422, -82.0126),
                ("Madruga", 22.9147, -81.8582),
            ],
        },
        "Matanzas": {
            "municipios": [
                ("Matanzas", 23.0494, -81.5766),
                ("Varadero", 23.1422, -81.2861),
                ("Cárdenas", 23.0361, -81.2056),
            ],
        },
        "Villa Clara": {
            "municipios": [
                ("Santa Clara", 22.4069, -79.9647),
                ("Placetas", 22.3172, -79.6477),
                ("Remedios", 22.4928, -79.5458),
            ],
        },
        "Cienfuegos": {
            "municipios": [
                ("Cienfuegos", 22.1456, -80.4521),
                ("Abreus", 22.2783, -80.5686),
                ("Cruces", 22.3403, -80.2708),
            ],
        },
        "Sancti Spíritus": {
            "municipios": [
                ("Sancti Spíritus", 21.9322, -79.4425),
                ("Trinidad", 21.8067, -79.9847),
                ("Yaguajay", 22.3311, -79.2367),
            ],
        },
        "Ciego de Ávila": {
            "municipios": [
                ("Ciego de Ávila", 21.8400, -78.7619),
                ("Morón", 22.1094, -78.6267),
                ("Chambas", 22.1958, -78.4917),
            ],
        },
        "Camagüey": {
            "municipios": [
                ("Camagüey", 21.3789, -77.9186),
                ("Florida", 21.5256, -78.2272),
                ("Nuevitas", 21.5461, -77.2644),
            ],
        },
        "Las Tunas": {
            "municipios": [
                ("Las Tunas", 20.9608, -76.9511),
                ("Puerto Padre", 21.1958, -76.5886),
                ("Amancio", 20.8197, -77.5794),
            ],
        },
        "Holguín": {
            "municipios": [
                ("Holguín", 20.8881, -76.2606),
                ("Gibara", 21.1097, -76.1328),
                ("Banes", 20.9694, -75.7186),
            ],
        },
        "Granma": {
            "municipios": [
                ("Bayamo", 20.3769, -76.6436),
                ("Manzanillo", 20.3403, -77.1167),
                ("Jiguaní", 20.3775, -76.4250),
            ],
        },
        "Santiago de Cuba": {
            "municipios": [
                ("Santiago de Cuba", 20.0247, -75.8219),
                ("San Luis", 20.1883, -75.8508),
                ("El Cobre", 20.0486, -75.9461),
            ],
        },
        "Guantánamo": {
            "municipios": [
                ("Guantánamo", 20.1453, -75.2039),
                ("Baracoa", 20.3478, -74.4961),
                ("Maisí", 20.2469, -74.1517),
            ],
        },
        "Isla de la Juventud": {
            "municipios": [
                ("Nueva Gerona", 21.8867, -82.8008),
                ("San Fe", 21.7833, -82.8833),
            ],
        },
    }

    PROPERTY_TYPE_VALUES = [
        value for value, _label in PROPERTY_TYPES
    ]

    OFFER_TYPES = [
        PropertyOfferType.SALE,
        PropertyOfferType.RENT,
        PropertyOfferType.SWAP,
        PropertyOfferType.SALE_OR_RENT,
    ]

    ADJECTIVES = [
        "Cómodo",
        "Luminoso",
        "Amplio",
        "Moderno",
        "Acogedor",
        "Exclusivo",
        "Céntrico",
        "Tranquilo",
    ]

    NOUNS = [
        "apartamento",
        "casa",
        "villa",
        "local",
        "terreno",
        "chalet",
        "dúplex",
        "ático",
    ]

    FEATURES = [
        "con vistas al mar",
        "cerca del centro",
        "totalmente reformado",
        "con piscina",
        "con jardín",
        "en urbanización privada",
        "ideal para familias",
        "rentabilidad asegurada",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--total",
            type=int,
            default=50,
            help=(
                "Número total de propiedades a crear. "
                "Se distribuyen entre todas las provincias."
            ),
        )

        parser.add_argument(
            "--images-per-property",
            type=int,
            default=5,
            help=(
                "Número de imágenes por propiedad. "
                f"Máximo permitido: {MAX_IMAGES_PER_PROPERTY}."
            ),
        )

        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help=(
                "Si existe alguna propiedad, no crea nuevas "
                "para evitar duplicados."
            ),
        )

        parser.add_argument(
            "--create-provinces",
            action="store_true",
            help=(
                "Crea las provincias y municipios antes "
                "de crear las propiedades."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        total = options["total"]
        images_per_property = options["images_per_property"]
        skip_existing = options["skip_existing"]
        create_provinces = options["create_provinces"]

        if total < 0:
            self.stdout.write(
                self.style.ERROR(
                    "El número total de propiedades no puede ser negativo."
                )
            )
            return

        if images_per_property < 0:
            self.stdout.write(
                self.style.ERROR(
                    "El número de imágenes no puede ser negativo."
                )
            )
            return

        images_per_property = min(
            images_per_property,
            MAX_IMAGES_PER_PROPERTY,
        )

        if skip_existing and Property.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Ya existen propiedades. Saltando creación."
                )
            )
            return

        if create_provinces:
            self._create_provinces_and_municipalities()

        province_cache = {}
        municipality_cache = {}

        for province_name, data in self.CUBAN_DATA.items():
            province, _ = Province.objects.get_or_create(
                name=province_name,
                defaults={
                    "slug": slugify(province_name),
                },
            )

            province_cache[province_name] = province

            for mun_name, lat, lng in data["municipios"]:
                municipality = self._get_or_update_municipality(
                    province=province,
                    name=mun_name,
                    latitude=lat,
                    longitude=lng,
                )

                municipality_cache[
                    f"{province_name}_{mun_name}"
                ] = municipality

        num_provinces = len(self.CUBAN_DATA)
        base_count, extra = divmod(total, num_provinces)
        created_properties = 0

        for index, (province_name, data) in enumerate(
            self.CUBAN_DATA.items()
        ):
            count = base_count + (1 if index < extra else 0)

            if count == 0:
                continue

            self.stdout.write(
                f"Creando {count} propiedades en {province_name}..."
            )

            province = province_cache[province_name]

            for _ in range(count):
                mun_name, lat, lng = random.choice(
                    data["municipios"]
                )

                municipality = municipality_cache[
                    f"{province_name}_{mun_name}"
                ]

                property_obj = self._create_property(
                    province=province,
                    municipality=municipality,
                    city=mun_name,
                    latitude=lat,
                    longitude=lng,
                )

                for image_index in range(images_per_property):
                    self._create_image(
                        property_obj,
                        image_index,
                    )

                created_properties += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Se crearon {created_properties} propiedades "
                f"con {images_per_property} imágenes cada una."
            )
        )

    def _create_provinces_and_municipalities(self):
        """Crea o actualiza todas las provincias y municipios."""
        self.stdout.write(
            "Creando o actualizando provincias y municipios..."
        )

        created_provinces = 0
        updated_municipalities = 0
        created_municipalities = 0

        for province_name, data in self.CUBAN_DATA.items():
            province, province_created = Province.objects.get_or_create(
                name=province_name,
                defaults={
                    "slug": slugify(province_name),
                },
            )

            if province_created:
                created_provinces += 1

            for mun_name, lat, lng in data["municipios"]:
                municipality, municipality_created = (
                    Municipality.objects.get_or_create(
                        province=province,
                        name=mun_name,
                        defaults={
                            "slug": slugify(mun_name),
                            "latitude": lat,
                            "longitude": lng,
                        },
                    )
                )

                if municipality_created:
                    created_municipalities += 1
                    continue

                changed = False

                if municipality.slug != slugify(mun_name):
                    municipality.slug = slugify(mun_name)
                    changed = True

                lat_decimal = Decimal(str(lat))
                lng_decimal = Decimal(str(lng))

                if municipality.latitude != lat_decimal:
                    municipality.latitude = lat_decimal
                    changed = True

                if municipality.longitude != lng_decimal:
                    municipality.longitude = lng_decimal
                    changed = True

                if changed:
                    municipality.save()
                    updated_municipalities += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Provincias nuevas: {created_provinces}; "
                f"municipios nuevos: {created_municipalities}; "
                f"municipios actualizados: {updated_municipalities}."
            )
        )

    def _get_or_update_municipality(
        self,
        province,
        name,
        latitude,
        longitude,
    ):
        """Obtiene un municipio y mantiene sus coordenadas actualizadas."""
        municipality, _ = Municipality.objects.get_or_create(
            province=province,
            name=name,
            defaults={
                "slug": slugify(name),
                "latitude": latitude,
                "longitude": longitude,
            },
        )

        changed = False

        if municipality.slug != slugify(name):
            municipality.slug = slugify(name)
            changed = True

        latitude = Decimal(str(latitude))
        longitude = Decimal(str(longitude))

        if municipality.latitude != latitude:
            municipality.latitude = latitude
            changed = True

        if municipality.longitude != longitude:
            municipality.longitude = longitude
            changed = True

        if changed:
            municipality.save()

        return municipality

    def _create_property(
        self,
        province,
        municipality,
        city,
        latitude,
        longitude,
    ):
        """Crea una propiedad con datos realistas."""
        property_type = random.choice(self.PROPERTY_TYPE_VALUES)
        offer_type = random.choice(self.OFFER_TYPES)

        adjective = random.choice(self.ADJECTIVES)
        noun = random.choice(self.NOUNS)
        feature = random.choice(self.FEATURES)

        title = (
            f"{adjective} {noun} en {city}, "
            f"{province.name} - {feature}"
        )

        base_slug = slugify(title)[:80]
        property_slug = base_slug
        counter = 1

        while Property.objects.filter(
            slug=property_slug
        ).exists():
            property_slug = f"{base_slug}-{counter}"
            counter += 1

        sale_price = None
        rent_price = None
        seasonal_rent_price = None
        deposit_amount = None

        if offer_type in (
            PropertyOfferType.SALE,
            PropertyOfferType.SALE_OR_RENT,
        ):
            sale_price = Decimal(random.randint(5000, 500000))

        if offer_type in (
            PropertyOfferType.RENT,
            PropertyOfferType.SALE_OR_RENT,
        ):
            rent_price = Decimal(random.randint(200, 5000))
            deposit_amount = rent_price * Decimal(
                random.randint(1, 3)
            )

            if random.choice([True, False]):
                seasonal_rent_price = Decimal(
                    random.randint(50, 500)
                )

        surface = random.randint(40, 400)
        rooms = random.randint(1, 5)
        bathrooms = random.randint(1, 3)

        has_elevator = random.choice([True, False])
        has_heating = random.choice([True, False])
        has_air_conditioning = random.choice([True, False])

        status = random.choices(
            [
                PropertyStatus.AVAILABLE,
                PropertyStatus.RESERVED,
                PropertyStatus.SOLD,
            ],
            weights=[0.8, 0.1, 0.1],
        )[0]

        description = (
            f"Excelente {noun} en {city}, "
            f"provincia de {province.name}. "
            f"Superficie de {surface} m², "
            f"{rooms} habitaciones y {bathrooms} baños. "
            f"{'Cuenta con ascensor. ' if has_elevator else ''}"
            f"{'Calefacción central. ' if has_heating else ''}"
            f"{'Aire acondicionado en todas las estancias. ' if has_air_conditioning else ''}"
        ) + self._get_price_description(
            offer_type,
            sale_price,
            rent_price,
            seasonal_rent_price,
        ) + (
            f"{feature}. "
            "Ideal para inversión o residencia familiar."
        )

        property_obj = Property(
            property_type=property_type,
            offer_type=offer_type,
            sale_price=sale_price,
            rent_price=rent_price,
            seasonal_rent_price=seasonal_rent_price,
            deposit_amount=deposit_amount,
            city=city,
            province=province,
            municipality=municipality,
            address=(
                f"Calle {random.randint(1, 100)} "
                f"#{random.randint(1, 50)}"
            ),
            location=Point(
                longitude,
                latitude,
                srid=4326,
            ),
            surface=surface,
            rooms=rooms,
            bathrooms=bathrooms,
            has_elevator=has_elevator,
            has_heating=has_heating,
            has_air_conditioning=has_air_conditioning,
            slug=property_slug,
            is_active=True,
            views_count=random.randint(0, 500),
            status=status,
        )

        property_obj.set_current_language("es")
        property_obj.title = title
        property_obj.description = description

        property_obj.full_clean()
        property_obj.save()

        return property_obj

    def _get_price_description(
        self,
        offer_type,
        sale_price,
        rent_price,
        seasonal_rent_price,
    ):
        """Genera una descripción según el tipo de oferta."""
        if offer_type == PropertyOfferType.SALE:
            return f"Precio de venta: {sale_price} CUP. "

        if offer_type == PropertyOfferType.RENT:
            description = (
                f"Precio de alquiler: {rent_price} CUP/mes. "
            )

            if seasonal_rent_price is not None:
                description += (
                    f"Alquiler por temporada: "
                    f"{seasonal_rent_price} CUP/día. "
                )

            return description

        if offer_type == PropertyOfferType.SALE_OR_RENT:
            description = (
                f"Precio de venta: {sale_price} CUP. "
                f"Alquiler: {rent_price} CUP/mes. "
            )

            if seasonal_rent_price is not None:
                description += (
                    f"Alquiler por temporada: "
                    f"{seasonal_rent_price} CUP/día. "
                )

            return description

        return "Propiedad en permuta. Consultar condiciones. "

    def _create_image(self, property_obj, index):
        """Genera una imagen ficticia asociada a la propiedad."""
        width, height = 800, 600

        color = (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )

        image = Image.new(
            "RGB",
            (width, height),
            color=color,
        )

        draw = ImageDraw.Draw(image)
        text = (
            f"Propiedad #{property_obj.pk} - "
            f"Imagen {index + 1}"
        )

        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except OSError:
            font = ImageFont.load_default()

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font,
        )

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        draw.text(
            (x + 2, y + 2),
            text,
            fill=(255, 255, 255),
            font=font,
        )

        draw.text(
            (x, y),
            text,
            fill=(0, 0, 0),
            font=font,
        )

        image_io = BytesIO()
        image.save(
            image_io,
            format="JPEG",
            quality=90,
        )
        image_io.seek(0)

        filename = (
            f"property_{property_obj.pk}_"
            f"img_{index + 1}.jpg"
        )

        image_file = ImageFile(
            image_io,
            name=filename,
        )

        PropertyImage.objects.create(
            property=property_obj,
            image=image_file,
            order=index,
            is_cover=(index == 0),
        )

        image_io.close()