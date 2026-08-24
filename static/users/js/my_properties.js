    (function () {
    'use strict';

    const gridEl = document.getElementById('myPropertiesGrid');
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

    const propertyTypes  = JSON.parse(document.getElementById('property-types-data').textContent);
    const offerTypes     = JSON.parse(document.getElementById('offer-types-data').textContent);
    const provinces      = JSON.parse(document.getElementById('provinces-data').textContent);
    const municipalities = JSON.parse(document.getElementById('municipalities-data').textContent);
    const MAX_IMAGES_PER_PROPERTY = JSON.parse(document.getElementById('max-images-data').textContent) || 10;

    console.log('MAX_IMAGES_PER_PROPERTY:', MAX_IMAGES_PER_PROPERTY);

    const propertyTypeLookup = propertyTypes.map(t => ({ value: t[0], text: t[1] }));
    const offerTypeLookup    = offerTypes.map(t => ({ value: t[0], text: t[1] }));
    const provinceLookup     = provinces.map(p => ({ value: p.id, text: p.name }));
    const municipalityLookup = municipalities.map(m => ({ value: m.id, text: m.name, province_id: m.province_id }));

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

    const AVATAR_COLORS = [
        { bg: '#E1F5EE', fg: '#085041' }, { bg: '#E6F1FB', fg: '#0C447C' },
        { bg: '#EEEDFE', fg: '#3C3489' }, { bg: '#FAEEDA', fg: '#633806' },
        { bg: '#FAECE7', fg: '#712B13' }, { bg: '#EAF3DE', fg: '#27500A' }
    ];
    function avatarColor(id) { return AVATAR_COLORS[(id || 0) % AVATAR_COLORS.length]; }
    function initials(str) {
        return (str || '').trim().split(/\s+/).slice(0, 2).map(w => w[0] || '').join('').toUpperCase() || '?';
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

    // ===== BUILD URL CORREGIDA =====
    // FIX: el regex anterior usaba el flag global 'g', que sustituía TODAS las
    // apariciones de "/0/" en cada .replace(), no solo una por argumento. En
    // URLs con dos placeholders (image_cover, image_delete: ".../0/images/0/cover/")
    // el primer argumento (rowData.id) sustituía los DOS ceros de golpe, dejando
    // al segundo argumento (img.id) sin nada que sustituir -- "Eliminar" y
    // "Marcar portada" acababan llamando con image_id = property_id.
    // String.prototype.replace sin regex (con un string literal) solo sustituye
    // la PRIMERA ocurrencia, que es justo el comportamiento posicional que
    // necesitamos: un argumento -> el siguiente "/0/" de izquierda a derecha.
    function buildUrl(baseUrl, ...args) {
        let url = baseUrl;
        for (const arg of args) {
            url = url.replace('/0/', `/${arg}/`);
        }
        return url;
    }

    // ===== LIMPIEZA DE DATOS =====
    const ALLOWED_FIELDS = [
        'title', 'description', 'property_type', 'offer_type',
        'sale_price', 'rent_price', 'seasonal_rent_price', 'deposit_amount',
        'postal_code', 'province', 'municipality', 'address',
        'surface', 'rooms', 'bathrooms',
        'has_elevator', 'has_heating', 'has_air_conditioning',
        'status', 'is_active'
    ];

    const NUMERIC_FIELDS = ['sale_price', 'rent_price', 'seasonal_rent_price', 'deposit_amount', 'surface', 'rooms', 'bathrooms'];
    const CALCULATED_FIELDS = ['id', '__KEY__', 'status_display', 'property_type_display', 'offer_type_display', 'province_name', 'municipality_name', 'detail_url', 'images', 'max_images', 'created_at', 'updated_at', 'image_count', 'cover_image', 'display_price', 'display_price_label', 'price_range_display'];

    function cleanPayload(raw) {
        const clean = {};
        const allowedFields = new Set(ALLOWED_FIELDS);
        
        for (const [k, v] of Object.entries(raw)) {
            if (CALCULATED_FIELDS.includes(k) || !allowedFields.has(k)) continue;
            if (v === undefined || v === null) continue;
            
            if (NUMERIC_FIELDS.includes(k)) {
                const n = parseFloat(v);
                if (!isNaN(n)) {
                    clean[k] = n;
                }
            } else if (typeof v === 'boolean') {
                clean[k] = v;
            } else if (typeof v === 'string' && v.trim() !== '') {
                clean[k] = v.trim();
            } else if (typeof v === 'number') {
                clean[k] = v;
            }
        }
        
        return clean;
    }

    // ===== API REQUEST CORREGIDA =====
    function apiRequest(url, method, body, isFormData) {
        const opts = {
            method: method,
            headers: { 'X-CSRFToken': csrfToken, 'Accept': 'application/json' },
            credentials: 'same-origin'
        };
        
        if (body !== undefined) {
            if (isFormData) {
                // IMPORTANTE: NO establecer Content-Type para FormData
                opts.body = body;
                delete opts.headers['Content-Type'];
            } else {
                opts.headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(body);
            }
        }

        console.log('[API]', method, url, isFormData ? '(FormData)' : body);

        return fetch(url, opts).then(res => {
            if (!res.ok) {
                return res.text().then(txt => {
                    let errBody = {};
                    try { errBody = JSON.parse(txt); } catch(e) { errBody = { detail: txt }; }
                    
                    let errorMsg = errBody.detail || errBody.error || `HTTP ${res.status}`;
                    if (errBody.errors) {
                        const fieldErrors = Object.entries(errBody.errors)
                            .map(([field, msgs]) => {
                                const msg = Array.isArray(msgs) ? msgs.join(' ') : msgs;
                                return `${field}: ${msg}`;
                            })
                            .join('; ');
                        errorMsg = `Errores de validación: ${fieldErrors}`;
                    }
                    
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

    function formatFormErrors(errBody) {
        if (!errBody) return gettext('Ha ocurrido un error.');
        if (typeof errBody === 'string') return errBody;
        if (errBody.detail) return errBody.detail;
        if (errBody.errors) {
            return Object.keys(errBody.errors).map(field => {
                const msgs = errBody.errors[field];
                const text = Array.isArray(msgs) ? msgs.map(m => m.message || m).join(' ') : msgs;
                return field + ': ' + text;
            }).join('\n');
        }
        return errBody.error || gettext('Ha ocurrido un error.');
    }

    // ===== IMAGE MANAGER =====
    function renderImageManager($container, rowData, onChange) {
        $container.empty();

        if (!rowData || !rowData.id) {
            $container.append(
                `<div class="img-manager-empty">
                    <i class="fas fa-camera-retro"></i>
                    <p>${gettext('Guarda primero los datos generales del inmueble. En cuanto se cree, podrás añadir fotos editando el registro.')}</p>
                </div>`
            );
            return;
        }

        const images = rowData.images || [];
        const maxImages = rowData.max_images || 10;
        
        const $hint = $(`<p class="img-manager-hint">${images.length} / ${maxImages} ${gettext('fotos')}</p>`);
        const $gallery = $('<div class="img-gallery"></div>');
        const $uploader = $('<div></div>');

        images.forEach(img => {
            const $thumb = $('<div class="img-thumb"></div>').toggleClass('is-cover', img.is_cover);
            $thumb.append(`<img src="${escapeHtml(img.url)}" alt="${gettext('Foto del inmueble')}">`);
            if (img.is_cover) {
                $thumb.append(`<span class="cover-tag">${gettext('Portada')}</span>`);
            }
            const $tools = $('<div class="img-tools"></div>');
            if (!img.is_cover) {
                $(`<button type="button" title="${gettext('Marcar portada')}"><i class="fas fa-star"></i></button>`)
                    .on('click', function(e) {
                        e.stopPropagation();
                        const url = buildUrl(URLS.image_cover, rowData.id, img.id);
                        apiRequest(url, 'POST')
                            .then(() => {
                                images.forEach(i => i.is_cover = (i.id === img.id));
                                renderImageManager($container, rowData, onChange);
                                onChange();
                            })
                            .catch(err => {
                                DevExpress.ui.notify(formatFormErrors(err.body), 'error', 3000);
                            });
                    })
                    .appendTo($tools);
            }
            $(`<button type="button" title="${gettext('Eliminar')}"><i class="fas fa-trash"></i></button>`)
                .on('click', function(e) {
                    e.stopPropagation();
                    const url = buildUrl(URLS.image_delete, rowData.id, img.id);
                    apiRequest(url, 'DELETE')
                        .then(() => {
                            const index = images.findIndex(i => i.id === img.id);
                            if (index !== -1) images.splice(index, 1);
                            if (img.is_cover && images.length > 0) images[0].is_cover = true;
                            renderImageManager($container, rowData, onChange);
                            onChange();
                        })
                        .catch(err => {
                            DevExpress.ui.notify(formatFormErrors(err.body), 'error', 3000);
                        });
                })
                .appendTo($tools);
            $thumb.append($tools);
            $gallery.append($thumb);
        });

        $container.append($hint, $gallery, $uploader);

        if (images.length < maxImages) {
            const uploadUrl = buildUrl(URLS.images, rowData.id);
            $uploader.dxFileUploader({
                selectButtonText: gettext('Añadir foto'),
                labelText: '',
                accept: 'image/*',
                uploadMode: 'instantly',
                uploadUrl: uploadUrl,
                // FIX: sin esto, dxFileUploader envía el fichero con su
                // propio nombre de campo interno por defecto, distinto
                // de 'image'. El backend solo busca
                // request.FILES.get('image') (my_property_image_upload),
                // así que la petición llegaba sin el fichero reconocido
                // y devolvía 400 "No image file provided." -- de ahí que
                // subir fotos en EDICIÓN fallara mientras que en ALTA
                // funcionaba (subirFicherosPendientes ya arma el
                // FormData a mano con formData.append('image', file)).
                name: 'image',
                uploadHeaders: { 'X-CSRFToken': csrfToken },
                onUploaded: function(e) {
                    try {
                        const response = JSON.parse(e.request.responseText);
                        images.push(response);
                        renderImageManager($container, rowData, onChange);
                        onChange();
                        DevExpress.ui.notify(gettext('Foto añadida correctamente'), 'success', 2000);
                    } catch (error) {
                        DevExpress.ui.notify(gettext('Error al procesar la respuesta del servidor'), 'error', 3000);
                    }
                },
                onUploadError: function(e) {
                    DevExpress.ui.notify(gettext('No se pudo subir la imagen.'), 'error', 3000);
                }
            });
        }
    }

    // ===== DROPZONE DE FOTOS PARA ALTA =====
    const PENDING_FILE_MAX_BYTES = 8 * 1024 * 1024;
    const PENDING_FILE_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];

    function formatFileSize(bytes) {
        if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return Math.round(bytes / 1024) + ' KB';
    }

    function validatePendingFile(file) {
        if (PENDING_FILE_ALLOWED_TYPES.indexOf(file.type) === -1) {
            return gettext('formato no admitido (solo JPG, PNG, WEBP o HEIC)');
        }
        if (file.size > PENDING_FILE_MAX_BYTES) {
            return gettext('pesa demasiado; el máximo permitido es 8 MB');
        }
        return null;
    }

    // ===== VARIABLES GLOBALES PARA FOTOS PENDIENTES =====
    let pendingNewFiles = [];
    let pendingFilesRefs = null;

    // ===== GUARD ANTI "GHOST CLICK" TRAS EL DIÁLOGO NATIVO DE FICHEROS =====
    // Bug: al abrir el selector de ficheros vía JS ($input.trigger('click')), algunos
    // navegadores (Chromium) reenvían un click "fantasma" al elemento que queda bajo el
    // cursor cuando el diálogo del SO se cierra. En el popup de edición, ese punto coincide
    // con el botón "Guardar", lo que dispara un guardado prematuro (con validación fallida)
    // y el popup se cierra solo, perdiendo pendingNewFiles. Este guard absorbe ese único
    // click fantasma justo cuando la ventana recupera el foco tras el diálogo.
    let expectingFileDialogClose = false;
    let suppressGhostClick = false;

    function armFileDialogGhostClickGuard() {
        expectingFileDialogClose = true;
    }

    window.addEventListener('focus', function () {
        if (expectingFileDialogClose) {
            expectingFileDialogClose = false;
            suppressGhostClick = true;
            setTimeout(function () { suppressGhostClick = false; }, 400);
        }
    });

    document.addEventListener('click', function (e) {
        if (suppressGhostClick) {
            suppressGhostClick = false;
            e.stopPropagation();
            e.preventDefault();
            console.log('🛡️ Ghost-click tras selector de ficheros bloqueado (evitado cierre accidental del popup)');
        }
    }, true);

    function addPendingFiles(fileList) {
        console.log('=== ADD PENDING FILES ===');
        console.log('Archivos a añadir:', fileList.length);
        
        const errores = [];
        Array.prototype.forEach.call(fileList, function (file) {
            if (pendingNewFiles.length >= MAX_IMAGES_PER_PROPERTY) {
                errores.push(gettext('Solo puede adjuntar un máximo de') + ' ' + MAX_IMAGES_PER_PROPERTY + ' ' + gettext('fotos.'));
                return;
            }
            const yaExiste = pendingNewFiles.some(function (f) {
                return f.name === file.name && f.size === file.size && f.lastModified === file.lastModified;
            });
            if (yaExiste) return;

            const error = validatePendingFile(file);
            if (error) {
                errores.push('«' + file.name + '»: ' + error + '.');
                return;
            }
            pendingNewFiles.push(file);
            console.log('Archivo añadido a pendingNewFiles:', file.name);
        });

        console.log('pendingNewFiles.length después de añadir:', pendingNewFiles.length);

        if (pendingFilesRefs) renderPendingFilesPreview();

        if (errores.length) {
            errores.forEach(function (msg) {
                DevExpress.ui.notify(msg, 'error', 3500);
            });
        }
    }

    function removePendingFile(index) {
        console.log('=== REMOVE PENDING FILE ===');
        console.log('Eliminando archivo en índice:', index);
        pendingNewFiles.splice(index, 1);
        console.log('pendingNewFiles.length después de eliminar:', pendingNewFiles.length);
        if (pendingFilesRefs) renderPendingFilesPreview();
    }

    function renderPendingFilesPreview() {
        if (!pendingFilesRefs) return;
        const { $gallery, $counter } = pendingFilesRefs;

        $gallery.empty();
        pendingNewFiles.forEach(function (file, index) {
            const $item = $('<div class="img-pending-item"></div>');
            const objectUrl = URL.createObjectURL(file);
            $item.append(`<img src="${objectUrl}" alt="${escapeHtml(file.name)}">`);
            if (index === 0) {
                $item.append(`<span class="cover-tag">${gettext('Portada')}</span>`);
            }
            $(`<button type="button" class="img-pending-remove" title="${gettext('Quitar')}">&times;</button>`)
                .on('click', function (e) {
                    e.stopPropagation();
                    removePendingFile(index);
                })
                .appendTo($item);
            $gallery.append($item);
        });

        $counter.html(`<i class="fas fa-info-circle"></i> ${pendingNewFiles.length} ${gettext('de')} ${MAX_IMAGES_PER_PROPERTY} ${gettext('fotos seleccionadas')}`);
        $counter.toggleClass('limit-reached', pendingNewFiles.length >= MAX_IMAGES_PER_PROPERTY);
    }

    function renderPendingFilesDropzone($container) {
        console.log('=== RENDER PENDING FILES DROPZONE === pendingNewFiles.length AL PINTAR:', pendingNewFiles.length, pendingNewFiles.map(f => f.name));
        $container.empty();

        $container.append(
            `<p class="img-manager-hint">${gettext('Puedes añadir fotos ahora mismo: se subirán automáticamente en cuanto guardes el inmueble.')}</p>`
        );

        const $dropzone = $(
            `<div class="img-dropzone" tabindex="0" role="button" aria-label="${gettext('Adjuntar fotos del inmueble')}">
                <i class="fas fa-camera"></i>
                <span class="img-dropzone-text">${gettext('Arrastra tus fotos aquí o haz clic para seleccionar')}
                    <span class="img-dropzone-sub">JPG, PNG, WEBP ${gettext('o')} HEIC · ${gettext('máx.')} 8 MB · ${gettext('hasta')} ${MAX_IMAGES_PER_PROPERTY} ${gettext('fotos')}</span>
                </span>
                <input type="file" multiple accept="image/jpeg,image/png,image/webp,image/heic,image/heif">
            </div>`
        );
        const $input = $dropzone.find('input[type="file"]');
        const $gallery = $('<div class="img-gallery"></div>');
        const $counter = $('<p class="img-pending-counter"></p>');

        $dropzone.on('click', function () {
            armFileDialogGhostClickGuard();
            $input.trigger('click');
        });
        $dropzone.on('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                armFileDialogGhostClickGuard();
                $input.trigger('click');
            }
        });
        $input.on('click', function (e) { e.stopPropagation(); });
        $input.on('change', function () {
            console.log('INPUT CHANGE - files seleccionados:', this.files.length);
            addPendingFiles(this.files);
            this.value = '';
        });
        $dropzone.on('dragenter dragover', function (e) {
            e.preventDefault();
            e.stopPropagation();
            $dropzone.addClass('dragover');
        });
        $dropzone.on('dragleave drop', function (e) {
            e.preventDefault();
            e.stopPropagation();
            $dropzone.removeClass('dragover');
        });
        $dropzone.on('drop', function (e) {
            const files = e.originalEvent.dataTransfer && e.originalEvent.dataTransfer.files;
            console.log('DROP - files soltados:', files ? files.length : 0);
            if (files) addPendingFiles(files);
        });

        $container.append($dropzone, $counter, $gallery);

        pendingFilesRefs = { $gallery, $counter };
        renderPendingFilesPreview();
    }

    // ===== SUBIR FICHEROS PENDIENTES CORREGIDA =====
    function subirFicherosPendientes(propertyId) {
        console.log('=== SUBIR FICHEROS PENDIENTES ===');
        console.log('Property ID:', propertyId);
        console.log('pendingNewFiles.length:', pendingNewFiles.length);
        console.log('pendingNewFiles:', pendingNewFiles.map(f => f.name));
        
        if (pendingNewFiles.length === 0) {
            console.log('❌ No hay archivos pendientes');
            return Promise.resolve();
        }

        const files = pendingNewFiles.slice();
        console.log('📤 Subiendo', files.length, 'archivos');
        
        const uploadUrl = buildUrl(URLS.images, propertyId);
        console.log('📤 uploadUrl:', uploadUrl);
        
        const errores = [];

        // Subida SECUENCIAL
        return files.reduce(function (chain, file, index) {
            return chain.then(function () {
                console.log(`📤 Subiendo ${index + 1}/${files.length}: ${file.name} (${file.size} bytes)`);
                const formData = new FormData();
                formData.append('image', file);
                return apiRequest(uploadUrl, 'POST', formData, true).then(function (response) {
                    console.log(`✅ Subido ${file.name} - respuesta:`, response);
                    return response;
                }).catch(function (err) {
                    console.error(`❌ Error subiendo ${file.name}:`, err);
                    errores.push(`«${file.name}»: ${err.message || gettext('error desconocido')}`);
                });
            });
        }, Promise.resolve()).then(function () {
            if (errores.length) {
                const msg = `${gettext('Inmueble guardado, pero algunas fotos no se pudieron subir')}: ${errores.join('; ')}`;
                console.warn('⚠️', msg);
                DevExpress.ui.notify(msg, 'warning', 6000);
            } else {
                const msg = `${gettext('Inmueble y')} ${files.length} ${gettext('foto(s) guardados correctamente')}`;
                console.log('✅', msg);
                DevExpress.ui.notify(msg, 'success', 2500);
            }
            resetPendingNewFiles();
        });
    }

    function resetPendingNewFiles() {
        console.log('=== RESET PENDING NEW FILES ===');
        console.log('pendingNewFiles antes del reset:', pendingNewFiles.length);
        pendingNewFiles = [];
        pendingFilesRefs = null;
        console.log('pendingNewFiles después del reset:', pendingNewFiles.length);
    }

    // ===== ESTADO DEL FORMULARIO =====
    let municipalityEditorInstance = null;
    const priceEditorInstances = { sale_price: null, rent_price: null, seasonal_rent_price: null, deposit_amount: null };
    let gridInstanceRef = null;

    // FIX: fuente única y fiable de la fila que se está editando.
    // Antes, el template de la pestaña "Fotos" intentaba leer
    // data.component.option('formData') desde dentro de un item anidado
    // en itemType:'tabbed' -> tabs[].items[]. En ese contexto anidado
    // 'data.component' no resuelve de forma fiable a la instancia del
    // dxForm; si fallaba, el try/catch lo tragaba en silencio
    // (console.warn) y rowData se quedaba en null, cayendo SIEMPRE a la
    // rama de "modo ALTA" (dropzone) aunque se estuviera editando un
    // inmueble ya persistido -- de ahí que no aparecieran las fotos
    // guardadas, y que las fotos "añadidas" en ese estado se perdieran
    // en silencio (el dropzone de alta solo encola en pendingNewFiles;
    // esos ficheros solo se suben desde el callback insert() del store,
    // nunca desde update()).
    //
    // onEditingStart(e) es un evento documentado y fiable de dxDataGrid
    // que entrega la fila completa (e.data, incluida su images[]) justo
    // al abrir el popup de edición -- se usa esa fuente en vez de fiarse
    // del contexto del Form.
    let currentEditingRowData = null;

    function resetEditFormEditorRefs() {
        municipalityEditorInstance = null;
        priceEditorInstances.sale_price = null;
        priceEditorInstances.rent_price = null;
        priceEditorInstances.seasonal_rent_price = null;
        priceEditorInstances.deposit_amount = null;
    }

    function filterMunicipalitiesByProvince(provinceId) {
        if (!municipalityEditorInstance) return;
        const filteredData = provinceId ? municipalityLookup.filter(m => m.province_id === provinceId) : [];
        municipalityEditorInstance.option('dataSource', filteredData);
        municipalityEditorInstance.option('disabled', !provinceId);
        if (!provinceId) {
            municipalityEditorInstance.option('value', null);
            municipalityEditorInstance.option('placeholder', gettext('Selecciona primero una provincia...'));
        } else if (filteredData.length === 0) {
            municipalityEditorInstance.option('value', null);
            municipalityEditorInstance.option('placeholder', gettext('No hay municipios para esta provincia'));
        } else {
            municipalityEditorInstance.option('placeholder', gettext('Selecciona un municipio...'));
        }
    }

    function isPriceFieldEnabled(dataField, offerType) {
        if (!offerType) return false;
        if (dataField === 'sale_price') {
            return offerType === 'sale' || offerType === 'sale_or_rent';
        }
        if (['rent_price', 'seasonal_rent_price', 'deposit_amount'].includes(dataField)) {
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

   
    // ===== CUSTOM STORE CORREGIDO =====
    const store = new DevExpress.data.CustomStore({
        key: 'id',  // Usar 'key' en lugar de 'keyExpr' para CustomStore
        load: function() {
            console.log('📥 LOAD - Cargando propiedades');
            return apiRequest(URLS.data, 'GET').then(function (data) {
                // DEBUG TEMPORAL: para verificar si el backend ya devuelve
                // imágenes cruzadas entre inmuebles, o si el cruce ocurre
                // solo en el cliente después de esto.
                console.log('🔍 DEBUG LOAD - imágenes por inmueble:', data.map(function (p) {
                    return { id: p.id, title: p.title, image_count: p.image_count, image_ids: (p.images || []).map(function (i) { return i.id; }) };
                }));
                return data;
            });
        },
        insert: function(values) {
            console.log('📝 INSERT - Creando nueva propiedad');
            console.log('values:', values);
            console.log('pendingNewFiles.length:', pendingNewFiles.length);
            
            const payload = cleanPayload(values);
            console.log('payload limpio:', payload);
            
            if (Object.keys(payload).length === 0) {
                DevExpress.ui.notify(gettext('No hay datos válidos para guardar.'), 'warning', 3000);
                return Promise.reject(new Error('No hay datos válidos para guardar.'));
            }
            
            return apiRequest(URLS.data, 'POST', payload).then(function (response) {
                console.log('📝 INSERT - Respuesta del servidor:', response);
                console.log('response.id:', response.id);
                console.log('pendingNewFiles.length DESPUÉS de insert:', pendingNewFiles.length);
                
                if (pendingNewFiles.length > 0 && response && response.id) {
                    console.log('✅ Hay archivos pendientes, subiendo...');
                    return subirFicherosPendientes(response.id).then(function () {
                        console.log('✅ Archivos subidos, retornando response');
                        return response;
                    });
                } else {
                    console.log('❌ No hay archivos pendientes o falta response.id');
                    if (pendingNewFiles.length === 0) console.log('  - pendingNewFiles está vacío');
                    if (!response) console.log('  - response es null/undefined');
                    if (!response || !response.id) console.log('  - response.id es:', response ? response.id : 'N/A');
                }
                return response;
            });
        },
        update: function(key, values) {
            console.log('📝 UPDATE - Actualizando propiedad', key);
            const payload = {...values};
            CALCULATED_FIELDS.forEach(field => delete payload[field]);
            
            const allowedSet = new Set(ALLOWED_FIELDS);
            Object.keys(payload).forEach(key => {
                if (!allowedSet.has(key)) {
                    delete payload[key];
                }
            });

            if (Object.keys(payload).length === 0) {
                console.warn('[Update] Sin cambios válidos para enviar. Se omite petición.');
                return Promise.resolve();
            }

            const url = buildUrl(URLS.detail, key);
            console.log('📝 UPDATE URL:', url);
            console.log('📝 UPDATE payload:', payload);
            return apiRequest(url, 'PATCH', payload);
        },
        remove: function(key) {
            console.log('🗑️ REMOVE - Eliminando propiedad', key);
            const url = buildUrl(URLS.detail, key);
            return apiRequest(url, 'DELETE');
        }
    });
    // ===== GRID PRINCIPAL =====
    gridInstanceRef = $('#myPropertiesGrid').dxDataGrid({
        dataSource: store,
        keyExpr: 'id',
        showBorders: true,
        rowAlternationEnabled: true,
        columnAutoWidth: false,
        columnResizingMode: 'widget',
        hoverStateEnabled: true,
        columnFixing: { enabled: true },
        errorRowEnabled: true,

        groupPanel: {
            visible: true,
            emptyPanelText: gettext('Arrastre una columna aquí para agrupar')
        },
        grouping: { contextMenuEnabled: true, autoExpandAll: false },

        paging: { pageSize: 10 },
        pager: { showPageSizeSelector: true, allowedPageSizes: [10, 20, 50], showInfo: true },
        searchPanel: { visible: true, placeholder: gettext('Buscar...') },

        editing: {
            mode: 'popup',
            allowAdding: true,
            allowUpdating: true,
            // Se retira la posibilidad de eliminar inmuebles desde esta
            // grilla (ver columna de acciones más abajo, sin botón de
            // papelera). Se desactiva aquí también para no dejar
            // habilitada una operación sin ningún disparador en la UI.
            allowDeleting: false,
            useIcons: true,
            popup: {
                title: gettext('Inmueble'),
                showTitle: true,
                width: function () {
                    return Math.min(window.innerWidth * 0.94, 1500);
                },
                // FIX: con height:'auto' DevExtreme mide el popup por su
                // contenido real y crece hasta maxHeight; a partir de ahí
                // el propio dx-popup-content interno hace scroll. El
                // truncamiento de Guardar/Cancelar que había antes NO lo
                // causaba 'auto' en sí, sino un max-height fijo en CSS que
                // competía con este cálculo (ya retirado más abajo, ver
                // .property-edit-popup .dx-popup-content). Si aquí se fija
                // una altura constante en vez de 'auto', el popup deja un
                // hueco vacío enorme cuando el contenido de la pestaña
                // activa es corto (p.ej. "General"), así que se mantiene
                // 'auto'.
                height: 'auto',
                maxHeight: 'calc(100vh - 80px)',
                wrapperAttr: { class: 'property-edit-popup' },
                // FIX: NO se debe sustituir editing.popup.toolbarItems por un
                // array propio -- eso reemplaza también el binding interno
                // (validación, estado disabled, etc.) del botón "Guardar"
                // que genera el grid, y en la práctica el botón dejaba de
                // pintarse (solo sobrevivía "Cancelar"). La forma correcta y
                // soportada de tocar esos botones es personalizar los que
                // el propio grid genera (toolbarItems[0] = Guardar,
                // toolbarItems[1] = Cancelar) desde onInitialized, dejando
                // intacto su comportamiento por defecto.
                onInitialized: function (e) {
                    e.component.option('toolbarItems[0].options.icon', 'save');
                    e.component.option('toolbarItems[0].options.type', 'success');
                    e.component.option('toolbarItems[0].options.stylingMode', 'contained');
                    e.component.option('toolbarItems[1].options.icon', 'close');
                    e.component.option('toolbarItems[1].options.type', 'danger');
                    e.component.option('toolbarItems[1].options.stylingMode', 'contained');
                },
                // FIX: sin esto, el diálogo nativo del SO para elegir fotos (input type="file")
                // hace que el navegador pierda el foco un instante; DevExtreme lo interpreta
                // como "click fuera del popup" y lo cierra solo, perdiendo pendingNewFiles.
                hideOnOutsideClick: false,
                animation: {
                    show: { type: 'fade', duration: 200 },
                    hide: { type: 'fade', duration: 150 }
                },
                onHiding: function () {
                    console.log('Popup hiding - resetting editors');
                    resetEditFormEditorRefs();
                    // FIX: aquí (y no en cada cambio de foto) es donde se
                    // refresca el grid, para que la fila muestre el conteo
                    // de fotos / portada actualizados. Los cambios de fotos
                    // (subir, borrar, marcar portada) ya se guardan al
                    // instante contra el backend según se hacen, así que
                    // refrescar al cerrar -- se guarde o se cancele el resto
                    // del formulario -- es correcto y no afecta a la pestaña
                    // activa porque el popup ya se está cerrando.
                    try { gridInstanceRef.refresh(); } catch (e) {}
                    // FIX: evita que la fila de esta sesión de edición
                    // sobreviva y se reutilice por error en la siguiente
                    // apertura del popup (alta o edición de otra fila).
                    currentEditingRowData = null;
                },
                onHidden: function() {
                    try {
                        if (municipalityEditorInstance) {
                            municipalityEditorInstance = null;
                        }
                        Object.keys(priceEditorInstances).forEach(function(key) {
                            priceEditorInstances[key] = null;
                        });
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
                                colCount: 2,
                                colCountByScreen: { xs: 1, sm: 1, md: 2, lg: 2, xl: 2 },
                                items: [
                                    {
                                        itemType: 'group',
                                        caption: gettext('Datos generales'),
                                        colCount: 2,
                                        items: [
                                            {
                                                dataField: 'title',
                                                editorType: 'dxTextBox',
                                                colSpan: 2,
                                                label: { text: gettext('Título') },
                                                validationRules: [
                                                    { type: 'required', message: gettext('El título es obligatorio.') },
                                                    { type: 'stringLength', max: 200, message: gettext('Máximo 200 caracteres.') }
                                                ]
                                            },
                                            {
                                                dataField: 'property_type',
                                                editorType: 'dxSelectBox',
                                                label: { text: gettext('Tipo') },
                                                editorOptions: {
                                                    dataSource: propertyTypeLookup,
                                                    valueExpr: 'value',
                                                    displayExpr: 'text',
                                                    searchEnabled: true,
                                                    placeholder: gettext('Selecciona un tipo...')
                                                },
                                                validationRules: [{ type: 'required', message: gettext('Selecciona un tipo de inmueble.') }]
                                            },
                                            {
                                                dataField: 'offer_type',
                                                editorType: 'dxSelectBox',
                                                label: { text: gettext('Oferta') },
                                                editorOptions: {
                                                    dataSource: offerTypeLookup,
                                                    valueExpr: 'value',
                                                    displayExpr: 'text',
                                                    searchEnabled: true,
                                                    placeholder: gettext('Selecciona un tipo de oferta...')                            
                                                },
                                                validationRules: [{ type: 'required', message: gettext('Selecciona un tipo de oferta.') }]
                                            },
                                            {
                                                dataField: 'status',
                                                editorType: 'dxSelectBox',
                                                label: { text: gettext('Estado') },
                                                editorOptions: {
                                                    dataSource: [
                                                        { value: 'available', text: gettext('Disponible') },
                                                        { value: 'reserved', text: gettext('Reservado') },
                                                        { value: 'sold', text: gettext('Vendido') }
                                                    ],
                                                    valueExpr: 'value',
                                                    displayExpr: 'text',
                                                    placeholder: gettext('Selecciona un estado...')
                                                },
                                                validationRules: [{ type: 'required', message: gettext('El estado es obligatorio.') }]
                                            },
                                            {
                                                dataField: 'is_active',
                                                editorType: 'dxCheckBox',
                                                label: { text: gettext('Activo') }
                                            }
                                        ]
                                    },
                                    {
                                        itemType: 'group',
                                        caption: gettext('Descripción'),
                                        items: [{
                                            dataField: 'description',
                                            editorType: 'dxTextArea',
                                            label: { text: gettext('Descripción') },
                                            editorOptions: {
                                                height: 160,
                                                placeholder: gettext('Describe el inmueble...'),
                                                maxLength: 500
                                            },
                                            validationRules: [{ type: 'required', message: gettext('La descripción es obligatoria.') }]
                                        }]
                                    }
                                ]
                            },
                            {
                                title: gettext('Precio y ubicación'),
                                colCount: 2,
                                colCountByScreen: { xs: 1, sm: 1, md: 2, lg: 2, xl: 2 },
                                items: [
                                    {
                                        itemType: 'group',
                                        caption: gettext('Precio'),
                                        colCount: 2,
                                        items: [
                                            {
                                                dataField: 'sale_price',
                                                editorType: 'dxNumberBox',
                                                editorOptions: { min: 0, format: { type: 'fixedPoint', precision: 2 }, placeholder: gettext('0.00'), showClearButton: true },
                                                label: { text: gettext('Venta') },
                                                validationRules: [
                                                    {
                                                        type: 'custom',
                                                        reevaluate: true,
                                                        message: gettext('El precio de venta es obligatorio para ofertas de venta.'),
                                                        validationCallback: function (options) {
                                                            const offerType = options.data && options.data.offer_type;
                                                            if (offerType === 'sale' || offerType === 'sale_or_rent') {
                                                                return options.value != null && options.value !== '' && parseFloat(options.value) > 0;
                                                            }
                                                            return true;
                                                        }
                                                    },
                                                    { type: 'range', min: 0, max: 999999999.99, message: gettext('El precio debe ser mayor que 0.') }
                                                ]
                                            },
                                            {
                                                dataField: 'rent_price',
                                                editorType: 'dxNumberBox',
                                                editorOptions: { min: 0, format: { type: 'fixedPoint', precision: 2 }, placeholder: gettext('0.00'), showClearButton: true },
                                                label: { text: gettext('Alquiler') },
                                                validationRules: [
                                                    {
                                                        type: 'custom',
                                                        reevaluate: true,
                                                        message: gettext('El precio de alquiler es obligatorio para ofertas de alquiler.'),
                                                        validationCallback: function (options) {
                                                            const offerType = options.data && options.data.offer_type;
                                                            if (offerType === 'rent' || offerType === 'sale_or_rent') {
                                                                return options.value != null && options.value !== '' && parseFloat(options.value) > 0;
                                                            }
                                                            return true;
                                                        }
                                                    },
                                                    { type: 'range', min: 0, max: 999999999.99, message: gettext('El precio debe ser mayor que 0.') }
                                                ]
                                            },
                                            {
                                                dataField: 'seasonal_rent_price',
                                                editorType: 'dxNumberBox',
                                                editorOptions: { min: 0, format: { type: 'fixedPoint', precision: 2 }, placeholder: gettext('0.00'), showClearButton: true },
                                                label: { text: gettext('Alquiler temporal') },
                                                validationRules: [{ type: 'range', min: 0, max: 999999999.99, message: gettext('El precio no puede ser negativo.') }]
                                            },
                                            {
                                                dataField: 'deposit_amount',
                                                editorType: 'dxNumberBox',
                                                editorOptions: { min: 0, format: { type: 'fixedPoint', precision: 2 }, placeholder: gettext('0.00'), showClearButton: true },
                                                label: { text: gettext('Depósito') },
                                                validationRules: [{ type: 'range', min: 0, max: 999999999.99, message: gettext('El importe no puede ser negativo.') }]
                                            }
                                        ]
                                    },
                                    {
                                        itemType: 'group',
                                        caption: gettext('Ubicación'),
                                        colCount: 2,
                                        items: [
                                            {
                                                dataField: 'postal_code',
                                                editorType: 'dxTextBox',
                                                label: { text: gettext('Código postal') },
                                                editorOptions: { placeholder: gettext('CP'), maxLength: 10 }
                                            },
                                            {
                                                dataField: 'address',
                                                editorType: 'dxTextBox',
                                                colSpan: 2,
                                                label: { text: gettext('Dirección') },
                                                editorOptions: { placeholder: gettext('Calle, número, etc.') }
                                            },
                                            {
                                                dataField: 'province',
                                                editorType: 'dxSelectBox',
                                                label: { text: gettext('Provincia') },
                                                editorOptions: {
                                                    dataSource: provinceLookup,
                                                    valueExpr: 'value',
                                                    displayExpr: 'text',
                                                    searchEnabled: true,
                                                    placeholder: gettext('Selecciona una provincia...')
                                                }
                                            },
                                            {
                                                dataField: 'municipality',
                                                editorType: 'dxSelectBox',
                                                label: { text: gettext('Municipio') },
                                                editorOptions: {
                                                    dataSource: [],
                                                    valueExpr: 'value',
                                                    displayExpr: 'text',
                                                    searchEnabled: true,
                                                    disabled: true,
                                                    placeholder: gettext('Selecciona primero una provincia...')
                                                }
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                title: gettext('Características'),
                                items: [
                                    {
                                        itemType: 'group',
                                        colCount: 3,
                                        items: [
                                            {
                                                dataField: 'surface',
                                                editorType: 'dxNumberBox',
                                                editorOptions: { min: 0, max: 10000, format: { type: 'fixedPoint', precision: 1 }, placeholder: gettext('0.0'), showClearButton: true },
                                                label: { text: gettext('m²') },
                                                validationRules: [{ type: 'range', min: 0, max: 10000, message: gettext('La superficie debe estar entre 0 y 10,000 m².') }]
                                            },
                                            {
                                                dataField: 'rooms',
                                                editorType: 'dxNumberBox',
                                                editorOptions: { min: 0, max: 99, step: 1, format: { type: 'fixedPoint', precision: 0 }, placeholder: gettext('0'), showClearButton: true },
                                                label: { text: gettext('Habitaciones') },
                                                validationRules: [{ type: 'range', min: 0, max: 99, message: gettext('El número de habitaciones debe estar entre 0 y 99.') }]
                                            },
                                            {
                                                dataField: 'bathrooms',
                                                editorType: 'dxNumberBox',
                                                editorOptions: { min: 0, max: 99, step: 1, format: { type: 'fixedPoint', precision: 0 }, placeholder: gettext('0'), showClearButton: true },
                                                label: { text: gettext('Baños') },
                                                validationRules: [{ type: 'range', min: 0, max: 99, message: gettext('El número de baños debe estar entre 0 y 99.') }]
                                            },
                                            { dataField: 'has_elevator', editorType: 'dxCheckBox', label: { text: gettext('Ascensor') } },
                                            { dataField: 'has_heating', editorType: 'dxCheckBox', label: { text: gettext('Calefacción') } },
                                            { dataField: 'has_air_conditioning', editorType: 'dxCheckBox', label: { text: gettext('Aire acondicionado') } }
                                        ]
                                    }
                                ]
                            },
                            {
                                title: gettext('Fotos'),
                                items: [{
                                    itemType: 'item',
                                    name: 'imagesManager',
                                    template: function (data, container) {
                                        console.log('🎨 Renderizando pestaña Fotos');
                                        const $container = $('<div class="img-manager img-manager-tab"></div>');
                                        $(container).append($container);

                                        // FIX: ya no se lee data.component.option('formData').
                                        // Dentro de un item anidado en itemType:'tabbed' ->
                                        // tabs[].items[], 'data.component' no resolvía de forma
                                        // fiable al dxForm; cuando fallaba, el try/catch lo
                                        // tragaba en silencio y esta pestaña caía SIEMPRE en el
                                        // modo "ALTA" (dropzone), incluso editando un inmueble ya
                                        // persistido con fotos guardadas. currentEditingRowData
                                        // se rellena de forma fiable en onEditingStart(e.data) /
                                        // se limpia en onInitNewRow, y es la misma fila que carga
                                        // el grid (con su images[] ya resuelta por el backend).
                                        const rowData = currentEditingRowData;

                                        if (!rowData || !rowData.id) {
                                            console.log('📸 Modo ALTA - renderizando dropzone');
                                            renderPendingFilesDropzone($container);
                                            return;
                                        }

                                        console.log('📸 Modo EDICIÓN - renderizando manager con imágenes. rowData.id:', rowData.id, 'image_ids:', (rowData.images || []).map(function (i) { return i.id; }));
                                        // FIX: antes, notifyChange() llamaba a
                                        // gridInstanceRef.refresh() -- un refresco
                                        // COMPLETO del grid en cada alta/baja/portada de
                                        // foto, con el popup de edición todavía abierto.
                                        // Ese refresh recargaba los datos y reconstruía el
                                        // formulario del popup, y como el dxTabPanel no
                                        // conserva su selectedIndex entre reconstrucciones,
                                        // la pestaña activa volvía siempre a "General" (la
                                        // primera). rowData.images es la misma referencia
                                        // que ya usa el grid (currentEditingRowData = e.data
                                        // en onEditingStart, ver más abajo), así que no hace
                                        // falta refrescar nada mientras se edita: los cambios
                                        // ya están reflejados en esa misma fila. El refresco
                                        // real de la lista (para que el conteo de fotos y la
                                        // miniatura de portada se vean actualizados) se hace
                                        // una sola vez al cerrar el popup, en editing.popup.onHiding.
                                        const notifyChange = function() {};

                                        renderImageManager($container, rowData, notifyChange);
                                    }
                                }]
                            }
                        ]
                    }
                ]
            }
        },

        columns: [
            {
                dataField: 'title',
                caption: gettext('Título'),
                minWidth: 220,
                fixed: true,
                fixedPosition: 'left',
                cellTemplate: function (container, options) {
                    const c = avatarColor(options.data.id);
                    const location = [options.data.municipality_name, options.data.province_name].filter(Boolean).join(', ');
                    $(container).append(
                        `<div class="cell-wrap">
                            <div class="avatar" style="background:${c.bg};color:${c.fg}">${initials(options.value || '')}</div>
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
                lookup: { dataSource: propertyTypeLookup, valueExpr: 'value', displayExpr: 'text' },
                cellTemplate: function (container, options) {
                    const info = getTipoInfo(options.value, options.data.property_type_display);
                    $(`<span class="tipo-badge"></span>`)
                        .css({ background: info.badgeBg, color: info.badgeText })
                        .html(`<i class="fas ${info.icon}"></i> ${escapeHtml(info.text)}`)
                        .appendTo(container);
                }
            },
            {
                dataField: 'offer_type',
                caption: gettext('Oferta'),
                width: 130,
                lookup: { dataSource: offerTypeLookup, valueExpr: 'value', displayExpr: 'text' }
            },
            {
                dataField: 'province',
                caption: gettext('Provincia'),
                width: 140,
                lookup: { dataSource: provinceLookup, valueExpr: 'value', displayExpr: 'text' }
            },
            {
                dataField: 'municipality',
                caption: gettext('Municipio'),
                width: 150,
                lookup: { dataSource: municipalityLookup, valueExpr: 'value', displayExpr: 'text' }
            },
            { dataField: 'sale_price', caption: gettext('Venta'), dataType: 'number', format: { type: 'currency', currency: 'EUR' }, alignment: 'right', width: 110 },
            { dataField: 'rent_price', caption: gettext('Alquiler'), dataType: 'number', format: { type: 'currency', currency: 'EUR' }, alignment: 'right', width: 110 },
            { dataField: 'surface', caption: gettext('m²'), dataType: 'number', width: 80, alignment: 'right', format: { type: 'fixedPoint', precision: 1 } },
            { dataField: 'rooms', caption: gettext('Hab.'), dataType: 'number', width: 70, alignment: 'center' },
            { dataField: 'bathrooms', caption: gettext('Baños'), dataType: 'number', width: 70, alignment: 'center' },
            { dataField: 'status', visible: false },
            { dataField: 'description', visible: false },
            { dataField: 'address', visible: false },
            { dataField: 'postal_code', visible: false },
            { dataField: 'is_active', visible: false },
            { dataField: 'has_elevator', visible: false },
            { dataField: 'has_heating', visible: false },
            { dataField: 'has_air_conditioning', visible: false },
            { dataField: 'seasonal_rent_price', visible: false },
            { dataField: 'deposit_amount', visible: false },
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
                        // FIX: 'eye' no es un nombre de icono válido del
                        // set propio de DevExtreme (no existe en su
                        // fuente de iconos), así que el botón se
                        // renderizaba sin glifo -- visualmente invisible
                        // aunque el botón sí estaba ahí y era clicable.
                        // DevExtreme sí admite clases de Font Awesome
                        // directamente en 'icon', y FA ya está cargado
                        // en la página (se usa en el resto de la UI).
                        icon: 'fas fa-eye',
                        cssClass: 'rbtn rbtn-view',
                        visible: function(e) { return !!e.row.data.detail_url; },
                        onClick: function(e) {
                            if (e.row.data.detail_url) {
                                window.open(e.row.data.detail_url, '_blank');
                            }
                        }
                    },
                    {
                        hint: gettext('Editar'),
                        icon: 'edit',
                        cssClass: 'rbtn rbtn-edit',
                        onClick: function(e) {
                            const rowIndex = e.row.rowIndex;
                            e.component.editRow(rowIndex);
                        }
                    }
                    // Botón "Eliminar" retirado a petición: ya no se
                    // permite borrar inmuebles desde esta grilla (ver
                    // editing.allowDeleting: false más arriba).
                ]
            }
        ],

        summary: {
            totalItems: [
                { column: 'title', summaryType: 'count', displayFormat: `${gettext('Total')}: {0}` },
                { column: 'surface', summaryType: 'sum', displayFormat: `Σ ${gettext('Superficie')}: {0} m²`, valueFormat: '#,##0.0' }
            ]
        },

        toolbar: {
            items: [
                { location: 'before', template: () => `<div style="font-weight:600;padding:8px 4px">${gettext('Mis inmuebles')}</div>` },
                'groupPanel',
                'addRowButton',
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

        onInitNewRow: function(e) {
            console.log('🆕 INIT NEW ROW');
            e.data.is_active = true;
            e.data.status = 'available';
            resetPendingNewFiles();
            // FIX: onEditingStart NO se dispara para altas (solo para
            // edición de una fila existente), así que sin esto
            // currentEditingRowData podía arrastrar la fila de la ÚLTIMA
            // edición anterior y "colarse" en un alta nueva.
            currentEditingRowData = null;
            console.log('pendingNewFiles reiniciado');
        },
        onEditingStart: function(e) {
            // Refuerzo: cualquier inicio de edición (alta o edición de fila
            // existente) parte de cero en cuanto a fotos pendientes de ALTA --
            // pendingNewFiles nunca debería sobrevivir entre sesiones de popup.
            console.log('✏️ EDITING START - key:', e.key);
            resetPendingNewFiles();
            // FIX: fuente fiable de la fila en edición para la pestaña
            // "Fotos" (ver comentario junto a la declaración de la
            // variable). e.data es la fila completa tal y como la cargó
            // el grid, incluida su images[] ya resuelta por el backend.
            currentEditingRowData = e.data;
        },
        onRowInserting: function(e) {
            console.log('📝 ROW INSERTING - e.data:', e.data);
            e.data = cleanPayload(e.data);
            console.log('📝 ROW INSERTING - cleaned:', e.data);
        },
        onRowInserted: function(e) {
            console.log('✅ ROW INSERTED - e.data:', e.data);
            console.log('✅ ROW INSERTED - e.key:', e.key);
            // Refrescar el grid para mostrar las imágenes subidas
            setTimeout(function() {
                gridInstanceRef.refresh();
            }, 1000);
        },
        onRowUpdating: function(e) {
            // El store ya maneja la limpieza en update
        },

        onEditorPreparing: function (e) {
            if (e.parentType !== 'dataRow') return;

            if (e.dataField === 'province') {
                const originalOnValueChanged = e.editorOptions.onValueChanged;
                e.editorOptions.onValueChanged = function (args) {
                    if (originalOnValueChanged) originalOnValueChanged.call(this, args);
                    filterMunicipalitiesByProvince(args.value);
                    if (municipalityEditorInstance) {
                        const currentMunicipality = municipalityEditorInstance.option('value');
                        if (currentMunicipality) {
                            const stillValid = municipalityLookup.some(
                                m => m.value === currentMunicipality && m.province_id === args.value
                            );
                            if (!stillValid) municipalityEditorInstance.option('value', null);
                        }
                    }
                };
            }

            if (e.dataField === 'municipality') {
                const originalOnInitialized = e.editorOptions.onInitialized;
                e.editorOptions.onInitialized = function (args) {
                    if (originalOnInitialized) originalOnInitialized.call(this, args);
                    municipalityEditorInstance = args.component;
                    const currentProvince = e.row && e.row.data ? e.row.data.province : null;
                    filterMunicipalitiesByProvince(currentProvince);
                };
            }

            if (e.dataField === 'offer_type') {
                const originalOnValueChanged = e.editorOptions.onValueChanged;
                e.editorOptions.onValueChanged = function (args) {
                    if (originalOnValueChanged) originalOnValueChanged.call(this, args);
                    updatePriceFieldsAvailability(args.value);
                };
            }

            if (['sale_price', 'rent_price', 'seasonal_rent_price', 'deposit_amount'].includes(e.dataField)) {
                const originalOnInitialized = e.editorOptions.onInitialized;
                e.editorOptions.onInitialized = function (args) {
                    if (originalOnInitialized) originalOnInitialized.call(this, args);
                    priceEditorInstances[e.dataField] = args.component;
                    const currentOfferType = e.row && e.row.data ? e.row.data.offer_type : null;
                    args.component.option('disabled', !isPriceFieldEnabled(e.dataField, currentOfferType));
                };
            }
        },

        onDataErrorOccurred: function(e) {
            console.error('DataGrid error:', e.error);
            const msg = e.error && (e.error.message || e.error.body && formatFormErrors(e.error.body)) || gettext('Error desconocido');
            DevExpress.ui.notify(gettext('Error: ') + msg, 'error', 5000);
        }
    }).dxDataGrid('instance');

    // ===== FUNCIONES DE UTILIDAD =====
    function doRefresh() {
        gridInstanceRef.refresh();
        DevExpress.ui.notify(gettext('Datos actualizados'), 'success', 1800);
    }

    function exportarExcel() {
        DevExpress.ui.notify(gettext('Generando archivo Excel…'), 'info', 2000);
        try {
            const wb = new ExcelJS.Workbook();
            const ws = wb.addWorksheet(gettext('Mis inmuebles'));
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
                    saveAs(blob, `mis_inmuebles_${new Date().toISOString().slice(0, 10)}.xlsx`);
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
            DevExpress.ui.notify(gettext('No hay inmuebles para imprimir'), 'warning', 3000);
            return;
        }
        const fecha = new Date().toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' });
        const hora = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });

        let html = `<!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>${gettext('Mis inmuebles')}</title>
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
        <div class="header"><h1>${gettext('Mis inmuebles')}</h1>
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

        html += `</tbody></table><div class="footer">cu2home.com · ${gettext('Mis inmuebles')}</div></body></html>`;
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

    console.log('🚀 my_properties.js inicializado correctamente');
})();
