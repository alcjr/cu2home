from .models import Property

def featured_properties(request):
    """Context processor para disponer de propiedades destacadas en cualquier template."""
    return {
        'featured_properties': Property.get_featured(limit=6),
    }
