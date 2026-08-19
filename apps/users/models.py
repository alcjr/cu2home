from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


def avatar_upload_path(instance, filename):
    """Ruta de subida para el avatar del usuario."""
    return f'users/{instance.user_id}/avatar_{filename}'


class UserProfile(models.Model):
    class UserType(models.TextChoices):
        BUYER = 'buyer', _('Buyer / visitor')
        AGENT = 'agent', _('Agent')

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('User'),
    )

    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.BUYER,
        verbose_name=_('Account type'),
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_('Phone'),
    )

    avatar = models.ImageField(
        upload_to=avatar_upload_path,
        null=True,
        blank=True,
        verbose_name=_('Avatar'),
    )

    bio = models.TextField(
        blank=True,
        verbose_name=_('Bio'),
    )

    agency_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_('Agency name'),
    )

    receive_email_alerts = models.BooleanField(
        default=True,
        verbose_name=_('Receive email alerts'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('User profile')
        verbose_name_plural = _('User profiles')

    def __str__(self):
        return f'{self.user} ({self.get_user_type_display()})'

    def save(self, *args, **kwargs):
        """
        Si el avatar cambia (o se quita), borra el fichero anterior del
        storage antes de guardar. Sin esto, cada avatar nuevo se sumaba
        al anterior en media/users/<id>/ sin límite -- nunca se
        sobrescribía ni se limpiaba, solo se acumulaba.
        """
        if self.pk:
            try:
                old_avatar = UserProfile.objects.get(pk=self.pk).avatar
            except UserProfile.DoesNotExist:
                old_avatar = None
            if old_avatar and old_avatar != self.avatar:
                old_avatar.delete(save=False)
        super().save(*args, **kwargs)

    @property
    def is_agent(self):
        return self.user_type == self.UserType.AGENT


@receiver(post_delete, sender=UserProfile)
def delete_avatar_on_profile_delete(sender, instance, **kwargs):
    """Borra el fichero de avatar del storage cuando se elimina el
    UserProfile (p.ej. al borrarse el User en cascada), para no dejarlo
    huérfano en media/ sin ninguna fila que lo referencie."""
    if instance.avatar:
        instance.avatar.delete(save=False)


class Favorite(models.Model):
    """
    Relación de favoritos usuario-inmueble. Un registro por par
    (user, property) -- el UniqueConstraint de Meta evita duplicados si
    el usuario pulsa "guardar en favoritos" dos veces sobre el mismo
    inmueble (doble clic, doble submit, etc.), así toggle_favorite() en
    views.py puede confiar en get_or_create sin preocuparse de índices
    repetidos.

    Referencia a 'properties.Property' como string (no import directo)
    para evitar dependencia circular entre apps.users y apps.properties
    a nivel de módulo -- mismo motivo por el que apps.py importa
    signals dentro de ready() y no arriba del todo.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name=_('User'),
    )

    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name=_('Property'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Favorite')
        verbose_name_plural = _('Favorites')
        constraints = [
            models.UniqueConstraint(fields=['user', 'property'], name='unique_user_property_favorite'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} → {self.property}'
