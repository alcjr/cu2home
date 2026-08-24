DevExpress.localization.locale("es");

// =========================================================================
// DARK MODE - Misma lógica que navigation.html / comunidad.js (key: fingest_theme)
// =========================================================================

window.toggleDarkMode = function() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    var newTheme = isDark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('cu2home_theme', newTheme);
    var icon = document.getElementById('darkmode-icon');
    if (icon) icon.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
};

(function initTheme() {
    var saved = localStorage.getItem('cu2home_theme');
    if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        var icon = document.getElementById('darkmode-icon');
        if (icon) icon.className = 'fas fa-sun';
    }
})();

// =========================================================================
// CONTINÚA EL RESTO DEL CÓDIGO DE config.js
// =========================================================================

$(function () {
    // =========================================================================
    // URLs
    // =========================================================================
    var URLS = window.CONFIG_URLS || {
        config:       "/panel-control/api/config/",
        configSave:   "/panel-control/api/config/save/",
        configReload: "/panel-control/api/config/reload/"
    };

    // =========================================================================
    // UTILIDADES (idénticas al patrón canónico de comunidad.js)
    // =========================================================================
    function getCsrfToken() {
        if (typeof Fingest !== 'undefined' && Fingest.getCsrfToken) return Fingest.getCsrfToken();
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) return m.getAttribute('content');
        var c = document.cookie.split(';').find(function(x) { return x.trim().startsWith('csrftoken='); });
        return c ? decodeURIComponent(c.trim().substring('csrftoken='.length)) : '';
    }

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        var d = document.createElement('div');
        d.textContent = String(text);
        return d.innerHTML;
    }

    function handleError(msg, type, dur) {
        DevExpress.ui.notify({ message: msg, type: type || 'error', displayTime: dur || 4000 });
    }
    function handleSuccess(msg, dur) {
        DevExpress.ui.notify({ message: msg, type: 'success', displayTime: dur || 2000 });
    }

    // =========================================================================
    // LOADING STATE MANAGEMENT
    // =========================================================================
    var loadingOverlay = document.getElementById('global-loading');
    var activeRequests = 0;

    function showLoading(message) {
        activeRequests++;
        if (loadingOverlay) {
            loadingOverlay.style.display = 'flex';
            var msgSpan = loadingOverlay.querySelector('span');
            if (msgSpan && message) msgSpan.textContent = message;
        }
    }

    function hideLoading() {
        activeRequests--;
        if (activeRequests <= 0 && loadingOverlay) {
            activeRequests = 0;
            loadingOverlay.style.display = 'none';
            var msgSpan = loadingOverlay.querySelector('span');
            if (msgSpan) msgSpan.textContent = 'Cargando...';
        }
    }

    // =========================================================================
    // ESTADO
    // =========================================================================
    var _configData = null;       // estructura completa { path, exists, last_modified, sections: [...] }
    var _originalSnapshot = null; // JSON.stringify de los valores originales, para detectar cambios
    var _activeChip = 'all';
    var _searchText = '';
    var _seccionFiltro = '';
    var _selectedField = null;    // { sectionName, key, type, value, raw }
    var _activeDpTab = 'info';
    var _collapsedSections = {};

    var TYPE_LABELS = { boolean: 'Booleano', integer: 'Entero', float: 'Decimal', string: 'Texto' };
    var TYPE_ICONS  = { boolean: 'fa-toggle-on', integer: 'fa-hashtag', float: 'fa-percent', string: 'fa-font' };

    function fieldId(sectionName, key) {
        return 'cfg__' + sectionName + '__' + key;
    }

    // =========================================================================
    // CARGA DE DATOS
    // =========================================================================
    function fetchConfig() {
        showLoading('Cargando config.ini...');
        return $.ajax({ url: URLS.config, method: 'GET', dataType: 'json' })
            .done(function(data) {
                _configData = data;
                _originalSnapshot = snapshotValues(data);
                renderAll();
            })
            .fail(function(xhr) {
                var msg = 'Error al cargar config.ini';
                try { var j = JSON.parse(xhr.responseText); if (j.detail) msg = j.detail; } catch(e) {}
                handleError(msg);
                renderErrorState(msg);
            })
            .always(function() { hideLoading(); });
    }

    function snapshotValues(data) {
        var snap = {};
        (data.sections || []).forEach(function(sec) {
            (sec.keys || []).forEach(function(k) {
                snap[fieldId(sec.name, k.key)] = k.value;
            });
        });
        return JSON.stringify(snap);
    }

    function currentValues() {
        var vals = {};
        (_configData.sections || []).forEach(function(sec) {
            (sec.keys || []).forEach(function(k) {
                vals[fieldId(sec.name, k.key)] = k.value;
            });
        });
        return vals;
    }

    function hasUnsavedChanges() {
        if (!_configData) return false;
        return JSON.stringify(currentValues()) !== _originalSnapshot;
    }

    // =========================================================================
    // RENDER PRINCIPAL
    // =========================================================================
    function renderErrorState(msg) {
        var container = document.getElementById('configSectionsContainer');
        if (!container) return;
        container.innerHTML = '<div class="config-empty-state is-error">'
            + '<i class="fas fa-triangle-exclamation"></i>'
            + '<span>' + escapeHtml(msg) + '</span>'
            + '</div>';
    }

    function renderAll() {
        populateSeccionFilter();
        renderSections();
        renderKpis();
        updateFilterBadge();
        renderPagerSummary();
        if (typeof Fingest !== 'undefined' && Fingest.updateTimestamp) {
            Fingest.updateTimestamp('#last-update-label');
        } else {
            var lu = document.getElementById('last-update-text');
            if (lu) lu.textContent = new Date().toLocaleTimeString('es-ES');
        }
    }

    function populateSeccionFilter() {
        var sel = document.getElementById('filter-seccion');
        if (!sel || !_configData) return;
        var current = sel.value;
        sel.innerHTML = '<option value="">Todas las secciones</option>';
        (_configData.sections || []).forEach(function(sec) {
            var opt = document.createElement('option');
            opt.value = sec.name;
            opt.textContent = sec.name;
            sel.appendChild(opt);
        });
        if (current) sel.value = current;
    }

    function matchesFilters(sectionName, item) {
        // chip
        if (_activeChip === 'modificados') {
            var id = fieldId(sectionName, item.key);
            var curVal = JSON.stringify(item.value);
            var origVals = JSON.parse(_originalSnapshot);
            if (JSON.stringify(origVals[id]) === curVal) return false;
        } else if (_activeChip === 'vacios') {
            if (item.value !== '' && item.value !== null && item.value !== undefined) return false;
        }
        // sección
        if (_seccionFiltro && sectionName !== _seccionFiltro) return false;
        // texto
        if (_searchText) {
            var hay = (sectionName + ' ' + item.key + ' ' + String(item.value)).toLowerCase();
            if (hay.indexOf(_searchText.toLowerCase()) === -1) return false;
        }
        return true;
    }

    function renderSections() {
        var container = document.getElementById('configSectionsContainer');
        if (!container || !_configData) return;

        if (!_configData.exists) {
            container.innerHTML = '<div class="config-empty-state is-error">'
                + '<i class="fas fa-file-circle-xmark"></i>'
                + '<span>No se encontró config.ini en la raíz del proyecto (' + escapeHtml(_configData.path || '') + ')</span>'
                + '</div>';
            return;
        }

        if (!_configData.sections || _configData.sections.length === 0) {
            container.innerHTML = '<div class="config-empty-state">'
                + '<i class="fas fa-inbox"></i>'
                + '<span>El archivo config.ini no contiene secciones</span>'
                + '</div>';
            return;
        }

        var html = '';
        var visibleSectionCount = 0;
        var visibleFieldCount = 0;

        _configData.sections.forEach(function(sec) {
            var rowsHtml = '';
            var sectionVisibleCount = 0;

            sec.keys.forEach(function(item) {
                var visible = matchesFilters(sec.name, item);
                if (visible) { sectionVisibleCount++; visibleFieldCount++; }
                rowsHtml += renderFieldRow(sec.name, item, visible);
            });

            var sectionVisible = sectionVisibleCount > 0;
            if (sectionVisible) visibleSectionCount++;

            var collapsed = !!_collapsedSections[sec.name];
            html += '<div class="config-section-card' + (sectionVisible ? '' : ' is-hidden') + (collapsed ? ' collapsed' : '') + '" data-section="' + escapeHtml(sec.name) + '">'
                + '<div class="config-section-header" onclick="toggleSection(this)">'
                +   '<div class="csh-icon"><i class="fas fa-layer-group"></i></div>'
                +   '<div class="csh-title">' + escapeHtml(sec.name) + '</div>'
                +   '<div class="csh-count">' + sec.keys.length + ' parámetro' + (sec.keys.length === 1 ? '' : 's') + '</div>'
                +   '<i class="fas fa-chevron-down csh-chevron"></i>'
                + '</div>'
                + '<div class="config-section-body">' + rowsHtml + '</div>'
                + '</div>';
        });

        container.innerHTML = html;

        document.getElementById('config-loading-state') && document.getElementById('config-loading-state').remove();

        wireFieldEvents();
        renderFloatingBar();
    }

    function renderFieldRow(sectionName, item, visible) {
        var id = fieldId(sectionName, item.key);
        var isModified = isFieldModified(sectionName, item.key, item.value);
        var typeLabel = TYPE_LABELS[item.type] || 'Texto';
        var control = '';

        if (item.type === 'boolean') {
            control = '<label class="cfr-toggle">'
                + '<input type="checkbox" id="' + id + '" data-section="' + escapeHtml(sectionName) + '" data-key="' + escapeHtml(item.key) + '" data-type="boolean"' + (item.value ? ' checked' : '') + '>'
                + '<span class="toggle-track"></span>'
                + '<span class="toggle-label">' + (item.value ? 'Activado' : 'Desactivado') + '</span>'
                + '</label>';
        } else if (item.type === 'integer' || item.type === 'float') {
            control = '<input type="number" id="' + id + '" data-section="' + escapeHtml(sectionName) + '" data-key="' + escapeHtml(item.key) + '" data-type="' + item.type + '"'
                + (item.type === 'float' ? ' step="any"' : ' step="1"')
                + ' value="' + escapeHtml(item.value) + '">';
        } else {
            var isEmpty = item.value === '' || item.value === null || item.value === undefined;
            control = '<input type="text" id="' + id + '" data-section="' + escapeHtml(sectionName) + '" data-key="' + escapeHtml(item.key) + '" data-type="string"'
                + ' class="' + (isEmpty ? 'is-empty' : '') + '"'
                + ' placeholder="(vacío)"'
                + ' value="' + escapeHtml(item.value) + '">';
        }

        return '<div class="config-field-row' + (isModified ? ' is-modified' : '') + (visible ? '' : ' is-hidden') + '" data-section="' + escapeHtml(sectionName) + '" data-key="' + escapeHtml(item.key) + '">'
            + '<div class="cfr-label">'
            +   '<div class="cfr-key-wrap"><span class="cfr-key">' + escapeHtml(item.key) + '</span>'
            +   '<button type="button" class="cfr-info-btn" title="Ver detalle" onclick="showFieldDetail(\'' + escapeHtml(sectionName).replace(/'/g, "\\'") + '\', \'' + escapeHtml(item.key).replace(/'/g, "\\'") + '\')"><i class="fas fa-circle-info"></i></button>'
            +   '</div>'
            +   '<span class="cfr-type-tag"><i class="fas ' + (TYPE_ICONS[item.type] || 'fa-font') + '"></i> ' + typeLabel + '</span>'
            + '</div>'
            + '<div class="cfr-control">' + control + '</div>'
            + '</div>';
    }

    function isFieldModified(sectionName, key, currentValue) {
        if (!_originalSnapshot) return false;
        var id = fieldId(sectionName, key);
        var origVals = JSON.parse(_originalSnapshot);
        return JSON.stringify(origVals[id]) !== JSON.stringify(currentValue);
    }

    function wireFieldEvents() {
        $('.cfr-control input[type="text"], .cfr-control input[type="number"]').off('input').on('input', function() {
            var $el = $(this);
            var section = $el.data('section');
            var key = $el.data('key');
            var type = $el.data('type');
            var raw = $el.val();
            var value = (type === 'integer') ? parseInt(raw, 10) : (type === 'float') ? parseFloat(raw) : raw;
            if ((type === 'integer' || type === 'float') && isNaN(value)) value = raw;
            updateFieldValue(section, key, value);
            $el.toggleClass('is-empty', type === 'string' && raw === '');
            refreshRowModifiedState(section, key);
            if (_selectedField && _selectedField.sectionName === section && _selectedField.key === key) {
                _selectedField.value = value;
                renderDpTab(_activeDpTab, _selectedField);
            }
        });

        $('.cfr-toggle input[type="checkbox"]').off('change').on('change', function() {
            var $el = $(this);
            var section = $el.data('section');
            var key = $el.data('key');
            var checked = $el.is(':checked');
            updateFieldValue(section, key, checked);
            $el.closest('.cfr-toggle').find('.toggle-label').text(checked ? 'Activado' : 'Desactivado');
            refreshRowModifiedState(section, key);
            if (_selectedField && _selectedField.sectionName === section && _selectedField.key === key) {
                _selectedField.value = checked;
                renderDpTab(_activeDpTab, _selectedField);
            }
        });
    }

    function updateFieldValue(sectionName, key, value) {
        var sec = _configData.sections.find(function(s) { return s.name === sectionName; });
        if (!sec) return;
        var item = sec.keys.find(function(k) { return k.key === key; });
        if (!item) return;
        item.value = value;
        renderKpis();
        renderFloatingBar();
    }

    function refreshRowModifiedState(sectionName, key) {
        var sec = _configData.sections.find(function(s) { return s.name === sectionName; });
        var item = sec && sec.keys.find(function(k) { return k.key === key; });
        if (!item) return;
        var modified = isFieldModified(sectionName, key, item.value);
        var $row = $('.config-field-row[data-section="' + cssEscape(sectionName) + '"][data-key="' + cssEscape(key) + '"]');
        $row.toggleClass('is-modified', modified);
    }

    function cssEscape(s) {
        return String(s).replace(/(["\\\]\[.#:>+~*^$|()=,/{}])/g, '\\$1');
    }

    // =========================================================================
    // KPIs
    // =========================================================================
    function renderKpis() {
        if (!_configData) return;
        var totalSecciones = (_configData.sections || []).length;
        var totalParametros = 0;
        (_configData.sections || []).forEach(function(s) { totalParametros += s.keys.length; });

        var modificados = 0;
        var origVals = JSON.parse(_originalSnapshot || '{}');
        (_configData.sections || []).forEach(function(sec) {
            sec.keys.forEach(function(k) {
                var id = fieldId(sec.name, k.key);
                if (JSON.stringify(origVals[id]) !== JSON.stringify(k.value)) modificados++;
            });
        });

        setKpi('kpi-secciones', totalSecciones);
        setKpi('kpi-parametros', totalParametros);
        setKpi('kpi-modificados', modificados);
        setKpi('kpi-estado', _configData.exists ? 'OK' : 'Falta');

        var estadoCard = document.getElementById('kpi-estado');
        if (estadoCard) estadoCard.style.color = _configData.exists ? 'var(--success)' : 'var(--danger)';

        var modCard = document.getElementById('kpi-modificados');
        if (modCard) modCard.style.color = modificados > 0 ? 'var(--warning)' : 'var(--text-900)';
    }

    function setKpi(id, value) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = value;
        el.classList.remove('loading');
    }

    // =========================================================================
    // FILTROS RÁPIDOS (mismo patrón que comunidad.js)
    // =========================================================================
    function updateFilterBadge() {
        var count = 0;
        if (_activeChip && _activeChip !== 'all') count++;
        if (_seccionFiltro) count++;
        if (_searchText) count++;
        var badge = document.getElementById('active-filter-badge');
        if (!badge) return;
        if (count > 0) {
            document.getElementById('active-filter-count').textContent = count;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    function applyQuickFilters() {
        renderSections();
        updateFilterBadge();
        renderPagerSummary();
    }
    window.applyQuickFilters = applyQuickFilters;

    function setChip(btn) {
        document.querySelectorAll('.chip[data-filter]').forEach(function(c){ c.classList.remove('active'); });
        btn.classList.add('active');
        _activeChip = btn.dataset.filter;
        applyQuickFilters();
    }
    window.setChip = setChip;

    function clearSearch() {
        var input = document.getElementById('filter-search');
        if (input) input.value = '';
        _searchText = '';
        var clearBtn = document.getElementById('clear-search');
        if (clearBtn) clearBtn.classList.remove('visible');
        applyQuickFilters();
    }
    window.clearSearch = clearSearch;

    var _searchTimer;
    $('#filter-search').on('input', function() {
        _searchText = this.value.trim();
        var clearBtn = document.getElementById('clear-search');
        if (clearBtn) clearBtn.classList.toggle('visible', _searchText.length > 0);
        clearTimeout(_searchTimer);
        _searchTimer = setTimeout(function() {
            applyQuickFilters();
        }, 220);
    });

    $('#filter-seccion').on('change', function() {
        _seccionFiltro = this.value;
        applyQuickFilters();
    });

    function renderPagerSummary() {
        var info = document.getElementById('pager-info');
        var ctrl = document.getElementById('pager-controls');
        if (!info || !_configData) return;

        var totalSecciones = (_configData.sections || []).length;
        var totalParametros = 0;
        var visibleParametros = 0;
        (_configData.sections || []).forEach(function(sec) {
            sec.keys.forEach(function(item) {
                totalParametros++;
                if (matchesFilters(sec.name, item)) visibleParametros++;
            });
        });

        if (totalParametros === 0) {
            info.textContent = 'Sin parámetros';
        } else if (visibleParametros === totalParametros) {
            info.textContent = totalParametros + ' parámetros en ' + totalSecciones + ' secciones';
        } else {
            info.textContent = visibleParametros + ' de ' + totalParametros + ' parámetros (filtrados)';
        }
        if (ctrl) ctrl.innerHTML = '';
    }

    // =========================================================================
    // COLAPSAR / EXPANDIR SECCIÓN
    // =========================================================================
    function toggleSection(headerEl) {
        var card = headerEl.closest('.config-section-card');
        if (!card) return;
        var name = card.dataset.section;
        var collapsed = card.classList.toggle('collapsed');
        _collapsedSections[name] = collapsed;
    }
    window.toggleSection = toggleSection;

    // =========================================================================
    // PANEL DE DETALLE LATERAL
    // =========================================================================
    function showFieldDetail(sectionName, key) {
        var sec = _configData.sections.find(function(s) { return s.name === sectionName; });
        var item = sec && sec.keys.find(function(k) { return k.key === key; });
        if (!item) return;

        _selectedField = { sectionName: sectionName, key: key, type: item.type, value: item.value, raw: item.raw };

        var av = document.getElementById('dp-avatar');
        if (av) av.innerHTML = '<i class="fas ' + (TYPE_ICONS[item.type] || 'fa-font') + '"></i>';

        var nameEl = document.getElementById('dp-name');
        if (nameEl) nameEl.textContent = key;

        var codigoEl = document.getElementById('dp-codigo');
        if (codigoEl) codigoEl.textContent = sectionName;

        var ciudadEl = document.getElementById('dp-ciudad');
        if (ciudadEl) ciudadEl.textContent = TYPE_LABELS[item.type] || 'Texto';

        var tipoEl = document.getElementById('dp-kpi-inm');
        if (tipoEl) tipoEl.textContent = TYPE_LABELS[item.type] || 'Texto';

        var estadoEl = document.getElementById('dp-kpi-inc');
        if (estadoEl) {
            var modified = isFieldModified(sectionName, key, item.value);
            estadoEl.textContent = modified ? 'Modificado' : 'Original';
            estadoEl.style.color = modified ? 'var(--warning)' : 'var(--success)';
        }

        renderDpTab(_activeDpTab, _selectedField);
        document.getElementById('detail-panel').classList.add('visible');

        document.querySelectorAll('.config-field-row').forEach(function(r){ r.classList.remove('row-selected'); });
        var rowEl = document.querySelector('.config-field-row[data-section="' + cssEscape(sectionName) + '"][data-key="' + cssEscape(key) + '"]');
        if (rowEl) rowEl.classList.add('row-selected');
    }
    window.showFieldDetail = showFieldDetail;

    function closePanel() {
        document.getElementById('detail-panel').classList.remove('visible');
        _selectedField = null;
        document.querySelectorAll('.config-field-row').forEach(function(r){ r.classList.remove('row-selected'); });
    }
    window.closePanel = closePanel;

    function switchDpTab(btn) {
        document.querySelectorAll('.dp-tab').forEach(function(t){ t.classList.remove('active'); });
        btn.classList.add('active');
        _activeDpTab = btn.dataset.tab;
        if (_selectedField) renderDpTab(_activeDpTab, _selectedField);
    }
    window.switchDpTab = switchDpTab;

    function dpRow(icon, label, value, accent) {
        return '<div class="dp-row">'
            + '<span class="dp-label"><i class="fas fa-' + icon + '"></i>' + escapeHtml(label) + '</span>'
            + '<span class="dp-value' + (accent ? ' accent' : '') + '">' + escapeHtml(String(value === '' || value === null || value === undefined ? '–' : value)) + '</span>'
            + '</div>';
    }

    function dpSection(title) {
        return '<div class="dp-section"><div class="dp-section-title">' + title + '</div></div>';
    }

    function renderDpTab(tab, f) {
        var body = document.getElementById('dp-body');
        if (!body || !f) return;

        if (tab === 'info') {
            body.innerHTML =
                dpSection('Identificación')
              + dpRow('layer-group', 'Sección', f.sectionName)
              + dpRow('key', 'Clave', f.key)
              + dpRow('tag', 'Tipo', TYPE_LABELS[f.type] || 'Texto')
              + dpSection('Valor actual')
              + dpRow('pen', 'Valor', f.value, true)
              + dpRow('circle-check', 'Estado', isFieldModified(f.sectionName, f.key, f.value) ? 'Modificado (sin guardar)' : 'Sin cambios');
        } else if (tab === 'notas') {
            var line = f.key + ' = ' + (f.value === null || f.value === undefined ? '' : f.value);
            body.innerHTML = '<div style="background:var(--bg-subtle);border:1px solid var(--border);border-radius:var(--r-md);padding:14px;font-family:var(--font-mono);font-size:12px;line-height:1.7;white-space:pre-wrap;color:var(--text-700)">'
                + '<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin-bottom:8px;font-family:var(--font-body)"><i class="fas fa-code" style="margin-right:6px"></i>Representación .ini</div>'
                + '[' + escapeHtml(f.sectionName) + ']\n' + escapeHtml(line)
                + '</div>';
        }
    }

    // =========================================================================
    // BARRA FLOTANTE DE CAMBIOS SIN GUARDAR
    // =========================================================================
    function renderFloatingBar() {
        var existing = document.getElementById('config-floating-bar');
        var changed = hasUnsavedChanges();

        if (!existing) {
            var pager = document.getElementById('pager');
            var bar = document.createElement('div');
            bar.id = 'config-floating-bar';
            bar.className = 'config-floating-bar hidden';
            bar.innerHTML = '<span><i class="fas fa-triangle-exclamation"></i> Tienes cambios sin guardar</span>'
                + '<span class="cfb-actions">'
                + '<button type="button" onclick="reloadConfig()">Descartar</button>'
                + '<button type="button" class="primary" onclick="saveConfig()">Guardar cambios</button>'
                + '</span>';
            pager.parentNode.insertBefore(bar, pager);
            existing = bar;
        }
        existing.classList.toggle('hidden', !changed);

        var saveBtn = document.getElementById('btn-guardar');
        if (saveBtn) saveBtn.classList.toggle('has-changes', changed);
    }

    // =========================================================================
    // GUARDAR
    // =========================================================================
    function saveConfig() {
        if (!_configData) return;
        if (!hasUnsavedChanges()) {
            handleSuccess('No hay cambios que guardar', 1800);
            return;
        }

        var payload = {
            sections: _configData.sections.map(function(sec) {
                return {
                    name: sec.name,
                    keys: sec.keys.map(function(k) {
                        return { key: k.key, value: k.value, type: k.type };
                    })
                };
            })
        };

        showLoading('Guardando config.ini...');
        $.ajax({
            url: URLS.configSave,
            method: 'POST',
            contentType: 'application/json',
            headers: { 'X-CSRFToken': getCsrfToken() },
            data: JSON.stringify(payload)
        })
        .done(function(resp) {
            handleSuccess('Configuración guardada correctamente');
            _configData = resp;
            _originalSnapshot = snapshotValues(resp);
            renderAll();
        })
        .fail(function(xhr) {
            var msg = 'Error al guardar config.ini';
            try { var j = JSON.parse(xhr.responseText); if (j.detail) msg = j.detail; } catch(e) {}
            handleError(msg);
        })
        .always(function() { hideLoading(); });
    }
    window.saveConfig = saveConfig;

    // =========================================================================
    // RECARGAR (descarta cambios no guardados)
    // =========================================================================
    function reloadConfig() {
        if (hasUnsavedChanges()) {
            var ok = window.confirm('Hay cambios sin guardar. ¿Recargar desde disco y descartarlos?');
            if (!ok) return;
        }
        showLoading('Recargando config.ini...');
        $.ajax({
            url: URLS.configReload,
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
        .done(function(data) {
            _configData = data;
            _originalSnapshot = snapshotValues(data);
            _selectedField = null;
            document.getElementById('detail-panel').classList.remove('visible');
            renderAll();
            handleSuccess('Datos recargados', 1800);
        })
        .fail(function(xhr) {
            var msg = 'Error al recargar config.ini';
            try { var j = JSON.parse(xhr.responseText); if (j.detail) msg = j.detail; } catch(e) {}
            handleError(msg);
        })
        .always(function() { hideLoading(); });
    }
    window.reloadConfig = reloadConfig;

    // Aviso al salir si hay cambios sin guardar
    window.addEventListener('beforeunload', function(e) {
        if (hasUnsavedChanges()) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    // =========================================================================
    // DENSITY MODE (idéntico al patrón canónico)
    // =========================================================================
    function setDensity(btn) {
        document.querySelectorAll('.density-btn').forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        var d = btn.dataset.d || '';
        document.body.classList.remove('density-compact','density-comfortable');
        if (d) document.body.classList.add(d);
        localStorage.setItem('cu2home_density_config', d);
    }
    window.setDensity = setDensity;

    (function initDensity() {
        var saved = localStorage.getItem('cu2home_density_config') || 'density-compact';
        if (saved) document.body.classList.add(saved);
        document.querySelectorAll('.density-btn').forEach(function(b){ b.classList.toggle('active', (b.dataset.d||'') === saved); });
    })();

    // =========================================================================
    // INICIALIZACIÓN
    // =========================================================================
    fetchConfig();
});
