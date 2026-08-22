(function () {
    'use strict';

    const gridEl = document.getElementById('myFavoritesGrid');
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

    // FIX (mismo motivo que en my_properties.js): .replace() con string
    // literal sustituye solo la PRIMERA ocurrencia de "/0/", así que un
    // solo argumento encaja de forma posicional sin arrastrar los demás
    // placeholders si en el futuro la URL tuviera más de uno.
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
    // Contrato esperado de URLS.data (GET, lista de inmuebles favoritos
    // del usuario autenticado), un objeto por fila:
    // {
    //   "id": <property_id>,                 // clave de la grilla
    //   "title": "...",
    //   "property_type": "apartment",        // código, para icono/color
    //   "property_type_display": "...",      // texto ya traducido
    //   "offer_type_display": "...",
    //   "province_name": "...", "municipality_name": "...",
    //   "sale_price": 120000, "rent_price": null,
    //   "surface": 85.0, "rooms": 3, "bathrooms": 2,
    //   "status": "available", "status_display": "Disponible",
    //   "detail_url": "/inmuebles/123/",
    //   "cover_image": "/media/.../foto.jpg" | null,
    //   "favorited_at": "2026-08-10T12:00:00Z"
    // }
    // URLS.remove es la MISMA url de toggle_favorite que usa detail.html
    // (con placeholder "/0/" para el id del inmueble): togglear un
    // favorito ya existente lo elimina, así que no hace falta un
    // endpoint nuevo solo para "quitar de favoritos".
    const store = new DevExpress.data.CustomStore({
        key: 'id',
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
    const gridInstanceRef = $('#myFavoritesGrid').dxDataGrid({
        dataSource: store,
        keyExpr: 'id',
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

        // Grilla de solo lectura respecto al inmueble: no se puede crear
        // ni editar desde aquí (eso vive en "Mis inmuebles"); la única
        // operación posible es "eliminar", que en este contexto significa
        // "quitar de favoritos" -- NUNCA borra el inmueble en sí.
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
                dataField: 'title',
                caption: gettext('Título'),
                minWidth: 220,
                fixed: true,
                fixedPosition: 'left',
                allowEditing: false,
                cellTemplate: function (container, options) {
                    const location = [options.data.municipality_name, options.data.province_name].filter(Boolean).join(', ');
                    const thumb = options.data.cover_image
                        ? `<img class="cover-thumb" src="${escapeHtml(options.data.cover_image)}" alt="">`
                        : `<div class="cover-thumb-fallback"><i class="fas fa-image"></i></div>`;
                    $(container).append(
                        `<div class="cell-wrap">
                            ${thumb}
                            <div class="cell-stack">
                                <span class="cell-primary">${escapeHtml(options.value || gettext('Sin título'))}</span>
                                <span class="cell-secondary">${escapeHtml(location) || '&nbsp;'}</span>
                            </div>
                        </div>`
                    );
                }
            },
            {
                dataField: 'property_type',
                caption: gettext('Tipo'),
                width: 150,
                allowEditing: false,
                cellTemplate: function (container, options) {
                    const info = getTipoInfo(options.value, options.data.property_type_display);
                    $(`<span class="tipo-badge"></span>`)
                        .css({ background: info.badgeBg, color: info.badgeText })
                        .html(`<i class="fas ${info.icon}"></i> ${escapeHtml(info.text)}`)
                        .appendTo(container);
                }
            },
            { dataField: 'offer_type_display', caption: gettext('Oferta'), width: 130, allowEditing: false },
            { dataField: 'province_name', caption: gettext('Provincia'), width: 140, allowEditing: false },
            { dataField: 'municipality_name', caption: gettext('Municipio'), width: 150, allowEditing: false },
            {
                dataField: 'sale_price', caption: gettext('Venta'), dataType: 'number',
                format: { type: 'currency', currency: 'EUR' }, alignment: 'right', width: 110, allowEditing: false
            },
            {
                dataField: 'rent_price', caption: gettext('Alquiler'), dataType: 'number',
                format: { type: 'currency', currency: 'EUR' }, alignment: 'right', width: 110, allowEditing: false
            },
            { dataField: 'surface', caption: gettext('m²'), dataType: 'number', width: 80, alignment: 'right', format: { type: 'fixedPoint', precision: 1 }, allowEditing: false },
            { dataField: 'rooms', caption: gettext('Hab.'), dataType: 'number', width: 70, alignment: 'center', allowEditing: false },
            { dataField: 'bathrooms', caption: gettext('Baños'), dataType: 'number', width: 70, alignment: 'center', allowEditing: false },
            {
                dataField: 'status_display',
                caption: gettext('Estado'),
                width: 110,
                allowEditing: false,
                cellTemplate: function (container, options) {
                    const cls = { 'available': 'status-available', 'reserved': 'status-reserved', 'sold': 'status-sold' }[options.data.status] || '';
                    $(`<span class="status-badge"></span>`).addClass(cls).text(options.value).appendTo(container);
                }
            },
            {
                dataField: 'favorited_at',
                caption: gettext('Guardado el'),
                dataType: 'date',
                format: 'dd/MM/yyyy',
                width: 110,
                allowEditing: false,
                sortOrder: 'desc'
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
                { column: 'title', summaryType: 'count', displayFormat: `${gettext('Total')}: {0}` }
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
                    if (opt.gridCell.column && ['sale_price', 'rent_price'].includes(opt.gridCell.column.dataField)) {
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
            <th>${gettext('Título')}</th><th>${gettext('Tipo')}</th><th>${gettext('Oferta')}</th>
            <th>${gettext('Provincia')}</th><th>${gettext('Municipio')}</th><th>${gettext('Venta')}</th>
            <th>${gettext('Alquiler')}</th><th>m²</th><th>${gettext('Estado')}</th>
        </tr></thead><tbody>`;

        items.forEach(d => {
            html += `<tr>
                <td>${escapeHtml(d.title || '–')}</td>
                <td>${escapeHtml(d.property_type_display || '–')}</td>
                <td>${escapeHtml(d.offer_type_display || '–')}</td>
                <td>${escapeHtml(d.province_name || '–')}</td>
                <td>${escapeHtml(d.municipality_name || '–')}</td>
                <td style="text-align:right">${d.sale_price != null ? formatCurrency(d.sale_price) : '–'}</td>
                <td style="text-align:right">${d.rent_price != null ? formatCurrency(d.rent_price) : '–'}</td>
                <td style="text-align:right">${d.surface != null ? d.surface.toFixed(1) : '–'}</td>
                <td>${escapeHtml(d.status_display || '–')}</td>
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
