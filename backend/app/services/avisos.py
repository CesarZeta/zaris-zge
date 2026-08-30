"""
ZARIS API - Avisos persistentes al ciudadano (bandeja "Alertas" de la App Vecinos).

Mig 99 (`ciudadano_aviso`). Complementa el push (services/push.py), que es
efimero y solo llega a quien tiene una suscripcion activa: el aviso queda en DB
SIEMPRE y la PWA lo lista con GET /api/v1/publico/avisos (leido / no leido).

Best-effort como el push: se llama post-commit desde los hooks de negocio, abre
sesion propia (AsyncSessionLocal — patron §29 background tasks: la sesion del
request ya esta cerrada) y JAMAS levanta excepcion. Si falla, se loguea y el
flujo de negocio sigue igual.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

logger = logging.getLogger("zaris.avisos")

# Espejo del CHECK ck_ciudadano_aviso_tipo (mig 99). Un tipo nuevo exige migracion.
TIPOS_AVISO = ("reclamo_estado", "emergencia_estado", "municipio")


async def registrar_aviso_ciudadano(
    id_ciudadano: int,
    tipo: str,
    titulo: str,
    mensaje: Optional[str] = None,
    url_destino: str = "/inicio",
    recurso_tipo: Optional[str] = None,
    recurso_id: Optional[int] = None,
) -> Optional[int]:
    """Inserta un aviso en la bandeja del ciudadano. Devuelve el id o None si fallo.

    `url_destino` es una ruta RELATIVA dentro de la PWA (misma convencion que el
    payload del push: "/reclamos/123", "/emergencias").
    """
    if tipo not in TIPOS_AVISO:
        logger.warning("registrar_aviso_ciudadano: tipo desconocido %r (ciudadano %s)", tipo, id_ciudadano)
        return None
    try:
        async with AsyncSessionLocal() as db:
            id_aviso = await db.scalar(text("""
                INSERT INTO ciudadano_aviso
                    (id_ciudadano, tipo, titulo, mensaje, url_destino,
                     recurso_tipo, recurso_id, activo)
                VALUES (:c, :t, :ti, :m, :u, :rt, :ri, TRUE)
                RETURNING id_ciudadano_aviso
            """), {
                "c": id_ciudadano, "t": tipo, "ti": titulo[:200], "m": mensaje,
                "u": url_destino[:300] if url_destino else None,
                "rt": recurso_tipo, "ri": recurso_id,
            })
            await db.commit()
        return int(id_aviso) if id_aviso else None
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.warning("registrar_aviso_ciudadano(%s, %s) fallo: %s", id_ciudadano, tipo, e)
        return None
