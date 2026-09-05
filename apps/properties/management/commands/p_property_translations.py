# -*- coding: utf-8 -*-
"""
properties/management/commands/p_property_translations.py
============================================================

Management command complementario a p_properties.py: rellena
`title`/`description` (campos traducidos vía parler, idioma 'es') para
los inmuebles que no tengan NINGUNA traducción todavía.

Por qué hace falta: p_properties.py usa Property.objects.bulk_create(),
que NO pasa por el guardado normal de TranslatableModel/parler, así que
los inmuebles que genera quedan sin fila en Property_translation. Sin
título, Property.__str__ cae a mostrar el pk numérico -- mala imagen
para una demo.

Por defecto SOLO afecta a inmuebles sin ninguna traducción
(`translations__isnull=True`), así que es seguro relanzarlo: nunca
toca un inmueble que ya tenga título (ni los creados por p_properties
en una tanda anterior, ni los que un usuario real haya creado y
titulado a mano desde el portal).

UBICACIÓN DEL ARCHIVO:
    properties/
        management/
            commands/
                p_property_translations.py   <-- este archivo

USO:
    python manage.py p_property_translations
    python manage.py p_property_translations --dry-run
    python manage.py p_property_translations --seed 42
    python manage.py p_property_translations --limit 50
    python manage.py p_property_translations --language en   (título/desc. en inglés)
"""

import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import Property, PropertyOfferType

# --------------------------------------------------------------------- #
# CONTENIDO DE APOYO (independiente del sistema de traducción de Django:
# generamos texto de demo directamente en el idioma pedido, sin depender
# de que haya una traducción activa fuera del ciclo request/response)
# --------------------------------------------------------------------- #

PROPERTY_TYPE_LABELS_ES = {
    "apartment": "apartamento",
    "house": "casa",
    "villa": "villa",
    "commercial": "local comercial",
    "land": "terreno",
    "other": "inmueble",
}

OFFER_TYPE_PHRASES_ES = {
    PropertyOfferType.SALE: "en venta",
    PropertyOfferType.RENT: "en alquiler",
    PropertyOfferType.SALE_OR_RENT: "en venta o alquiler",
    PropertyOfferType.SWAP: "para permuta",
}

TITLE_TEMPLATES_ES = [
    "{Tipo} {oferta} en {municipio}, {provincia}",
    "Bonito {tipo} {oferta} en {municipio}",
    "{Tipo} de {rooms} habitaciones {oferta} en {municipio}, {provincia}",
    "Amplio {tipo} {oferta} cerca del centro de {municipio}",
    "{Tipo} luminoso {oferta} en {provincia}",
]

DESCRIPTION_INTROS_ES = [
    "Se ofrece {tipo} {oferta}, ubicado en {municipio}, provincia de {provincia}.",
    "{Tipo_cap} {oferta} situado en una zona tranquila de {municipio}, {provincia}.",
    "Excelente oportunidad: {tipo} {oferta} en {municipio}, {provincia}.",
]

AMENITY_PHRASES_ES = {
    "has_elevator": "cuenta con ascensor",
    "has_heating": "dispone de calefacción",
    "has_air_conditioning": "incluye aire acondicionado",
}

PROPERTY_TYPE_LABELS_EN = {
    "apartment": "apartment",
    "house": "house",
    "villa": "villa",
    "commercial": "commercial property",
    "land": "plot of land",
    "other": "property",
}

OFFER_TYPE_PHRASES_EN = {
    PropertyOfferType.SALE: "for sale",
    PropertyOfferType.RENT: "for rent",
    PropertyOfferType.SALE_OR_RENT: "for sale or rent",
    PropertyOfferType.SWAP: "for swap",
}

TITLE_TEMPLATES_EN = [
    "{Tipo} {oferta} in {municipio}, {provincia}",
    "Lovely {tipo} {oferta} in {municipio}",
    "{Tipo} with {rooms} bedrooms, {oferta}, in {municipio}, {provincia}",
    "Spacious {tipo} {oferta} near the center of {municipio}",
]

DESCRIPTION_INTROS_EN = [
    "This {tipo} {oferta} is located in {municipio}, {provincia}.",
    "{Tipo_cap} {oferta} in a quiet area of {municipio}, {provincia}.",
    "Great opportunity: {tipo} {oferta} in {municipio}, {provincia}.",
]

AMENITY_PHRASES_EN = {
    "has_elevator": "has an elevator",
    "has_heating": "has heating",
    "has_air_conditioning": "has air conditioning",
}


class Command(BaseCommand):
    help = (
        "Rellena title/description (traducción parler) para los inmuebles que "
        "no tengan ninguna traducción todavía -- pensado como complemento de "
        "p_properties.py, que los crea vía bulk_create sin traducciones."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--language", type=str, default="es", choices=["es", "en"],
            help="Idioma de las traducciones generadas (default: es).",
        )
        parser.add_argument(
            "--seed", type=int, default=None,
            help="Semilla aleatoria para resultados reproducibles.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Procesa como máximo N inmuebles (útil para probar).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo muestra ejemplos generados, no escribe nada.",
        )

    def handle(self, *args, **options):
        if options["seed"] is not None:
            random.seed(options["seed"])

        language = options["language"]
        type_labels = PROPERTY_TYPE_LABELS_ES if language == "es" else PROPERTY_TYPE_LABELS_EN
        offer_phrases = OFFER_TYPE_PHRASES_ES if language == "es" else OFFER_TYPE_PHRASES_EN
        title_templates = TITLE_TEMPLATES_ES if language == "es" else TITLE_TEMPLATES_EN
        desc_intros = DESCRIPTION_INTROS_ES if language == "es" else DESCRIPTION_INTROS_EN
        amenity_phrases = AMENITY_PHRASES_ES if language == "es" else AMENITY_PHRASES_EN

        # SOLO inmuebles sin ninguna traducción todavía -- nunca toca uno
        # que ya tenga título, sea de una tanda anterior de este mismo
        # comando o escrito a mano por un usuario real.
        qs = Property.objects.filter(translations__isnull=True).select_related(
            "province", "municipality"
        ).distinct().order_by("id")

        if options["limit"]:
            qs = qs[: options["limit"]]

        properties = list(qs)

        if not properties:
            self.stdout.write(self.style.WARNING(
                "No hay inmuebles sin traducción. Nada que hacer."
            ))
            return

        self.stdout.write("=" * 60)
        self.stdout.write(f"PLAN: {len(properties)} inmuebles sin título -> generando en '{language}'")
        self.stdout.write("=" * 60)

        if options["dry_run"]:
            for obj in properties[:5]:
                title, description = self._build_translation(
                    obj, type_labels, offer_phrases, title_templates, desc_intros, amenity_phrases
                )
                self.stdout.write(f"\n[{obj.pk}] {title}\n  {description}")
            if len(properties) > 5:
                self.stdout.write(f"\n... y {len(properties) - 5} más.")
            self.stdout.write(self.style.WARNING("\n[dry-run] No se ha escrito nada."))
            return

        created = 0
        failed = []
        for obj in properties:
            try:
                title, description = self._build_translation(
                    obj, type_labels, offer_phrases, title_templates, desc_intros, amenity_phrases
                )
                with transaction.atomic():
                    obj.set_current_language(language)
                    obj.title = title
                    obj.description = description
                    obj.save()
                created += 1
            except Exception as exc:  # noqa: BLE001 - seguimos con el resto
                failed.append((obj.pk, str(exc)))
                self.stdout.write(self.style.ERROR(f"  [error] inmueble {obj.pk}: {exc}"))

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"RESULTADO: {created} traducciones creadas en '{language}'"
        ))
        if failed:
            self.stdout.write(self.style.WARNING(f"{len(failed)} fallos:"))
            for pk, error in failed[:20]:
                self.stdout.write(f"  - inmueble {pk}: {error}")
        self.stdout.write("=" * 60)

    # ------------------------------------------------------------------ #
    def _build_translation(self, obj, type_labels, offer_phrases, title_templates, desc_intros, amenity_phrases):
        tipo = type_labels.get(obj.property_type, type_labels["other"])
        oferta = offer_phrases.get(obj.offer_type, "")
        municipio = obj.municipality.name if obj.municipality else ""
        provincia = obj.province.name if obj.province else ""

        title_template = random.choice(title_templates)
        title = title_template.format(
            tipo=tipo,
            Tipo=tipo.capitalize(),
            oferta=oferta,
            municipio=municipio,
            provincia=provincia,
            rooms=obj.rooms or "varias",
        )

        intro = random.choice(desc_intros).format(
            tipo=tipo,
            Tipo_cap=tipo.capitalize(),
            oferta=oferta,
            municipio=municipio,
            provincia=provincia,
        )

        details = []
        if obj.rooms:
            details.append(f"{obj.rooms} habitaciones" if amenity_phrases is AMENITY_PHRASES_ES else f"{obj.rooms} bedrooms")
        if obj.bathrooms:
            details.append(f"{obj.bathrooms} baños" if amenity_phrases is AMENITY_PHRASES_ES else f"{obj.bathrooms} bathrooms")
        if obj.surface:
            details.append(f"{obj.surface} m²" if amenity_phrases is AMENITY_PHRASES_ES else f"{obj.surface} sqm")

        amenities = [
            phrase for field, phrase in amenity_phrases.items() if getattr(obj, field, False)
        ]

        parts = [intro]
        if details:
            joiner = "Cuenta con " if amenity_phrases is AMENITY_PHRASES_ES else "It has "
            parts.append(joiner + ", ".join(details) + ".")
        if amenities:
            joiner = "Además, " if amenity_phrases is AMENITY_PHRASES_ES else "It also "
            parts.append(joiner + " y ".join(amenities) + ".")
        if obj.address:
            parts.append(f"Dirección: {obj.address}." if amenity_phrases is AMENITY_PHRASES_ES else f"Address: {obj.address}.")

        description = " ".join(parts)
        return title, description
