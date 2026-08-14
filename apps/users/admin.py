from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'phone', 'receive_email_alerts', 'created_at')
    list_filter = ('user_type', 'receive_email_alerts')
    search_fields = ('user__username', 'user__email', 'phone', 'agency_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {'fields': ('user', 'user_type')}),
        (_('Contact'), {'fields': ('phone', 'avatar', 'bio')}),
        (_('Agent'), {'fields': ('agency_name',)}),
        (_('Notifications'), {'fields': ('receive_email_alerts',)}),
        (_('Metadata'), {'fields': ('created_at', 'updated_at')}),
    )
