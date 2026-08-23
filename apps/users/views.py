import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.mail import send_mail
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST, require_GET, require_http_methods

# Importaciones corregidas
from apps.properties.models import SavedSearch, Property, PropertyImage, Province, Municipality
from apps.properties.forms import PropertyForm, PropertyFilterForm
from apps.properties.constants import DEFAULT_FAVORITE_LIST_NAME, PROPERTY_TYPES, OFFER_TYPES
from .forms import ForgotUsernameForm, RegisterForm, SaveSearchForm
from .models import Favorite, UserProfile

User = get_user_model()

# Igual que apps/properties/admin.py: el límite de imágenes por inmueble
# se define en settings, no aquí, para tenerlo en un único sitio.
MAX_IMAGES_PER_PROPERTY = settings.MAX_IMAGES_PER_PROPERTY


def _auth_view(request, active_tab):
    """
    Página combinada de acceso al portal público: dos pestañas
    (Iniciar sesión / Crear cuenta) sobre la misma URL/plantilla, igual
    que el patrón de pestañas del hero (Comprar/Alquilar/Permutar en
    index.html). El botón "Registro" del header apunta aquí -- si el
    visitante ya tiene cuenta, cambia de pestaña e inicia sesión sin
    salir de la página; si no la tiene, se registra.

    NO tiene relación con apps/authentication (ese es el login de
    staff para el panel admin, con su propio StaffLoginForm que exige
    is_staff). Este es el login del portal público, para
    compradores/agentes.

    active_tab: 'login' o 'register' -- cuál pestaña se muestra activa
    al cargar la página (viene de qué URL entró el usuario:
    users:login o users:register). Si el POST es de la otra pestaña,
    se reactiva esa para mostrar los errores en el formulario correcto.
    """
    if request.user.is_authenticated:
        return redirect('properties:list')

    login_form = AuthenticationForm(request)
    register_form = RegisterForm()

    if request.method == 'POST':
        submitted_form = request.POST.get('form')

        if submitted_form == 'login':
            active_tab = 'login'
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                auth_login(request, login_form.get_user())
                messages.success(request, _('Welcome back!'))
                return redirect('properties:list')

        elif submitted_form == 'register':
            active_tab = 'register'
            register_form = RegisterForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                auth_login(request, user)
                messages.success(request, _('Welcome to cu2home! Your account has been created.'))
                return redirect('properties:list')

    return render(request, 'users/auth.html', {
        'login_form': login_form,
        'register_form': register_form,
        'active_tab': active_tab,
    })


def register(request):
    return _auth_view(request, active_tab='register')


def login_view(request):
    return _auth_view(request, active_tab='login')


@require_POST
def logout_view(request):
    """
    Logout vía POST (no GET) -- así evitamos que el logout se dispare por
    accidente desde un link, prefetch del navegador, o crawler, y de paso
    cumplimos con lo que Django >=4.1 exige por defecto en LogoutView.
    El botón "Cerrar sesión" del dropdown del header envía este form.
    """
    auth_logout(request)
    messages.success(request, _('You have been logged out.'))
    return redirect('properties:list')


@login_required(login_url='users:login')
@require_POST
def toggle_favorite(request, property_id):
    """
    Alterna (añade/quita) el inmueble indicado en los favoritos del
    usuario autenticado.

    FUSIÓN de las dos versiones que convivían en el archivo (bug
    corregido): esta única vista atiende a los dos consumidores que
    existen hoy, distinguiéndolos por la cabecera de la petición en vez
    de por dos vistas/URLs distintas con el mismo nombre:

    - Form clásico (properties/detail.html, <form method="post"> con
      submit normal del navegador): espera una redirección de vuelta a
      la ficha de la propiedad, con un mensaje via `messages`. Es una
      petición "no-AJAX" -- sin X-Requested-With ni Accept:
      application/json.
    - Llamada AJAX (p.ej. un botón de favorito en el grid dxDataGrid de
      favoritos/listado, o cualquier fetch/$.ajax futuro): espera JSON
      con {is_favorite, property_id} para poder actualizar el icono sin
      recargar la página, en vez de recibir una redirección HTML.

    get_or_create + delete si ya existía, igual que describe el
    docstring de Favorite en models.py: evita duplicados ante doble
    submit sin necesitar una comprobación previa aparte.
    """
    property_obj = get_object_or_404(Property, pk=property_id, is_active=True)

    favorite, created = Favorite.objects.get_or_create(user=request.user, property=property_obj)
    if not created:
        favorite.delete()
        is_favorite = False
    else:
        is_favorite = True

    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
    if is_ajax:
        return JsonResponse({'is_favorite': is_favorite, 'property_id': property_obj.pk})

    if is_favorite:
        messages.success(request, _('Added to favorites.'))
    else:
        messages.success(request, _('Removed from favorites.'))

    next_url = request.POST.get('next') or reverse(
        'properties:detail', args=[property_obj.pk, property_obj.slug]
    )
    return redirect(next_url)


@login_required(login_url='users:login')
def favorites_page(request):
    """Renderiza la página con la grilla DevExpress (dxDataGrid) de
    favoritos -- 'Mis favoritos' del dashboard de usuario."""
    return render(request, 'users/favorites.html', {
        'title': _('Mis favoritos'),
    })


@login_required(login_url='users:login')
def favorites_data(request):
    """
    Endpoint JSON que alimenta el dataSource de la dxDataGrid.
    IMPORTANTE: el queryset SIEMPRE se filtra por request.user -- nunca se
    acepta un parámetro de usuario desde el cliente, para no exponer
    favoritos de otras personas.
    """
    favorites = (
        Favorite.objects
        .filter(user=request.user)
        .select_related('property', 'property__province', 'property__municipality')
        .order_by('-created_at')
    )

    data = []
    for fav in favorites:
        prop = fav.property
        data.append({
            'favorite_id': fav.id,
            'property_id': prop.id,
            'codigo': prop.slug,
            'tipo': prop.get_property_type_display(),
            'tipo_raw': prop.property_type,
            'ubicacion': f'{prop.province.name if prop.province else ""}'.strip(', '),
            'oferta': prop.get_offer_type_display(),
            'precio': float(prop.display_price) if prop.display_price else None,
            'superficie': prop.surface,
            'estado': prop.get_status_display(),
            'anadido': fav.created_at.strftime('%d/%m/%Y'),
            'detail_url': reverse('properties:detail', args=[prop.pk, prop.slug]),
        })

    return JsonResponse(data, safe=False)


def _generate_unique_slug(title, exclude_pk=None):
    """
    Property.slug es único y obligatorio, pero no se pide al usuario en
    el popup de alta (no tiene sentido pedirle un 'slug' a alguien que
    solo quiere publicar un piso) -- se deriva del título, igual que ya
    hacen Province.save() y Municipality.save() en apps/properties/models.py,
    solo que Property no tiene esa lógica en su propio save(), así que la
    ponemos aquí, en la vista, antes de guardar.
    """
    base_slug = slugify(title) or 'inmueble'
    slug = base_slug
    qs = Property.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    i = 1
    while qs.filter(slug=slug).exists():
        i += 1
        slug = f'{base_slug}-{i}'
    return slug


def _sync_location_with_municipality(obj):
    """
    El popup de 'Mis inmuebles' no tiene editores de latitud/longitud
    para el propio Property -- nunca se pide al usuario un punto
    exacto -- así que Property.location se queda en NULL en cada alta
    aunque el usuario sí elija provincia/municipio. Municipality ya
    tiene su propio 'location' georreferenciado (ver
    apps/properties/models.py::Municipality.save()), así que usamos
    ese punto como aproximación razonable: sitúa el inmueble en el
    centro de su municipio en vez de dejarlo sin geolocalizar.

    Se sincroniza siempre que haya municipio (no solo si location
    está vacío) porque, al no existir ningún campo manual de
    coordenadas en este formulario, todo 'location' guardado hasta
    ahora proviene de este mismo mecanismo -- así un cambio de
    municipio en un PATCH también actualiza el punto en vez de dejar
    el del municipio anterior.
    """
    if obj.municipality_id and obj.municipality.location:
        obj.location = obj.municipality.location


def _serialize_owner_property(obj, request):
    """
    Serializa un Property para el dueño (grid + popup de edición de
    'Mis inmuebles'). A diferencia de _serialize_property_for_grid en
    apps/properties/views.py (pensado para el listado público, con
    precios ya formateados/etiquetados), aquí se exponen los valores
    RAW de cada campo -- el popup de edición de dxDataGrid necesita
    bindear un valor editable por cada dataField, no un texto ya
    traducido a mostrar.
    """
    images = [
        {
            'id': img.pk,
            'url': request.build_absolute_uri(img.image.url),
            'is_cover': img.is_cover,
            'order': img.order,
        }
        for img in obj.images.all()
    ]
    cover = obj.cover_image
    return {
        'id': obj.pk,
        'title': obj.safe_translation_getter('title', any_language=True) or '',
        'description': obj.safe_translation_getter('description', any_language=True) or '',
        'property_type': obj.property_type,
        'property_type_display': obj.get_property_type_display(),
        'offer_type': obj.offer_type,
        'offer_type_display': obj.get_offer_type_display(),
        'sale_price': float(obj.sale_price) if obj.sale_price is not None else None,
        'rent_price': float(obj.rent_price) if obj.rent_price is not None else None,
        'seasonal_rent_price': float(obj.seasonal_rent_price) if obj.seasonal_rent_price is not None else None,
        'deposit_amount': float(obj.deposit_amount) if obj.deposit_amount is not None else None,
        'province': obj.province_id,
        'province_name': obj.province.name if obj.province else '',
        'municipality': obj.municipality_id,
        'municipality_name': obj.municipality.name if obj.municipality else '',
        'address': obj.address or '',
        'surface': obj.surface,
        'rooms': obj.rooms,
        'bathrooms': obj.bathrooms,
        'has_elevator': obj.has_elevator,
        'has_heating': obj.has_heating,
        'has_air_conditioning': obj.has_air_conditioning,
        'status': obj.status,
        'status_display': obj.get_status_display(),
        'is_active': obj.is_active,
        'views_count': obj.views_count,
        'images': images,
        'cover_image_url': request.build_absolute_uri(cover.image.url) if cover else None,
        'image_count': len(images),
        'max_images': MAX_IMAGES_PER_PROPERTY,
        'detail_url': reverse('properties:detail', args=[obj.pk, obj.slug]),
        'created_at': obj.created_at.strftime('%d/%m/%Y'),
    }


@login_required(login_url='users:login')
def my_properties(request):
    """Renderiza la página con la grilla DevExpress de 'Mis inmuebles'
    (alta/edición/borrado, con imágenes) -- mismo patrón CustomStore que
    favorites.html, pero con edición vía popup como en FINGEST."""
    # Provincias/municipios se inyectan como JSON en el template (vía
    # json_script) en vez de exponer un endpoint JSON aparte: son datos
    # de referencia estáticos (geografía de Cuba), no cambian por
    # usuario ni con frecuencia, así que no vale la pena una llamada
    # AJAX extra solo para rellenar dos <select> del popup.
    provinces = list(Province.objects.order_by('name').values('id', 'name'))
    municipalities = list(
        Municipality.objects.select_related('province').order_by('name').values('id', 'name', 'province_id')
    )

    return render(request, 'users/my_properties.html', {
        'title': _('Mis inmuebles'),
        'property_types': list(Property._meta.get_field('property_type').choices),
        'offer_types': list(Property._meta.get_field('offer_type').choices),
        'provinces': provinces,
        'municipalities': municipalities,
    })


@login_required(login_url='users:login')
@require_http_methods(['GET', 'POST'])
def my_properties_data(request):
    """
    Recurso de listado (GET) + alta (POST) para el CustomStore del grid
    de 'Mis inmuebles'. Un único endpoint para las dos operaciones,
    igual que URLS.inmuebles en FINGEST se usa tanto para el load()
    como para el insert() del CustomStore.

    El queryset SIEMPRE se filtra por agent=request.user (igual que
    favorites_data se filtra por user=request.user) -- nunca se acepta
    un id de propietario desde el cliente.
    """
    if request.method == 'GET':
        properties = (
            Property.objects
            .filter(agent=request.user)
            .select_related('province', 'municipality')
            .prefetch_related('images')
            .order_by('-created_at')
        )
        return JsonResponse(
            [_serialize_owner_property(p, request) for p in properties],
            safe=False,
        )

    # POST -- alta de un inmueble nuevo. Sin imágenes en este paso: hace
    # falta el pk del Property para poder subirlas (property_image_upload_path
    # las guarda en properties/<property_id>/images/), así que las
    # imágenes se añaden en una segunda llamada, ya con el inmueble creado.
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': _('Invalid JSON payload.')}, status=400)

    form = PropertyForm(payload)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)

    obj = form.save(commit=False)
    obj.agent = request.user
    obj.slug = _generate_unique_slug(form.cleaned_data['title'])
    _sync_location_with_municipality(obj)

    try:
        obj.clean()
    except ValidationError as e:
        return JsonResponse({'errors': e.message_dict}, status=400)

    obj.save()
    return JsonResponse(_serialize_owner_property(obj, request), status=201)


def _full_payload_for_patch(obj, payload):
    """
    dxDataGrid solo envía en update() los campos que el usuario cambió
    en el popup (un diff), no la fila completa. PropertyForm es un
    ModelForm normal: al vincularlo con `data=payload` valida SOLO
    contra las claves presentes en payload, sin caer nunca en los
    valores de `instance` para los campos requeridos que falten --
    'title', 'description', 'property_type' u 'offer_type' ausentes del
    diff hacían fallar la validación con "This field is required."
    aunque el inmueble ya tuviera esos valores guardados. Peor aún con
    los BooleanField (has_elevator, has_heating, has_air_conditioning,
    is_active): al ser required=False en el form, un campo ausente del
    diff no fallaba, se interpretaba en silencio como False y
    desmarcaba la casilla en cada PATCH que no la mencionara.

    Este helper arma el payload completo que necesita el form: parte de
    los valores ACTUALES del objeto (incluidas title/description, que
    viven en la tabla de traducciones de parler y por eso no las
    captura model_to_dict) y los sobreescribe solo con las claves que sí
    vengan en el payload del cliente. 'agent' se excluye a propósito:
    PropertyForm ya no lo declara en Meta.fields (ver forms.py), así
    que no se toca aquí -- el dueño de un inmueble no debe poder
    reasignarlo a otro agente ni siquiera con un PATCH manual fuera del
    grid.
    """
    current = model_to_dict(obj, fields=PropertyForm.Meta.fields)
    current['title'] = obj.safe_translation_getter('title', any_language=True) or ''
    current['description'] = obj.safe_translation_getter('description', any_language=True) or ''
    current.update(payload)
    return current


@login_required(login_url='users:login')
@require_http_methods(['PATCH', 'DELETE'])
def my_properties_detail(request, pk):
    """Edición (PATCH) y borrado (DELETE) de un inmueble propio, para
    update()/remove() del CustomStore. get_object_or_404 con
    agent=request.user: un usuario nunca puede editar/borrar un
    inmueble que no es suyo, ni aunque adivine el id."""
    obj = get_object_or_404(Property, pk=pk, agent=request.user)

    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'deleted': True})

    # PATCH -- payload puede ser parcial (solo los campos que cambiaron
    # en el popup), así que se completa con los valores actuales del
    # objeto antes de validar. Ver _full_payload_for_patch().
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': _('Invalid JSON payload.')}, status=400)

    full_payload = _full_payload_for_patch(obj, payload)
    form = PropertyForm(full_payload, instance=obj)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)

    obj = form.save(commit=False)
    _sync_location_with_municipality(obj)
    try:
        obj.clean()
    except ValidationError as e:
        return JsonResponse({'errors': e.message_dict}, status=400)

    obj.save()
    return JsonResponse(_serialize_owner_property(obj, request))


@login_required(login_url='users:login')
@require_POST
def my_property_image_upload(request, pk):
    """
    Sube una imagen a un inmueble propio. Se llama por separado del
    CustomStore principal (petición multipart, no JSON) desde el
    dxFileUploader del popup de edición -- ver comentario en
    my_properties_data sobre por qué las imágenes van aparte del
    insert() del grid.
    """
    obj = get_object_or_404(Property, pk=pk, agent=request.user)

    if obj.images.count() >= MAX_IMAGES_PER_PROPERTY:
        return JsonResponse(
            {'error': _('Maximum number of images reached (%(max)s).') % {'max': MAX_IMAGES_PER_PROPERTY}},
            status=400,
        )

    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'error': _('No image file provided.')}, status=400)

    is_first = not obj.images.exists()
    image = PropertyImage.objects.create(
        property=obj,
        image=image_file,
        is_cover=is_first,
        order=obj.images.count(),
    )
    return JsonResponse({
        'id': image.pk,
        'url': request.build_absolute_uri(image.image.url),
        'is_cover': image.is_cover,
        'order': image.order,
    }, status=201)


@login_required(login_url='users:login')
@require_http_methods(['DELETE'])
def my_property_image_delete(request, pk, image_id):
    """Borra una imagen concreta de un inmueble propio. Si la imagen
    borrada era la portada, promociona la siguiente por 'order' a
    portada -- sin esto un inmueble con imágenes podría quedarse sin
    ninguna marcada is_cover=True y cover_image devolvería None aun
    teniendo fotos."""
    obj = get_object_or_404(Property, pk=pk, agent=request.user)
    image = get_object_or_404(PropertyImage, pk=image_id, property=obj)

    was_cover = image.is_cover
    image.image.delete(save=False)
    image.delete()

    if was_cover:
        next_image = obj.images.order_by('order').first()
        if next_image:
            next_image.is_cover = True
            next_image.save(update_fields=['is_cover'])

    return JsonResponse({'deleted': True})


@login_required(login_url='users:login')
@require_POST
def my_property_image_set_cover(request, pk, image_id):
    """Marca una imagen como portada, desmarcando cualquier otra --
    is_cover debe ser único por inmueble (no hay UniqueConstraint en el
    modelo para esto, así que se garantiza aquí en la vista)."""
    obj = get_object_or_404(Property, pk=pk, agent=request.user)
    image = get_object_or_404(PropertyImage, pk=image_id, property=obj)

    obj.images.exclude(pk=image.pk).update(is_cover=False)
    image.is_cover = True
    image.save(update_fields=['is_cover'])

    return JsonResponse({'set_cover': True})


@login_required(login_url='users:login')
def saved_search_list(request):
    searches = SavedSearch.objects.filter(user=request.user)
    return render(request, 'users/saved_searches.html', {'searches': searches})


@login_required(login_url='users:login')
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


@login_required(login_url='users:login')
@require_POST
def delete_saved_search(request, pk):
    search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    search.delete()
    messages.success(request, _('Search deleted.'))
    return redirect('users:saved_search_list')


@login_required(login_url='users:login')
@require_POST
def toggle_saved_search(request, pk):
    search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    search.is_active = not search.is_active
    search.save()
    status = _('activated') if search.is_active else _('deactivated')
    messages.success(request, f'Search {status}.')
    return redirect('users:saved_search_list')


# ===== Mis alertas (dxDataGrid) =====
# Grilla con edición/borrado sobre SavedSearch, mismo patrón CustomStore +
# popup que 'Mis inmuebles' (my_properties_data/my_properties_detail),
# como alternativa a las vistas clásicas de arriba (saved_search_list,
# create_saved_search...) que se mantienen intactas para no romper nada
# que ya las use.
#
# query_params usa DELIBERADAMENTE los MISMOS nombres de campo que
# PropertyFilterForm (apps/properties/forms.py): province_id,
# municipality_id, property_type, offer_type, min_sale_price,
# max_sale_price, min_rent_price, max_rent_price, has_elevator,
# has_heating, has_air_conditioning. Así SavedSearch.get_matches()
# (apps/properties/models.py) puede validarlo e interpretarlo con ese
# mismo form sin inventar un esquema nuevo ni duplicar reglas de filtrado.
ALERT_QUERY_PARAM_FIELDS = [
    'province_id', 'municipality_id', 'property_type', 'offer_type',
    'min_sale_price', 'max_sale_price', 'min_rent_price', 'max_rent_price',
    'has_elevator', 'has_heating', 'has_air_conditioning',
]

# Para property_type_display/offer_type_display en _serialize_alert: a
# diferencia de Property.get_property_type_display(), aquí no hay una
# instancia de Property de la que tirar (SavedSearch solo guarda el
# código en query_params), así que se resuelve a mano contra las mismas
# choices que ya usa el modelo.
_PROPERTY_TYPE_LABELS = dict(PROPERTY_TYPES)
_OFFER_TYPE_LABELS = dict(OFFER_TYPES)


def _alert_query_params_from_payload(payload, base=None):
    """Extrae y limpia el sub-objeto query_params a partir de las claves
    planas que envía el popup del grid, partiendo de `base` (el
    query_params YA guardado, cuando se está editando) y sobreescribiendo
    solo las claves presentes en `payload`. Los booleanos SÍ se
    conservan aunque vengan en False (a diferencia de los demás, donde
    False/None/'' significa "quitar este filtro"), porque False es su
    valor real por defecto, no una ausencia de dato."""
    params = dict(base) if base else {}
    for key in ALERT_QUERY_PARAM_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if key in ('has_elevator', 'has_heating', 'has_air_conditioning'):
            params[key] = bool(value)
        elif value in (None, ''):
            params.pop(key, None)
        else:
            params[key] = value
    return params


def _serialize_alert(obj, province_map=None, municipality_map=None):
    qp = obj.query_params or {}
    province_map = province_map or {}
    municipality_map = municipality_map or {}
    return {
        'id': obj.pk,
        'name': obj.name,
        'frequency': obj.frequency,
        'frequency_display': obj.get_frequency_display(),
        'is_active': obj.is_active,
        'province_id': qp.get('province_id'),
        'province_name': province_map.get(qp.get('province_id'), ''),
        'municipality_id': qp.get('municipality_id'),
        'municipality_name': municipality_map.get(qp.get('municipality_id'), ''),
        'property_type': qp.get('property_type', ''),
        'property_type_display': str(_PROPERTY_TYPE_LABELS.get(qp.get('property_type'), '')),
        'offer_type': qp.get('offer_type', ''),
        'offer_type_display': str(_OFFER_TYPE_LABELS.get(qp.get('offer_type'), '')),
        'min_sale_price': qp.get('min_sale_price'),
        'max_sale_price': qp.get('max_sale_price'),
        'min_rent_price': qp.get('min_rent_price'),
        'max_rent_price': qp.get('max_rent_price'),
        'has_elevator': bool(qp.get('has_elevator')),
        'has_heating': bool(qp.get('has_heating')),
        'has_air_conditioning': bool(qp.get('has_air_conditioning')),
        'last_notified_at': obj.last_notified_at.strftime('%d/%m/%Y %H:%M') if obj.last_notified_at else None,
        'created_at': obj.created_at.strftime('%d/%m/%Y'),
    }


def _build_alert(user, payload, instance=None):
    """Valida y arma un SavedSearch (nuevo o existente) a partir del
    payload del popup. Devuelve (obj, errors) -- errors es None si todo
    fue bien, o un dict de errores por campo listo para JsonResponse si
    no.

    FIX (mismo motivo que _full_payload_for_patch para PropertyForm):
    dxDataGrid en modo popup solo envía en update() los campos que el
    usuario cambió, no la fila completa. Sin partir de los valores
    ACTUALES de `instance` (name, frequency, is_active y cada clave de
    query_params) antes de aplicar el payload, editar por ejemplo solo
    la casilla "Activa" habría reseteado en silencio provincia, tipo,
    oferta, rango de precio y amenities a "sin filtro" en cada guardado
    parcial.

    La validación de los filtros de búsqueda se delega en
    PropertyFilterForm -- así un SavedSearch nunca queda guardado con,
    p.ej., un province_id inexistente que rompería get_matches() en cada
    tick del beat en vez de fallar aquí con un 400 legible para el
    usuario que está editando la alerta."""
    base_query_params = (instance.query_params or {}) if instance else {}
    query_params = _alert_query_params_from_payload(payload, base=base_query_params)

    filter_form = PropertyFilterForm(query_params)
    if not filter_form.is_valid():
        return None, filter_form.errors

    valid_frequencies = set(SavedSearch.Frequency.values)
    current_frequency = instance.frequency if instance else SavedSearch.Frequency.DAILY
    frequency = payload.get('frequency', current_frequency) or current_frequency
    if frequency not in valid_frequencies:
        return None, {'frequency': [_('Invalid frequency.')]}

    current_name = instance.name if instance else ''
    current_is_active = instance.is_active if instance else True

    obj = instance or SavedSearch(user=user)
    obj.name = (payload.get('name', current_name) or '').strip() or str(DEFAULT_FAVORITE_LIST_NAME)
    obj.frequency = frequency
    obj.is_active = bool(payload.get('is_active', current_is_active))
    obj.query_params = query_params
    return obj, None


@login_required(login_url='users:login')
def alerts_page(request):
    """Renderiza la página con la grilla DevExpress (dxDataGrid) de
    alertas -- 'Mis alertas' del dashboard de usuario. Provincias y
    municipios se inyectan como JSON en el template (json_script), igual
    que en my_properties: son datos de referencia estáticos, no vale la
    pena una llamada AJAX aparte solo para rellenar los <select> del
    popup."""
    provinces = list(Province.objects.order_by('name').values('id', 'name'))
    municipalities = list(
        Municipality.objects.select_related('province').order_by('name').values('id', 'name', 'province_id')
    )
    return render(request, 'users/alerts.html', {
        'title': _('Mis alertas'),
        'property_types': list(Property._meta.get_field('property_type').choices),
        'offer_types': list(Property._meta.get_field('offer_type').choices),
        'frequencies': list(SavedSearch.Frequency.choices),
        'provinces': provinces,
        'municipalities': municipalities,
    })


def _province_municipality_maps():
    """dicts {id: name} para resolver province_id/municipality_id a texto
    en _serialize_alert sin una query por fila. Se construye una vez por
    request (nunca son tantas provincias/municipios como para pesar)."""
    provinces = dict(Province.objects.values_list('id', 'name'))
    municipalities = dict(Municipality.objects.values_list('id', 'name'))
    return provinces, municipalities


@login_required(login_url='users:login')
@require_http_methods(['GET', 'POST'])
def alerts_data(request):
    """Listado (GET) + alta (POST) para el CustomStore del grid de 'Mis
    alertas'. El queryset SIEMPRE se filtra por user=request.user --
    nunca se acepta un id de usuario desde el cliente."""
    province_map, municipality_map = _province_municipality_maps()

    if request.method == 'GET':
        searches = SavedSearch.objects.filter(user=request.user).order_by('-created_at')
        return JsonResponse(
            [_serialize_alert(s, province_map, municipality_map) for s in searches],
            safe=False,
        )

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': _('Invalid JSON payload.')}, status=400)

    obj, errors = _build_alert(request.user, payload)
    if errors:
        return JsonResponse({'errors': errors}, status=400)

    obj.save()
    return JsonResponse(_serialize_alert(obj, province_map, municipality_map), status=201)


@login_required(login_url='users:login')
@require_http_methods(['PATCH', 'DELETE'])
def alerts_detail(request, pk):
    """Edición (PATCH) y borrado (DELETE) de una alerta propia, para
    update()/remove() del CustomStore. get_object_or_404 con
    user=request.user: un usuario nunca puede editar/borrar una alerta
    que no es suya, ni aunque adivine el id."""
    obj = get_object_or_404(SavedSearch, pk=pk, user=request.user)

    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'deleted': True})

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': _('Invalid JSON payload.')}, status=400)

    obj, errors = _build_alert(request.user, payload, instance=obj)
    if errors:
        return JsonResponse({'errors': errors}, status=400)

    obj.save()
    province_map, municipality_map = _province_municipality_maps()
    return JsonResponse(_serialize_alert(obj, province_map, municipality_map))


def forgot_username(request):
    """
    'Olvidé mi usuario', complementario a PasswordResetView (que ya trae
    Django de serie para la contraseña -- ver urls.py). No es una vista
    de Django, porque no existe equivalente built-in para recuperar el
    *username*.

    A propósito SIEMPRE renderiza el mismo template de confirmación tras
    un POST válido, exista o no ese email en la base de datos, y con
    fail_silently=True en el envío -- así este formulario no sirve para
    enumerar qué correos están registrados en el portal (mismo motivo
    por el que PasswordResetView de Django se comporta igual).
    """
    if request.method == 'POST':
        form = ForgotUsernameForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            matching_users = User.objects.filter(email__iexact=email)
            if matching_users.exists():
                usernames = ', '.join(sorted(u.username for u in matching_users))
                send_mail(
                    subject=_('Your cu2home username'),
                    message=render_to_string('users/emails/forgot_username_email.txt', {
                        'usernames': usernames,
                    }),
                    from_email=None,  # usa settings.DEFAULT_FROM_EMAIL
                    recipient_list=[email],
                    fail_silently=True,
                )
            return render(request, 'users/forgot_username_done.html')
    else:
        form = ForgotUsernameForm()

    return render(request, 'users/forgot_username.html', {'form': form})


# ============================================================================
# MIS DATOS
# ============================================================================

@login_required(login_url='users:login')
def my_data(request):
    """
    Página de gestión de datos del usuario registrado.
    Permite leer y actualizar: nombre, apellidos, email, teléfono,
    tipo de usuario (comprador/agente), avatar, biografía, nombre de
    agencia y preferencia de alertas por email.
    """
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        # ===== DATOS DEL USER =====
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()

        # Validación de email único
        if email:
            if User.objects.exclude(pk=user.pk).filter(email__iexact=email).exists():
                messages.error(request, _('Este correo electrónico ya está registrado por otro usuario.'))
                return redirect('users:my_data')
            user.email = email

        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # ===== DATOS DEL PERFIL =====
        profile.user_type = request.POST.get('user_type', profile.user_type)
        profile.phone = request.POST.get('phone', '').strip()
        profile.bio = request.POST.get('bio', '').strip()
        profile.agency_name = request.POST.get('agency_name', '').strip()
        profile.receive_email_alerts = request.POST.get('receive_email_alerts') == 'on'

        # Avatar - si se sube una nueva imagen
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']

        # Eliminar avatar si se marca la casilla
        if request.POST.get('remove_avatar') == 'on' and profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None

        profile.save()

        messages.success(request, _('Tus datos han sido actualizados correctamente.'))
        return redirect('users:my_data')

    return render(request, 'users/my_data.html', {
        'title': _('Mis datos'),
        'user': user,
        'profile': profile,
        'user_type_choices': UserProfile.UserType.choices,
    })