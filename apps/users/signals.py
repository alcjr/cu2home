from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Crea el UserProfile automáticamente al crear un User -- así
    deliver_saved_search_alert (apps/users/tasks.py) puede acceder a
    user.profile.receive_email_alerts sin tener que comprobar
    DoesNotExist en cada envío. get_or_create (no create a secas) por si
    en algún flujo save() se dispara más de una vez sobre un User ya
    existente con created=True por algún motivo raro (poco probable, pero
    barato de blindar).
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
