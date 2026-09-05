# -*- coding: utf-8 -*-
"""
properties/management/commands/p_agent_bootstrap.py
=====================================================
(vive en apps/users/management/commands/, no en properties -- ver nota
de ubicación más abajo)

Management command que crea (o actualiza) un pequeño número de agentes
"protagonistas" con usuario/contraseña FIJOS y conocidos, pensados para
poder iniciar sesión durante una demo (a diferencia de p_users.py, que
genera agentes de volumen con contraseña aleatoria que nunca se
imprime, y que por tanto sirven para poblar pero no para hacer login).

Idempotente: usa get_or_create por username. Relanzarlo (p.ej. en cada
Build Command) NO crea duplicados ni sobreescribe nada salvo que pidas
explícitamente --reset-password. Es seguro tenerlo siempre en el
pipeline de deploy.

UBICACIÓN DEL ARCHIVO:
    apps/
        users/
            management/
                __init__.py
                commands/
                    __init__.py
                    p_agent_bootstrap.py   <-- este archivo

(Va en apps.users porque crea User + UserProfile, ambos modelos de esa
app -- no depende de apps.properties para nada.)

USO:
    python manage.py p_agent_bootstrap
    python manage.py p_agent_bootstrap --password "OtraClave123"
    python manage.py p_agent_bootstrap --reset-password
    python manage.py p_agent_bootstrap --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import UserProfile

DEFAULT_PASSWORD = "Demo_2026!"

# Agentes protagonistas fijos. Amplía esta lista si necesitas más de 2 --
# el username es la clave de idempotencia, así que mantenlos estables
# entre ejecuciones (no los renombres de un deploy a otro).
PROTAGONIST_AGENTS = [
    {
        "username": "agente.alejandro",
        "first_name": "Alejandro",
        "last_name": "García",
        "email": "alejandro.garcia@cu2home.com",
        "phone": "+53 55123456",
        "agency_name": "CasaReal Inmobiliaria",
        "bio": "Agente inmobiliario con 8 años de experiencia en La Habana y Artemisa.",
    },
    {
        "username": "agente.maria",
        "first_name": "María",
        "last_name": "Rodríguez",
        "email": "maria.rodriguez@cu2home.com",
        "phone": "+53 55987654",
        "agency_name": "Vedado Inversiones",
        "bio": "Especialista en propiedades de venta y alquiler en el litoral habanero.",
    },
]


class Command(BaseCommand):
    help = (
        "Crea (o actualiza) agentes 'protagonistas' fijos, con usuario/contraseña "
        "conocidos, pensados para hacer login durante una demo. Idempotente: "
        "seguro de relanzar en cada deploy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password", type=str, default=DEFAULT_PASSWORD,
            help=f"Contraseña a asignar a los agentes protagonistas (default: {DEFAULT_PASSWORD}).",
        )
        parser.add_argument(
            "--reset-password", action="store_true",
            help="Si el usuario ya existe, fuerza la contraseña al valor de --password. "
                 "Sin este flag, un usuario ya existente NO cambia su contraseña actual.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo muestra qué haría, no escribe nada.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        password = options["password"]
        reset_password = options["reset_password"]

        if options["dry_run"]:
            self.stdout.write("=" * 60)
            self.stdout.write(f"[dry-run] Se procesarían {len(PROTAGONIST_AGENTS)} agentes protagonistas:")
            for data in PROTAGONIST_AGENTS:
                exists = User.objects.filter(username=data["username"]).exists()
                estado = "ya existe" if exists else "se crearía"
                self.stdout.write(f"  - {data['username']} ({estado})")
            self.stdout.write("=" * 60)
            return

        created_credentials = []

        for data in PROTAGONIST_AGENTS:
            with transaction.atomic():
                user, user_created = User.objects.get_or_create(
                    username=data["username"],
                    defaults={
                        "email": data["email"],
                        "first_name": data["first_name"],
                        "last_name": data["last_name"],
                    },
                )

                if user_created:
                    user.set_password(password)
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Usuario creado: {data['username']}"))
                elif reset_password:
                    user.set_password(password)
                    user.save()
                    self.stdout.write(self.style.WARNING(f"  ⟳ Contraseña reseteada: {data['username']}"))
                else:
                    self.stdout.write(f"  = Ya existía, sin cambios de contraseña: {data['username']}")

                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "user_type": UserProfile.UserType.AGENT,
                        "phone": data["phone"],
                        "agency_name": data["agency_name"],
                        "bio": data["bio"],
                    },
                )

            created_credentials.append((data["username"], password if (user_created or reset_password) else "(sin cambios)"))

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("Agentes protagonistas listos para login:"))
        for username, pwd in created_credentials:
            self.stdout.write(f"  usuario: {username}   contraseña: {pwd}")
        self.stdout.write("=" * 60)
