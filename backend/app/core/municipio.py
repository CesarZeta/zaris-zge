"""
ZARIS API — Municipio de cada request (IT-01 multi-municipio, F2).

Punto único: ningún router lee el municipio de un query param, del body ni de un header propio.
- Funcionario logueado: `municipio_actual` (claim `mun` del JWT, validado en get_current_user).
  Es el único lugar que F3 cambia para el super administrador (header X-Municipio).
- Vecino logueado: `municipio_vecino` (claim `mun` del token de ciudadano).
- Público sin token: `municipio_de_origen` (subdominio del header Origin) o `municipio_por_slug`
  cuando la ruta recibe `?m=<codigo_corto>`. Las rutas con token en la URL (encuesta, turno,
  reserva, pantalla) toman el municipio de la fila del token.

Origen → municipio: `<sub>.zge|vecinos|agentes.zaris.com.ar` → `municipios.subdominio = sub`.
Sin subdominio (sin Origin, zge.zaris.com.ar, localhost) → el municipio con
`direccion_base`. Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tarea 6.

Super administrador (IT-01 F3): `municipio_actual` es el ÚNICO lugar que lee el header
X-Municipio, y solo para `es_super_admin`; a cualquier otra cuenta se le ignora. Cada request
válida del super administrador deja una fila en super_admin_acceso antes de que corra el handler.
Plan: PLAN_MULTI_MUNICIPIO_F3.md, Tarea 3.

Estado del municipio (IT-01 F4): solo los ESTADOS_OPERABLES resuelven por origen o por slug, entran
en los procesos programados y dejan usar sus cuentas. El `modelo` lo opera solo el super (con
X-Municipio, para curar sus catálogos); `baja` no lo opera nadie.
Plan: PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 5.
"""
import logging
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano, get_current_user
from app.core.database import get_db
from app.services.municipios.constantes import ESTADOS_OPERABLES

logger = logging.getLogger("zaris.municipio")

_PATRON_HOST = re.compile(r"^(?P<sub>[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:zge|vecinos|agentes)\.zaris\.com\.ar$")
_PATRON_ID = re.compile(r"^[0-9]{1,9}$")
_TTL_SEGUNDOS = 60
_cache: dict = {"vence": 0.0, "por_subdominio": {}, "base": None, "ids_activos": set(), "estados": {}}
HEADER_MUNICIPIO = "X-Municipio"


def subdominio_de_origen(origin: Optional[str]) -> Optional[str]:
    """Subdominio del municipio en un header Origin, o None si no es una dirección de municipio."""
    if not origin:
        return None
    try:
        host = (urlparse(origin).hostname or "").lower()
    except ValueError:
        return None
    m = _PATRON_HOST.match(host)
    return m.group("sub") if m else None


async def _municipios(db: AsyncSession) -> dict:
    if time.monotonic() >= _cache["vence"]:
        rows = (await db.execute(text(
            "SELECT id_municipio, subdominio, direccion_base, estado FROM municipios"))).fetchall()
        operables = [r for r in rows if r.estado in ESTADOS_OPERABLES]
        _cache["estados"] = {r.id_municipio: r.estado for r in rows}
        _cache["por_subdominio"] = {r.subdominio: r.id_municipio for r in operables if r.subdominio}
        _cache["base"] = next((r.id_municipio for r in operables if r.direccion_base), None)
        _cache["ids_activos"] = {r.id_municipio for r in operables}
        _cache["vence"] = time.monotonic() + _TTL_SEGUNDOS
    return _cache


def invalidar_cache_municipios() -> None:
    _cache["vence"] = 0.0


async def estado_municipio(db: AsyncSession, id_municipio: int) -> Optional[str]:
    """Estado del municipio (cacheado como el resto), o None si no existe."""
    return (await _municipios(db))["estados"].get(id_municipio)


async def id_municipio_base(db: AsyncSession) -> Optional[int]:
    """Municipio de las direcciones sin prefijo (`direccion_base`), o None si no hay."""
    return (await _municipios(db))["base"]


async def por_cada_municipio(db: AsyncSession, proceso: str, fn) -> dict[int, Any]:
    """Procesos sin request (cron, dispatcher): corre `fn(id_municipio)` para cada
    municipio operable (ESTADOS_OPERABLES), con su configuracion. Si uno falla se registra, se revierte lo
    suyo y se sigue con el siguiente. Devuelve {id_municipio: resultado | {"error": ...}}."""
    ids = [r[0] for r in (await db.execute(text(
        "SELECT id_municipio FROM municipios WHERE estado = ANY(:e) ORDER BY id_municipio"),
        {"e": list(ESTADOS_OPERABLES)})).fetchall()]
    resultados: dict[int, Any] = {}
    for id_m in ids:
        try:
            resultados[id_m] = await fn(id_m)
        except Exception as e:  # noqa: BLE001 — un municipio no frena a los demas
            await db.rollback()
            logger.exception("%s: fallo el municipio %s; sigue con el siguiente", proceso, id_m)
            resultados[id_m] = {"error": f"{type(e).__name__}: {e}"}
    return resultados


async def resolver_municipio_de_origen(request: Request, db: AsyncSession) -> int:
    """Municipio del header Origin de la request. 404 si el subdominio no existe o está inactivo;
    503 si no hay municipio base para las direcciones sin prefijo."""
    sub = subdominio_de_origen(request.headers.get("origin"))
    datos = await _municipios(db)
    if sub is not None:
        id_mun = datos["por_subdominio"].get(sub)
        if id_mun is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Municipio no encontrado")
        return id_mun
    if datos["base"] is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="No hay un municipio configurado para esta dirección")
    return datos["base"]


async def municipio_de_origen(request: Request, db: AsyncSession = Depends(get_db)) -> int:
    """Dependency para rutas públicas sin token."""
    return await resolver_municipio_de_origen(request, db)


async def municipio_por_slug(db: AsyncSession, slug: str) -> dict:
    """{id_municipio, nombre, slug} del municipio operable con ese codigo_corto; 404 si no existe
    o si es el modelo o está de baja."""
    slug_norm = (slug or "").strip().lower()
    row = None
    if slug_norm:
        row = (await db.execute(text("""
            SELECT id_municipio, nombre, codigo_corto FROM municipios
             WHERE LOWER(codigo_corto) = :slug AND estado = ANY(:e)"""),
            {"slug": slug_norm, "e": list(ESTADOS_OPERABLES)})).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Municipio no encontrado")
    return {"id_municipio": row.id_municipio, "nombre": row.nombre, "slug": row.codigo_corto}


async def municipio_actual(request: Request, current_user: dict = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)) -> int:
    """Municipio del funcionario logueado: el claim `mun` del JWT, ya validado contra la base y el
    origen. Para el super administrador, el del header X-Municipio (elegido en el selector), que
    queda registrado; para cualquier otra cuenta el header se ignora."""
    if not current_user.get("es_super_admin"):
        return current_user["id_municipio"]
    crudo = (request.headers.get(HEADER_MUNICIPIO) or "").strip()
    if not crudo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Elegí un municipio en el selector")
    if not _PATRON_ID.match(crudo):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Municipio inválido")
    id_mun = int(crudo)
    # El super opera los municipios operables y el modelo (para curar sus catálogos); no los de baja.
    if (await _municipios(db))["estados"].get(id_mun) not in ESTADOS_OPERABLES | {"modelo"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Municipio no encontrado")
    from app.services.accesos_super import registrar_acceso_super
    from app.utils.request_helpers import get_real_ip
    await registrar_acceso_super(
        id_usuario=current_user["id_usuario"], accion="request", id_municipio=id_mun,
        metodo=request.method, ruta=request.url.path, ip=get_real_ip(request),
        user_agent=request.headers.get("user-agent"))
    return id_mun


async def municipio_vecino(ciudadano: dict = Depends(get_current_ciudadano)) -> int:
    """Municipio del vecino logueado (claim `mun` del token de ciudadano)."""
    return ciudadano["id_municipio"]
