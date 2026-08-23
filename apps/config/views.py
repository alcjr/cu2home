from django.shortcuts import render
from apps.core.decorators import superuser_required


@superuser_required
def config(request):
    return render(request, 'config/config.html', {})