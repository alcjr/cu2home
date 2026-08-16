"""
Script de gestión para poblar la tabla UserProfile con datos de prueba.

Ubicación recomendada: apps/users/management/commands/create_test_profiles.py

Uso:
    python manage.py create_test_profiles
    python manage.py create_test_profiles --count 50
    python manage.py create_test_profiles --delete
    python manage.py create_test_profiles --delete --count 30
"""

import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from apps.users.models import UserProfile

User = get_user_model()

# ============================================================
# DATOS DE EJEMPLO
# ============================================================

AGENCIAS = [
    "Cuba Real Estate",
    "Habana Propiedades",
    "Caribe Inmobiliaria",
    "Isla Homes",
    "Cuban Properties Group",
    "Varadero Realty",
    "Santiago Inmobiliaria",
    "Trinidad Casas",
    "Cienfuegos Propiedades",
    "Camagüey Real Estate",
    "Holguín Homes",
    "Pinar del Río Inmobiliaria",
    "Villa Clara Properties",
    "Matanzas Realty",
    "Guantánamo Inmobiliaria",
]

NOMBRES = [
    "Carlos", "Marta", "Jorge", "Ana", "Luis", "María", "Pedro", "Elena",
    "Antonio", "Carmen", "José", "Teresa", "Manuel", "Isabel", "Francisco",
    "Rosa", "David", "Patricia", "Miguel", "Dolores", "Fernando", "Beatriz",
    "Enrique", "Alicia", "Javier", "Cristina", "Roberto", "Laura", "Daniel",
    "Sofía", "Pablo", "Mercedes", "Juan", "Luisa", "Ramón", "Rafael", "Julián"
]

APELLIDOS = [
    "García", "Martínez", "López", "Hernández", "Pérez", "González",
    "Rodríguez", "Sánchez", "Ramírez", "Torres", "Rivera", "Morales",
    "Ortiz", "Cruz", "Reyes", "Gutiérrez", "Mendoza", "Ramos", "Díaz",
    "Jiménez", "Romero", "Álvarez", "Castillo", "Vásquez", "Gómez", "Ruiz"
]

BIO_EJEMPLOS = [
    "Agente inmobiliario con más de 10 años de experiencia en el mercado cubano. Especialista en propiedades de lujo en La Habana y Varadero.",
    "Apasionada por ayudar a las familias a encontrar su hogar ideal. Conocedora de todas las provincias cubanas y sus particularidades.",
    "Experto en inversiones inmobiliarias y propiedades comerciales. Asesoría personalizada para clientes nacionales e internacionales.",
    "Agente certificado con enfoque en propiedades de playa y zonas turísticas. Amplia red de contactos en toda la isla.",
    "Profesional con amplia experiencia en tasaciones y valoración de propiedades. Miembro de la Cámara de Inmobiliarias de Cuba.",
    "Especialista en propiedades históricas y coloniales en el centro histórico de La Habana y Trinidad.",
    "Comprometida con brindar el mejor servicio a sus clientes. Conocimiento profundo del mercado de alquileres vacacionales.",
    "Agente con experiencia en propiedades agrícolas y fincas. Ideal para inversores interesados en el campo cubano.",
]

TELEFONOS = [
    "555-1001", "555-1002", "555-1003", "555-1004", "555-1005",
    "555-1006", "555-1007", "555-1008", "555-1009", "555-1010",
    "555-1011", "555-1012", "555-1013", "555-1014", "555-1015",
    "555-1016", "555-1017", "555-1018", "555-1019", "555-1020",
]


class Command(BaseCommand):
    help = 'Crea perfiles de usuario (UserProfile) con datos de prueba'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=25,
            help='Número de perfiles a crear (por defecto: 25)'
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Elimina todos los perfiles existentes antes de crear nuevos'
        )
        parser.add_argument(
            '--delete-only',
            action='store_true',
            help='Solo elimina todos los perfiles, sin crear nuevos'
        )
        parser.add_argument(
            '--agent-ratio',
            type=float,
            default=0.40,
            help='Proporción de agentes respecto al total (0-1, por defecto: 0.40)'
        )

    def handle(self, *args, **options):
        count = options['count']
        delete = options['delete']
        delete_only = options['delete_only']
        agent_ratio = options['agent_ratio']

        # Validación
        if count < 1:
            raise CommandError('El número de perfiles debe ser al menos 1')

        if not 0 <= agent_ratio <= 1:
            raise CommandError('agent_ratio debe estar entre 0 y 1')

        # Manejo de eliminación
        if delete_only:
            self._delete_all_profiles()
            return

        if delete:
            self._delete_all_profiles()

        # Crear perfiles
        self._create_profiles(count, agent_ratio)

    def _delete_all_profiles(self):
        """Elimina todos los UserProfile existentes."""
        # Primero, eliminar los perfiles
        profile_count = UserProfile.objects.count()
        if profile_count > 0:
            self.stdout.write(f'Eliminando {profile_count} perfiles existentes...')
            UserProfile.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Perfiles eliminados correctamente'))
        else:
            self.stdout.write('No hay perfiles para eliminar')

        # Opcional: también eliminar usuarios sin perfil que no sean superusers
        users_without_profile = User.objects.filter(
            profile__isnull=True,
            is_superuser=False,
            is_staff=False
        )
        user_count = users_without_profile.count()
        if user_count > 0:
            self.stdout.write(f'Eliminando {user_count} usuarios huérfanos...')
            users_without_profile.delete()
            self.stdout.write(self.style.SUCCESS('✓ Usuarios huérfanos eliminados'))

    def _create_profiles(self, count, agent_ratio):
        """Crea nuevos perfiles de usuario."""
        created_count = 0
        skipped_count = 0

        # Lista de emails a usar, con incremento
        existing_users = set(User.objects.values_list('username', flat=True))
        existing_emails = set(User.objects.values_list('email', flat=True))

        # Determinar cuántos agentes y compradores
        agent_count = int(count * agent_ratio)
        buyer_count = count - agent_count

        self.stdout.write(f'Creando {count} perfiles: {agent_count} agentes, {buyer_count} compradores...')

        with transaction.atomic():
            # --- CREAR AGENTES ---
            for i in range(agent_count):
                user, skipped = self._create_user(
                    username_prefix='agent',
                    email_prefix='agente',
                    user_type=UserProfile.UserType.AGENT,
                    existing_users=existing_users,
                    existing_emails=existing_emails,
                    index=i
                )
                if skipped:
                    skipped_count += 1
                    continue

                # Crear perfil de agente
                self._create_profile(user, UserProfile.UserType.AGENT, i)
                created_count += 1

            # --- CREAR COMPRADORES ---
            for i in range(buyer_count):
                user, skipped = self._create_user(
                    username_prefix='buyer',
                    email_prefix='comprador',
                    user_type=UserProfile.UserType.BUYER,
                    existing_users=existing_users,
                    existing_emails=existing_emails,
                    index=i + agent_count  # Continuar índice para evitar colisiones
                )
                if skipped:
                    skipped_count += 1
                    continue

                # Crear perfil de comprador
                self._create_profile(user, UserProfile.UserType.BUYER, i + agent_count)
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Proceso completado: {created_count} perfiles creados, {skipped_count} omitidos'
            )
        )
        self.stdout.write(
            f'📊 Resumen: {UserProfile.objects.filter(user_type=UserProfile.UserType.AGENT).count()} agentes, '
            f'{UserProfile.objects.filter(user_type=UserProfile.UserType.BUYER).count()} compradores'
        )

    def _create_user(self, username_prefix, email_prefix, user_type, existing_users, existing_emails, index):
        """Crea un usuario con credenciales únicas."""
        max_attempts = 100
        attempts = 0

        while attempts < max_attempts:
            attempts += 1
            # Generar nombre y apellido aleatorios
            first_name = random.choice(NOMBRES)
            last_name = random.choice(APELLIDOS)
            username = f"{username_prefix}_{first_name.lower()}{last_name.lower()}_{index}".lower()

            if username in existing_users:
                continue

            email = f"{email_prefix}_{first_name.lower()}.{last_name.lower()}_{index}@example.com".lower()
            if email in existing_emails:
                continue

            # Crear usuario
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='testpass123',  # Contraseña estándar para pruebas
                    first_name=first_name,
                    last_name=last_name,
                )
                existing_users.add(username)
                existing_emails.add(email)
                return user, False
            except Exception:
                continue

        self.stdout.write(self.style.WARNING(f'⚠️ No se pudo crear usuario para índice {index}'))
        return None, True

    def _create_profile(self, user, user_type, seed):
        """Crea un perfil para el usuario dado."""
        if not user:
            return

        # Generar datos aleatorios basados en seed para consistencia
        rng = random.Random(seed)

        is_agent = user_type == UserProfile.UserType.AGENT

        # Datos base
        profile_data = {
            'user': user,
            'user_type': user_type,
            'phone': rng.choice(TELEFONOS) if rng.random() > 0.3 else '',
            'bio': rng.choice(BIO_EJEMPLOS) if is_agent and rng.random() > 0.2 else '',
            'receive_email_alerts': rng.random() > 0.2,
        }

        # Datos específicos para agentes
        if is_agent:
            profile_data['agency_name'] = rng.choice(AGENCIAS)

        # Crear perfil
        try:
            profile = UserProfile.objects.create(**profile_data)

            # Simular fechas de creación/actualización variadas
            # (usamos update para no disparar auto_now)
            days_ago = rng.randint(1, 365)
            created_at = timezone.now() - timedelta(days=days_ago)
            updated_at = created_at + timedelta(hours=rng.randint(1, 720))

            UserProfile.objects.filter(pk=profile.pk).update(
                created_at=created_at,
                updated_at=updated_at
            )

            self.stdout.write(
                f'  ✓ Creado: {user.username} ({user.first_name} {user.last_name}) '
                f'→ {profile.get_user_type_display()}'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error creando perfil para {user.username}: {e}'))
            # Si falla la creación del perfil, eliminamos el usuario para no dejar huérfanos
            user.delete()