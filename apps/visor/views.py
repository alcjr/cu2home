from django.shortcuts import render
from apps.core.decorators import superuser_required


@superuser_required
def visor(request):
    return render(request, 'visor/visor.html', {})