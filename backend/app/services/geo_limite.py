"""
Limite geografico del municipio (mig 111): clave `geo_limite_geojson` de
configuracion_general con un GeoJSON Polygon (coordenadas [lon, lat]).

Fuente unica para el mapa del inicio (dashboard.py la devuelve como capa) y
para el generador demo (descarta puntos fuera del contorno). Fail-closed:
clave ausente, vacia o con basura -> None, y los consumidores siguen sin capa
ni recorte en vez de romper.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_municipio import leer_config, leer_configs
from app.core.geo_zona import CLAVES_ZONA, zona_completa

logger = logging.getLogger(__name__)

CLAVE = "geo_limite_geojson"


def _validar(geo: Any) -> dict | None:
    """Acepta solo un Polygon con anillo exterior de >= 4 pares numericos."""
    if not isinstance(geo, dict) or geo.get("type") != "Polygon":
        return None
    anillos = geo.get("coordinates")
    if not isinstance(anillos, list) or not anillos:
        return None
    for anillo in anillos:
        if not isinstance(anillo, list) or len(anillo) < 4:
            return None
        for par in anillo:
            if (not isinstance(par, list) or len(par) != 2
                    or not all(isinstance(v, (int, float)) for v in par)):
                return None
    return geo


async def leer_limite(db: AsyncSession, id_municipio: int) -> dict | None:
    """Contorno del municipio (GeoJSON Polygon validado) o None si falta o es inválido."""
    valor = await leer_config(db, CLAVE, id_municipio)
    if not (valor or "").strip():
        return None
    try:
        geo = _validar(json.loads(valor))
    except (ValueError, TypeError):
        geo = None
    if geo is None:
        logger.warning("%s invalido en configuracion_general: se ignora", CLAVE)
    return geo


# Encuadre de un país cuando el municipio no tiene contorno ni zona de búsqueda. Nunca Vicente
# López ni ningún otro municipio (César, 2026-10-28). Hoy solo Argentina da de alta municipios; un
# país sin fila acá cae a Argentina.
ENCUADRE_PAIS = {"AR": {"sur": -55.1, "oeste": -73.6, "norte": -21.7, "este": -53.6}}


async def encuadre_municipio(db: AsyncSession, id_municipio: int) -> dict:
    """Recuadro donde arrancan los mapas del municipio: el contorno; si no hay, la zona de búsqueda
    (Configuración → Sistema); si tampoco, el país. `origen` dice de cuál de los tres salió."""
    limite = await leer_limite(db, id_municipio)
    if limite:
        anillo = limite["coordinates"][0]
        return {"sur": min(p[1] for p in anillo), "oeste": min(p[0] for p in anillo),
                "norte": max(p[1] for p in anillo), "este": max(p[0] for p in anillo), "origen": "contorno"}
    zona = await leer_configs(db, list(CLAVES_ZONA), id_municipio)
    if zona_completa(zona):
        lat, lon, delta = (float(zona[c]) for c in CLAVES_ZONA)
        return {"sur": lat - delta, "oeste": lon - delta, "norte": lat + delta, "este": lon + delta, "origen": "zona"}
    pais = await db.scalar(text("SELECT codigo_pais FROM municipios WHERE id_municipio = :m"), {"m": id_municipio})
    return {**ENCUADRE_PAIS.get(pais or "AR", ENCUADRE_PAIS["AR"]), "origen": "pais"}


def punto_en_limite(geo: dict, lat: float, lon: float) -> bool:
    """Ray casting sobre el anillo exterior menos los huecos (regla par-impar)."""
    dentro = False
    for anillo in geo["coordinates"]:
        n = len(anillo)
        j = n - 1
        for i in range(n):
            xi, yi = anillo[i]
            xj, yj = anillo[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                dentro = not dentro
            j = i
    return dentro
