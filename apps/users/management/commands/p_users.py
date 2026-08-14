import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.users.models import UserProfile


class Command(BaseCommand):
    help = "Create sample users with profiles (buyers and agents) for testing."

    # Listas de nombres y apellidos cubanos
    FIRST_NAMES = [
        "Alejandro", "María", "José", "Ana", "Carlos", "Marta", "Luis", "Yenisey",
        "Jorge", "Yamilé", "Pedro", "Diana", "Raúl", "Lisandra", "Miguel", "Dayana",
        "Enrique", "Lianne", "Antonio", "Yusleidys", "Roberto", "Yanet", "Frank", "Bárbara",
        "Iván", "Sandra", "Manuel", "Caridad", "José Antonio", "Yasmin", "Yosvani", "Leyanis",
        "Osmany", "Yudith", "Danilo", "Ariadna", "Yunior", "Yusmila", "Reinier", "Yohana"
    ]

    LAST_NAMES = [
        "García", "Rodríguez", "Martínez", "Pérez", "González", "Hernández", "López",
        "Díaz", "Fernández", "Cabrera", "Gutiérrez", "Mendoza", "Castillo", "Reyes",
        "Cruz", "Morales", "Acosta", "Medina", "Suárez", "Gómez", "Ortega", "Vega",
        "Sánchez", "Ramírez", "Torres", "Rivera", "Núñez", "Pardo", "León", "Castro",
        "Piedra", "Álvarez", "Domínguez", "Molina", "Santos", "Ríos", "Marín", "Ramos"
    ]

    # Agencias ficticias
    AGENCIES = [
        "CasaReal Inmobiliaria", "Sofía Propiedades", "Ciudad Habana Realty",
        "Varadero Luxury Homes", "Cuba Caribe Real Estate", "Inmobiliaria Miramar",
        "Agencia Havana", "Vedado Inversiones", "Cuban Dream Properties",
        "Inversiones Caribe", "Real Estate Santiago", "Cienfuegos Propiedades"
    ]

    # Dominios de correo
    EMAIL_DOMAINS = ["gmail.com", "yahoo.es", "nauta.cu", "cubarte.cu", "hotmail.com"]

    def add_arguments(self, parser):
        parser.add_argument(
            "--total",
            type=int,
            default=20,
            help="Número total de usuarios a crear (mínimo 2).",
        )
        parser.add_argument(
            "--agent-ratio",
            type=float,
            default=0.3,
            help="Proporción de agentes (0-1). Ej: 0.3 = 30% agentes, 70% compradores.",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Elimina todos los usuarios y perfiles existentes antes de crear nuevos.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        total = max(2, options["total"])
        agent_ratio = max(0, min(1, options["agent_ratio"]))
        clean = options["clean"]

        if clean:
            self.stdout.write("Eliminando usuarios existentes...")
            UserProfile.objects.all().delete()
            User.objects.all().delete()

        existing_count = User.objects.count()
        if existing_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Ya existen {existing_count} usuarios y perfiles. "
                    f"Se crearán {total} usuarios adicionales."
                )
            )

        created_users = 0
        # Determinar cuántos agentes y compradores
        num_agents = int(total * agent_ratio)
        num_buyers = total - num_agents

        # Crear agentes
        for i in range(num_agents):
            user = self._create_user(user_type=UserProfile.UserType.AGENT)
            if user:
                created_users += 1

        # Crear compradores
        for i in range(num_buyers):
            user = self._create_user(user_type=UserProfile.UserType.BUYER)
            if user:
                created_users += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Se crearon {created_users} nuevos usuarios "
                f"({num_agents} agentes, {num_buyers} compradores). "
                f"Total de usuarios ahora: {User.objects.count()}"
            )
        )

    def _create_user(self, user_type):
        """Crea un usuario y su perfil asociado, evitando duplicados."""
        # Generar nombre y apellido
        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)
        # Añadir un número aleatorio para evitar duplicados
        random_suffix = random.randint(1, 9999)
        username = f"{first_name.lower()}.{last_name.lower()}{random_suffix}".replace(" ", "")

        # Correo
        domain = random.choice(self.EMAIL_DOMAINS)
        email = f"{first_name.lower()}.{last_name.lower()}{random_suffix}@{domain}".replace(" ", "")

        # Contraseña fija (para pruebas)
        password = f"Test123_{random.randint(100, 999)}"

        # Teléfono cubano (formato: 5XXXXXXX)
        phone = f"+53 5{random.randint(1000000, 9999999)}"

        # Verificar si ya existe el usuario (por si acaso)
        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.WARNING(f"El usuario {username} ya existe. Saltando..."))
            return None
        except User.DoesNotExist:
            pass

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creando usuario {username}: {e}"))
            return None

        # Crear perfil (o actualizar si ya existe)
        agency_name = ""
        if user_type == UserProfile.UserType.AGENT:
            agency_name = random.choice(self.AGENCIES)

        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "user_type": user_type,
                "phone": phone,
                "agency_name": agency_name,
                "bio": self._generate_bio(user_type, first_name),
            }
        )

        if not created:
            # Si ya existía, actualizar algunos campos
            profile.user_type = user_type
            profile.phone = phone
            profile.agency_name = agency_name
            profile.bio = self._generate_bio(user_type, first_name)
            profile.save()
            self.stdout.write(self.style.WARNING(f"  ⟳ Perfil actualizado para {username}"))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ {user_type} {username} ({first_name} {last_name}) - {phone}")
            )

        return user

    def _generate_bio(self, user_type, first_name):
        """Genera una biografía según el tipo de usuario."""
        if user_type == UserProfile.UserType.AGENT:
            return f"Agente inmobiliario con {random.randint(2, 15)} años de experiencia. Especialista en el mercado cubano. Contacte con {first_name} para más información sobre propiedades."
        else:
            return f"Usuario interesado en {random.choice(['comprar', 'alquilar', 'invertir en'])} propiedades en {random.choice(['La Habana', 'Varadero', 'Santiago de Cuba', 'Trinidad'])}."
