"""
Integridad de cuentas (mig 77) — Fase 2 del roadmap usuario↔agente/ciudadano.

Invariante del sistema: todo `usuario` activo debe tener un agente O un ciudadano
asociado (interno → agente, vecino → ciudadano). Un usuario "pelado" (sin ninguno
de los dos) no es un estado válido permanente — típicamente es un alta a medias
(se creó el usuario y nunca se completó el agente/ciudadano).

Motor disparado por el endpoint de mantenimiento (cron diario, routes/
usuarios_mantenimiento.py):

  suspender_usuarios_sin_vinculo(db)
    Usuarios activos, nivel_acceso > 1 (admin exento), creados hace más de
    GRACIA_HORAS, sin agente activo y sin ciudadano vinculado por email:
      - activo = FALSE (baja lógica → no pueden loguear, /auth/login exige activo)
      - suspendido_motivo = 'sin_vinculo'
      - fecha_suspension = NOW()
    Reversible: un admin puede crear el agente/ciudadano faltante y reactivar la
    cuenta desde Maestros → Usuarios.

El vínculo a ciudadano se resuelve por email (mismo criterio que el backfill y que
/auth/login, que loguea por email): un ciudadano activo cuyo email coincide con el
del usuario. El vínculo a agente es la FK directa agentes.id_usuario.

Admin (nivel 1) queda EXENTO para evitar un lockout total: si el único admin
quedara sin vínculo, nadie podría reactivar a los demás.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("zaris.integridad_cuentas")

# Período de gracia: no suspender altas recién hechas (el alta de 2 pasos puede
# estar a mitad de camino). El alta interna crea el agente en la misma tx, así
# que esto solo cubre altas a medias o casos raros.
GRACIA_HORAS = 24

MOTIVO_SIN_VINCULO = "sin_vinculo"


# Subquery común: usuarios activos SIN agente activo y SIN ciudadano vinculado por
# email. Admin (nivel 1) exento. NO filtra por gracia (lo agrega cada caller).
_COND_SIN_VINCULO = """
    u.activo = TRUE
    AND u.nivel_acceso > 1
    AND NOT EXISTS (
        SELECT 1 FROM agentes a
        WHERE a.id_usuario = u.id_usuario AND a.activo = TRUE
    )
    AND NOT EXISTS (
        SELECT 1 FROM ciudadanos c
        WHERE lower(c.email) = lower(u.email) AND c.activo = TRUE
    )
"""


async def listar_usuarios_sin_vinculo(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Diagnóstico (no muta): usuarios activos sin vínculo, con su antigüedad y si ya
    pasaron la gracia. Útil para inspección y para el reporte del endpoint.
    """
    rows = (await db.execute(
        text(f"""
            SELECT u.id_usuario, u.username, u.email, u.nivel_acceso, u.es_externo,
                   u.fecha_alta,
                   (u.fecha_alta < (NOW() AT TIME ZONE 'UTC') - INTERVAL '{GRACIA_HORAS} hours') AS supera_gracia
            FROM usuarios u
            WHERE {_COND_SIN_VINCULO}
            ORDER BY u.id_usuario
        """)
    )).mappings().all()
    return [dict(r) for r in rows]


async def suspender_usuarios_sin_vinculo(db: AsyncSession) -> dict[str, Any]:
    """
    Suspende (baja lógica + marca) los usuarios activos sin agente ni ciudadano que
    ya superaron el período de gracia. Idempotente: un usuario ya inactivo no se
    re-procesa (la condición exige activo=TRUE).

    `fecha_alta` es `timestamp without time zone` (legacy §5); se compara contra
    NOW() en UTC para evitar mismatch de tz.

    Devuelve {suspendidos: int, detalle: [{id_usuario, username, email}]}.
    """
    rows = (await db.execute(
        text(f"""
            UPDATE usuarios u
            SET activo = FALSE,
                suspendido_motivo = :motivo,
                fecha_suspension = NOW(),
                fecha_modif = NOW()
            WHERE {_COND_SIN_VINCULO}
              AND u.fecha_alta < (NOW() AT TIME ZONE 'UTC') - INTERVAL '{GRACIA_HORAS} hours'
            RETURNING u.id_usuario, u.username, u.email, u.nivel_acceso
        """),
        {"motivo": MOTIVO_SIN_VINCULO},
    )).mappings().all()

    detalle = [dict(r) for r in rows]
    await db.commit()

    if detalle:
        logger.warning(
            "Integridad cuentas: %s usuario(s) suspendido(s) por sin_vinculo: %s",
            len(detalle),
            ", ".join(f"{d['username']}(id={d['id_usuario']})" for d in detalle),
        )
    return {"suspendidos": len(detalle), "detalle": detalle}
