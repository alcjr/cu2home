from .models import Property


def featured_properties(request):
    """
    Context processor global: expone las propiedades destacadas a todos
    los templates (hoy solo se usa en el home, apps/core/templates/core/index.html,
    para el contador "N propiedades destacadas" del hero).

    Reutiliza Property.get_featured(), ya definido en models.py, en vez de
    duplicar aquí el filtro is_active + orden por created_at.
    """
    return {
        'featured_properties': Property.get_featured(),
    }
