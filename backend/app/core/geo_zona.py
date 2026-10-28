"""Zona de búsqueda de direcciones de un municipio (claves geo_bbox_* de configuracion_general).

Los mismos rangos que acepta el geocoding (`routes/geo.py::_bbox_municipio`): fuera de ellos el
buscador responde 409 «sin zona». Validar al guardar evita que una clave mal cargada (por ejemplo,
«lat, lon» pegado de Google Maps en la latitud) quede guardada y rompa el buscador sin avisar.
"""
from typing import Optional

CLAVES_ZONA = ("geo_bbox_centro_lat", "geo_bbox_centro_lon", "geo_bbox_delta_grados")

_RANGOS = {
    "geo_bbox_centro_lat": (-90.0, 90.0, "La latitud tiene que ser un número entre -90 y 90"),
    "geo_bbox_centro_lon": (-180.0, 180.0, "La longitud tiene que ser un número entre -180 y 180"),
    "geo_bbox_delta_grados": (0.0, 5.0, "El radio tiene que ser un número mayor que 0 y hasta 5"),
}

SIN_ZONA_BUSQUEDA = ("la zona de búsqueda no está completa: el buscador de direcciones no va a funcionar "
                     "hasta que se carguen latitud, longitud y radio en Configuración → Sistema")


def problema_valor_zona(clave: str, valor: Optional[str]) -> Optional[str]:
    """Por qué `valor` no sirve para `clave`, o None si sirve. Vacío vale: es «sin cargar»."""
    if clave not in _RANGOS or valor is None or str(valor).strip() == "":
        return None
    minimo, maximo, mensaje = _RANGOS[clave]
    try:
        n = float(str(valor).strip())
    except ValueError:
        return mensaje
    if clave == "geo_bbox_delta_grados":
        return None if minimo < n <= maximo else mensaje
    return None if minimo <= n <= maximo else mensaje


def zona_completa(valores: dict) -> bool:
    """Las tres claves cargadas y válidas: lo que el geocoding necesita para buscar."""
    return all((valores.get(c) or "").strip() and problema_valor_zona(c, valores.get(c)) is None
               for c in CLAVES_ZONA)
