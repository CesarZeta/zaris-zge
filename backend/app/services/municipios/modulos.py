"""
Módulos habilitados por municipio (IT-01 F4, PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 7).

`modulos` es el catálogo global (su `min_nivel_acceso` es el valor por defecto del alta);
`municipio_modulo` dice, por municipio, si cada módulo está habilitado y con qué nivel mínimo.
- Habilitar o quitar: solo el super administrador. El nivel mínimo (1-5): el administrador.
- Un módulo apagado no se ve en el menú ni responde por la API: cada router lleva la dependency
  `modulo_habilitado(...)` (404, para no revelar qué tiene cada municipio). Mapa en MODULOS_POR_ROUTER.
- Un override de `usuario_modulos` no habilita un módulo apagado.

Efectos cruzados que se apagan con el módulo (la guarda va en el servicio, no solo en el router):
- `encuestas`: `encuestas_service.encuestas_estan_activas` (la usan todos los disparos de envíos:
  reclamo, turno, entrada, trámite) y el dispatcher (`encuestas_admin.dispatcher`).
- `ot_*`: la asignación automática de reclamos (`autoasignacion.autoasignar_reclamo`); sin OT el
  reclamo se resuelve con el cierre directo que ya existe.
- `emergencias`: la Guardia (rutas /turnos/guardia/*), además de `turnos`.
- `turnos`: la derivación de un evento de emergencias a la Guardia (/emergencias/eventos/{id}/derivar-guardia).
- `tramites`: el cron de mantenimiento (`tramites_mantenimiento`).
"""
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.municipios.constantes import DEPENDENCIAS_MODULOS

# Router (variable de app/main.py) → códigos que lo habilitan (alcanza con uno).
MODULOS_POR_ROUTER: dict[str, tuple[str, ...]] = {
    "reclamos_router": ("reclamos",),
    "reclamo_adjuntos_router": ("reclamos",),
    "publico_reclamos_router": ("reclamos",),
    "publico_reclamos_adjuntos_router": ("reclamos",),
    "ot_router": ("ot_supervisor", "ot_agente", "ot_auditoria"),
    "ot_adjuntos_router": ("ot_supervisor", "ot_agente", "ot_auditoria"),
    "agenda_v2_router": ("agenda",),
    "agenda_espacios_router": ("agenda",),
    "agenda_disponibilidad_router": ("agenda",),
    "agenda_novedades_router": ("agenda",),
    "turnos_router": ("turnos",),
    "turnos_publico_router": ("turnos",),
    "publico_turnos_vecino_router": ("turnos",),
    "agenda_publico_router": ("entradas",),
    "publico_entradas_vecino_router": ("entradas",),
    "tramites_router": ("tramites",),
    "tramites_admin_router": ("tramites",),
    "emergencias_router": ("emergencias",),
    "publico_emergencias_router": ("emergencias",),
    "encuestas_admin_router": ("encuestas",),
    "encuestas_publico_router": ("encuestas",),
    "bi_router": ("bi",),
    "bi_ejecutivo_router": ("bi",),
    "bi_atencion_router": ("bi",),
}

_TTL_SEGUNDOS = 60
_cache: dict[int, tuple[float, dict[str, int]]] = {}

NO_ENCONTRADO = HTTPException(status_code=404, detail="Not Found")


async def modulos_habilitados(db: AsyncSession, id_municipio: int) -> dict[str, int]:
    """{modulo_codigo: min_nivel_acceso} de los módulos habilitados del municipio (y activos en
    el catálogo). Cacheado por proceso 60 s; `invalidar_modulos` al cambiarlos."""
    hit = _cache.get(id_municipio)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    rows = (await db.execute(text("""
        SELECT mm.modulo_codigo, mm.min_nivel_acceso
          FROM municipio_modulo mm
          JOIN modulos m ON m.modulo_codigo = mm.modulo_codigo AND m.activo
         WHERE mm.id_municipio = :mun AND mm.habilitado AND mm.activo"""), {"mun": id_municipio})).fetchall()
    datos = {r.modulo_codigo: r.min_nivel_acceso for r in rows}
    _cache[id_municipio] = (time.monotonic() + _TTL_SEGUNDOS, datos)
    return datos


def invalidar_modulos(id_municipio: Optional[int] = None) -> None:
    if id_municipio is None:
        _cache.clear()
    else:
        _cache.pop(id_municipio, None)


async def modulo_esta_habilitado(db: AsyncSession, id_municipio: int, codigo: str) -> bool:
    return codigo in await modulos_habilitados(db, id_municipio)


async def _overrides(db: AsyncSession, ids: list[int]) -> dict[int, dict[str, bool]]:
    rows = (await db.execute(text(
        "SELECT id_usuario, modulo_codigo, permitido FROM usuario_modulos "
        "WHERE activo = TRUE AND id_usuario = ANY(:ids)"), {"ids": ids})).fetchall()
    res: dict[int, dict[str, bool]] = {}
    for r in rows:
        res.setdefault(r.id_usuario, {})[r.modulo_codigo] = r.permitido
    return res


async def _catalogo(db: AsyncSession, id_municipio: Optional[int]) -> dict[str, int]:
    """Módulos a considerar con su nivel mínimo: los habilitados del municipio, o el catálogo
    global si no hay municipio (super administrador sin selección)."""
    if id_municipio is not None:
        return await modulos_habilitados(db, id_municipio)
    rows = (await db.execute(text(
        "SELECT modulo_codigo, min_nivel_acceso FROM modulos WHERE activo = TRUE"))).fetchall()
    return {r.modulo_codigo: r.min_nivel_acceso for r in rows}


def _resolver(catalogo: dict[str, int], nivel: int, overrides: dict[str, bool]) -> list[str]:
    permitidos = {cod for cod, minimo in catalogo.items() if minimo >= nivel}
    for cod, ok in overrides.items():
        if cod not in catalogo:
            continue  # un override no habilita un módulo apagado
        if ok:
            permitidos.add(cod)
        else:
            permitidos.discard(cod)
    return sorted(permitidos)


async def modulos_permitidos(db: AsyncSession, id_usuario: int, nivel: int,
                             id_municipio: Optional[int]) -> list[str]:
    """Modelo híbrido (§30) a escala del municipio: nivel mínimo + overrides por usuario, solo
    sobre los módulos habilitados."""
    return _resolver(await _catalogo(db, id_municipio), nivel,
                     (await _overrides(db, [id_usuario])).get(id_usuario, {}))


async def modulos_permitidos_lote(db: AsyncSession, usuarios: list[tuple[int, int]],
                                  id_municipio: Optional[int]) -> dict[int, list[str]]:
    """Lo mismo para un lote de (id_usuario, nivel), con dos consultas en total."""
    if not usuarios:
        return {}
    catalogo = await _catalogo(db, id_municipio)
    overrides = await _overrides(db, [u for u, _ in usuarios])
    return {u: _resolver(catalogo, nivel, overrides.get(u, {})) for u, nivel in usuarios}


async def validar_dependencias(habilitados: set[str]) -> None:
    """422 si un módulo habilitado no tiene habilitadas sus dependencias."""
    for modulo, deps in DEPENDENCIAS_MODULOS.items():
        if modulo in habilitados:
            for dep in sorted(deps - habilitados):
                raise HTTPException(422, f"{modulo} necesita {dep} habilitado.")


async def _municipio_de_la_request(request: Request, db: AsyncSession) -> Optional[int]:
    """Municipio de la request sin exigir token: el `mun` del token (agente o vecino, con la firma
    verificada), el X-Municipio del super o el del Origin. Un token que no decodifica o sin `mun` no
    corta acá: decide el Origin, así un token basura no saltea el 404 de las rutas públicas. None si no
    se puede saber: la ruta resuelve su propia autenticación y responde lo que corresponda."""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        try:
            payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            payload = {}  # token basura: decide el Origin, como sin token (revisión de F4+F5)
        if payload.get("sa"):
            # Un X-Municipio inválido, inexistente o de baja lo responde `municipio_actual` en la ruta
            # («Municipio no encontrado»), no esta dependency.
            from app.core.municipio import HEADER_MUNICIPIO, estado_municipio
            from app.services.municipios.constantes import ESTADOS_OPERABLES
            crudo = (request.headers.get(HEADER_MUNICIPIO) or "").strip()
            if not (crudo.isdigit() and len(crudo) <= 9):
                return None
            estado = await estado_municipio(db, int(crudo))
            return int(crudo) if estado in ESTADOS_OPERABLES | {"modelo"} else None
        mun = payload.get("mun")
        if isinstance(mun, int):
            return mun
    from app.core.municipio import resolver_municipio_de_origen
    try:
        return await resolver_municipio_de_origen(request, db)
    except HTTPException:
        return None


def modulo_habilitado(*codigos: str):
    """Dependency de router: 404 si ninguno de `codigos` está habilitado en el municipio de la
    request. `include_router(r, dependencies=[Depends(modulo_habilitado("reclamos"))])`."""
    async def _dep(request: Request, db: AsyncSession = Depends(get_db)) -> None:
        id_municipio = await _municipio_de_la_request(request, db)
        if id_municipio is None:
            return
        habilitados = await modulos_habilitados(db, id_municipio)
        if not any(c in habilitados for c in codigos):
            raise NO_ENCONTRADO
    return _dep
