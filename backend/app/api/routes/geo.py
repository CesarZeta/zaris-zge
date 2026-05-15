"""
ZARIS API — Endpoints de geolocalización.
Prefijo: /api/v1/geo/

Provee:
- Catálogos provincias / partidos / localidades (DB local).
- Proxy a Nominatim (OSM) para geocoding directo e inverso, respetando la
  política de uso de Nominatim: max 1 req/s, User-Agent identificable.
"""
import asyncio
import logging
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/geo", tags=["Geo"])
logger = logging.getLogger("zaris.geo")

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
NOMINATIM_UA = "ZARIS-API/1.0 (cesar@zaris.dev)"
NOMINATIM_TIMEOUT = 8.0
_NOMINATIM_LOCK = asyncio.Lock()
_NOMINATIM_LAST_CALL = 0.0
_NOMINATIM_MIN_INTERVAL = 1.05  # margen sobre el 1 req/s


async def _nominatim_get(path: str, params: dict) -> list | dict:
    """GET a Nominatim respetando rate-limit global de la app."""
    global _NOMINATIM_LAST_CALL
    async with _NOMINATIM_LOCK:
        delta = time.monotonic() - _NOMINATIM_LAST_CALL
        if delta < _NOMINATIM_MIN_INTERVAL:
            await asyncio.sleep(_NOMINATIM_MIN_INTERVAL - delta)
        try:
            async with httpx.AsyncClient(timeout=NOMINATIM_TIMEOUT) as client:
                r = await client.get(
                    f"{NOMINATIM_BASE}{path}",
                    params=params,
                    headers={"User-Agent": NOMINATIM_UA, "Accept-Language": "es"},
                )
        finally:
            _NOMINATIM_LAST_CALL = time.monotonic()
    if r.status_code != 200:
        logger.warning("Nominatim %s -> HTTP %s", path, r.status_code)
        raise HTTPException(status_code=502, detail="Servicio de geocoding no disponible")
    return r.json()


# ── Catálogos DB ─────────────────────────────────────────────────────────────

@router.get("/provincias")
async def listar_provincias(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    r = await db.execute(text(
        "SELECT id_provincia, nombre, iso_code FROM provincias "
        "WHERE activo = TRUE ORDER BY nombre"
    ))
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/partidos")
async def listar_partidos(
    id_provincia: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if id_provincia:
        r = await db.execute(text(
            "SELECT id_partido, id_provincia, nombre FROM partidos "
            "WHERE activo = TRUE AND id_provincia = :ip ORDER BY nombre"
        ), {"ip": id_provincia})
    else:
        r = await db.execute(text(
            "SELECT id_partido, id_provincia, nombre FROM partidos "
            "WHERE activo = TRUE ORDER BY nombre"
        ))
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/localidades")
async def listar_localidades(
    id_partido: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="Filtro por nombre (ILIKE)"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    where = ["l.activo = TRUE"]
    params: dict = {"lim": limit}
    if id_partido:
        where.append("l.id_partido = :ip")
        params["ip"] = id_partido
    if q and q.strip():
        where.append("l.nombre ILIKE :q")
        params["q"] = f"%{q.strip()}%"
    sql = f"""
        SELECT l.id_localidad, l.id_partido, l.nombre, l.codigo_postal,
               p.nombre AS partido, p.id_provincia, pr.nombre AS provincia
        FROM localidades l
        JOIN partidos p ON p.id_partido = l.id_partido
        JOIN provincias pr ON pr.id_provincia = p.id_provincia
        WHERE {' AND '.join(where)}
        ORDER BY l.nombre
        LIMIT :lim
    """
    r = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


# ── Proxy Nominatim ──────────────────────────────────────────────────────────

@router.get("/buscar")
async def buscar_direccion(
    q: str = Query(..., min_length=3, description="Texto a geocodificar"),
    limit: int = Query(5, ge=1, le=10),
    solo_direcciones: bool = Query(
        False,
        description="Si True, excluye POIs (comercios, oficinas, etc.) y devuelve solo calles/edificios.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Geocoding directo: texto → candidatos con lat/lon.

    Cuando `solo_direcciones=True`, pasa `layer=address` a Nominatim y filtra el
    response para excluir resultados con `class` de POI (amenity/shop/office/etc.).
    Útil para formularios de domicilio: el ciudadano vive en una calle, no en
    un bar/oficina/local.
    """
    # Cuando solo_direcciones=True pedimos el máximo que Nominatim acepta (40)
    # porque algunas queries devuelven decenas de POIs antes de las calles
    # válidas. No usamos `layer=address` porque excluye `highway/secondary` que
    # sí son direcciones válidas (calle sin número exacto).
    upstream_limit = 40 if solo_direcciones else limit
    params: dict = {
        "q": q,
        "format": "json",
        "limit": str(upstream_limit),
        "countrycodes": "ar",
        "addressdetails": "1",
    }
    data = await _nominatim_get("/search", params)
    if not isinstance(data, list):
        return []

    # Filtros para `solo_direcciones=True`:
    # - class POI puro (amenity/shop/office/etc.) sin `road` válido → descarta.
    # - Resultados con `address.road` válido pero `display_name` que arranca con
    #   nombre de POI (ej. "Warner Chappell Music, 1351, Avenida Córdoba...") →
    #   se mantiene pero reescribimos `display_name` desde address para
    #   ocultar el nombre del comercio. El edificio puede alojar un comercio,
    #   pero la calle+altura sigue siendo la misma dirección postal.
    POI_CLASS_BLACKLIST = {
        "amenity", "shop", "office", "tourism", "leisure",
        "craft", "healthcare", "club", "emergency", "man_made",
    }

    def _es_pieza_de_direccion(d: dict) -> bool:
        """Tiene calle o lugar geográfico identificable → es candidato válido."""
        a = d.get("address") or {}
        return bool(
            a.get("road") or a.get("pedestrian") or a.get("footway")
            or a.get("cycleway") or a.get("path")
        )

    def _display_name_desde_address(d: dict) -> str:
        """Reconstruye un display_name limpio desde `address`, sin el nombre
        del POI/comercio que Nominatim a veces antepone."""
        a = d.get("address") or {}
        partes = []
        calle = a.get("road") or a.get("pedestrian") or a.get("footway") or ""
        hn = a.get("house_number")
        if calle:
            partes.append(f"{hn} {calle}" if hn else calle)
        loc = (a.get("suburb") or a.get("neighbourhood") or a.get("city")
               or a.get("town") or a.get("village"))
        if loc:
            partes.append(loc)
        # partido / departamento intermedio
        med = a.get("state_district") or a.get("city_district") or a.get("county")
        if med and med not in partes:
            partes.append(med)
        if a.get("state"):
            partes.append(a["state"])
        if a.get("postcode"):
            partes.append(a["postcode"])
        if a.get("country"):
            partes.append(a["country"])
        return ", ".join(partes) if partes else (d.get("display_name") or "")

    out = []
    for d in data:
        cls = d.get("class")
        typ = d.get("type")
        if solo_direcciones:
            tiene_calle = _es_pieza_de_direccion(d)
            # POI puro y sin calle reconocible → descartar.
            if cls in POI_CLASS_BLACKLIST and not tiene_calle:
                continue
            # POI con calle (ej. McDonalds tiene `road` en su address) → también
            # descartar: la búsqueda por el nombre del POI es lo que el usuario
            # NO quiere en un campo de domicilio.
            if cls in POI_CLASS_BLACKLIST:
                continue
            # Reescribir display_name si viene un nombre propio antes de la calle.
            display_name = d.get("display_name") or ""
            address = d.get("address") or {}
            calle_busqueda = (address.get("road") or address.get("pedestrian")
                              or address.get("footway") or "")
            arranca_con_calle = (
                display_name.lower().startswith(calle_busqueda.lower())
                or (address.get("house_number") and
                    display_name.lower().startswith(str(address["house_number"]).lower()))
            )
            if calle_busqueda and not arranca_con_calle:
                display_name = _display_name_desde_address(d)
            out.append({
                "display_name": display_name,
                "lat": float(d["lat"]) if d.get("lat") else None,
                "lon": float(d["lon"]) if d.get("lon") else None,
                "type": typ,
                "class": cls,
                "address": d.get("address") or {},
            })
        else:
            out.append({
                "display_name": d.get("display_name"),
                "lat": float(d["lat"]) if d.get("lat") else None,
                "lon": float(d["lon"]) if d.get("lon") else None,
                "type": typ,
                "class": cls,
                "address": d.get("address") or {},
            })
        if len(out) >= limit:
            break
    return out


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    current_user: dict = Depends(get_current_user),
):
    """Geocoding inverso: lat/lon → dirección normalizada."""
    data = await _nominatim_get("/reverse", {
        "lat": str(lat),
        "lon": str(lon),
        "format": "json",
        "addressdetails": "1",
    })
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="Sin resultados")
    return {
        "display_name": data.get("display_name"),
        "address": data.get("address") or {},
        "lat": float(data["lat"]) if data.get("lat") else lat,
        "lon": float(data["lon"]) if data.get("lon") else lon,
    }
