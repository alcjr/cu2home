"""
Script para corregir y validar la asignación de agentes a propiedades.

Ubicación: apps/properties/management/commands/fix_property_agents.py

Uso:
    python manage.py fix_property_agents --validate
    python manage.py fix_property_agents --assign-all
    python manage.py fix_property_agents --assign-missing
    python manage.py fix_property_agents --cleanup
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Count
from apps.users.models import UserProfile
from apps.properties.models import Property

User = get_user_model()


class Command(BaseCommand):
    help = 'Corrige y valida la asignación de agentes a propiedades'

    def add_arguments(self, parser):
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Valida el estado actual de las asignaciones'
        )
        parser.add_argument(
            '--assign-all',
            action='store_true',
            help='Asigna todas las propiedades al primer agente disponible'
        )
        parser.add_argument(
            '--assign-missing',
            action='store_true',
            help='Asigna solo las propiedades que no tienen agente'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Elimina propiedades sin agente (útil para limpieza)'
        )
        parser.add_argument(
            '--agent-id',
            type=int,
            help='ID del agente a usar para la asignación'
        )

    def handle(self, *args, **options):
        validate = options['validate']
        assign_all = options['assign_all']
        assign_missing = options['assign_missing']
        cleanup = options['cleanup']
        agent_id = options['agent_id']

        if validate:
            self._validate()
        elif assign_all:
            self._assign_all(agent_id)
        elif assign_missing:
            self._assign_missing(agent_id)
        elif cleanup:
            self._cleanup()
        else:
            self.print_help('manage.py', 'fix_property_agents')

    def _validate(self):
        """Valida el estado de las asignaciones"""
        self.stdout.write('🔍 Validando asignaciones de agentes...\n')

        total = Property.objects.count()
        with_agent = Property.objects.exclude(agent__isnull=True).count()
        without_agent = Property.objects.filter(agent__isnull=True).count()

        self.stdout.write(f'📊 Total de propiedades: {total}')
        self.stdout.write(f'📊 Con agente: {with_agent}')
        self.stdout.write(f'📊 Sin agente: {without_agent}')

        # Verificar agentes existentes
        agents = UserProfile.objects.filter(user_type=UserProfile.UserType.AGENT)
        self.stdout.write(f'\n👤 Agentes registrados: {agents.count()}')

        # Propiedades por agente
        if with_agent > 0:
            self.stdout.write('\n📋 Distribución por agente:')
            agent_counts = (
                Property.objects
                .exclude(agent__isnull=True)
                .values('agent__username', 'agent__first_name', 'agent__last_name')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            for item in agent_counts[:10]:
                name = item['agent__first_name'] or ''
                last = item['agent__last_name'] or ''
                username = item['agent__username'] or ''
                display_name = f"{name} {last}".strip() or username
                self.stdout.write(f'   • {display_name}: {item["count"]} propiedades')

        if without_agent > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️ Hay {without_agent} propiedades sin agente asignado.'
                )
            )
            self.stdout.write('   Para corregir:')
            self.stdout.write('   python manage.py fix_property_agents --assign-missing')

    def _assign_all(self, agent_id):
        """Asigna todas las propiedades a un agente específico"""
        if not agent_id:
            # Obtener el primer agente disponible
            agent_profile = UserProfile.objects.filter(
                user_type=UserProfile.UserType.AGENT
            ).first()

            if not agent_profile:
                self.stdout.write(
                    self.style.ERROR('❌ No hay agentes disponibles. Crea agentes primero.')
                )
                return

            agent = agent_profile.user
        else:
            try:
                agent = User.objects.get(pk=agent_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ No existe un usuario con ID {agent_id}')
                )
                return

        self.stdout.write(
            f'🎯 Asignando todas las propiedades al agente: '
            f'{agent.get_full_name() or agent.username} (ID: {agent.id})'
        )

        total = Property.objects.count()
        with transaction.atomic():
            updated = Property.objects.update(agent=agent)

        self.stdout.write(
            self.style.SUCCESS(f'✅ {updated} propiedades actualizadas')
        )

    def _assign_missing(self, agent_id):
        """Asigna solo las propiedades sin agente"""
        properties = Property.objects.filter(agent__isnull=True)
        count = properties.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay propiedades sin agente.'))
            return

        if agent_id:
            try:
                agent = User.objects.get(pk=agent_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ No existe un usuario con ID {agent_id}')
                )
                return
        else:
            # Obtener el primer agente disponible
            agent_profile = UserProfile.objects.filter(
                user_type=UserProfile.UserType.AGENT
            ).first()

            if not agent_profile:
                self.stdout.write(
                    self.style.ERROR('❌ No hay agentes disponibles. Crea agentes primero.')
                )
                return

            agent = agent_profile.user

        self.stdout.write(
            f'🎯 Asignando {count} propiedades al agente: '
            f'{agent.get_full_name() or agent.username}'
        )

        with transaction.atomic():
            updated = properties.update(agent=agent)

        self.stdout.write(
            self.style.SUCCESS(f'✅ {updated} propiedades actualizadas')
        )

    def _cleanup(self):
        """Elimina propiedades sin agente (útil para limpieza)"""
        properties = Property.objects.filter(agent__isnull=True)
        count = properties.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay propiedades sin agente para eliminar.'))
            return

        self.stdout.write(
            self.style.WARNING(f'⚠️ Se eliminarán {count} propiedades sin agente.')
        )
        confirm = input('¿Estás seguro? (s/N): ')

        if confirm.lower() != 's':
            self.stdout.write('❌ Operación cancelada.')
            return

        with transaction.atomic():
            properties.delete()

        self.stdout.write(
            self.style.SUCCESS(f'✅ {count} propiedades eliminadas')
        )