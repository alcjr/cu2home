from django.db import migrations, models
import django.db.models.deletion


def migrate_province_to_fk(apps, schema_editor):
    Province = apps.get_model('properties', 'Province')
    Property = apps.get_model('properties', 'Property')

    # Obtener nombres de provincia únicos desde las propiedades existentes
    province_names = (
        Property.objects
        .exclude(province__isnull=True)
        .exclude(province='')
        .values_list('province', flat=True)
        .distinct()
    )

    # Crear las provincias que no existan
    province_map = {}
    for name in province_names:
        province, created = Province.objects.get_or_create(name=name)
        province_map[name] = province

    # Asignar provincia a cada propiedad
    for prop in Property.objects.all():
        old_name = getattr(prop, 'province', None)
        if old_name and old_name in province_map:
            prop.province_fk = province_map[old_name]
            prop.save(update_fields=['province_fk'])


def reverse_migration(apps, schema_editor):
    # No se puede revertir limpiamente, solo pasamos
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0005_province_municipality'),
    ]

    operations = [
        # 1. Agregar campo temporario como ForeignKey a Province
        migrations.AddField(
            model_name='property',
            name='province_fk',
            field=models.ForeignKey(
                to='properties.Province',
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name='properties',
                verbose_name='Province',
            ),
        ),

        # 2. Poblar el campo con los datos existentes
        migrations.RunPython(migrate_province_to_fk, reverse_migration),

        # 3. Eliminar el antiguo campo CharField
        migrations.RemoveField(
            model_name='property',
            name='province',
        ),

        # 4. Renombrar el nuevo campo a 'province'
        migrations.RenameField(
            model_name='property',
            old_name='province_fk',
            new_name='province',
        ),
    ]