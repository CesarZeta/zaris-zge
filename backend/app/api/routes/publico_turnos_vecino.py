"""
ZARIS API - TURNOS del vecino logueado (App Vecinos, etapa C del plan).

Bajo /api/v1/publico/turnos/*. Guard get_current_ciudadano (JWT scope 'publico').

A diferencia del autoservicio anonimo por token (turnos_publico, §33), aca el
vecino opera desde su CUENTA: el id_ciudadano SIEMPRE sale del token (no se pide
DNI ni datos personales) y sus turnos quedan asociados a "Mis turnos".

Reusa los helpers de turnos_publico (_resolver_prestacion, _slots, validaciones
de disponibilidad/solape) — misma logica de negocio, distinta identidad:
  - GET    /api/v1/publico/turnos              -> mis turnos (token)
  - POST   /api/v1/publico/turnos/reservar     -> reservar a mi nombre
  - PATCH  /api/v1/publico/turnos/{id}/cancelar -> cancelar un turno MIO

Prestaciones y slots NO se duplican: la PWA usa los endpoints anonimos
existentes GET /api/v1/turnos/publico/prestaciones y /slots (no requieren
identidad). Turno ajeno -> 404 con cuerpo generico (no filtrar terceros).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip
from app.api.routes.turnos_publico import _resolver_prestacion
from app.services.agenda import disponibilidad_efectiva, turnos_respeta_disponibilidad

router = APIRouter(prefix="/api/v1/publico/turnos", tags=["publico-turnos"])
logger = logging.getLogger("zaris.publico_turnos")


class TurnoVecinoCreate(BaseModel):
    id_tipo_prestacion: int
    fecha: date
    hora_inicio: time
    observaciones: Optional[str] = None


def _to_dict(row) -> dict:
    d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# ─── GET /publico/turnos — mis turnos ────────────────────────────────────────

@router.get("")
async def listar_mis_turnos(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Turnos del vecino logueado (vigentes + historico), mas recientes primero."""
    rows = (await db.execute(text("""
        SELECT t.id_turno, t.estado, t.fecha, t.hora_inicio, t.hora_fin,
               t.observaciones,
               tp.nombre AS prestacion_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               (t.id_espacio IS NOT NULL) AS es_espacio
        FROM turnos t
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN agentes         a  ON a.id_agente            = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio           = t.id_espacio
        WHERE t.activo = TRUE AND t.id_ciudadano = :c
        ORDER BY t.fecha DESC, t.hora_inicio DESC
        LIMIT 100
    """), {"c": current["id_ciudadano"]})).mappings().all()
    return [_to_dict(r) for r in rows]


# ─── POST /publico/turnos/reservar ───────────────────────────────────────────

@router.post("/reservar", status_code=201)
async def reservar_turno_vecino(
    payload: TurnoVecinoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Reserva un turno A NOMBRE del vecino del token. Mismas validaciones que
    el autoservicio anonimo (disponibilidad, solape, un turno por dia)."""
    check_rate_limit(f"turnovec:{get_real_ip(request)}", max_requests=5, window_seconds=60)

    id_ciudadano = current["id_ciudadano"]
    prest = await _resolver_prestacion(db, payload.id_tipo_prestacion)
    tipo_recurso = prest["tipo_recurso"]
    id_recurso = prest["id_recurso"]
    duracion_min = prest["duracion_min"]

    if payload.fecha < date.today():
        raise HTTPException(422, "No se puede reservar un turno en una fecha pasada")

    hora_inicio = payload.hora_inicio
    hora_fin = (datetime.combine(payload.fecha, hora_inicio)
                + timedelta(minutes=duracion_min)).time()
    if hora_fin <= hora_inicio:
        raise HTTPException(422, "La duracion de la prestacion excede el dia")

    if await turnos_respeta_disponibilidad(db):
        rangos = await disponibilidad_efectiva(db, tipo_recurso, id_recurso, payload.fecha)
        dentro = any(
            r["hora_inicio"] <= hora_inicio and hora_fin <= r["hora_fin"]
            for r in rangos
        )
        if not dentro:
            raise HTTPException(409, "El horario solicitado no esta dentro de la disponibilidad del recurso")

    solapado = await db.scalar(text("""
        SELECT 1 FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir AND fecha = :f
          AND hora_inicio < :hf AND hora_fin > :hi
        LIMIT 1
    """), {"tr": tipo_recurso, "ir": id_recurso, "f": payload.fecha, "hi": hora_inicio, "hf": hora_fin})
    if solapado:
        raise HTTPException(409, "El horario solicitado ya no esta disponible")

    dup = await db.scalar(text("""
        SELECT 1 FROM turnos
        WHERE id_ciudadano = :ic AND fecha = :f AND activo = TRUE AND estado <> 'cancelado'
        LIMIT 1
    """), {"ic": id_ciudadano, "f": payload.fecha})
    if dup:
        raise HTTPException(409, "Ya tenes un turno reservado para ese dia")

    id_ocupacion = await db.scalar(text("""
        INSERT INTO ocupaciones (
            tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
            id_ciudadano, motivo, id_municipio, id_usuario_alta
        ) VALUES (
            'turno', :tr, :ir, :f, :hi, :hf, :ic, :mot, 1, NULL
        )
        RETURNING id_ocupacion
    """), {
        "tr": tipo_recurso, "ir": id_recurso, "f": payload.fecha,
        "hi": hora_inicio, "hf": hora_fin, "ic": id_ciudadano,
        "mot": f"Turno (app vecinos): {payload.observaciones}" if payload.observaciones else "Turno (app vecinos)",
    })

    row = (await db.execute(text("""
        INSERT INTO turnos (
            id_ciudadano, id_agente, id_espacio, id_tipo_prestacion, id_ocupacion,
            fecha, hora_inicio, hora_fin, estado, observaciones,
            origen, id_municipio, id_subarea
        ) VALUES (
            :ic, :ia, :ie, :itp, :iocup,
            :f, :hi, :hf, 'reservado', :obs,
            'autoservicio', 1, :isa
        )
        RETURNING id_turno
    """), {
        "ic": id_ciudadano,
        "ia": id_recurso if tipo_recurso == "agente" else None,
        "ie": id_recurso if tipo_recurso == "espacio" else None,
        "itp": payload.id_tipo_prestacion, "iocup": id_ocupacion,
        "f": payload.fecha, "hi": hora_inicio, "hf": hora_fin,
        "obs": payload.observaciones, "isa": prest["id_subarea"],
    })).mappings().first()
    await db.commit()

    return {
        "id_turno": int(row["id_turno"]),
        "estado": "reservado",
        "fecha": payload.fecha.isoformat(),
        "hora_inicio": hora_inicio.isoformat(),
        "hora_fin": hora_fin.isoformat(),
        "prestacion_nombre": None,  # la PWA ya lo conoce (eligio la prestacion)
        "recurso_nombre": prest["recurso_nombre"],
    }


# ─── PATCH /publico/turnos/{id}/cancelar ─────────────────────────────────────

@router.patch("/{id_turno}/cancelar")
async def cancelar_mi_turno(
    id_turno: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Cancela un turno PROPIO en estado 'reservado' y libera la ocupacion
    espejo. Turno ajeno o inexistente -> 404 generico."""
    t = (await db.execute(text("""
        SELECT id_turno, estado, id_ocupacion
        FROM turnos
        WHERE id_turno = :id AND activo = TRUE AND id_ciudadano = :c
    """), {"id": id_turno, "c": current["id_ciudadano"]})).mappings().first()
    if not t:
        raise HTTPException(404, "Turno no encontrado")
    if t["estado"] == "cancelado":
        return {"id_turno": id_turno, "estado": "cancelado", "ya_cancelado": True}
    if t["estado"] != "reservado":
        raise HTTPException(409, f"No se puede cancelar un turno '{t['estado']}'")

    await db.execute(text("""
        UPDATE turnos SET estado = 'cancelado', fecha_modificacion = NOW()
        WHERE id_turno = :id
    """), {"id": id_turno})
    if t["id_ocupacion"]:
        await db.execute(text("""
            UPDATE ocupaciones SET activo = FALSE, fecha_modificacion = NOW()
            WHERE id_ocupacion = :io
        """), {"io": int(t["id_ocupacion"])})
    await db.commit()
    return {"id_turno": id_turno, "estado": "cancelado"}
