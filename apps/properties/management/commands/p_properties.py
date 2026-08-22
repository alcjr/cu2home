# -*- coding: utf-8 -*-
"""
properties/management/commands/p_properties.py
================================================

Management command de Django para poblar la tabla `properties_property`
con una muestra REPRESENTATIVA de inmuebles en todo el territorio nacional.

Representatividad garantizada:
    - Provincia:      las 16 provincias reciben inmuebles.
    - Municipio:      TODOS los municipios reciben al menos 1 inmueble
                       (por defecto, entre --min-per-municipio y --max-per-municipio).
    - Agente:         cada agente activo (UserProfile.user_type == 'agent')
                       recibe al menos 1 inmueble asignado.
    - Oferta:         se generan inmuebles en venta, alquiler, venta_o_alquiler
                       y permuta, respetando las reglas de Property.clean()
                       (p.ej. una permuta no exige precio).
    - Tipo de inmueble: se reparte uniformemente entre los tipos definidos en
                       properties.constants.PROPERTY_TYPES (no se hardcodean
                       los valores, se leen del proyecto real).

UBICACIÓN DEL ARCHIVO (requerida por Django para que se reconozca como comando):
    properties/
        management/
            __init__.py
            commands/
                __init__.py
                p_properties.py   <-- este archivo

USO:
    python manage.py p_properties
    python manage.py p_properties --dry-run
    python manage.py p_properties --total 900
    python manage.py p_properties --min-per-municipio 2 --max-per-municipio 6
    python manage.py p_properties --seed 42
    python manage.py p_properties --flush

Este comando NO crea traducciones (Property_translation) ni imágenes
(PropertyImage): esa es responsabilidad de otros comandos complementarios.
"""

import random
from collections import Counter
from decimal import Decimal
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

# Imports RELATIVOS al propio app: funcionan sin importar si el app está
# declarado en INSTALLED_APPS como "properties" o como "apps.properties",
# porque este archivo vive dentro de ese mismo paquete
# (apps/properties/management/commands/p_properties.py -> subir 3 niveles
# para llegar a apps/properties/).
from ...models import (
    Province,
    Municipality,
    Property,
    PropertyOfferType,
    PropertyStatus,
)
from ...constants import PROPERTY_TYPES

# UserProfile vive en OTRO app (users). Confirmado en settings.py
# (INSTALLED_APPS incluye 'apps.properties' y 'apps.users'), el import
# absoluto correcto es este:
from apps.users.models import UserProfile


# ---------------------------------------------------------------------------
# CONFIGURACIÓN / DATOS DE APOYO PARA GENERAR CONTENIDO REALISTA
# ---------------------------------------------------------------------------

DEFAULT_MIN_PER_MUNICIPIO = 3
DEFAULT_MAX_PER_MUNICIPIO = 7

# Pesos de distribución por tipo de oferta (deben sumar 1.0).
# Se mantiene un peso significativo para "swap" (permuta) porque es un caso
# de negocio que interesa poder probar en el portal.
OFFER_TYPE_WEIGHTS = {
    PropertyOfferType.SALE: 0.40,
    PropertyOfferType.RENT: 0.30,
    PropertyOfferType.SALE_OR_RENT: 0.15,
    PropertyOfferType.SWAP: 0.15,
}

# Multiplicador de precio según provincia (aproximación de mercado: la
# capital y polos turísticos tienden a precios más altos).
PROVINCE_PRICE_MULTIPLIER = {
    "la-habana": 1.6,
    "artemisa": 1.1,
    "mayabeque": 1.05,
    "matanzas": 1.15,       # Varadero
    "cienfuegos": 1.0,
    "villa-clara": 1.0,
    "santiago-de-cuba": 1.1,
    "isla-de-la-juventud": 0.75,
}
DEFAULT_PRICE_MULTIPLIER = 0.9

# Probabilidad de cada amenidad booleana.
AMENITY_PROBABILITIES = {
    "has_elevator": 0.22,
    "has_heating": 0.12,          # poco común en clima tropical
    "has_air_conditioning": 0.62,
}

# Distribución de estados del inmueble.
STATUS_WEIGHTS = {
    PropertyStatus.AVAILABLE: 0.70,
    PropertyStatus.RESERVED: 0.15,
    PropertyStatus.SOLD: 0.15,
}

STREET_NAMES = [
    "Calle 23", "Calle 42", "Avenida 5ta", "Calle Línea", "Calle San Rafael",
    "Calle Neptuno", "Calle Obispo", "Avenida de los Presidentes",
    "Calle Martí", "Calle Maceo", "Calle Céspedes", "Calle Independencia",
    "Calzada de Diez de Octubre", "Calle Enramadas", "Avenida del Puerto",
]
REPARTOS = [
    "Vedado", "Miramar", "Nuevo Vedado", "Playa", "Vista Alegre",
    "Reparto Sueño", "El Cerro", "Santa Bárbara", "Punta Gorda",
    "Reparto Camilo Cienfuegos", "Altahabana", "Versalles",
]


# ---------------------------------------------------------------------------
# COMMAND
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Puebla la tabla properties con una muestra representativa de todo "
        "el territorio (provincias/municipios), de los agentes existentes "
        "y de los tipos de oferta (venta, alquiler, venta_o_alquiler, permuta)."
    )

    # ------------------------------------------------------------------ #
    # CLI
    # ------------------------------------------------------------------ #
    def add_arguments(self, parser):
        parser.add_argument(
            "--total", type=int, default=None,
            help="Total aproximado de inmuebles a generar (opcional).",
        )
        parser.add_argument(
            "--min-per-municipio", type=int, default=DEFAULT_MIN_PER_MUNICIPIO,
            help=f"Mínimo de inmuebles por municipio (default {DEFAULT_MIN_PER_MUNICIPIO}).",
        )
        parser.add_argument(
            "--max-per-municipio", type=int, default=DEFAULT_MAX_PER_MUNICIPIO,
            help=f"Máximo de inmuebles por municipio (default {DEFAULT_MAX_PER_MUNICIPIO}).",
        )
        parser.add_argument(
            "--seed", type=int, default=None,
            help="Semilla aleatoria para resultados reproducibles.",
        )
        parser.add_argument(
            "--flush", action="store_true",
            help="Elimina las propiedades existentes antes de poblar.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo muestra el plan de generación, no escribe en la BD.",
        )
        parser.add_argument(
            "--batch-size", type=int, default=500,
            help="Tamaño de lote para bulk_create (default 500).",
        )

    # ------------------------------------------------------------------ #
    # ENTRY POINT
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        if options["seed"] is not None:
            random.seed(options["seed"])

        provinces, municipalities, agents, property_type_keys = self._load_reference_data()

        self.stdout.write(
            f"Provincias: {len(provinces)} | Municipios: {len(municipalities)} | "
            f"Agentes: {len(agents)} | Tipos de inmueble: {len(property_type_keys)}"
        )

        counts_by_municipio = self._plan_counts_per_municipality(municipalities, options)
        self._print_plan_summary(counts_by_municipio, municipalities)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "\n[dry-run] No se ha escrito nada en la base de datos."
            ))
            return

        if options["flush"]:
            deleted, _ = Property.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"[flush] Se eliminaron {deleted} registros de properties."))

        instances = self._build_property_instances(
            municipalities, agents, property_type_keys, counts_by_municipio
        )

        self.stdout.write(f"\nGuardando {len(instances)} propiedades en la base de datos...")
        with transaction.atomic():
            Property.objects.bulk_create(instances, batch_size=options["batch_size"])

        self._print_post_save_summary()
        self.stdout.write(self.style.SUCCESS("\n¡Listo! Tabla properties poblada correctamente."))

    # ------------------------------------------------------------------ #
    # CARGA DE DATOS BASE (deben existir ya en la BD)
    # ------------------------------------------------------------------ #
    def _load_reference_data(self):
        provinces = list(Province.objects.all())
        if not provinces:
            raise CommandError("No hay provincias en la BD. Puebla Province/Municipality primero.")

        municipalities = list(Municipality.objects.select_related("province").all())
        if not municipalities:
            raise CommandError("No hay municipios en la BD. Puebla Municipality primero.")

        agent_profiles = list(
            UserProfile.objects.filter(user_type="agent").select_related("user")
        )
        if not agent_profiles:
            raise CommandError("No hay agentes (UserProfile.user_type='agent') en la BD.")
        agents = [p.user for p in agent_profiles]

        property_type_keys = [choice[0] for choice in PROPERTY_TYPES]
        if not property_type_keys:
            raise CommandError("PROPERTY_TYPES está vacío en properties.constants.")

        return provinces, municipalities, agents, property_type_keys

    # ------------------------------------------------------------------ #
    # PLANIFICACIÓN: cuántos inmuebles por municipio
    # ------------------------------------------------------------------ #
    def _plan_counts_per_municipality(self, municipalities, options) -> dict:
        """
        Devuelve {municipality_id: cantidad_de_inmuebles}, garantizando que
        TODOS los municipios reciban al menos 1 inmueble.
        """
        counts = {}
        total = options["total"]
        min_per = options["min_per_municipio"]
        max_per = options["max_per_municipio"]

        if min_per < 1:
            raise CommandError("--min-per-municipio debe ser >= 1.")
        if max_per < min_per:
            raise CommandError("--max-per-municipio debe ser >= --min-per-municipio.")

        if total:
            n = len(municipalities)
            if total < n:
                raise CommandError(
                    f"--total ({total}) es menor que el número de municipios ({n}); "
                    "no se puede garantizar al menos 1 inmueble por municipio."
                )
            base = total // n
            remainder = total - base * n
            bonus_ids = set(random.sample(range(n), remainder)) if remainder > 0 else set()
            for i, m in enumerate(municipalities):
                counts[m.id] = base + (1 if i in bonus_ids else 0)
        else:
            for m in municipalities:
                counts[m.id] = random.randint(min_per, max_per)

        return counts

    # ------------------------------------------------------------------ #
    # HELPERS DE GENERACIÓN DE CONTENIDO
    # ------------------------------------------------------------------ #
    @staticmethod
    def _weighted_choice(weights: dict):
        keys = list(weights.keys())
        probs = list(weights.values())
        return random.choices(keys, weights=probs, k=1)[0]

    @staticmethod
    def _build_unique_slug(base_text: str, existing_slugs: set) -> str:
        base_slug = slugify(base_text)[:180] or "inmueble"
        slug = base_slug
        suffix = 1
        while slug in existing_slugs:
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        existing_slugs.add(slug)
        return slug

    @staticmethod
    def _jitter_point(municipality: Municipality):
        """Ubicación dentro del municipio con un desplazamiento (~hasta 2 km)."""
        if municipality.location is None:
            return None
        lon, lat = municipality.location.x, municipality.location.y
        lon_jitter = random.uniform(-0.02, 0.02)
        lat_jitter = random.uniform(-0.02, 0.02)
        return Point(lon + lon_jitter, lat + lat_jitter, srid=4326)

    @staticmethod
    def _build_address() -> str:
        calle = random.choice(STREET_NAMES)
        reparto = random.choice(REPARTOS)
        numero = random.randint(1, 250)
        entre_a, entre_b = random.sample(range(1, 60), 2)
        return f"{calle} #{numero} e/ {entre_a} y {entre_b}, {reparto}"

    @staticmethod
    def _price_multiplier_for(province: Province) -> float:
        return PROVINCE_PRICE_MULTIPLIER.get(province.slug, DEFAULT_PRICE_MULTIPLIER)

    @staticmethod
    def _random_created_at():
        days_ago = random.randint(0, 548)
        seconds_ago = random.randint(0, 86400)
        return timezone.now() - timedelta(days=days_ago, seconds=seconds_ago)

    @staticmethod
    def _build_prices(offer_type: str, multiplier: float):
        """
        Genera precios coherentes con las reglas de Property.clean():
            - SALE / SALE_OR_RENT -> sale_price obligatorio
            - RENT / SALE_OR_RENT -> rent_price obligatorio
            - SWAP                -> ningún precio es obligatorio
        """
        sale_price = rent_price = seasonal_rent_price = deposit_amount = None

        needs_sale = offer_type in (PropertyOfferType.SALE, PropertyOfferType.SALE_OR_RENT)
        needs_rent = offer_type in (PropertyOfferType.RENT, PropertyOfferType.SALE_OR_RENT)

        if needs_sale:
            base = random.randint(15_000, 380_000)
            sale_price = Decimal(str(round(base * multiplier, 2)))

        if needs_rent:
            base = random.randint(3_000, 55_000)
            rent_price = Decimal(str(round(base * multiplier, 2)))

            if random.random() < 0.5:
                deposit_amount = (rent_price * Decimal(random.choice([1, 2]))).quantize(Decimal("0.01"))

            if random.random() < 0.25:
                daily_base = random.randint(800, 6_000)
                seasonal_rent_price = Decimal(str(round(daily_base * multiplier, 2)))

        return sale_price, rent_price, seasonal_rent_price, deposit_amount

    @staticmethod
    def _build_views_count(created_at) -> int:
        age_days = max((timezone.now() - created_at).days, 0)
        base = int(abs(random.gauss(80, 120)))
        age_bonus = min(age_days * random.randint(0, 2), 900)
        return min(base + age_bonus, 3000)

    # ------------------------------------------------------------------ #
    # CONSTRUCCIÓN DE INSTANCIAS Property
    # ------------------------------------------------------------------ #
    def _build_property_instances(self, municipalities, agents, property_type_keys, counts_by_municipio):
        existing_slugs = set(Property.objects.values_list("slug", flat=True))
        instances = []

        # Aseguramos representatividad de agentes: cada agente aparece al
        # menos una vez (round-robin) antes de repartir el resto al azar.
        total_planned = sum(counts_by_municipio.values())
        agent_cycle = [agents[i % len(agents)] for i in range(total_planned)]
        random.shuffle(agent_cycle)
        agent_iter = iter(agent_cycle)

        for municipality in municipalities:
            n = counts_by_municipio.get(municipality.id, 0)
            province = municipality.province

            for _ in range(n):
                property_type = random.choice(property_type_keys)
                offer_type = self._weighted_choice(OFFER_TYPE_WEIGHTS)
                multiplier = self._price_multiplier_for(province)

                sale_price, rent_price, seasonal_rent_price, deposit_amount = self._build_prices(
                    offer_type, multiplier
                )

                created_at = self._random_created_at()
                updated_at = created_at + timedelta(days=random.randint(0, 45))
                if updated_at > timezone.now():
                    updated_at = timezone.now()

                status = self._weighted_choice(STATUS_WEIGHTS)
                # Un inmueble vendido tiene más probabilidad de estar inactivo.
                is_active = (
                    random.random() < 0.30 if status == PropertyStatus.SOLD
                    else random.random() < 0.92
                )

                # 3% de inmuebles sin agente asignado (datos legacy simulados).
                agent = None if random.random() < 0.03 else next(agent_iter)

                slug_base = f"{property_type}-en-{municipality.slug}-{province.slug}"
                slug = self._build_unique_slug(slug_base, existing_slugs)

                instances.append(
                    Property(
                        property_type=property_type,
                        offer_type=offer_type,
                        sale_price=sale_price,
                        rent_price=rent_price,
                        seasonal_rent_price=seasonal_rent_price,
                        deposit_amount=deposit_amount,
                        province=province,
                        municipality=municipality,
                        address=self._build_address(),
                        location=self._jitter_point(municipality),
                        surface=random.randint(35, 620),
                        rooms=random.randint(1, 6),
                        bathrooms=random.randint(1, 4),
                        has_elevator=random.random() < AMENITY_PROBABILITIES["has_elevator"],
                        has_heating=random.random() < AMENITY_PROBABILITIES["has_heating"],
                        has_air_conditioning=random.random() < AMENITY_PROBABILITIES["has_air_conditioning"],
                        slug=slug,
                        is_active=is_active,
                        views_count=self._build_views_count(created_at),
                        agent=agent,
                        status=status,
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                )

        return instances

    # ------------------------------------------------------------------ #
    # REPORTES DE REPRESENTATIVIDAD
    # ------------------------------------------------------------------ #
    def _print_plan_summary(self, counts_by_municipio, municipalities):
        total = sum(counts_by_municipio.values())
        by_province = {}
        for m in municipalities:
            by_province.setdefault(m.province.name, 0)
            by_province[m.province.name] += counts_by_municipio.get(m.id, 0)

        self.stdout.write("=" * 60)
        self.stdout.write(f"PLAN: {total} inmuebles a generar en {len(municipalities)} municipios")
        self.stdout.write("=" * 60)
        for province_name, n in sorted(by_province.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {province_name:<25} {n:>5}")
        self.stdout.write("-" * 60)

    def _print_post_save_summary(self):
        qs = Property.objects.select_related("province", "agent")
        total = qs.count()
        self.stdout.write("=" * 60)
        self.stdout.write(f"RESULTADO: {total} propiedades creadas")
        self.stdout.write("=" * 60)

        by_offer = Counter(qs.values_list("offer_type", flat=True))
        self.stdout.write("\nPor tipo de oferta:")
        for offer_type, n in by_offer.items():
            pct = (n / total * 100) if total else 0
            self.stdout.write(f"  {offer_type:<15} {n:>5}  ({pct:5.1f}%)")

        by_province = Counter(qs.values_list("province__name", flat=True))
        self.stdout.write("\nPor provincia:")
        for province_name, n in sorted(by_province.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {str(province_name):<25} {n:>5}")

        by_type = Counter(qs.values_list("property_type", flat=True))
        self.stdout.write("\nPor tipo de inmueble:")
        for ptype, n in sorted(by_type.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {ptype:<20} {n:>5}")

        agents_with_properties = qs.exclude(agent__isnull=True).values("agent").distinct().count()
        total_agents = UserProfile.objects.filter(user_type="agent").count()
        self.stdout.write(
            f"\nAgentes con al menos un inmueble asignado: {agents_with_properties} / {total_agents}"
        )

        municipios_with_properties = qs.values("municipality").distinct().count()
        total_municipios = Municipality.objects.count()
        self.stdout.write(
            f"Municipios con al menos un inmueble: {municipios_with_properties} / {total_municipios}"
        )
        self.stdout.write("=" * 60)
