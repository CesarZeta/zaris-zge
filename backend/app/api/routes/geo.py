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
import unicodedata
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.auth import get_current_user
from app.core.config_municipio import leer_configs
from app.core.geo_zona import CLAVES_ZONA, zona_completa
from app.core.municipio import municipio_actual
from app.services.geo_limite import encuadre_municipio

router = APIRouter(prefix="/api/v1/geo", tags=["Geo"])
logger = logging.getLogger("zaris.geo")

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
NOMINATIM_UA = "ZARIS-API/1.0 (cesar@zaris.dev)"
NOMINATIM_TIMEOUT = 8.0
_NOMINATIM_LOCK = asyncio.Lock()
_NOMINATIM_LAST_CALL = 0.0
_NOMINATIM_MIN_INTERVAL = 1.05  # margen sobre el 1 req/s

# Sesgo geográfico del geocoding (regla de diseño §23, pedido del usuario
# 2026-06-11): el municipio opera en una zona acotada — una búsqueda de
# "Avenida Maipú" NO debe traer la de Mendoza. Restringimos los resultados a
# un bounding box centrado en el municipio (± ~28 km: cubre el partido, CABA
# y los partidos linderos; el operador puede cargar direcciones cercanas de
# la otra jurisdicción). Aplica a TODOS los consumidores porque viven sobre
# `geocodificar_direccion`.
#
# Desde mig 87 el bbox es CONFIGURABLE en `configuracion_general` (claves
# geo_bbox_centro_lat / geo_bbox_centro_lon / geo_bbox_delta_grados, editables
# en Config → Sistema §41). Sin las tres claves válidas, CUALQUIER municipio
# recibe 409: no hay respaldo con la zona de otro municipio (César, 2026-10-28;
# hasta entonces San Andrés caía a constantes de Vicente López). Se leen con
# cache TTL 5 min (la función corre también desde routers públicos sin sesión
# DB inyectada → sesión propia).
SIN_ZONA = "El municipio no tiene configurada su zona de búsqueda: cargala en Configuración → Sistema."
_BBOX_TTL_SEG = 300.0
# Cache por municipio (IT-01, R9): con la clave sin municipio, B usaría el bbox de A.
_bbox_cache: dict[int, dict] = {}


async def _bbox_municipio(id_municipio: int) -> tuple[float, float, float]:
    """(lat, lon, delta) del bbox del municipio, desde configuracion_general con cache.

    Sin las tres claves válidas (core/geo_zona.py), 409 para cualquier municipio: buscaría en la
    zona de otro sin avisar (guía de arranque, R4).
    """
    now = time.monotonic()
    cache = _bbox_cache.get(id_municipio)
    if cache and now - cache["ts"] < _BBOX_TTL_SEG:
        return cache["lat"], cache["lon"], cache["delta"]
    async with AsyncSessionLocal() as db:
        vals = await leer_configs(db, list(CLAVES_ZONA), id_municipio)
    if not zona_completa(vals):
        raise HTTPException(409, SIN_ZONA)
    lat, lon, delta = (float(vals[c]) for c in CLAVES_ZONA)
    _bbox_cache[id_municipio] = {"ts": now, "lat": lat, "lon": lon, "delta": delta}
    return lat, lon, delta


def invalidar_bbox(id_municipio: int) -> None:
    """La zona cambió (se guardó o se quitó el contorno): el próximo geocoding la vuelve a leer."""
    _bbox_cache.pop(id_municipio, None)


def _viewbox_municipio(lat: float, lon: float, delta: float) -> str:
    """Formato Nominatim: lon1,lat1,lon2,lat2 (dos esquinas opuestas)."""
    return f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"


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


# ── Encuadre de los mapas ────────────────────────────────────────────────────

@router.get("/encuadre", responses={200: {"description": "Recuadro inicial de los mapas: contorno, zona de búsqueda o país"}})
async def encuadre(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Dónde arrancan los mapas del municipio de la request (sur, oeste, norte, este y `origen`):
    contorno, zona de búsqueda o país. Ningún mapa arranca en un municipio fijo (César, 2026-10-28)."""
    return await encuadre_municipio(db, id_municipio)


# ── Catálogos DB ─────────────────────────────────────────────────────────────

@router.get("/paises")
async def listar_paises(
    para_alta: bool = Query(False, description="Solo los habilitados para dar de alta municipios"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Catálogo global de países (IT-01 F4) con el nombre de cada nivel (Provincia/Partido…)."""
    r = await db.execute(text(
        "SELECT codigo_pais, nombre, etiqueta_nivel_1, etiqueta_nivel_2, zona_horaria, habilitado_para_alta "
        "FROM paises WHERE activo = TRUE AND (NOT :alta OR habilitado_para_alta) ORDER BY nombre"
    ), {"alta": para_alta})
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/provincias")
async def listar_provincias(
    codigo_pais: Optional[str] = Query(None, pattern=r"^[A-Z]{2}$"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    r = await db.execute(text(
        "SELECT id_provincia, nombre, iso_code, codigo_pais FROM provincias "
        "WHERE activo = TRUE AND (CAST(:p AS text) IS NULL OR codigo_pais = :p) ORDER BY nombre"
    ), {"p": codigo_pais})
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/partidos")
async def listar_partidos(
    id_provincia: Optional[int] = Query(None, ge=1, le=2_147_483_647),
    q: Optional[str] = Query(None, max_length=100, description="Texto: cada palabra en el nombre o el nombre completo"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Por defecto 20 con q; sin q, todos"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Partidos / gobiernos locales activos (mig 132: con su código de Georef). Con `q`, para el
    autocompletar: una provincia puede tener cientos (Córdoba, 427)."""
    where = ["activo = TRUE"]
    params: dict = {}
    if id_provincia:
        where.append("id_provincia = :ip")
        params["ip"] = id_provincia
    # Sin distinguir tildes: «rio cuarto» encuentra «Río Cuarto» (sin depender de la extensión unaccent).
    sin_tildes = "translate(lower({}), 'áéíóúüñàèìòù', 'aeiouunaeiou')"
    for i, palabra in enumerate((q or "").split()):
        where.append(f"({sin_tildes.format('nombre')} LIKE {sin_tildes.format(f':p{i}')} "
                     f"OR {sin_tildes.format('nombre_completo')} LIKE {sin_tildes.format(f':p{i}')})")
        params[f"p{i}"] = f"%{palabra.replace(chr(92), '').replace('%', '').replace('_', '')}%"
    if q and q.strip() and limit is None:
        limit = 20
    sql = ("SELECT id_partido, id_provincia, nombre, nombre_completo, categoria, codigo_georef FROM partidos "
           f"WHERE {' AND '.join(where)} ORDER BY nombre")
    if limit:
        sql += " LIMIT :lim"
        params["lim"] = limit
    r = await db.execute(text(sql), params)
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

async def geocodificar_direccion(q: str, limit: int = 5, solo_direcciones: bool = False, *,
                                 id_municipio: int) -> list:
    """Geocoding directo (texto → candidatos con lat/lon) SIN dependencia de auth.

    Extraído del handler `/buscar` para poder reutilizarlo desde un endpoint público
    (alta de vecinos) sin duplicar la lógica de filtrado de POIs. El rate-limit hacia
    Nominatim es global (`_nominatim_get`), así que no se vulnera la política de uso.
    """
    # Cuando solo_direcciones=True pedimos el máximo que Nominatim acepta (40)
    # porque algunas queries devuelven decenas de POIs antes de las calles
    # válidas. No usamos `layer=address` porque excluye `highway/secondary` que
    # sí son direcciones válidas (calle sin número exacto).
    upstream_limit = 40 if solo_direcciones else limit
    bbox_lat, bbox_lon, bbox_delta = await _bbox_municipio(id_municipio)
    params: dict = {
        "q": q,
        "format": "json",
        "limit": str(upstream_limit),
        "countrycodes": "ar",
        "addressdetails": "1",
        # bounded=1 EXCLUYE lo que cae fuera del viewbox (no es solo un bias):
        # sin esto, "Avenida Maipú" devuelve resultados de Mendoza/otras
        # provincias que son ruido para un operador municipal.
        "viewbox": _viewbox_municipio(bbox_lat, bbox_lon, bbox_delta),
        "bounded": "1",
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


@router.get("/buscar")
async def buscar_direccion(
    q: str = Query(..., min_length=3, description="Texto a geocodificar"),
    limit: int = Query(5, ge=1, le=10),
    solo_direcciones: bool = Query(
        False,
        description="Si True, excluye POIs (comercios, oficinas, etc.) y devuelve solo calles/edificios.",
    ),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Geocoding directo: texto → candidatos con lat/lon. Requiere JWT (backoffice).

    Para la versión pública (alta de vecinos), ver `/api/v1/publico/alta/geo/buscar`,
    que reutiliza la misma `geocodificar_direccion`.
    """
    return await geocodificar_direccion(q, limit, solo_direcciones, id_municipio=id_municipio)


async def reverse_geocodificar(lat: float, lon: float) -> dict:
    """Geocoding inverso (lat/lon → dirección legible) SIN dependencia de auth.

    Extraído del handler `/reverse` para reutilizarlo desde la vía pública del
    vecino (`/publico/reclamos/geo/reverse`: autocompletado por GPS de la PWA).
    Devuelve SIEMPRE 200 con `encontrado`: Nominatim responde HTTP 200 con
    `{"error": "Unable to geocode"}` para el mar o zonas sin datos; el caller
    (PWA) cae a las coordenadas crudas como dirección de respaldo.

    `direccion` es la forma corta "Calle Altura, Localidad" que la app usa en el
    campo de domicilio; `display_name`/`address` son los crudos de Nominatim.
    """
    data = await _nominatim_get("/reverse", {
        "lat": f"{lat:.7f}",
        "lon": f"{lon:.7f}",
        "format": "jsonv2",
        "addressdetails": "1",
        "zoom": "18",   # nivel edificio/calle (default 18; explícito por claridad)
    })
    if not isinstance(data, dict) or data.get("error") or not data.get("display_name"):
        return {
            "encontrado": False, "direccion": None, "display_name": None,
            "calle": None, "altura": None, "localidad": None, "provincia": None,
            "lat": lat, "lon": lon, "address": {},
        }
    a = data.get("address") or {}
    calle = (a.get("road") or a.get("pedestrian") or a.get("footway")
             or a.get("cycleway") or a.get("path") or "")
    altura = str(a.get("house_number") or "")
    localidad = (a.get("city") or a.get("town") or a.get("village")
                 or a.get("suburb") or a.get("city_district") or a.get("municipality") or "")
    provincia = a.get("state") or ""
    if calle:
        direccion = f"{calle} {altura}".strip() + (f", {localidad}" if localidad else "")
    else:
        direccion = data.get("display_name")
    return {
        "encontrado": True,
        "direccion": direccion,
        "display_name": data.get("display_name"),
        "calle": calle or None,
        "altura": altura or None,
        "localidad": localidad or None,
        "provincia": provincia or None,
        "lat": float(data["lat"]) if data.get("lat") else lat,
        "lon": float(data["lon"]) if data.get("lon") else lon,
        "address": a,
    }


def _norm_localidad(s: str) -> str:
    """lower + sin tildes, para matchear nombres de Nominatim contra el catálogo."""
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


# Campos de `address` de Nominatim en orden BARRIO-primero. OJO: distinto del
# orden de `localidad` en reverse_geocodificar (city-primero, para la dirección
# legible): acá queremos la localidad fina ("Olivos", "Florida"), no el partido
# ("Vicente López" es a la vez partido y localidad).
_CAMPOS_LOCALIDAD = ("suburb", "neighbourhood", "quarter", "city_district",
                     "town", "village", "city", "municipality")


async def localidad_desde_coords(db: AsyncSession, lat: float, lon: float) -> Optional[dict]:
    """Deriva la localidad del catálogo (`localidades`) desde lat/lon.

    Reverse geocoding (helper §23) + match POR NOMBRE contra el catálogo — nunca
    por id (los ids de partido/localidad divergen entre entornos). Devuelve
    {"id_localidad", "nombre"} o None (punto fuera del catálogo, Nominatim caído,
    etc.). Best-effort: NUNCA levanta — los creates de reclamos la usan como
    derivación automática y no deben fallar por geocoding (2026-08-30, backfill
    y regla de captura de localidad para el BI Ejecutivo).
    """
    try:
        out = await reverse_geocodificar(float(lat), float(lon))
        addr = out.get("address") or {}
        candidatos = [addr.get(c) for c in _CAMPOS_LOCALIDAD if addr.get(c)]
        if not candidatos:
            return None
        r = await db.execute(text(
            "SELECT id_localidad, nombre FROM localidades WHERE activo = TRUE"
        ))
        catalogo = {_norm_localidad(row.nombre): row for row in r.fetchall()}
        for cand in candidatos:
            hit = catalogo.get(_norm_localidad(cand))
            if hit:
                return {"id_localidad": hit.id_localidad, "nombre": hit.nombre}
        return None
    except Exception as e:  # noqa: BLE001 — derivación accesoria, jamás rompe el caller
        logger.warning("localidad_desde_coords(%s, %s) falló: %s", lat, lon, e)
        return None


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Geocoding inverso: lat/lon → dirección normalizada. Requiere JWT (backoffice).

    Compat: conserva `display_name`/`address`/`lat`/`lon` y suma `encontrado`,
    `direccion` (corta) y las piezas (`calle`/`altura`/`localidad`/`provincia`).
    Desde 2026-08-30 suma `id_localidad`/`localidad_catalogo` (match del catálogo
    `localidades`, o None) para que el form de Reclamos autocomplete la localidad.
    Sin resultado → 404 (comportamiento histórico de esta ruta; la pública
    devuelve 200 con `encontrado=false`).
    """
    out = await reverse_geocodificar(lat, lon)
    if not out["encontrado"]:
        raise HTTPException(status_code=404, detail="Sin resultados")
    loc = await localidad_desde_coords(db, lat, lon)
    out["id_localidad"] = loc["id_localidad"] if loc else None
    out["localidad_catalogo"] = loc["nombre"] if loc else None
    return out
