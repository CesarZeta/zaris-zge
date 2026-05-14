"""
ZARIS API - Router del modulo Turnos (mig 45).

Un turno reserva un bloque de la disponibilidad de un agente para que un
ciudadano realice un tramite (tipo de servicio). Estados:
  reservado -> cumplido | cancelado

Cada turno mantiene una fila espejo en `ocupaciones` (tipo='turno',
tipo_recurso='agente') para que aparezca en la grilla del modulo Agenda.
El backend sincroniza ambas tablas:
  - crear turno    -> INSERT turno + INSERT ocupacion espejo
  - cumplir turno  -> UPDATE turno.estado (la ocupacion espejo se mantiene)
  - cancelar turno -> UPDATE turno.estado + soft-delete de la ocupacion espejo
  - reprogramar    -> UPDATE turno + UPDATE ocupacion espejo

Permisos: nivel 1-3 (admin/supervisor/operador) puede mutar; cualquier nivel
autenticado puede leer.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.turnos import (
    TipoServicioTurnoOut,
    TurnoCreate,
    TurnoOut,
    TurnoUpdate,
)


router = APIRouter(prefix="/api/v1/turnos", tags=["turnos"])


def _require_gestion(user: dict) -> None:
    """Nivel 1-3 puede gestionar turnos. Nivel 4 (consultor) solo lee."""
    if int(user.get("nivel_acceso", 99)) > 3:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 3)")


async def _turno_to_out(db: AsyncSession, id_turno: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT t.id_turno, t.id_ciudadano,
               COALESCE(c.apellido, '') || ', ' || COALESCE(c.nombre, '') AS ciudadano_nombre,
               c.doc_nro AS ciudadano_dni,
               t.id_agente,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               t.id_tipo_servicio_turno, ts.nombre AS tipo_servicio_nombre,
               t.id_ocupacion, t.fecha, t.hora_inicio, t.hora_fin, t.estado,
               t.observaciones, t.activo, t.id_municipio, t.id_subarea,
               t.fecha_alta, t.fecha_modificacion
        FROM turnos t
        LEFT JOIN ciudadanos          c  ON c.id_ciudadano           = t.id_ciudadano
        LEFT JOIN agentes             a  ON a.id_agente              = t.id_agente
        LEFT JOIN tipo_servicio_turno ts ON ts.id_tipo_servicio_turno = t.id_tipo_servicio_turno
        WHERE t.id_turno = :id
    """), {"id": id_turno})).mappings().first()
    return dict(row) if row else None


# =============================================================================
# Catalogo: tipos de servicio de turno
# =============================================================================
@router.get("/catalogo/tipos-servicio", response_model=list[TipoServicioTurnoOut])
async def listar_tipos_servicio(
    id_municipio: int = 1,
    q: Optional[str] = Query(None, description="Texto libre sobre nombre"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    where = ["activo = TRUE", "id_municipio = :m"]
    params: dict[str, Any] = {"m": id_municipio}
    if q:
        where.append("nombre ILIKE :q"); params["q"] = f"%{q}%"
    rows = (await db.execute(text(f"""
        SELECT id_tipo_servicio_turno, nombre, descripcion, duracion_min, activo
        FROM tipo_servicio_turno
        WHERE {' AND '.join(where)}
        ORDER BY nombre
    """), params)).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# CRUD turnos
# =============================================================================
@router.get("", response_model=list[TurnoOut])
async def listar_turnos(
    response: Response,
    estado: Optional[str] = Query(None, description="reservado|cumplido|cancelado"),
    id_agente: Optional[int] = None,
    id_ciudadano: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    id_municipio: int = 1,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    where = ["t.activo = TRUE", "t.id_municipio = :m"]
    params: dict[str, Any] = {"m": id_municipio}
    if estado:
        where.append("t.estado = :e"); params["e"] = estado
    if id_agente is not None:
        where.append("t.id_agente = :ia"); params["ia"] = id_agente
    if id_ciudadano is not None:
        where.append("t.id_ciudadano = :ic"); params["ic"] = id_ciudadano
    if fecha_desde:
        where.append("t.fecha >= :fd"); params["fd"] = fecha_desde
    if fecha_hasta:
        where.append("t.fecha <= :fh"); params["fh"] = fecha_hasta
    where_sql = " AND ".join(where)
    total = await db.scalar(text(f"SELECT COUNT(*) FROM turnos t WHERE {where_sql}"), params)
    params_page = {**params, "lim": limit, "off": offset}
    rows = (await db.execute(text(f"""
        SELECT t.id_turno, t.id_ciudadano,
               COALESCE(c.apellido, '') || ', ' || COALESCE(c.nombre, '') AS ciudadano_nombre,
               c.doc_nro AS ciudadano_dni,
               t.id_agente,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               t.id_tipo_servicio_turno, ts.nombre AS tipo_servicio_nombre,
               t.id_ocupacion, t.fecha, t.hora_inicio, t.hora_fin, t.estado,
               t.observaciones, t.activo, t.id_municipio, t.id_subarea,
               t.fecha_alta, t.fecha_modificacion
        FROM turnos t
        LEFT JOIN ciudadanos          c  ON c.id_ciudadano           = t.id_ciudadano
        LEFT JOIN agentes             a  ON a.id_agente              = t.id_agente
        LEFT JOIN tipo_servicio_turno ts ON ts.id_tipo_servicio_turno = t.id_tipo_servicio_turno
        WHERE {where_sql}
        ORDER BY t.fecha DESC, t.hora_inicio
        LIMIT :lim OFFSET :off
    """), params_page)).mappings().all()
    response.headers["X-Total-Count"] = str(int(total or 0))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [dict(r) for r in rows]


@router.get("/{id_turno}", response_model=TurnoOut)
async def detalle_turno(
    id_turno: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    out = await _turno_to_out(db, id_turno)
    if out is None:
        raise HTTPException(404, "Turno no encontrado")
    return out


@router.post("", response_model=TurnoOut, status_code=201)
async def crear_turno(
    payload: TurnoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Crea un turno + su ocupacion espejo en la grilla de Agenda."""
    _require_gestion(user)

    # Validar FKs
    ciu = (await db.execute(text(
        "SELECT 1 FROM ciudadanos WHERE id_ciudadano = :id AND activo = TRUE"
    ), {"id": payload.id_ciudadano})).first()
    if not ciu:
        raise HTTPException(404, "Ciudadano no encontrado o inactivo")
    ag = (await db.execute(text(
        "SELECT 1 FROM agentes WHERE id_agente = :id AND activo = TRUE"
    ), {"id": payload.id_agente})).first()
    if not ag:
        raise HTTPException(404, "Agente no encontrado o inactivo")
    tipo = (await db.execute(text(
        "SELECT duracion_min FROM tipo_servicio_turno WHERE id_tipo_servicio_turno = :id AND activo = TRUE"
    ), {"id": payload.id_tipo_servicio_turno})).mappings().first()
    if not tipo:
        raise HTTPException(404, "Tipo de servicio no encontrado o inactivo")

    # hora_fin: usa la del payload o la calcula con la duracion del tipo de servicio
    hora_fin = payload.hora_fin
    if hora_fin is None:
        base = datetime.combine(payload.fecha, payload.hora_inicio)
        hora_fin = (base + timedelta(minutes=int(tipo["duracion_min"]))).time()
        if hora_fin <= payload.hora_inicio:
            raise HTTPException(422, "La duracion del tipo de servicio excede el dia")

    # Solapamiento con otro turno reservado/cumplido del mismo agente
    solapado = await db.scalar(text("""
        SELECT 1 FROM turnos
        WHERE id_agente = :ia AND fecha = :f AND activo = TRUE
          AND estado <> 'cancelado'
          AND hora_inicio < :hf AND hora_fin > :hi
        LIMIT 1
    """), {"ia": payload.id_agente, "f": payload.fecha, "hi": payload.hora_inicio, "hf": hora_fin})
    if solapado:
        raise HTTPException(409, "El agente ya tiene un turno en ese horario")

    # Ocupacion espejo en la grilla de Agenda
    id_ocupacion = await db.scalar(text("""
        INSERT INTO ocupaciones (
            tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
            id_ciudadano, motivo, id_municipio, id_usuario_alta
        ) VALUES (
            'turno', 'agente', :ia, :f, :hi, :hf,
            :ic, :mot, :mun, :uid
        )
        RETURNING id_ocupacion
    """), {
        "ia": payload.id_agente, "f": payload.fecha,
        "hi": payload.hora_inicio, "hf": hora_fin,
        "ic": payload.id_ciudadano,
        "mot": f"Turno: {payload.observaciones}" if payload.observaciones else "Turno",
        "mun": payload.id_municipio, "uid": user["id_usuario"],
    })

    id_turno = await db.scalar(text("""
        INSERT INTO turnos (
            id_ciudadano, id_agente, id_tipo_servicio_turno, id_ocupacion,
            fecha, hora_inicio, hora_fin, estado, observaciones,
            id_municipio, id_subarea, id_usuario_alta, id_usuario_modificacion
        ) VALUES (
            :ic, :ia, :its, :iocup,
            :f, :hi, :hf, 'reservado', :obs,
            :mun, :isa, :uid, :uid
        )
        RETURNING id_turno
    """), {
        "ic": payload.id_ciudadano, "ia": payload.id_agente,
        "its": payload.id_tipo_servicio_turno, "iocup": id_ocupacion,
        "f": payload.fecha, "hi": payload.hora_inicio, "hf": hora_fin,
        "obs": payload.observaciones,
        "mun": payload.id_municipio, "isa": payload.id_subarea,
        "uid": user["id_usuario"],
    })
    await db.commit()
    out = await _turno_to_out(db, int(id_turno))
    if out is None:
        raise HTTPException(500, "Turno creado pero no se pudo releer")
    return out


@router.put("/{id_turno}", response_model=TurnoOut)
async def reprogramar_turno(
    id_turno: int,
    payload: TurnoUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Reprograma un turno en estado 'reservado'. Sincroniza la ocupacion espejo."""
    _require_gestion(user)
    turno = (await db.execute(text("""
        SELECT id_turno, id_agente, id_ocupacion, fecha, hora_inicio, hora_fin, estado
        FROM turnos WHERE id_turno = :id AND activo = TRUE
    """), {"id": id_turno})).mappings().first()
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    if turno["estado"] != "reservado":
        raise HTTPException(409, f"Solo se puede reprogramar un turno 'reservado' (estado actual: '{turno['estado']}')")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        out = await _turno_to_out(db, id_turno)
        return out  # type: ignore

    # Resolver valores efectivos
    fecha = data.get("fecha", turno["fecha"])
    hora_inicio = data.get("hora_inicio", turno["hora_inicio"])
    hora_fin = data.get("hora_fin")
    if hora_fin is None:
        if "id_tipo_servicio_turno" in data or "hora_inicio" in data or "fecha" in data:
            # Recalcular con la duracion del tipo (nuevo o el que ya tenia)
            its = data.get("id_tipo_servicio_turno")
            if its is not None:
                dur_row = (await db.execute(text(
                    "SELECT duracion_min FROM tipo_servicio_turno WHERE id_tipo_servicio_turno = :id AND activo = TRUE"
                ), {"id": its})).mappings().first()
                if not dur_row:
                    raise HTTPException(404, "Tipo de servicio no encontrado o inactivo")
                base = datetime.combine(fecha, hora_inicio)
                hora_fin = (base + timedelta(minutes=int(dur_row["duracion_min"]))).time()
            else:
                hora_fin = turno["hora_fin"]
        else:
            hora_fin = turno["hora_fin"]
    if hora_fin <= hora_inicio:
        raise HTTPException(422, "hora_fin debe ser mayor que hora_inicio")

    if "id_tipo_servicio_turno" in data and data["id_tipo_servicio_turno"] is not None:
        tipo = (await db.execute(text(
            "SELECT 1 FROM tipo_servicio_turno WHERE id_tipo_servicio_turno = :id AND activo = TRUE"
        ), {"id": data["id_tipo_servicio_turno"]})).first()
        if not tipo:
            raise HTTPException(404, "Tipo de servicio no encontrado o inactivo")

    # Solapamiento (excluyendo el propio turno)
    solapado = await db.scalar(text("""
        SELECT 1 FROM turnos
        WHERE id_agente = :ia AND fecha = :f AND activo = TRUE
          AND estado <> 'cancelado' AND id_turno <> :id
          AND hora_inicio < :hf AND hora_fin > :hi
        LIMIT 1
    """), {"ia": turno["id_agente"], "f": fecha, "hi": hora_inicio, "hf": hora_fin, "id": id_turno})
    if solapado:
        raise HTTPException(409, "El agente ya tiene un turno en ese horario")

    sets = ["fecha = :f", "hora_inicio = :hi", "hora_fin = :hf",
            "fecha_modificacion = NOW()", "id_usuario_modificacion = :uid"]
    params: dict[str, Any] = {
        "id": id_turno, "f": fecha, "hi": hora_inicio, "hf": hora_fin,
        "uid": user["id_usuario"],
    }
    if "id_tipo_servicio_turno" in data and data["id_tipo_servicio_turno"] is not None:
        sets.append("id_tipo_servicio_turno = :its"); params["its"] = data["id_tipo_servicio_turno"]
    if "observaciones" in data:
        sets.append("observaciones = :obs"); params["obs"] = data["observaciones"]
    await db.execute(text(f"UPDATE turnos SET {', '.join(sets)} WHERE id_turno = :id"), params)

    # Sincronizar ocupacion espejo
    if turno["id_ocupacion"]:
        await db.execute(text("""
            UPDATE ocupaciones
            SET fecha = :f, hora_inicio = :hi, hora_fin = :hf,
                fecha_modificacion = NOW(), id_usuario_modificacion = :uid
            WHERE id_ocupacion = :io
        """), {"f": fecha, "hi": hora_inicio, "hf": hora_fin,
               "uid": user["id_usuario"], "io": turno["id_ocupacion"]})
    await db.commit()
    out = await _turno_to_out(db, id_turno)
    return out  # type: ignore


@router.patch("/{id_turno}/cumplir", response_model=TurnoOut)
async def cumplir_turno(
    id_turno: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Marca el turno como cumplido (el ciudadano se presento y se atendio)."""
    _require_gestion(user)
    turno = (await db.execute(text(
        "SELECT estado FROM turnos WHERE id_turno = :id AND activo = TRUE"
    ), {"id": id_turno})).mappings().first()
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    if turno["estado"] == "cumplido":
        out = await _turno_to_out(db, id_turno)
        return out  # type: ignore
    if turno["estado"] != "reservado":
        raise HTTPException(409, f"Solo se puede cumplir un turno 'reservado' (estado actual: '{turno['estado']}')")
    await db.execute(text("""
        UPDATE turnos
        SET estado = 'cumplido', fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_turno = :id
    """), {"id": id_turno, "uid": user["id_usuario"]})
    await db.commit()
    out = await _turno_to_out(db, id_turno)
    return out  # type: ignore


@router.patch("/{id_turno}/cancelar", response_model=TurnoOut)
async def cancelar_turno(
    id_turno: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Cancela el turno y soft-deletea su ocupacion espejo (libera la grilla)."""
    _require_gestion(user)
    turno = (await db.execute(text(
        "SELECT id_ocupacion, estado FROM turnos WHERE id_turno = :id AND activo = TRUE"
    ), {"id": id_turno})).mappings().first()
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    if turno["estado"] == "cancelado":
        out = await _turno_to_out(db, id_turno)
        return out  # type: ignore
    if turno["estado"] != "reservado":
        raise HTTPException(409, f"Solo se puede cancelar un turno 'reservado' (estado actual: '{turno['estado']}')")
    await db.execute(text("""
        UPDATE turnos
        SET estado = 'cancelado', fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_turno = :id
    """), {"id": id_turno, "uid": user["id_usuario"]})
    if turno["id_ocupacion"]:
        await db.execute(text("""
            UPDATE ocupaciones
            SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
            WHERE id_ocupacion = :io
        """), {"io": turno["id_ocupacion"], "uid": user["id_usuario"]})
    await db.commit()
    out = await _turno_to_out(db, id_turno)
    return out  # type: ignore
