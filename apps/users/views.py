from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.conf import settings

# Importaciones corregidas
from apps.properties.constants import DEFAULT_FAVORITE_LIST_NAME
from apps.properties.models import SavedSearch, Property
from apps.properties.forms import PropertyFilterForm
from .models import UserProfile
from .forms import SaveSearchForm, FavoriteListForm


@login_required
def favorites(request):
    # Aquí la lógica para obtener los favoritos del usuario
    return render(request, 'users/favorites.html')


@login_required
def favorite_list(request):
    """
    Muestra la lista de favoritos del usuario actual.
    """
    # Aquí se debe obtener la lista de propiedades favoritas del usuario.
    # Por ahora, devolvemos un template con un mensaje.
    return render(request, 'users/favorites.html', {
        'title': _('Mis favoritos'),
        'favorites': [],  # Reemplazar con la lógica real
    })


@login_required
def saved_search_list(request):
    searches = SavedSearch.objects.filter(user=request.user)
    return render(request, 'users/saved_searches.html', {'searches': searches})


@login_required
def create_saved_search(request):
    if request.method == 'POST':
        form = SaveSearchForm(request.POST)
        if form.is_valid():
            search = form.save(commit=False)
            search.user = request.user
            search.save()
            messages.success(request, _('Search saved successfully.'))
            return redirect('users:saved_search_list')
    else:
        form = SaveSearchForm()
    return render(request, 'users/create_saved_search.html', {'form': form})


@login_required
def delete_saved_search(request, pk):
    search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    search.delete()
    messages.success(request, _('Search deleted.'))
    return redirect('users:saved_search_list')


@login_required
def toggle_saved_search(request, pk):
    search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    search.is_active = not search.is_active
    search.save()
    status = _('activated') if search.is_active else _('deactivated')
    messages.success(request, f'Search {status}.')
    return redirect('users:saved_search_list')