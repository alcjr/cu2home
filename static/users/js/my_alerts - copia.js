(function () {
    'use strict';

    const gridEl = document.getElementById('alertsGrid');
    if (!gridEl) return;
    if (typeof DevExpress === 'undefined') {
        console.error('DevExpress no está disponible.');
        return;
    }

    DevExpress.localization.locale('es');

    const csrfToken = window.csrfToken || '';
    let URLS;
    try {
        URLS = JSON.parse(document.getElementById('urls-config').textContent);
        console.log('URLS cargadas:', URLS);
    } catch (e) {
        console.error('Error parsing URLs config:', e);
        return;
    }

    function gettext(message) {
        if (typeof window.gettext === 'function') return window.gettext(message);
        return message;
    }

    function escapeHtml(text) {
        if (!text) return '';
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    function formatCurrency(value) {
        if (value == null) return '';
        return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);
    }

    // Mismo motivo que en my_properties.js/favorites.js: .replace() con
    // string literal sustituye solo la PRIMERA ocurrencia de "/0/".
    function buildUrl(baseUrl, ...args) {
        let url = baseUrl;
        for (const arg of args) {
            url = url.replace('/0/', `/${arg}/`);
        }
        return url;
    }

    function apiRequest(url, method, body) {
        const opts = {
            method: method,
            headers: { 'X-CSRFToken': csrfToken, 'Accept': 'application/json' },
            credentials: 'same-origin'
        };
        if (body !== undefined) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }

        console.log('[API]', method, url, body);

        return fetch(url, opts).then(res => {
            if (!res.ok) {
                return res.text().then(txt => {
                    let errBody = {};
                    try { errBody = JSON.parse(txt); } catch (e) { errBody = { detail: txt }; }
                    const errorMsg = errBody.detail || errBody.error || flattenFormErrors(errBody.errors) || `HTTP ${res.status}`;
                    const err = new Error(errorMsg);
                    err.body = errBody;
                    err.status = res.status;
                    console.error('[API ERROR]', url, errBody);
                    throw err;
                });
            }
            if (res.status === 204) return null;
            return res.json();
        });
    }

    function flattenFormErrors(errors) {
        if (!errors || typeof errors !== 'object') return '';
        return Object.keys(errors).map(field => {
            const msgs = Array.isArray(errors[field]) ? errors[field] : [errors[field]];
            return `${field}: ${msgs.map(m => (m && m.message) || m).join(' ')}`;
        }).join(' | ');
    }

    // ===== DATOS DE REFERENCIA (server-rendered vía json_script) =====
    function readJson(id, fallback) {
        const el = document.getElementById(id);
        if (!el) return fallback;
        try { return JSON.parse(el.textContent); } catch (e) { return fallback; }
    }

    const PROPERTY_TYPES = readJson('property-types-data', []);   // [[code, label], ...]
    const OFFER_TYPES = readJson('offer-types-data', []);
    const FREQUENCIES = readJson('frequencies-data', []);
    const PROVINCES = readJson('provinces-data', []);             // [{id, name}, ...]
    const MUNICIPALITIES = readJson('municipalities-data', []);   // [{id, name, province_id}, ...]

    const provinceLookup = PROVINCES.map(p => ({ id: p.id, name: p.name }));
    const municipalityLookupAll = MUNICIPALITIES.map(m => ({ id: m.id, name: m.name, province_id: m.province_id }));
    const propertyTypeLookup = [{ code: '', label: gettext('Cualquiera') }, ...PROPERTY_TYPES.map(([code, label]) => ({ code, label }))];
    const offerTypeLookup = [{ code: '', label: gettext('Cualquiera') }, ...OFFER_TYPES.map(([code, label]) => ({ code, label }))];
    const frequencyLookup = FREQUENCIES.map(([code, label]) => ({ code, label }));

    const PROPERTY_TYPE_LABELS = Object.fromEntries(PROPERTY_TYPES);
    const OFFER_TYPE_LABELS = Object.fromEntries(OFFER_TYPES);

    // ===== CAMPOS EDITABLES (lo demás son calculados por el backend y se
    // limpian del payload antes de enviarlo, igual que en my_properties.js) =====
    const CALCULATED_FIELDS = [
        'id', '__KEY__', 'frequency_display', 'province_name', 'municipality_name',
        'property_type_display', 'offer_type_display', 'last_notified_at', 'created_at'
    ];

    function cleanPayload(values) {
        const clean = {};
        Object.keys(values || {}).forEach(key => {
            if (!CALCULATED_FIELDS.includes(key)) clean[key] = values[key];
        });
        return clean;
    }

    // ===== REFERENCIAS A EDITORES DEL POPUP (cascada provincia→municipio
    // y visibilidad de rangos de precio según oferta) =====
    let provinceEditorInstance = null;
    let municipalityEditorInstance = null;
    const priceEditorInstances = {};

    // Instancia del Form del popup + bandera de "ya renderizado al menos
    // una vez para esta apertura". Se usan desde form.onFieldDataChanged
    // (ver más abajo) para saber si un cambio en offer_type/province_id
    // es una acción real del usuario o la asignación inicial de datos al
    // abrir el popup en modo edición.
    let formInstance = null;
    let formReady = false;

    // isUserAction=false (valor por defecto): la cascada solo actualiza el
    // dataSource/placeholder del municipio, nunca borra su valor. Esto
    // cubre la vez que onFieldDataChanged se dispara con formReady=false
    // (asignación inicial de datos al abrir el popup en modo edición) --
    // si en ese caso se limpiara el municipio, se perdería un valor que
    // el usuario nunca tocó. Solo cuando el cambio de provincia llega
    // con formReady=true (el popup ya terminó su primer render y el
    // cambio es una interacción real del usuario) tiene sentido limpiar
    // un municipio que ya no encaja con la provincia recién elegida.
    function updateMunicipalityOptions(provinceId, isUserAction) {
        if (!municipalityEditorInstance) return;
        const filtered = provinceId
            ? municipalityLookupAll.filter(m => String(m.province_id) === String(provinceId))
            : municipalityLookupAll;
        municipalityEditorInstance.option('dataSource', filtered);
        if (!provinceId) {
            municipalityEditorInstance.option('placeholder', gettext('Cualquier municipio'));
        } else if (filtered.length === 0) {
            if (isUserAction) municipalityEditorInstance.option('value', null);
            municipalityEditorInstance.option('placeholder', gettext('No hay municipios para esta provincia'));
        } else {
            municipalityEditorInstance.option('placeholder', gettext('Cualquier municipio'));
        }
    }

    // Igual convención que my_properties.js: sale_price-like campos solo
    // tienen sentido para 'sale'/'sale_or_rent'; rent_price-like para
    // 'rent'/'sale_or_rent'. offer_type vacío ("Cualquiera") o 'swap'
    // deshabilita ambos rangos -- no hay un precio único al que aplicar
    // un filtro cuando la alerta no se restringe a un tipo de oferta.
    function isPriceFieldEnabled(dataField, offerType) {
        if (!offerType) return false;
        if (['min_sale_price', 'max_sale_price'].includes(dataField)) {
            return offerType === 'sale' || offerType === 'sale_or_rent';
        }
        if (['min_rent_price', 'max_rent_price'].includes(dataField)) {
            return offerType === 'rent' || offerType === 'sale_or_rent';
        }
        return true;
    }

    // Título de la card fusionada "Rango de precio" según el offer_type
    // actual -- puramente informativo (UI), no toca formData/values, así
    // que no interfiere en absoluto con qué se guarda al pulsar Guardar.
    function priceRangeCaption(offerType) {
        if (offerType === 'sale') return gettext('Rango de precio · Venta');
        if (offerType === 'rent') return gettext('Rango de precio · Alquiler (mensual)');
        if (offerType === 'sale_or_rent') return gettext('Rango de precio · Venta y alquiler');
        return gettext('Rango de precio');
    }

    // isUserAction=false (valor por defecto): solo actualiza el estado
    // visual disabled/enabled, NUNCA toca el valor introducido. Necesario
    // porque esta función se llama también desde form.onContentReady --
    // que se dispara de forma programática cada vez que se (re)renderiza
    // el contenido del form, incluida la revalidación interna que
    // DevExtreme hace al pulsar "Guardar" en un form con pestañas -- y en
    // esos disparos offerType puede llegar undefined de forma transitoria
    // aunque el usuario nunca haya tocado "Tipo de oferta". Si en ese
    // momento se limpiara el valor, se perdería el precio ya introducido
    // justo antes de construir el payload que se envía al backend (el bug
    // reportado: precio de venta y provincia desaparecidos tras guardar).
    // Solo cuando form.onFieldDataChanged confirma que el popup ya
    // terminó su render inicial (isUserAction=true, es decir
    // formReady === true) tiene sentido borrar un precio que ya no
    // aplica al nuevo tipo de oferta elegido.
    //
    // Nota sobre el guardado: cambiar el título de la card (más abajo,
    // formInstance.itemOption(..., 'caption', ...)) es solo estético y
    // se hace SIEMPRE, tenga o no isUserAction=true -- a diferencia de
    // limpiar un valor, mostrar el título correcto nunca puede perder
    // datos, así que no hace falta protegerlo detrás de isUserAction.
    function updatePriceFieldsAvailability(offerType, isUserAction) {
        Object.keys(priceEditorInstances).forEach(field => {
            const editor = priceEditorInstances[field];
            if (!editor) return;
            const enabled = isPriceFieldEnabled(field, offerType);
            editor.option('disabled', !enabled);
            if (isUserAction && !enabled && editor.option('value') !== null) {
                editor.option('value', null);
            }
        });
        if (formInstance) {
            formInstance.itemOption('priceRangeCard', 'caption', priceRangeCaption(offerType));
        }
    }

    // ===== RESUMEN LEGIBLE DE FILTROS (celda "Alerta") =====
    function buildSummary(data) {
        const parts = [];
        parts.push(data.property_type_display || gettext('Cualquier tipo'));
        parts.push(data.offer_type_display || gettext('Cualquier oferta'));
        const location = [data.municipality_name, data.province_name].filter(Boolean).join(', ');
        parts.push(location || gettext('Cualquier ubicación'));

        const priceBits = [];
        if (data.min_sale_price != null || data.max_sale_price != null) {
            priceBits.push(`${gettext('Venta')} ${data.min_sale_price != null ? formatCurrency(data.min_sale_price) : '…'}–${data.max_sale_price != null ? formatCurrency(data.max_sale_price) : '…'}`);
        }
        if (data.min_rent_price != null || data.max_rent_price != null) {
            priceBits.push(`${gettext('Alquiler')} ${data.min_rent_price != null ? formatCurrency(data.min_rent_price) : '…'}–${data.max_rent_price != null ? formatCurrency(data.max_rent_price) : '…'}`);
        }
        if (priceBits.length) parts.push(priceBits.join(' · '));

        const amenities = [];
        if (data.has_elevator) amenities.push(gettext('Ascensor'));
        if (data.has_air_conditioning) amenities.push(gettext('A/C'));
        if (amenities.length) parts.push(amenities.join(', '));

        return parts.join(' · ');
    }

    // ===== CUSTOM STORE =====
    const store = new DevExpress.data.CustomStore({
        key: 'id',
        load: function () {
            console.log('📥 LOAD - Cargando alertas');
            return apiRequest(URLS.data, 'GET');
        },
        insert: function (values) {
            console.log('➕ INSERT - Creando alerta', values);
            return apiRequest(URLS.data, 'POST', cleanPayload(values));
        },
        update: function (key, values) {
            console.log('✏️ UPDATE - Editando alerta', key, values);
            const url = buildUrl(URLS.detail, key);
            return apiRequest(url, 'PATCH', cleanPayload(values));
        },
        remove: function (key) {
            console.log('🗑️ REMOVE - Borrando alerta', key);
            const url = buildUrl(URLS.detail, key);
            return apiRequest(url, 'DELETE');
        }
    });

    // Getter reasignado por el editor de offer_type en cuanto se
    // inicializa (dentro del popup); el placeholder cubre el caso de que
    // se consulte antes de que el popup se haya abierto una vez.
    let offerTypeCurrentValue = function () { return null; };

    // ===== GRID PRINCIPAL =====
    const gridInstanceRef = $('#alertsGrid').dxDataGrid({
        dataSource: store,
        keyExpr: 'id',
        showBorders: true,
        rowAlternationEnabled: true,
        columnAutoWidth: false,
        columnResizingMode: 'widget',
        allowColumnResizing: true,
        wordWrapEnabled: false,
        height: 'auto',

        noDataText: gettext('Aún no tienes alertas guardadas. Crea una para recibir un aviso cuando aparezcan inmuebles que encajen con tus filtros.'),

        paging: { pageSize: 10 },
        pager: { showPageSizeSelector: true, allowedPageSizes: [10, 20, 50], showInfo: true },
        searchPanel: { visible: true, placeholder: gettext('Buscar...') },

        editing: {
            mode: 'popup',
            allowAdding: true,
            allowUpdating: true,
            allowDeleting: true,
            useIcons: true,
            texts: {
                confirmDeleteMessage: gettext('¿Borrar esta alerta? Dejarás de recibir avisos para estos filtros.'),
                confirmDeleteTitle: gettext('Borrar alerta'),
                addRow: gettext('Nueva alerta'),
                editRow: gettext('Editar'),
                saveRowChanges: gettext('Guardar'),
                cancelRowChanges: gettext('Cancelar')
            },
            popup: {
                title: gettext('Alerta de búsqueda'),
                showTitle: true,
                // Antes 800px, luego 920px: al fusionar las dos cards de
                // "Rango de precio" en una sola (ver priceRangeCard más
                // abajo) las otras 3 cards de la fila -- Tipo de
                // inmueble, Ubicación y Comodidades -- son las que fijan
                // el ancho de columna en el layout a 3 columnas, y ahí
                // viven los selects (sobre todo provincia/municipio, con
                // nombres largos) cuyo valor elegido se veía cortado por
                // falta de espacio. Más ancho de popup = más ancho de
                // columna = más ancho de cada select.
                width: function () { return Math.min(window.innerWidth * 0.97, 1000); },
                // FIX (reemplaza el enfoque anterior basado en height:'auto'
                // + deferRendering:false): con height 'auto' el popup mide
                // su alto contra el contenido de la pestaña activa, así que
                // el resultado depende de CUÁL pestaña esté abierta en ese
                // momento. Aquí se fija una altura EXPLÍCITA e idéntica para
                // las dos pestañas (proporción del viewport, con techo);
                // title y barra Guardar/Cancelar quedan fuera de ese
                // presupuesto (ver my_alerts.css, flex-shrink:0) y el
                // contenido intermedio (.dx-popup-content) hace scroll
                // interno si una pestaña no cabe. Resultado: los botones
                // ocupan siempre la misma posición, se cambie o no de
                // pestaña. Techo subido de 640 a 700: junto con las 3
                // columnas de arriba (5 cards en 2 filas en vez de 3),
                // esto es lo que permite que "Filtros de búsqueda" quepa
                // sin scroll con el tamaño de letra más grande.
                height: function () { return Math.min(window.innerHeight * 0.86, 700); },
                wrapperAttr: { class: 'alert-edit-popup' },
                onInitialized: function (e) {
                    e.component.option('toolbarItems[0].options.icon', 'save');
                    e.component.option('toolbarItems[0].options.type', 'success');
                    e.component.option('toolbarItems[0].options.stylingMode', 'contained');
                    e.component.option('toolbarItems[1].options.icon', 'close');
                    e.component.option('toolbarItems[1].options.type', 'danger');
                    e.component.option('toolbarItems[1].options.stylingMode', 'contained');
                }
            },
            form: {
                colCount: 1,
                onInitialized: function (e) {
                    formInstance = e.component;
                    // Nueva apertura de popup: hasta que el primer
                    // onContentReady confirme que el render inicial
                    // terminó, cualquier onFieldDataChanged que llegue
                    // es la carga de datos existentes, no un clic real
                    // del usuario.
                    formReady = false;
                },
                onContentReady: function () {
                    // Puede dispararse varias veces por sesión de popup
                    // (apertura inicial, cambio de pestaña, revalidación
                    // al pulsar Guardar en un form con pestañas). Por eso
                    // se llama SIN isUserAction=true: solo sincroniza el
                    // estado visual disabled/enabled de los precios según
                    // la oferta actual, nunca borra un valor ya
                    // introducido por el usuario (ver comentario en
                    // updatePriceFieldsAvailability).
                    const offerType = offerTypeCurrentValue();
                    updatePriceFieldsAvailability(offerType);
                    formReady = true;
                },
                // ÚNICO sitio donde reaccionamos a los cambios de
                // offer_type/province_id. A diferencia de
                // editorOptions.onValueChanged (que SUSTITUYE el
                // manejador interno de Form y rompe la sincronización
                // value -> formData, dejando el campo fuera de
                // e.data/values al guardar), onFieldDataChanged es un
                // evento del Form que se dispara DESPUÉS de que Form ya
                // actualizó formData por su cuenta. No compite con la
                // sincronización interna, así que no hace falta (ni es
                // seguro) llamar a formInstance.updateData() a mano aquí.
                onFieldDataChanged: function (e) {
                    if (e.dataField === 'offer_type') {
                        updatePriceFieldsAvailability(e.value, formReady);
                    } else if (e.dataField === 'province_id') {
                        updateMunicipalityOptions(e.value, formReady);
                    }
                },
                items: [
                    {
                        itemType: 'tabbed',
                        // NOTA: ya no depende de esto la altura del popup
                        // (ahora es fija, ver popup.height más arriba). Se
                        // mantiene deferRendering:false por una razón
                        // distinta: los editores de la pestaña "Filtros de
                        // búsqueda" (offer_type, province_id,
                        // municipality_id, precios) necesitan estar
                        // inicializados desde la apertura del popup para
                        // que la cascada provincia→municipio y la
                        // habilitación de los rangos de precio según
                        // offer_type (ver form.onContentReady) se
                        // sincronicen correctamente aunque el usuario abra
                        // el popup directamente sobre la pestaña "General".
                        tabPanelOptions: {
                            deferRendering: false,
                            animationEnabled: true,
                            swipeEnabled: false
                        },
                        tabs: [
                            {
                                title: gettext('General'),
                                items: [
                                    {
                                        itemType: 'group',
                                        cssClass: 'alert-form-card',
                                        caption: gettext('Datos generales'),
                                        items: [
                                            {
                                                dataField: 'name',
                                                label: { text: gettext('Nombre de la alerta') },
                                                editorOptions: { placeholder: gettext('Ej. Apartamentos en La Habana') }
                                            },
                                            {
                                                dataField: 'frequency',
                                                label: { text: gettext('Frecuencia de aviso') },
                                                editorType: 'dxSelectBox',
                                                editorOptions: {
                                                    dataSource: frequencyLookup,
                                                    valueExpr: 'code',
                                                    displayExpr: 'label',
                                                    searchEnabled: false
                                                }
                                            },
                                            {
                                                dataField: 'is_active',
                                                label: { text: gettext('Activa') },
                                                editorType: 'dxCheckBox'
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                title: gettext('Filtros de búsqueda'),
                                // Antes: colCount fijo a 2 -> las 5 cards
                                // (Tipo de inmueble / Ubicación / Venta /
                                // Alquiler / Comodidades) ocupaban 3 filas
                                // y la pestaña necesitaba scroll vertical
                                // dentro de la altura fija del popup.
                                // Ahora: las cards "Rango de precio ·
                                // Venta" y "Rango de precio · Alquiler" se
                                // fusionan en una sola ("priceRangeCard",
                                // más abajo) cuyo título y campos
                                // visibles cambian según "Tipo de
                                // oferta". Con eso quedan 4 cards en vez
                                // de 5: 3 caben en la primera fila (3
                                // columnas en desktop) y la de precio
                                // ocupa las 2/3 de la segunda fila --
                                // todo en 2 filas, sin scroll.
                                // colCountByScreen reduce a 2 o 1 columna
                                // en pantallas medianas o móviles en vez
                                // de aplastar 3 columnas estrechas.
                                colCountByScreen: { xs: 1, sm: 1, md: 2, lg: 3 },
                                items: [
                                    {
                                        itemType: 'group',
                                        cssClass: 'alert-form-card',
                                        caption: gettext('Tipo de inmueble'),
                                        colCount: 1,
                                        items: [
                                            {
                                                dataField: 'property_type',
                                                label: { text: gettext('Tipo de inmueble') },
                                                editorType: 'dxSelectBox',
                                                editorOptions: {
                                                    dataSource: propertyTypeLookup,
                                                    valueExpr: 'code',
                                                    displayExpr: 'label',
                                                    searchEnabled: false
                                                }
                                            },
                                            {
                                                dataField: 'offer_type',
                                                label: { text: gettext('Tipo de oferta') },
                                                editorType: 'dxSelectBox',
                                                editorOptions: {
                                                    dataSource: offerTypeLookup,
                                                    valueExpr: 'code',
                                                    displayExpr: 'label',
                                                    searchEnabled: false,
                                                    onInitialized: function (args) {
                                                        // guarda getter accesible desde onContentReady
                                                        offerTypeCurrentValue = function () { return args.component.option('value'); };
                                                    }
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        itemType: 'group',
                                        cssClass: 'alert-form-card',
                                        caption: gettext('Ubicación'),
                                        colCount: 1,
                                        items: [
                                            {
                                                dataField: 'province_id',
                                                label: { text: gettext('Provincia') },
                                                editorType: 'dxSelectBox',
                                                editorOptions: {
                                                    dataSource: provinceLookup,
                                                    valueExpr: 'id',
                                                    displayExpr: 'name',
                                                    searchEnabled: true,
                                                    placeholder: gettext('Cualquier provincia'),
                                                    showClearButton: true,
                                                    onInitialized: function (args) {
                                                        provinceEditorInstance = args.component;
                                                    }
                                                }
                                            },
                                            {
                                                dataField: 'municipality_id',
                                                label: { text: gettext('Municipio') },
                                                editorType: 'dxSelectBox',
                                                editorOptions: {
                                                    dataSource: municipalityLookupAll,
                                                    valueExpr: 'id',
                                                    displayExpr: 'name',
                                                    searchEnabled: true,
                                                    placeholder: gettext('Cualquier municipio'),
                                                    showClearButton: true,
                                                    onInitialized: function (args) {
                                                        municipalityEditorInstance = args.component;
                                                        updateMunicipalityOptions(provinceEditorInstance ? provinceEditorInstance.option('value') : null);
                                                    }
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        itemType: 'group',
                                        cssClass: 'alert-form-card',
                                        caption: gettext('Comodidades'),
                                        colCount: 2,
                                        items: [
                                            { dataField: 'has_elevator', label: { text: gettext('Ascensor') }, editorType: 'dxCheckBox' },
                                            { dataField: 'has_air_conditioning', label: { text: gettext('A/C') }, editorType: 'dxCheckBox' }
                                        ]
                                    },
                                    {
                                        itemType: 'group',
                                        cssClass: 'alert-form-card',
                                        // "name" es lo que permite localizar esta card más
                                        // tarde vía formInstance.itemOption('priceRangeCard', ...)
                                        // para cambiarle el título en caliente. El texto inicial
                                        // (gettext('Rango de precio')) se sustituye enseguida por
                                        // updatePriceFieldsAvailability() en cuanto el form conoce
                                        // el offer_type actual (onContentReady / onFieldDataChanged),
                                        // así que este valor solo se ve en el primerísimo instante.
                                        name: 'priceRangeCard',
                                        caption: gettext('Rango de precio'),
                                        colSpan: 2,
                                        colCount: 2,
                                        items: [
                                            {
                                                dataField: 'min_sale_price',
                                                // Etiquetas con sufijo fijo ("venta"/"alquiler") en
                                                // vez de solo "Mínimo"/"Máximo": antes se distinguían
                                                // solo por el título de su card separada; al fusionar
                                                // las dos cards en una (con offer_type='sale_or_rent'
                                                // pueden verse los 4 campos a la vez) hace falta que
                                                // cada campo se identifique por sí mismo.
                                                label: { text: gettext('Mínimo (venta)') },
                                                editorType: 'dxNumberBox',
                                                editorOptions: {
                                                    format: { type: 'currency', currency: 'EUR' },
                                                    min: 0,
                                                    onInitialized: function (args) { priceEditorInstances['min_sale_price'] = args.component; }
                                                }
                                            },
                                            {
                                                dataField: 'max_sale_price',
                                                label: { text: gettext('Máximo (venta)') },
                                                editorType: 'dxNumberBox',
                                                editorOptions: {
                                                    format: { type: 'currency', currency: 'EUR' },
                                                    min: 0,
                                                    onInitialized: function (args) { priceEditorInstances['max_sale_price'] = args.component; }
                                                }
                                            },
                                            {
                                                dataField: 'min_rent_price',
                                                label: { text: gettext('Mínimo (alquiler)') },
                                                editorType: 'dxNumberBox',
                                                editorOptions: {
                                                    format: { type: 'currency', currency: 'EUR' },
                                                    min: 0,
                                                    onInitialized: function (args) { priceEditorInstances['min_rent_price'] = args.component; }
                                                }
                                            },
                                            {
                                                dataField: 'max_rent_price',
                                                label: { text: gettext('Máximo (alquiler)') },
                                                editorType: 'dxNumberBox',
                                                editorOptions: {
                                                    format: { type: 'currency', currency: 'EUR' },
                                                    min: 0,
                                                    onInitialized: function (args) { priceEditorInstances['max_rent_price'] = args.component; }
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        },

        onInitNewRow: function (e) {
            // Valores por defecto de una alerta nueva: activa, frecuencia
            // diaria, sin ningún filtro todavía (equivale a "cualquier
            // inmueble nuevo").
            e.data.is_active = true;
            e.data.frequency = 'daily';
            e.data.has_elevator = false;
            e.data.has_air_conditioning = false;
        },

        columns: [
            {
                dataField: 'name',
                caption: gettext('Alerta'),
                minWidth: 260,
                fixed: true,
                fixedPosition: 'left',
                cellTemplate: function (container, options) {
                    $(container).append(
                        `<div class="cell-wrap">
                            <div class="cell-icon"><i class="fas fa-bell"></i></div>
                            <div class="cell-stack">
                                <span class="cell-primary">${escapeHtml(options.value || gettext('Sin nombre'))}</span>
                                <span class="cell-secondary">${escapeHtml(buildSummary(options.data))}</span>
                            </div>
                        </div>`
                    );
                }
            },
            {
                dataField: 'frequency',
                caption: gettext('Frecuencia'),
                width: 130,
                lookup: { dataSource: frequencyLookup, valueExpr: 'code', displayExpr: 'label' },
                cellTemplate: function (container, options) {
                    $(`<span class="freq-badge"></span>`).text(options.data.frequency_display).appendTo(container);
                }
            },
            {
                dataField: 'is_active',
                caption: gettext('Estado'),
                width: 100,
                dataType: 'boolean',
                cellTemplate: function (container, options) {
                    const cls = options.value ? 'status-active' : 'status-inactive';
                    const text = options.value ? gettext('Activa') : gettext('Inactiva');
                    $(`<span class="status-badge"></span>`).addClass(cls).text(text).appendTo(container);
                }
            },
            {
                dataField: 'last_notified_at',
                caption: gettext('Última notif.'),
                width: 150,
                allowEditing: false,
                calculateCellValue: function (data) { return data.last_notified_at || gettext('Nunca'); }
            },
            {
                dataField: 'created_at',
                caption: gettext('Creada'),
                width: 110,
                allowEditing: false
            },
            // Columnas ocultas: mismo motivo que en my_properties.html
            // (Bug 1) -- cualquier campo presente en editing.form.items
            // (el popup) que NO tenga columna aquí, ni siquiera oculta,
            // es descartado por DevExtreme de e.data al insertar/
            // actualizar, aunque el usuario lo rellene en pantalla. Estas
            // 11 columnas cubren TODOS los campos de la pestaña "Filtros
            // de búsqueda" que no tienen ya una columna visible arriba.
            { dataField: 'property_type', visible: false },
            { dataField: 'offer_type', visible: false },
            { dataField: 'province_id', visible: false },
            { dataField: 'municipality_id', visible: false },
            { dataField: 'min_sale_price', visible: false },
            { dataField: 'max_sale_price', visible: false },
            { dataField: 'min_rent_price', visible: false },
            { dataField: 'max_rent_price', visible: false },
            { dataField: 'has_elevator', visible: false },
            { dataField: 'has_air_conditioning', visible: false },
            {
                type: 'buttons',
                caption: gettext('Acciones'),
                width: 90,
                fixed: true,
                fixedPosition: 'right',
                allowSorting: false,
                allowFiltering: false,
                allowResizing: false,
                allowReordering: false,
                allowHiding: false,
                buttons: [
                    {
                        name: 'edit',
                        hint: gettext('Editar'),
                        // FIX: usaba 'fas fa-pen' (Font Awesome), un glifo
                        // distinto al que se ve en la grilla de
                        // my_properties. Ahí el botón de editar usa el
                        // icono propio de DevExtreme ('edit') precisamente
                        // porque es el que coincide con el resto de iconos
                        // nativos de la UI (toolbar, refresh, etc.) -- ver
                        // comentario en my_properties.js. Se alinea aquí
                        // con el mismo criterio para que ambas grillas
                        // usen el mismo estilo de icono.
                        icon: 'edit',
                        cssClass: 'rbtn rbtn-edit'
                    },
                    {
                        name: 'delete',
                        hint: gettext('Borrar'),
                        // Mismo criterio que 'edit': icono built-in de
                        // DevExtreme en vez de Font Awesome, para que
                        // ambos botones de esta columna compartan el
                        // mismo estilo de trazo que el resto de iconos DX
                        // de la página.
                        icon: 'trash',
                        cssClass: 'rbtn rbtn-delete'
                    }
                ]
            }
        ],

        toolbar: {
            items: [
                { location: 'before', template: () => `<div style="font-weight:600;padding:8px 4px">${gettext('Mis alertas')}</div>` },
                {
                    location: 'after',
                    widget: 'dxButton',
                    options: {
                        icon: 'plus',
                        text: gettext('Nueva alerta'),
                        stylingMode: 'contained',
                        type: 'default',
                        onClick: function () { gridInstanceRef.addRow(); }
                    }
                },
                {
                    location: 'after',
                    widget: 'dxButton',
                    options: { icon: 'refresh', hint: gettext('Actualizar'), stylingMode: 'text', onClick: doRefresh }
                },
                'searchPanel'
            ]
        },

        onRowInserted: function () {
            DevExpress.ui.notify(gettext('Alerta creada'), 'success', 1800);
        },
        onRowUpdated: function () {
            DevExpress.ui.notify(gettext('Alerta actualizada'), 'success', 1800);
        },
        onRowRemoved: function () {
            DevExpress.ui.notify(gettext('Alerta eliminada'), 'success', 1800);
        }
    }).dxDataGrid('instance');

    function doRefresh() {
        gridInstanceRef.refresh();
        DevExpress.ui.notify(gettext('Datos actualizados'), 'success', 1800);
    }

    console.log('🚀 my_alerts.js inicializado correctamente');
})();
