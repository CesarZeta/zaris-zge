"""
ZARIS API - PORTAL del vecino (home / resumen del autoservicio logueado).

Bajo /api/v1/publico/portal/*. Guard get_current_ciudadano (JWT scope 'publico').

Pensado para la pantalla de inicio del portal del vecino: una sola llamada que
devuelve los conteos de lo que el ciudadano tiene activo (reclamos, turnos,
entradas), sin pedir cada listado por separado. Todo scopeado al id_ciudadano
del token (nunca de un parámetro).

Mono-tenant (§38): el deploy es de un municipio; no se filtra por municipio acá
(los datos del vecino ya son de este municipio por construcción).
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db

logger = logging.getLogger("zaris.publico_portal")

router = APIRouter(prefix="/api/v1/publico/portal", tags=["publico-portal"])


@router.get("/mi-resumen")
async def mi_resumen(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """
    Conteos del vecino logueado para la home del portal. Un solo round-trip.

    Define "vigente" por dominio:
      - reclamos: activo=TRUE y estado NO final (≠ Resuelto, Cancelado).
      - turnos:   activo=TRUE y estado='reservado' (cumplido/cancelado no son vigentes).
      - entradas: activo=TRUE y reserva en estado 'reservada' (asistio/cancelada no).
    Devuelve además el total histórico de cada dominio (para "ver todos").
    """
    id_c = current["id_ciudadano"]

    row = (await db.execute(text("""
        SELECT
          -- Reclamos
          (SELECT COUNT(*) FROM reclamos
             WHERE id_ciudadano = :id_c AND activo = TRUE
               AND estado NOT IN ('Resuelto', 'Cancelado'))           AS reclamos_vigentes,
          (SELECT COUNT(*) FROM reclamos
             WHERE id_ciudadano = :id_c AND activo = TRUE)             AS reclamos_total,
          -- Turnos
          (SELECT COUNT(*) FROM turnos
             WHERE id_ciudadano = :id_c AND activo = TRUE
               AND estado = 'reservado')                              AS turnos_vigentes,
          (SELECT COUNT(*) FROM turnos
             WHERE id_ciudadano = :id_c AND activo = TRUE)             AS turnos_total,
          -- Entradas (reservas de eventos)
          (SELECT COUNT(*) FROM evento_reservas er
             JOIN estado_reserva es ON es.id_estado_reserva = er.id_estado_reserva
             WHERE er.id_ciudadano = :id_c AND er.activo = TRUE
               AND es.codigo = 'reservada')                           AS entradas_vigentes,
          (SELECT COUNT(*) FROM evento_reservas
             WHERE id_ciudadano = :id_c AND activo = TRUE)             AS entradas_total
    """), {"id_c": id_c})).fetchone()

    return {
        "ciudadano": {
            "id_ciudadano": id_c,
            "nombre": current.get("nombre"),
            "apellido": current.get("apellido"),
        },
        "reclamos": {"vigentes": row.reclamos_vigentes, "total": row.reclamos_total},
        "turnos":   {"vigentes": row.turnos_vigentes,   "total": row.turnos_total},
        "entradas": {"vigentes": row.entradas_vigentes, "total": row.entradas_total},
    }
