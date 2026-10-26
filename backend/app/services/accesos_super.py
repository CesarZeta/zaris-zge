"""
ZARIS API — Registro de accesos del super administrador (IT-01 F3, mig 127b).

Cada request del super administrador sobre datos de un municipio, cada cambio de municipio y
cada acción global quedan en `super_admin_acceso` (append-only). El administrador de cada
municipio ve las filas de su municipio; las globales (id_municipio NULL) no las ve nadie más.

El INSERT va en una sesión propia y se confirma antes de seguir: la fila queda aunque el
handler falle o sea un GET que no hace commit. Si no se puede registrar, el acceso se niega
(503): sin registro no hay acceso, como en la historia clínica.
Plan: PLAN_MULTI_MUNICIPIO_F3.md, Tarea 2.
"""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal

logger = logging.getLogger("zaris.accesos_super")

# Mismo conjunto que el CHECK ck_super_admin_acceso_accion (mig 127b, ampliado en la 128).
ACCIONES: tuple[str, ...] = ("login", "seleccion", "request", "historia_clinica", "config_global",
                             "municipio_editar", "catalogo_global", "segundo_factor")


_INSERT = text("""
    INSERT INTO super_admin_acceso
        (id_usuario, id_municipio, accion, metodo, ruta, detalle, ip, user_agent)
    VALUES (:u, :m, :a, :metodo, :ruta, :detalle, :ip, :ua)""")


def _params(id_usuario: int, accion: str, id_municipio: Optional[int], metodo: Optional[str],
            ruta: Optional[str], detalle: Optional[str], ip: Optional[str], user_agent: Optional[str]) -> dict:
    return {
        "u": id_usuario, "m": id_municipio, "a": accion,
        "metodo": (metodo or None) and metodo[:10],
        "ruta": (ruta or None) and ruta[:300],
        "detalle": detalle,
        "ip": (ip or None) and ip[:64],
        "ua": (user_agent or None) and user_agent[:1000],
    }


def _negar(id_usuario: int, accion: str) -> HTTPException:
    logger.exception("No se pudo registrar el acceso del super administrador id=%s accion=%s",
                     id_usuario, accion)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                         detail="No se pudo registrar el acceso")


async def registrar_acceso_super(*, id_usuario: int, accion: str, id_municipio: Optional[int],
                                 metodo: Optional[str] = None, ruta: Optional[str] = None,
                                 detalle: Optional[str] = None, ip: Optional[str] = None,
                                 user_agent: Optional[str] = None) -> None:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(_INSERT, _params(id_usuario, accion, id_municipio, metodo, ruta, detalle, ip,
                                              user_agent))
            await db.commit()
    except Exception:  # noqa: BLE001 — cualquier falla del registro niega el acceso
        raise _negar(id_usuario, accion)


async def registrar_acceso_super_en(db: AsyncSession, *, id_usuario: int, accion: str,
                                    id_municipio: Optional[int], metodo: Optional[str] = None,
                                    ruta: Optional[str] = None, detalle: Optional[str] = None,
                                    ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
    """Variante para los cambios del super administrador: la fila va en la MISMA transacción que
    el cambio y se confirma con él. Si no se puede registrar, el cambio no queda (503)."""
    try:
        await db.execute(_INSERT, _params(id_usuario, accion, id_municipio, metodo, ruta, detalle, ip,
                                          user_agent))
    except Exception:  # noqa: BLE001
        raise _negar(id_usuario, accion)
