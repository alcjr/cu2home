"""
Script para asignar agentes a propiedades que no tienen agente asignado.

Ubicación: apps/properties/management/commands/assign_agents_to_properties.py

Uso:
    python manage.py assign_agents_to_properties
    python manage.py assign_agents_to_properties --dry-run
    python manage.py assign_agents_to_properties --specific-agent 3
    python manage.py assign_agents_to_properties --agent-ratio 0.8
"""

import random
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.users.models import UserProfile
from apps.properties.models import Property

User = get_user_model()


class Command(BaseCommand):
    help = 'Asigna agentes a propiedades que no tienen agente asignado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la asignación sin guardar cambios'
        )
        parser.add_argument(
            '--specific-agent',
            type=int,
            help='Asigna todas las propiedades a un agente específico (ID de usuario)'
        )
        parser.add_argument(
            '--agent-ratio',
            type=float,
            default=0.5,
            help='Proporción de propiedades que se asignarán a agentes (0-1, por defecto: 0.5)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limita el número de propiedades a procesar'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        specific_agent_id = options['specific_agent']
        agent_ratio = options['agent_ratio']
        limit = options['limit']

        # Validaciones
        if not 0 <= agent_ratio <= 1:
            raise CommandError('agent_ratio debe estar entre 0 y 1')

        # Obtener propiedades sin agente
        properties_without_agent = Property.objects.filter(agent__isnull=True)
        if limit:
            properties_without_agent = properties_without_agent[:limit]

        total_properties = properties_without_agent.count()

        if total_properties == 0:
            self.stdout.write(self.style.SUCCESS('✅ Todas las propiedades ya tienen agente asignado.'))
            return

        self.stdout.write(f'📊 Propiedades sin agente: {total_properties}')

        # Obtener agentes disponibles
        if specific_agent_id:
            # Usar un agente específico
            try:
                agent_user = User.objects.get(pk=specific_agent_id)
                agent_users = [agent_user]
                self.stdout.write(f'🎯 Usando agente específico: {agent_user.get_full_name() or agent_user.username} (ID: {agent_user.id})')
            except User.DoesNotExist:
                raise CommandError(f'No existe un usuario con ID {specific_agent_id}')
        else:
            # Obtener todos los usuarios con perfil de agente
            agent_profiles = UserProfile.objects.filter(
                user_type=UserProfile.UserType.AGENT
            ).select_related('user')

            if not agent_profiles.exists():
                self.stdout.write(self.style.WARNING('⚠️ No hay agentes disponibles en el sistema.'))
                self.stdout.write('   Primero debes crear agentes con:')
                self.stdout.write('   python manage.py create_test_profiles --count 10 --agent-ratio 1.0')
                return

            agent_users = [profile.user for profile in agent_profiles]

        self.stdout.write(f'👤 Agentes disponibles: {len(agent_users)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 MODO DRY-RUN: No se guardarán cambios'))
            # Mostrar muestra de asignaciones
            sample_size = min(10, total_properties)
            sample_properties = properties_without_agent[:sample_size]
            self.stdout.write(f'\n📋 Muestra de asignaciones ({sample_size} propiedades):')
            for prop in sample_properties:
                agent = random.choice(agent_users)
                self.stdout.write(
                    f'   • #{prop.id} "{prop.title[:40]}..." → {agent.get_full_name() or agent.username}'
                )
            return

        # Realizar asignación
        self.stdout.write('\n🔄 Asignando agentes...')

        with transaction.atomic():
            assigned_count = 0
            properties_to_assign = list(properties_without_agent)

            # Mezclar para asignación aleatoria
            random.shuffle(properties_to_assign)

            for idx, prop in enumerate(properties_to_assign):
                # Decidir si asignar agente (según agent_ratio)
                if random.random() > agent_ratio:
                    continue

                # Seleccionar agente aleatorio
                agent = random.choice(agent_users)
                prop.agent = agent
                prop.save(update_fields=['agent'])
                assigned_count += 1

                if assigned_count % 10 == 0:
                    self.stdout.write(f'   ✅ {assigned_count} propiedades asignadas...')

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Asignación completada: {assigned_count} propiedades actualizadas'
            )
        )

        # Estadísticas finales
        remaining = Property.objects.filter(agent__isnull=True).count()
        self.stdout.write(f'📊 Propiedades sin agente restantes: {remaining}')
        self.stdout.write(f'📊 Total de propiedades: {Property.objects.count()}')
        self.stdout.write(f'📊 Propiedades con agente: {Property.objects.exclude(agent__isnull=True).count()}')