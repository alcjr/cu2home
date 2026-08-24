# -*- coding: utf-8 -*-
"""
apps/config/views.py
------------------------------------------------------------------
Vistas para visualizar y editar el archivo config.ini situado en la
raíz del proyecto (\\cu2home\\config.ini).

Expone:
    GET  /config/                 -> render de config.html
    GET  /config/api/config/      -> JSON con secciones/claves/valores
    POST /config/api/config/save/   -> guarda cambios recibidos en JSON
    POST /config/api/config/reload/ -> recarga el archivo desde disco (descarta cambios no guardados)

El parser usado es configparser (stdlib). Se preserva el orden de
secciones/claves tal y como existan en el fichero original.

Acceso restringido a superusuarios (mismo patrón que dashboard/visor,
vía apps.core.decorators.superuser_required). No se usan permisos de
Django tipo "config.view_config" porque esta app no tiene modelo
propio y esos permisos no existirían nunca en la base de datos.
------------------------------------------------------------------
"""

import configparser
import json
import os
import shutil
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.core.decorators import superuser_required


# ------------------------------------------------------------------
# Ruta al config.ini en la raíz del proyecto.
# Ajustar si BASE_DIR no apunta directamente a la raíz del repo.
# ------------------------------------------------------------------
CONFIG_INI_PATH = os.path.join(settings.BASE_DIR, "config.ini")


# ------------------------------------------------------------------
# Heurística de tipado: a partir del string crudo del .ini, infiere
# si el campo es boolean / integer / float / string para que el
# frontend pueda renderizar el editor adecuado (checkbox, number, text)
# ------------------------------------------------------------------
BOOLEAN_TRUE = {"1", "true", "yes", "on", "si", "sí"}
BOOLEAN_FALSE = {"0", "false", "no", "off"}


def _infer_type(raw_value: str) -> str:
    v = (raw_value or "").strip().lower()
    if v in BOOLEAN_TRUE or v in BOOLEAN_FALSE:
        return "boolean"
    try:
        int(raw_value)
        return "integer"
    except (TypeError, ValueError):
        pass
    try:
        float(raw_value)
        return "float"
    except (TypeError, ValueError):
        pass
    return "string"


def _coerce_for_display(raw_value: str, field_type: str):
    if field_type == "boolean":
        return (raw_value or "").strip().lower() in BOOLEAN_TRUE
    if field_type == "integer":
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return raw_value
    if field_type == "float":
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return raw_value
    return raw_value


def _coerce_for_storage(value, field_type: str) -> str:
    """Convierte el valor recibido del frontend (JSON) a string para el .ini"""
    if field_type == "boolean":
        return "true" if value in (True, "true", "True", "1", 1) else "false"
    if field_type in ("integer", "float"):
        return str(value)
    return "" if value is None else str(value)


def _read_config_structured():
    """
    Lee config.ini y devuelve una estructura serializable:
    {
        "path": "...",
        "exists": true,
        "last_modified": "2026-06-21T10:32:00",
        "sections": [
            {
                "name": "DATABASE",
                "keys": [
                    {"key": "host", "value": "localhost", "type": "string", "raw": "localhost"},
                    ...
                ]
            },
            ...
        ]
    }
    """
    parser = configparser.ConfigParser()
    # preserve_case: ConfigParser por defecto pasa las claves a minúsculas.
    # Si el .ini usa mayúsculas/CamelCase en las claves, descomentar:
    # parser.optionxform = str

    exists = os.path.isfile(CONFIG_INI_PATH)
    sections = []

    if exists:
        # Usamos encoding utf-8 explícito para evitar problemas con
        # acentos/ñ en Windows.
        parser.read(CONFIG_INI_PATH, encoding="utf-8")
        for section_name in parser.sections():
            keys = []
            for key, raw_value in parser.items(section_name):
                field_type = _infer_type(raw_value)
                keys.append({
                    "key": key,
                    "raw": raw_value,
                    "value": _coerce_for_display(raw_value, field_type),
                    "type": field_type,
                })
            sections.append({"name": section_name, "keys": keys})

    last_modified = None
    if exists:
        ts = os.path.getmtime(CONFIG_INI_PATH)
        last_modified = datetime.fromtimestamp(ts).isoformat()

    return {
        "path": CONFIG_INI_PATH,
        "exists": exists,
        "last_modified": last_modified,
        "sections": sections,
    }


# ------------------------------------------------------------------
# VISTA DE PÁGINA
# ------------------------------------------------------------------
@superuser_required
def config(request):
    """Renderiza la plantilla config.html. Los datos se cargan vía AJAX."""
    return render(request, 'config/config.html', {})


# ------------------------------------------------------------------
# API: LEER CONFIG
# ------------------------------------------------------------------
@superuser_required
@require_GET
def config_api_get(request):
    try:
        data = _read_config_structured()
        return JsonResponse(data, status=200)
    except Exception as exc:
        return JsonResponse({"detail": f"Error al leer config.ini: {exc}"}, status=500)


# ------------------------------------------------------------------
# API: GUARDAR CONFIG
# ------------------------------------------------------------------
@superuser_required
@require_POST
def config_api_save(request):
    """
    Espera un payload JSON con la forma:
    {
        "sections": [
            {"name": "DATABASE", "keys": [{"key": "host", "value": "localhost", "type": "string"}, ...]},
            ...
        ]
    }
    Reescribe config.ini completo. Se crea una copia de seguridad
    .bak antes de sobrescribir.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    sections = payload.get("sections")
    if not isinstance(sections, list):
        return JsonResponse({"detail": "Formato de payload incorrecto: se esperaba 'sections'"}, status=400)

    # Backup antes de sobrescribir
    if os.path.isfile(CONFIG_INI_PATH):
        backup_path = CONFIG_INI_PATH + ".bak"
        try:
            shutil.copy2(CONFIG_INI_PATH, backup_path)
        except OSError as exc:
            return JsonResponse({"detail": f"No se pudo crear backup: {exc}"}, status=500)

    parser = configparser.ConfigParser()
    # parser.optionxform = str  # descomentar si se quiere preservar mayúsculas en claves

    try:
        for section in sections:
            section_name = section.get("name")
            if not section_name:
                continue
            parser.add_section(section_name)
            for item in section.get("keys", []):
                key = item.get("key")
                if not key:
                    continue
                field_type = item.get("type", "string")
                value = item.get("value")
                parser.set(section_name, key, _coerce_for_storage(value, field_type))

        tmp_path = CONFIG_INI_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            parser.write(f)
        os.replace(tmp_path, CONFIG_INI_PATH)

    except Exception as exc:
        return JsonResponse({"detail": f"Error al guardar config.ini: {exc}"}, status=500)

    data = _read_config_structured()
    return JsonResponse({"detail": "Configuración guardada correctamente", **data}, status=200)


# ------------------------------------------------------------------
# API: RECARGAR (descarta cambios no guardados, vuelve a leer disco)
# ------------------------------------------------------------------
@superuser_required
@require_POST
def config_api_reload(request):
    try:
        data = _read_config_structured()
        return JsonResponse(data, status=200)
    except Exception as exc:
        return JsonResponse({"detail": f"Error al recargar config.ini: {exc}"}, status=500)
