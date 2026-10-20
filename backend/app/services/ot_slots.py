"""
ZARIS — Huecos libres de un agente o equipo para agendar una OT.

Compartido por el planificador de la Mesa del Supervisor (routes/ordenes_trabajo.py:
GET /ot/slots-recurso y la sugerencia de auto-asignar) y la autoasignación de
reclamos (services/autoasignacion.py). Vivía en el router; se movió acá para que
el servicio no importe un router (2026-10-20).
"""
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agenda import disponibilidad_efectiva


def _slots_de_rango(rango_ini: time, rango_fin: time, duracion_min: int) -> list[tuple[time, time]]:
    """Parte un rango horario en slots consecutivos de `duracion_min`.
    Descarta el ultimo si no entra completo."""
    out: list[tuple[time, time]] = []
    cursor = datetime.combine(date.min, rango_ini)
    fin = datetime.combine(date.min, rango_fin)
    paso = timedelta(minutes=duracion_min)
    while cursor + paso <= fin:
        out.append((cursor.time(), (cursor + paso).time()))
        cursor += paso
    return out


def _solapa(a_ini: time, a_fin: time, b_ini: time, b_fin: time) -> bool:
    return a_ini < b_fin and a_fin > b_ini


async def slots_libres_recurso(
    db: AsyncSession, tipo_recurso: str, id_recurso: int, fecha: date, duracion_min: int,
) -> list[dict[str, Any]]:
    """Slots libres de un agente o equipo para una fecha.

    - agente: disponibilidad efectiva del agente menos sus ocupaciones.
    - equipo: union de las disponibilidades de los agentes del equipo
      (equipo_agentes) menos la union de ocupaciones de todos ellos. Si el
      equipo no tiene agentes con agenda cargada, devuelve [] (no disponible).
    """
    if tipo_recurso == "agente":
        rangos_raw = await disponibilidad_efectiva(db, "agente", id_recurso, fecha)
        rangos = [(r["hora_inicio"], r["hora_fin"]) for r in rangos_raw]
        ocup = (await db.execute(text("""
            SELECT hora_inicio, hora_fin FROM ocupaciones
            WHERE activo = TRUE AND tipo_recurso = 'agente' AND id_recurso = :ir AND fecha = :f
        """), {"ir": id_recurso, "f": fecha})).mappings().all()
        ocupadas = [(o["hora_inicio"], o["hora_fin"]) for o in ocup]
    elif tipo_recurso == "equipo":
        # Disponibilidad del equipo = union de sus agentes + override de equipo
        # sin agentes (mig 91). Delegamos en disponibilidad_efectiva para NO
        # duplicar la logica (esta duplicacion era la que hacia divergir la
        # grilla de Agenda del planificador de OT). Equipo sin agentes y sin
        # override -> [] (lo resuelve disponibilidad_efectiva).
        rangos_raw = await disponibilidad_efectiva(db, "equipo", id_recurso, fecha)
        rangos = [(r["hora_inicio"], r["hora_fin"]) for r in rangos_raw]
        if not rangos:
            return []
        # Agentes del equipo, para sumar sus ocupaciones individuales.
        agentes = (await db.execute(text("""
            SELECT id_agente FROM equipo_agentes
            WHERE id_equipo = :ie AND activo = TRUE
        """), {"ie": id_recurso})).scalars().all()
        # Ocupaciones: las del equipo + las de cualquiera de sus agentes.
        ocup = (await db.execute(text("""
            SELECT hora_inicio, hora_fin FROM ocupaciones
            WHERE activo = TRUE AND fecha = :f
              AND (
                (tipo_recurso = 'equipo' AND id_recurso = :ie)
                OR (tipo_recurso = 'agente' AND id_recurso = ANY(:ags))
              )
        """), {"f": fecha, "ie": id_recurso, "ags": list(agentes) or [-1]})).mappings().all()
        ocupadas = [(o["hora_inicio"], o["hora_fin"]) for o in ocup]
    else:
        raise HTTPException(422, "tipo_recurso debe ser 'agente' o 'equipo'")

    out: list[dict[str, Any]] = []
    for r_ini, r_fin in rangos:
        for s_ini, s_fin in _slots_de_rango(r_ini, r_fin, duracion_min):
            if any(_solapa(s_ini, s_fin, o_ini, o_fin) for o_ini, o_fin in ocupadas):
                continue
            out.append({
                "hora_inicio": s_ini.strftime("%H:%M:%S"),
                "hora_fin": s_fin.strftime("%H:%M:%S"),
            })
    return out
