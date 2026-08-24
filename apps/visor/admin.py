from django.contrib import admin
from .models import LogFilterPreset


@admin.register(LogFilterPreset)
class LogFilterPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'lines_per_page', 'created_at')
    list_filter = ('level', 'created_at')
    search_fields = ('name', 'search')
    readonly_fields = ('created_at',)
