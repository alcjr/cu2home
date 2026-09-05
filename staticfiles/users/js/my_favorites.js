(function () {
    'use strict';

    const gridEl = document.getElementById('favoritesGrid');
    if (!gridEl) return;
    if (typeof DevExpress === 'undefined') {
        console.error('DevExpress no está disponible.');
        return;
    }

    // Idioma activo del sitio (base.html ya pone <html lang="{{ LANGUAGE_CODE }}">),
    // en vez de forzar siempre español.
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

    // ===== INFO VISUAL POR TIPO DE INMUEBLE (igual que en my_properties) =====
    const PROPERTY_TYPE_INFO = {
        apartment:  { icon: 'fa-door-open',       badgeBg: '#eff6ff', badgeText: '#1e40af' },
        house:      { icon: 'fa-house',           badgeBg: '#f0fdf4', badgeText: '#166534' },
        villa:      { icon: 'fa-umbrella-beach',  badgeBg: '#fdf2ee', badgeText: '#9a3412' },
        commercial: { icon: 'fa-store',           badgeBg: '#fffbeb', badgeText: '#b45309' },
        land:       { icon: 'fa-mountain-sun',    badgeBg: '#f5f3ff', badgeText: '#5b21b6' },
        other:      { icon: 'fa-circle-question', badgeBg: '#f3f4f6', badgeText: '#374151' }
    };

    function getTipoInfo(propertyType, displayText) {
        const info = PROPERTY_TYPE_INFO[propertyType] || PROPERTY_TYPE_INFO.other;
        return { text: displayText || propertyType, icon: info.icon, badgeBg: info.badgeBg, badgeText: info.badgeText };
    }

    // favorites_data() solo envía 'estado' ya traducido (get_status_display()),
    // sin un código crudo equivalente al 'tipo_raw' que sí acompaña a 'tipo'.
    // Mapeo best-effort por texto para colorear el badge; si el texto no
    // coincide (locale distinto, texto cambiado en el modelo, etc.) se
    // muestra sin color en vez de romper. Si se puede, lo ideal sería que
    // favorites_data añadiera un 'estado_raw' como ya hace con 'tipo_raw'.
    const STATUS_BADGE_CLASS = {
        'Disponible': 'status-available',
        'Reservado': 'status-reserved',
        'Vendido': 'status-sold'
    };

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

    // Mismo motivo que en my_properties.js: .replace() con string literal
    // sustituye solo la PRIMERA ocurrencia de "/0/", encajando de forma
    // posicional con el placeholder de la URL de toggle_favorite.
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
                    const errorMsg = errBody.detail || errBody.error || `HTTP ${res.status}`;
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

    // ===== CUSTOM STORE (solo lectura + eliminar) =====
    // key: 'property_id' -- no 'favorite_id'. La vista toggle_favorite
    // (users:toggle_favorite) recibe property_id en la URL, así que usar
    // property_id como clave de la grilla permite construir la URL de
    // borrado directamente a partir de la key, sin tener que resolver
    // favorite_id -> property_id por separado. Es seguro como clave única
    // porque el modelo Favorite tiene UniqueConstraint(user, property):
    // un usuario nunca puede tener dos filas con el mismo property_id.
    //
    // "remove" reutiliza toggle_favorite (POST): como es un TOGGLE, quitar
    // un favorito ya existente lo borra -- no existe (ni hace falta) un
    // endpoint de borrado dedicado. Ojo: por ser un toggle, dos DELETE
    // seguidos sobre la misma fila (doble clic muy rápido antes de que la
    // grilla se refresque) volverían a AÑADIRLO en vez de fallar; con el
    // diálogo de confirmación de editing.texts esto es muy improbable.
    const store = new DevExpress.data.CustomStore({
        key: 'property_id',
        load: function () {
            console.log('📥 LOAD - Cargando favoritos');
            return apiRequest(URLS.data, 'GET');
        },
        remove: function (key) {
            console.log('🗑️ REMOVE - Quitando de favoritos', key);
            const url = buildUrl(URLS.remove, key);
            return apiRequest(url, 'POST');
        }
    });

    // ===== GRID PRINCIPAL =====
    const gridInstanceRef = $('#favoritesGrid').dxDataGrid({
        dataSource: store,
        keyExpr: 'property_id',
        showBorders: true,
        rowAlternationEnabled: true,
        columnAutoWidth: false,
        columnResizingMode: 'widget',
        allowColumnResizing: true,
        allowColumnReordering: true,
        wordWrapEnabled: false,
        height: 'auto',

        noDataText: gettext('Aún no has guardado ningún inmueble en favoritos. Pulsa el corazón en la ficha de un inmueble para guardarlo aquí.'),

        paging: { pageSize: 10 },
        pager: { showPageSizeSelector: true, allowedPageSizes: [10, 20, 50], showInfo: true },
        searchPanel: { visible: true, placeholder: gettext('Buscar...') },

        // Solo lectura respecto al inmueble: no se puede crear ni editar
        // desde aquí. La única operación es "eliminar", que aquí significa
        // "quitar de favoritos" -- nunca borra el inmueble en sí.
        editing: {
            mode: 'row',
            allowAdding: false,
            allowUpdating: false,
            allowDeleting: true,
            useIcons: true,
            texts: {
                confirmDeleteMessage: gettext('¿Quitar este inmueble de tus favoritos?'),
                confirmDeleteTitle: gettext('Quitar de favoritos')
            }
        },

        columns: [
            {
                dataField: 'codigo',
                caption: gettext('Inmueble'),
                minWidth: 200,
                fixed: true,
                fixedPosition: 'left',
                allowEditing: false,
                cellTemplate: function (container, options) {
                    $(container).append(
                        `<div class="cell-wrap">
                            <div class="cell-icon"><i class="fas fa-home"></i></div>
                            <div class="cell-stack">
                                <span class="cell-primary">${escapeHtml(options.value || gettext('Sin referencia'))}</span>
                                <span class="cell-secondary">${escapeHtml(options.data.ubicacion) || '&nbsp;'}</span>
                            </div>
                        </div>`
                    );
                }
            },
            {
                dataField: 'tipo_raw',
                caption: gettext('Tipo'),
                width: 150,
                allowEditing: false,
                cellTemplate: function (container, options) {
                    const info = getTipoInfo(options.value, options.data.tipo);
                    $(`<span class="tipo-badge"></span>`)
                        .css({ background: info.badgeBg, color: info.badgeText })
                        .html(`<i class="fas ${info.icon}"></i> ${escapeHtml(info.text)}`)
                        .appendTo(container);
                }
            },
            { dataField: 'oferta', caption: gettext('Oferta'), width: 130, allowEditing: false },
            { dataField: 'ubicacion', caption: gettext('Ubicación'), width: 160, allowEditing: false },
            {
                dataField: 'precio', caption: gettext('Precio'), dataType: 'number',
                format: { type: 'currency', currency: 'EUR' }, alignment: 'right', width: 120, allowEditing: false
            },
            { dataField: 'superficie', caption: gettext('m²'), dataType: 'number', width: 80, alignment: 'right', format: { type: 'fixedPoint', precision: 1 }, allowEditing: false },
            {
                dataField: 'estado',
                caption: gettext('Estado'),
                width: 120,
                allowEditing: false,
                cellTemplate: function (container, options) {
                    const cls = STATUS_BADGE_CLASS[options.value] || '';
                    $(`<span class="status-badge"></span>`).addClass(cls).text(options.value || '–').appendTo(container);
                }
            },
            {
                dataField: 'anadido',
                caption: gettext('Guardado el'),
                width: 110,
                allowEditing: false,
                allowSorting: false // ya viene pre-ordenado por el backend (-created_at) y es un string 'dd/mm/yyyy', no un valor de fecha ordenable
            },
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
                        hint: gettext('Ver ficha pública'),
                        icon: 'fas fa-eye',
                        cssClass: 'rbtn rbtn-view',
                        visible: function (e) { return !!e.row.data.detail_url; },
                        onClick: function (e) {
                            if (e.row.data.detail_url) {
                                window.open(e.row.data.detail_url, '_blank');
                            }
                        }
                    },
                    {
                        name: 'delete',
                        hint: gettext('Quitar de favoritos'),
                        icon: 'fas fa-heart-crack',
                        cssClass: 'rbtn rbtn-delete'
                    }
                ]
            }
        ],

        summary: {
            totalItems: [
                { column: 'codigo', summaryType: 'count', displayFormat: `${gettext('Total')}: {0}` }
            ]
        },

        toolbar: {
            items: [
                { location: 'before', template: () => `<div style="font-weight:600;padding:8px 4px">${gettext('Mis favoritos')}</div>` },
                'groupPanel',
                {
                    location: 'after',
                    widget: 'dxButton',
                    options: { icon: 'refresh', hint: gettext('Actualizar'), stylingMode: 'text', onClick: doRefresh }
                },
                {
                    location: 'after',
                    widget: 'dxButton',
                    options: { icon: 'exportxlsx', hint: gettext('Exportar a Excel'), stylingMode: 'text', onClick: exportarExcel }
                },
                {
                    location: 'after',
                    widget: 'dxButton',
                    options: { icon: 'print', hint: gettext('Imprimir listado'), stylingMode: 'text', onClick: imprimirListado }
                },
                'searchPanel'
            ]
        },

        onRowRemoved: function (e) {
            console.log('💔 FAVORITO ELIMINADO', e.key);
            DevExpress.ui.notify(gettext('Inmueble quitado de favoritos'), 'success', 1800);
        }
    }).dxDataGrid('instance');

    function doRefresh() {
        gridInstanceRef.refresh();
        DevExpress.ui.notify(gettext('Datos actualizados'), 'success', 1800);
    }

    function exportarExcel() {
        DevExpress.ui.notify(gettext('Generando archivo Excel…'), 'info', 2000);
        try {
            const wb = new ExcelJS.Workbook();
            const ws = wb.addWorksheet(gettext('Mis favoritos'));
            DevExpress.excelExporter.exportDataGrid({
                component: gridInstanceRef,
                worksheet: ws,
                autoFilterEnabled: true,
                customizeCell: function (opt) {
                    if (opt.gridCell.rowType === 'header') {
                        opt.excelCell.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 12 };
                        opt.excelCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFC0522D' } };
                    }
                    if (opt.gridCell.column && opt.gridCell.column.dataField === 'precio') {
                        if (opt.excelCell.value && typeof opt.excelCell.value === 'number') {
                            opt.excelCell.numFmt = '#,##0.00 €';
                        }
                    }
                }
            }).then(() => {
                wb.xlsx.writeBuffer().then((buf) => {
                    const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                    saveAs(blob, `mis_favoritos_${new Date().toISOString().slice(0, 10)}.xlsx`);
                    DevExpress.ui.notify(gettext('Excel exportado correctamente'), 'success', 2000);
                });
            });
        } catch (err) {
            DevExpress.ui.notify(`${gettext('Error al exportar')}: ${err.message || gettext('desconocido')}`, 'error', 4000);
        }
    }

    function imprimirListado() {
        const items = gridInstanceRef.getDataSource().items();
        if (!items || items.length === 0) {
            DevExpress.ui.notify(gettext('No hay favoritos para imprimir'), 'warning', 3000);
            return;
        }
        const fecha = new Date().toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' });
        const hora = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });

        let html = `<!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>${gettext('Mis favoritos')}</title>
        <style>
            *{box-sizing:border-box;margin:0;padding:0}
            body{font-family:"Segoe UI",Arial,sans-serif;font-size:11px;color:#1f2937;padding:20px;background:#fff}
            .header{text-align:center;margin-bottom:30px;padding-bottom:15px;border-bottom:2px solid #c0522d}
            h1{font-size:24px;color:#2c3e50;margin-bottom:5px}
            .subtitle{font-size:12px;color:#64748b}
            table{width:100%;border-collapse:collapse;margin-top:15px}
            th{background:#f1f5f9;text-align:left;padding:10px;font-size:11px;font-weight:700;color:#334155;border:1px solid #e2e8f0}
            td{padding:8px 10px;border:1px solid #e2e8f0;vertical-align:top}
            .footer{margin-top:30px;font-size:10px;color:#94a3b8;text-align:center;border-top:1px solid #e2e8f0;padding-top:15px}
            @media print{body{padding:0}th,td{border-color:#ddd}}
        </style></head><body>
        <div class="header"><h1>${gettext('Mis favoritos')}</h1>
        <div class="subtitle">${gettext('Generado el')} ${fecha} ${gettext('a las')} ${hora}</div>
        <div class="subtitle">${gettext('Total')}: ${items.length} ${gettext('inmuebles')}</div></div>
        <table><thead><tr>
            <th>${gettext('Inmueble')}</th><th>${gettext('Tipo')}</th><th>${gettext('Oferta')}</th>
            <th>${gettext('Ubicación')}</th><th>${gettext('Precio')}</th><th>m²</th>
            <th>${gettext('Estado')}</th><th>${gettext('Guardado el')}</th>
        </tr></thead><tbody>`;

        items.forEach(d => {
            html += `<tr>
                <td>${escapeHtml(d.codigo || '–')}</td>
                <td>${escapeHtml(d.tipo || '–')}</td>
                <td>${escapeHtml(d.oferta || '–')}</td>
                <td>${escapeHtml(d.ubicacion || '–')}</td>
                <td style="text-align:right">${d.precio != null ? formatCurrency(d.precio) : '–'}</td>
                <td style="text-align:right">${d.superficie != null ? Number(d.superficie).toFixed(1) : '–'}</td>
                <td>${escapeHtml(d.estado || '–')}</td>
                <td>${escapeHtml(d.anadido || '–')}</td>
            </tr>`;
        });

        html += `</tbody></table><div class="footer">cu2home.com · ${gettext('Mis favoritos')}</div></body></html>`;
        const win = window.open('', '_blank', 'width=1024,height=800');
        if (!win) {
            DevExpress.ui.notify(gettext('Active las ventanas emergentes para imprimir'), 'warning', 4000);
            return;
        }
        win.document.write(html);
        win.document.close();
        win.focus();
        setTimeout(() => { win.print(); }, 500);
    }

    function gettext(message) {
        if (typeof window.gettext === 'function') return window.gettext(message);
        return message;
    }

    console.log('🚀 my_favorites.js inicializado correctamente');
})();
