import os
import re
import logging
from datetime import datetime, timedelta
from collections import Counter

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required

from .models import LogFilterPreset

logger = logging.getLogger(__name__)

# Regex para parsear lineas de log en formato:
# LEVEL asctime module message
# Ejemplo: INFO 2024-01-15 10:30:00,123 myapp.views Hola mundo
LOG_PATTERN = re.compile(
    r'^(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+'
    r'(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+'
    r'(?P<module>\S+)\s+'
    r'(?P<message>.*)$'
)

LOG_LEVEL_ORDER = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
LOG_LEVEL_COLORS = {
    'DEBUG': '#6B7280',
    'INFO': '#3B82F6',
    'WARNING': '#F59E0B',
    'ERROR': '#EF4444',
    'CRITICAL': '#7C3AED',
}
LOG_LEVEL_BG = {
    'DEBUG': '#F3F4F6',
    'INFO': '#EFF6FF',
    'WARNING': '#FFFBEB',
    'ERROR': '#FEF2F2',
    'CRITICAL': '#F5F3FF',
}


def _get_log_file_path():
    """Devuelve la ruta al archivo de log activo."""
    return getattr(settings, 'LOG_FILE', None) or os.path.join(settings.BASE_DIR, 'logs', 'cu2home.log')


def _parse_log_line(line):
    """Intenta parsear una linea de log. Si falla, la devuelve como raw."""
    line = line.strip()
    if not line:
        return None
    match = LOG_PATTERN.match(line)
    if match:
        return {
            'level': match.group('level'),
            'timestamp': match.group('timestamp'),
            'module': match.group('module'),
            'message': match.group('message'),
            'raw': line,
            'parsed': True,
        }
    # Fallback: intentar detectar nivel al inicio
    for level in LOG_LEVEL_ORDER:
        if line.startswith(level):
            return {
                'level': level,
                'timestamp': '',
                'module': '',
                'message': line[len(level):].strip(),
                'raw': line,
                'parsed': False,
            }
    return {
        'level': 'UNKNOWN',
        'timestamp': '',
        'module': '',
        'message': line,
        'raw': line,
        'parsed': False,
    }


def _read_log_lines(path, max_lines=5000):
    """Lee las ultimas N lineas del archivo de log."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            return lines[-max_lines:] if len(lines) > max_lines else lines
    except Exception as e:
        logger.error(f"Error leyendo log {path}: {e}")
        return []


@staff_member_required
def visor(request):
    """Vista principal del visor de logs."""
    log_path = _get_log_file_path()
    log_exists = os.path.exists(log_path)
    log_size = os.path.getsize(log_path) if log_exists else 0

    stats = {}
    if log_exists and log_size > 0:
        lines = _read_log_lines(log_path, max_lines=2000)
        parsed = [_parse_log_line(l) for l in lines if l.strip()]
        levels = [p['level'] for p in parsed if p]
        stats = dict(Counter(levels))
        stats['total_lines'] = len(lines)
        stats['total_parsed'] = len([p for p in parsed if p.get('parsed')])

    context = {
        'log_path': str(log_path),
        'log_exists': log_exists,
        'log_size': log_size,
        'log_size_human': _human_readable_size(log_size),
        'stats': stats,
        'level_colors': LOG_LEVEL_COLORS,
        'level_bg': LOG_LEVEL_BG,
        'presets': LogFilterPreset.objects.all()[:10],
    }
    return render(request, 'visor/visor.html', context)


@staff_member_required
def visor_api(request):
    """API JSON para cargar logs con filtros y paginacion."""
    log_path = _get_log_file_path()
    if not os.path.exists(log_path):
        return JsonResponse({
            'lines': [],
            'total': 0,
            'page': 1,
            'total_pages': 0,
            'error': _('Archivo de log no encontrado')
        })

    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 100)), 500)
    level_filter = request.GET.get('level', '')
    search = request.GET.get('search', '').strip().lower()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    module_filter = request.GET.get('module', '').strip().lower()

    raw_lines = _read_log_lines(log_path, max_lines=5000)
    parsed_lines = []
    for line in raw_lines:
        p = _parse_log_line(line)
        if p:
            parsed_lines.append(p)

    filtered = []
    for entry in parsed_lines:
        if level_filter and entry['level'] != level_filter:
            continue
        if search and search not in entry['raw'].lower():
            continue
        if module_filter and module_filter not in entry['module'].lower():
            continue
        if date_from or date_to:
            ts = entry.get('timestamp', '')
            if ts:
                try:
                    entry_date = datetime.strptime(ts[:10], '%Y-%m-%d').date()
                    if date_from:
                        if entry_date < datetime.strptime(date_from, '%Y-%m-%d').date():
                            continue
                    if date_to:
                        if entry_date > datetime.strptime(date_to, '%Y-%m-%d').date():
                            continue
                except ValueError:
                    pass
        filtered.append(entry)

    def _sort_key(entry):
        ts = entry.get('timestamp', '')
        if ts:
            try:
                ts_clean = ts.replace(',', '.')
                return datetime.strptime(ts_clean[:19], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return datetime.min

    filtered.sort(key=_sort_key, reverse=True)

    total = len(filtered)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    page_lines = filtered[start:end]

    return JsonResponse({
        'lines': page_lines,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'filters': {
            'level': level_filter,
            'search': search,
            'date_from': date_from,
            'date_to': date_to,
            'module': module_filter,
        }
    })


@staff_member_required
def visor_stats_api(request):
    """API JSON con estadisticas de los logs."""
    log_path = _get_log_file_path()
    if not os.path.exists(log_path):
        return JsonResponse({'error': _('Archivo de log no encontrado'), 'stats': {}})

    lines = _read_log_lines(log_path, max_lines=5000)
    parsed = [_parse_log_line(l) for l in lines if l.strip()]
    levels = [p['level'] for p in parsed if p]
    stats = dict(Counter(levels))
    stats['total_lines'] = len(lines)
    stats['total_parsed'] = len([p for p in parsed if p.get('parsed')])

    now = datetime.now()
    last_24h = now - timedelta(hours=24)
    timeline = {}
    for entry in parsed:
        ts = entry.get('timestamp', '')
        if not ts:
            continue
        try:
            ts_clean = ts.replace(',', '.')
            dt = datetime.strptime(ts_clean[:19], '%Y-%m-%d %H:%M:%S')
            if dt >= last_24h:
                hour_key = dt.strftime('%H:00')
                if hour_key not in timeline:
                    timeline[hour_key] = {'DEBUG': 0, 'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'CRITICAL': 0}
                if entry['level'] in timeline[hour_key]:
                    timeline[hour_key][entry['level']] += 1
        except ValueError:
            continue

    sorted_timeline = {k: timeline[k] for k in sorted(timeline.keys())}

    return JsonResponse({
        'stats': stats,
        'timeline': sorted_timeline,
        'level_colors': LOG_LEVEL_COLORS,
    })


@staff_member_required
def visor_download(request):
    """Descarga el archivo de log completo."""
    log_path = _get_log_file_path()
    if not os.path.exists(log_path):
        return HttpResponseBadRequest(_('Archivo de log no encontrado'))

    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    response = HttpResponse(content, content_type='text/plain')
    filename = f"cu2home_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@staff_member_required
def visor_clear(request):
    """Vacía el contenido del archivo de log."""
    if request.method != 'POST':
        return JsonResponse({'error': _('Metodo no permitido')}, status=405)

    log_path = _get_log_file_path()
    if not os.path.exists(log_path):
        return JsonResponse({'error': _('Archivo de log no encontrado')}, status=404)

    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('')
        logger.info('visor.views Log file cleared by user %s', request.user.username)
        return JsonResponse({
            'success': True,
            'message': _('Archivo de log vaciado correctamente')
        })
    except Exception as e:
        logger.error('Error clearing log file: %s', e, exc_info=True)
        return JsonResponse({
            'error': _('Error al vaciar el archivo de log'),
            'detail': str(e)
        }, status=500)


def _human_readable_size(size_bytes):
    """Convierte bytes a formato legible."""
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
