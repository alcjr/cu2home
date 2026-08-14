from django.conf import settings
from django.db import models
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

    @property
    def is_agent(self):
        return self.user_type == self.UserType.AGENT