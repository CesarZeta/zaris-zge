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


async def leer_limite(db: AsyncSession) -> dict | None:
    fila = (await db.execute(text(
        "SELECT valor FROM configuracion_general WHERE clave = :c AND activo = TRUE"
    ), {"c": CLAVE})).fetchone()
    if not fila or not (fila.valor or "").strip():
        return None
    try:
        geo = _validar(json.loads(fila.valor))
    except (ValueError, TypeError):
        geo = None
    if geo is None:
        logger.warning("%s invalido en configuracion_general: se ignora", CLAVE)
    return geo


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
