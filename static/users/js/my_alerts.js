(function () {
    'use strict';

    const gridEl = document.getElementById('alertsGrid');
    if (!gridEl) return;
    if (typeof DevExpress === 'undefined') {
        console.error('DevExpress no está disponible.');
        return;
    }

    // Idioma activo del sitio
    DevExpress.localization.locale(document.documentElement.lang || 'es');

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

    function readJson(id, fallback) {
        const el = document.getElementById(id);
        if (!el) return fallback;
        try { return JSON.parse(el.textContent); } catch (e) { return fallback; }
    }

    const PROPERTY_TYPES = readJson('property-types-data', []);
    const OFFER_TYPES = readJson('offer-types-data', []);
    const FREQUENCIES = readJson('frequencies-data', []);
    const PROVINCES = readJson('provinces-data', []);
    const MUNICIPALITIES = readJson('municipalities-data', []);

    const provinceLookup = PROVINCES.map(p => ({ id: p.id, name: p.name }));
    const municipalityLookupAll = MUNICIPALITIES.map(m => ({ id: m.id, name: m.name, province_id: m.province_id }));
    const propertyTypeLookup = [{ code: '', label: gettext('Cualquiera') }, ...PROPERTY_TYPES.map(([code, label]) => ({ code, label }))];
    const offerTypeLookup = [{ code: '', label: gettext('Cualquiera') }, ...OFFER_TYPES.map(([code, label]) => ({ code, label }))];
    const frequencyLookup = FREQUENCIES.map(([code, label]) => ({ code, label }));

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

    let provinceEditorInstance = null;
    let municipalityEditorInstance = null;
    const priceEditorInstances = {};
    let gridInstanceRef = null;

    function updateMunicipalityOptions(provinceId) {
        if (!municipalityEditorInstance) return;
        const filtered = provinceId
            ? municipalityLookupAll.filter(m => String(m.province_id) === String(provinceId))
            : municipalityLookupAll;
        municipalityEditorInstance.option('dataSource', filtered);
        if (!provinceId) {
            municipalityEditorInstance.option('placeholder', gettext('Cualquier municipio'));
        } else if (filtered.length === 0) {
            municipalityEditorInstance.option('value', null);
            municipalityEditorInstance.option('placeholder', gettext('No hay municipios para esta provincia'));
        } else {
            municipalityEditorInstance.option('placeholder', gettext('Cualquier municipio'));
        }
    }

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

    function updatePriceFieldsAvailability(offerType) {
        Object.keys(priceEditorInstances).forEach(function (field) {
            const editor = priceEditorInstances[field];
            if (!editor) return;
            const enabled = isPriceFieldEnabled(field, offerType);
            editor.option('disabled', !enabled);
            if (!enabled && editor.option('value') !== null) {
                editor.option('value', null);
            }
        });
    }

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

    gridInstanceRef = $('#alertsGrid').dxDataGrid({
        dataSource: store,
        keyExpr: 'id',
        showBorders: true,
        rowAlternationEnabled: true,
        columnAutoWidth: false,
        columnResizingMode: 'widget',
        allowColumnResizing: true,
        wordWrapEnabled: false,

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
                width: function () {
                    return Math.min(window.innerWidth * 0.94, 1000);
                },
                height: 'auto',
                maxHeight: function () {
                    return window.innerHeight * 0.92;
                },
                wrapperAttr: { class: 'alert-edit-popup' },
                hideOnOutsideClick: false,
                animation: {
                    show: { type: 'fade', duration: 200 },
                    hide: { type: 'fade', duration: 150 }
                },
                onShown: function(e) {
                    const $content = $(e.component.content());
                    $content.css('overflow', 'visible');
                    
                    const $bottom = $content.find('.dx-popup-bottom');
                    if ($bottom.length) {
                        $bottom.css('overflow', 'visible');
                        $bottom.find('.dx-toolbar').css('overflow', 'visible');
                        $bottom.find('.dx-toolbar-items-container').css('overflow', 'visible');
                    }
                },
                onInitialized: function (e) {
                    e.component.option('toolbarItems[0].options.icon', 'save');
                    e.component.option('toolbarItems[0].options.type', 'success');
                    e.component.option('toolbarItems[0].options.stylingMode', 'contained');
                    e.component.option('toolbarItems[1].options.icon', 'close');
                    e.component.option('toolbarItems[1].options.type', 'danger');
                    e.component.option('toolbarItems[1].options.stylingMode', 'contained');
                },
                onHiding: function() {
                    try {
                        Object.keys(priceEditorInstances).forEach(function(key) {
                            priceEditorInstances[key] = null;
                        });
                        provinceEditorInstance = null;
                        municipalityEditorInstance = null;
                    } catch(e) {}
                }
            },
            form: {
                labelLocation: 'top',
                colCount: 1,
                items: [
                    {
                        itemType: 'tabbed',
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
                                                editorOptions: { placeholder: gettext('Ej. Apartamentos en La Habana') },
                                                validationRules: [
                                                    { type: 'required', message: gettext('El nombre es obligatorio.') }
                                                ]
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
                                                    searchEnabled: false
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
                                        colCount: 1,
                                        items: [
                                            { dataField: 'has_elevator', label: { text: gettext('Ascensor') }, editorType: 'dxCheckBox' },
                                            { dataField: 'has_air_conditioning', label: { text: gettext('A/C') }, editorType: 'dxCheckBox' }
                                        ]
                                    },
                                    {
                                        itemType: 'group',
                                        cssClass: 'alert-form-card',
                                        caption: gettext('Rango de precio'),
                                        colSpan: 2,
                                        colCount: 2,
                                        items: [
                                            {
                                                dataField: 'min_sale_price',
                                                label: { text: gettext('Mínimo (venta)') },
                                                editorType: 'dxNumberBox',
                                                editorOptions: {
                                                    format: { type: 'currency', currency: 'EUR' },
                                                    min: 0,
                                                    placeholder: gettext('€'),
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
                                                    placeholder: gettext('€'),
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
                                                    placeholder: gettext('€'),
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
                                                    placeholder: gettext('€'),
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
            e.data.is_active = true;
            e.data.frequency = 'daily';
            e.data.has_elevator = false;
            e.data.has_air_conditioning = false;
        },

        onEditorPreparing: function (e) {
            if (e.parentType !== 'dataRow') return;

            if (e.dataField === 'province_id') {
                const originalOnValueChanged = e.editorOptions.onValueChanged;
                e.editorOptions.onValueChanged = function (args) {
                    if (originalOnValueChanged) originalOnValueChanged.call(this, args);
                    updateMunicipalityOptions(args.value);
                    if (municipalityEditorInstance) {
                        const currentMunicipality = municipalityEditorInstance.option('value');
                        if (currentMunicipality) {
                            const stillValid = municipalityLookupAll.some(
                                m => m.id === currentMunicipality && m.province_id === args.value
                            );
                            if (!stillValid) municipalityEditorInstance.option('value', null);
                        }
                    }
                };
            }

            if (e.dataField === 'offer_type') {
                const originalOnValueChanged = e.editorOptions.onValueChanged;
                e.editorOptions.onValueChanged = function (args) {
                    if (originalOnValueChanged) originalOnValueChanged.call(this, args);
                    updatePriceFieldsAvailability(args.value);
                };
            }

            if (['min_sale_price', 'max_sale_price', 'min_rent_price', 'max_rent_price'].includes(e.dataField)) {
                const originalOnInitialized = e.editorOptions.onInitialized;
                e.editorOptions.onInitialized = function (args) {
                    if (originalOnInitialized) originalOnInitialized.call(this, args);
                    priceEditorInstances[e.dataField] = args.component;
                    const currentOfferType = e.row && e.row.data ? e.row.data.offer_type : null;
                    args.component.option('disabled', !isPriceFieldEnabled(e.dataField, currentOfferType));
                };
            }
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
                        icon: 'edit',
                        cssClass: 'rbtn rbtn-edit'
                    },
                    {
                        name: 'delete',
                        hint: gettext('Borrar'),
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