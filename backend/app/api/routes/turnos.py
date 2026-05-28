"""
ZARIS API - Router del modulo Turnos (mig 45, replanteado en mig 71).

Una PRESTACION (tipo_prestacion) define el recurso fijo (un agente O un lugar
de atencion), su duracion y su clase (atencion | reserva_espacio). Un turno
reserva un bloque de la disponibilidad efectiva de ese recurso para un
ciudadano. Estados: reservado -> cumplido | cancelado.

Al crear el turno, el backend resuelve el recurso DESDE LA PRESTACION y lo
COPIA al turno (turnos.id_agente / turnos.id_espacio, mig 70), de modo que el
turno queda autocontenido aunque la prestacion cambie de recurso despues.

Cada turno mantiene una fila espejo en `ocupaciones` (tipo='turno') para que
aparezca en la grilla del modulo Agenda. El backend sincroniza ambas tablas:
  - crear turno    -> INSERT turno + INSERT ocupacion espejo
  - cumplir turno  -> UPDATE turno.estado (la ocupacion espejo se mantiene)
  - cancelar turno -> UPDATE turno.estado + soft-delete de la ocupacion espejo
  - reprogramar    -> UPDATE turno + UPDATE ocupacion espejo

Permisos:
  - Gestion de turnos (crear/reprogramar/cumplir/cancelar): nivel 1-3.
  - ABM de prestaciones (crear/editar/baja): nivel 1-2 (supervisor/admin).
  - Lectura (catalogo + turnos): cualquier nivel autenticado.
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
    TipoPrestacionCreate,
    TipoPrestacionOut,
    TipoPrestacionUpdate,
    TurnoCreate,
    TurnoOut,
    TurnoUpdate,
)
from app.services.agenda import (
    disponibilidad_efectiva,
    turnos_respeta_disponibilidad,
)


router = APIRouter(prefix="/api/v1/turnos", tags=["turnos"])


def _require_gestion(user: dict) -> None:
    """Nivel 1-3 puede gestionar turnos. Nivel 4 (consultor) solo lee."""
    if int(user.get("nivel_acceso", 99)) > 3:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 3)")


def _require_supervisor(user: dict) -> None:
    """Nivel 1-2 (admin/supervisor) puede gestionar el catalogo de prestaciones."""
    if int(user.get("nivel_acceso", 99)) > 2:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 2)")


# =============================================================================
# Helpers de prestaciones
# =============================================================================
_PRESTACION_SELECT = """
    SELECT tp.id_tipo_prestacion, tp.nombre, tp.descripcion, tp.clase,
           tp.duracion_min, tp.tipo_recurso, tp.id_agente, tp.id_espacio,
           CASE WHEN tp.tipo_recurso = 'espacio' THEN e.nombre
                ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
           tp.id_subarea, tp.activo
    FROM tipo_prestacion tp
    LEFT JOIN agentes         a ON a.id_agente  = tp.id_agente
    LEFT JOIN espacios_agenda e ON e.id_espacio = tp.id_espacio
"""


async def _prestacion_out(db: AsyncSession, id_prestacion: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text(_PRESTACION_SELECT + " WHERE tp.id_tipo_prestacion = :id"),
                            {"id": id_prestacion})).mappings().first()
    return dict(row) if row else None


async def _validar_recurso_activo(db: AsyncSession, tipo_recurso: str, id_recurso: int) -> None:
    if tipo_recurso == "agente":
        ok = (await db.execute(text(
            "SELECT 1 FROM agentes WHERE id_agente = :id AND activo = TRUE"
        ), {"id": id_recurso})).first()
        if not ok:
            raise HTTPException(404, "Agente no encontrado o inactivo")
    else:
        ok = (await db.execute(text(
            "SELECT 1 FROM espacios_agenda WHERE id_espacio = :id AND activo = TRUE"
        ), {"id": id_recurso})).first()
        if not ok:
            raise HTTPException(404, "Espacio no encontrado o inactivo")


# =============================================================================
# CRUD prestaciones (catalogo)
# =============================================================================
@router.get("/prestaciones", response_model=list[TipoPrestacionOut])
async def listar_prestaciones(
    clase: Optional[str] = Query(None, description="atencion|reserva_espacio"),
    q: Optional[str] = Query(None, description="Texto libre sobre nombre"),
    id_municipio: int = 1,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    where = ["tp.activo = TRUE", "tp.id_municipio = :m"]
    params: dict[str, Any] = {"m": id_municipio}
    if clase:
        where.append("tp.clase = :c"); params["c"] = clase
    if q:
        where.append("tp.nombre ILIKE :q"); params["q"] = f"%{q}%"
    rows = (await db.execute(text(
        _PRESTACION_SELECT + f" WHERE {' AND '.join(where)} ORDER BY tp.nombre"
    ), params)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/prestaciones/{id_prestacion}", response_model=TipoPrestacionOut)
async def detalle_prestacion(
    id_prestacion: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    out = await _prestacion_out(db, id_prestacion)
    if out is None:
        raise HTTPException(404, "Prestacion no encontrada")
    return out


@router.post("/prestaciones", response_model=TipoPrestacionOut, status_code=201)
async def crear_prestacion(
    payload: TipoPrestacionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_supervisor(user)
    id_recurso = payload.id_agente if payload.tipo_recurso == "agente" else payload.id_espacio
    await _validar_recurso_activo(db, payload.tipo_recurso, int(id_recurso))  # type: ignore[arg-type]
    id_prestacion = await db.scalar(text("""
        INSERT INTO tipo_prestacion (
            nombre, descripcion, clase, duracion_min, tipo_recurso,
            id_agente, id_espacio, id_municipio, id_subarea,
            id_usuario_alta, id_usuario_modificacion
        ) VALUES (
            :nom, :desc, :clase, :dur, :tr, :ia, :ie, :mun, :isa, :uid, :uid
        ) RETURNING id_tipo_prestacion
    """), {
        "nom": payload.nombre, "desc": payload.descripcion, "clase": payload.clase,
        "dur": payload.duracion_min, "tr": payload.tipo_recurso,
        "ia": payload.id_agente, "ie": payload.id_espacio,
        "mun": payload.id_municipio, "isa": payload.id_subarea,
        "uid": user["id_usuario"],
    })
    await db.commit()
    out = await _prestacion_out(db, int(id_prestacion))
    if out is None:
        raise HTTPException(500, "Prestacion creada pero no se pudo releer")
    return out


@router.put("/prestaciones/{id_prestacion}", response_model=TipoPrestacionOut)
async def editar_prestacion(
    id_prestacion: int,
    payload: TipoPrestacionUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_supervisor(user)
    existe = (await db.execute(text(
        "SELECT 1 FROM tipo_prestacion WHERE id_tipo_prestacion = :id AND activo = TRUE"
    ), {"id": id_prestacion})).first()
    if not existe:
        raise HTTPException(404, "Prestacion no encontrada")
    id_recurso = payload.id_agente if payload.tipo_recurso == "agente" else payload.id_espacio
    await _validar_recurso_activo(db, payload.tipo_recurso, int(id_recurso))  # type: ignore[arg-type]
    await db.execute(text("""
        UPDATE tipo_prestacion SET
            nombre = :nom, descripcion = :desc, clase = :clase, duracion_min = :dur,
            tipo_recurso = :tr, id_agente = :ia, id_espacio = :ie, id_subarea = :isa,
            fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_tipo_prestacion = :id
    """), {
        "id": id_prestacion, "nom": payload.nombre, "desc": payload.descripcion,
        "clase": payload.clase, "dur": payload.duracion_min, "tr": payload.tipo_recurso,
        "ia": payload.id_agente, "ie": payload.id_espacio, "isa": payload.id_subarea,
        "uid": user["id_usuario"],
    })
    await db.commit()
    out = await _prestacion_out(db, id_prestacion)
    return out  # type: ignore


@router.delete("/prestaciones/{id_prestacion}", status_code=204)
async def baja_prestacion(
    id_prestacion: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_supervisor(user)
    res = await db.execute(text("""
        UPDATE tipo_prestacion
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_tipo_prestacion = :id AND activo = TRUE
    """), {"id": id_prestacion, "uid": user["id_usuario"]})
    if res.rowcount == 0:
        raise HTTPException(404, "Prestacion no encontrada")
    await db.commit()
    return Response(status_code=204)


# =============================================================================
# Helper de turnos
# =============================================================================
async def _turno_to_out(db: AsyncSession, id_turno: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT t.id_turno, t.id_ciudadano,
               COALESCE(c.apellido, '') || ', ' || COALESCE(c.nombre, '') AS ciudadano_nombre,
               c.doc_nro AS ciudadano_dni,
               t.id_agente,
               CASE WHEN t.id_agente IS NOT NULL
                    THEN COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS agente_nombre,
               t.id_espacio, e.nombre AS espacio_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN 'espacio' ELSE 'agente' END AS recurso_tipo,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               t.id_tipo_prestacion, tp.nombre AS prestacion_nombre, tp.clase AS prestacion_clase,
               t.id_ocupacion, t.fecha, t.hora_inicio, t.hora_fin, t.estado,
               t.observaciones, t.activo, t.id_municipio, t.id_subarea,
               t.fecha_alta, t.fecha_modificacion
        FROM turnos t
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano        = t.id_ciudadano
        LEFT JOIN agentes         a  ON a.id_agente           = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio          = t.id_espacio
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        WHERE t.id_turno = :id
    """), {"id": id_turno})).mappings().first()
    return dict(row) if row else None


# =============================================================================
# CRUD turnos
# =============================================================================
@router.get("", response_model=list[TurnoOut])
async def listar_turnos(
    response: Response,
    estado: Optional[str] = Query(None, description="reservado|cumplido|cancelado"),
    id_agente: Optional[int] = None,
    id_espacio: Optional[int] = None,
    id_ciudadano: Optional[int] = None,
    id_tipo_prestacion: Optional[int] = None,
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
    if id_espacio is not None:
        where.append("t.id_espacio = :ie"); params["ie"] = id_espacio
    if id_ciudadano is not None:
        where.append("t.id_ciudadano = :ic"); params["ic"] = id_ciudadano
    if id_tipo_prestacion is not None:
        where.append("t.id_tipo_prestacion = :itp"); params["itp"] = id_tipo_prestacion
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
               CASE WHEN t.id_agente IS NOT NULL
                    THEN COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS agente_nombre,
               t.id_espacio, e.nombre AS espacio_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN 'espacio' ELSE 'agente' END AS recurso_tipo,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               t.id_tipo_prestacion, tp.nombre AS prestacion_nombre, tp.clase AS prestacion_clase,
               t.id_ocupacion, t.fecha, t.hora_inicio, t.hora_fin, t.estado,
               t.observaciones, t.activo, t.id_municipio, t.id_subarea,
               t.fecha_alta, t.fecha_modificacion
        FROM turnos t
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano        = t.id_ciudadano
        LEFT JOIN agentes         a  ON a.id_agente           = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio          = t.id_espacio
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
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
    """Crea un turno + su ocupacion espejo en la grilla de Agenda. El recurso y
    la duracion salen de la prestacion; el recurso se copia al turno."""
    _require_gestion(user)

    # Validar ciudadano
    ciu = (await db.execute(text(
        "SELECT 1 FROM ciudadanos WHERE id_ciudadano = :id AND activo = TRUE"
    ), {"id": payload.id_ciudadano})).first()
    if not ciu:
        raise HTTPException(404, "Ciudadano no encontrado o inactivo")

    # Resolver la prestacion: recurso fijo + duracion.
    prest = (await db.execute(text("""
        SELECT tipo_recurso, id_agente, id_espacio, duracion_min
        FROM tipo_prestacion WHERE id_tipo_prestacion = :id AND activo = TRUE
    """), {"id": payload.id_tipo_prestacion})).mappings().first()
    if not prest:
        raise HTTPException(404, "Prestacion no encontrada o inactiva")
    tipo_recurso = prest["tipo_recurso"]
    id_recurso = prest["id_agente"] if tipo_recurso == "agente" else prest["id_espacio"]
    if id_recurso is None:
        raise HTTPException(422, "La prestacion no tiene un recurso valido asignado")
    await _validar_recurso_activo(db, tipo_recurso, int(id_recurso))

    # hora_fin: usa la del payload o la calcula con la duracion de la prestacion.
    hora_fin = payload.hora_fin
    if hora_fin is None:
        base = datetime.combine(payload.fecha, payload.hora_inicio)
        hora_fin = (base + timedelta(minutes=int(prest["duracion_min"]))).time()
        if hora_fin <= payload.hora_inicio:
            raise HTTPException(422, "La duracion de la prestacion excede el dia")

    # Switch global (mig 69): el turno debe caer dentro de la disponibilidad
    # efectiva del recurso (horario - feriados - novedades). Apagable.
    if await turnos_respeta_disponibilidad(db):
        rangos = await disponibilidad_efectiva(db, tipo_recurso, int(id_recurso), payload.fecha)
        dentro = any(
            r["hora_inicio"] <= payload.hora_inicio and hora_fin <= r["hora_fin"]
            for r in rangos
        )
        if not dentro:
            que = "del espacio" if tipo_recurso == "espacio" else "del agente"
            raise HTTPException(409, f"El horario no esta dentro de la disponibilidad {que} (feriado, inasistencia o fuera de horario)")

    # Solapamiento contra la ocupacion del mismo recurso.
    solapado = await db.scalar(text("""
        SELECT 1 FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir
          AND fecha = :f AND hora_inicio < :hf AND hora_fin > :hi
        LIMIT 1
    """), {"tr": tipo_recurso, "ir": int(id_recurso), "f": payload.fecha, "hi": payload.hora_inicio, "hf": hora_fin})
    if solapado:
        que = "El espacio" if tipo_recurso == "espacio" else "El agente"
        raise HTTPException(409, f"{que} ya tiene una ocupacion en ese horario")

    # Ocupacion espejo en la grilla de Agenda
    id_ocupacion = await db.scalar(text("""
        INSERT INTO ocupaciones (
            tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
            id_ciudadano, motivo, id_municipio, id_usuario_alta
        ) VALUES (
            'turno', :tr, :ir, :f, :hi, :hf, :ic, :mot, :mun, :uid
        )
        RETURNING id_ocupacion
    """), {
        "tr": tipo_recurso, "ir": int(id_recurso), "f": payload.fecha,
        "hi": payload.hora_inicio, "hf": hora_fin, "ic": payload.id_ciudadano,
        "mot": f"Turno: {payload.observaciones}" if payload.observaciones else "Turno",
        "mun": payload.id_municipio, "uid": user["id_usuario"],
    })

    # Copiar el recurso de la prestacion al turno (turno autocontenido).
    id_agente_turno = int(id_recurso) if tipo_recurso == "agente" else None
    id_espacio_turno = int(id_recurso) if tipo_recurso == "espacio" else None

    id_turno = await db.scalar(text("""
        INSERT INTO turnos (
            id_ciudadano, id_agente, id_espacio, id_tipo_prestacion, id_ocupacion,
            fecha, hora_inicio, hora_fin, estado, observaciones,
            id_municipio, id_subarea, id_usuario_alta, id_usuario_modificacion
        ) VALUES (
            :ic, :ia, :ie, :itp, :iocup,
            :f, :hi, :hf, 'reservado', :obs,
            :mun, :isa, :uid, :uid
        )
        RETURNING id_turno
    """), {
        "ic": payload.id_ciudadano, "ia": id_agente_turno, "ie": id_espacio_turno,
        "itp": payload.id_tipo_prestacion, "iocup": id_ocupacion,
        "f": payload.fecha, "hi": payload.hora_inicio, "hf": hora_fin,
        "obs": payload.observaciones, "mun": payload.id_municipio, "isa": payload.id_subarea,
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
    """Reprograma un turno 'reservado'. El recurso es el de la prestacion: si se
    cambia la prestacion, se re-resuelve recurso + duracion. Sincroniza la
    ocupacion espejo."""
    _require_gestion(user)
    turno = (await db.execute(text("""
        SELECT id_turno, id_agente, id_espacio, id_tipo_prestacion, id_ocupacion,
               fecha, hora_inicio, hora_fin, estado, id_municipio
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

    fecha = data.get("fecha", turno["fecha"])
    hora_inicio = data.get("hora_inicio", turno["hora_inicio"])

    # Recurso + duracion: si cambia la prestacion, se re-resuelven desde ella.
    cambia_prest = "id_tipo_prestacion" in data and data["id_tipo_prestacion"] is not None
    id_tipo_prestacion = data.get("id_tipo_prestacion", turno["id_tipo_prestacion"])
    prest = (await db.execute(text("""
        SELECT tipo_recurso, id_agente, id_espacio, duracion_min
        FROM tipo_prestacion WHERE id_tipo_prestacion = :id AND activo = TRUE
    """), {"id": id_tipo_prestacion})).mappings().first()
    if not prest:
        raise HTTPException(404, "Prestacion no encontrada o inactiva")
    tipo_recurso = prest["tipo_recurso"]
    id_recurso = prest["id_agente"] if tipo_recurso == "agente" else prest["id_espacio"]
    if id_recurso is None:
        raise HTTPException(422, "La prestacion no tiene un recurso valido asignado")

    # hora_fin: explicita, o recalculada con la duracion de la prestacion cuando
    # cambio algo que la afecta (prestacion, fecha u hora).
    hora_fin = data.get("hora_fin")
    if hora_fin is None:
        if cambia_prest or "hora_inicio" in data or "fecha" in data:
            base = datetime.combine(fecha, hora_inicio)
            hora_fin = (base + timedelta(minutes=int(prest["duracion_min"]))).time()
        else:
            hora_fin = turno["hora_fin"]
    if hora_fin <= hora_inicio:
        raise HTTPException(422, "hora_fin debe ser mayor que hora_inicio")

    # Switch global: el nuevo horario debe caer en la disponibilidad efectiva.
    if await turnos_respeta_disponibilidad(db):
        rangos = await disponibilidad_efectiva(db, tipo_recurso, int(id_recurso), fecha)
        if not any(r["hora_inicio"] <= hora_inicio and hora_fin <= r["hora_fin"] for r in rangos):
            raise HTTPException(409, "El nuevo horario no esta dentro de la disponibilidad del recurso")

    # Solapamiento contra la ocupacion del mismo recurso (excluyendo la propia).
    solapado = await db.scalar(text("""
        SELECT 1 FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir
          AND fecha = :f AND hora_inicio < :hf AND hora_fin > :hi
          AND (:io IS NULL OR id_ocupacion <> :io)
        LIMIT 1
    """), {"tr": tipo_recurso, "ir": int(id_recurso), "f": fecha, "hi": hora_inicio, "hf": hora_fin,
           "io": turno["id_ocupacion"]})
    if solapado:
        que = "El espacio" if tipo_recurso == "espacio" else "El agente"
        raise HTTPException(409, f"{que} ya tiene una ocupacion en ese horario")

    id_agente_turno = int(id_recurso) if tipo_recurso == "agente" else None
    id_espacio_turno = int(id_recurso) if tipo_recurso == "espacio" else None

    sets = ["fecha = :f", "hora_inicio = :hi", "hora_fin = :hf",
            "id_tipo_prestacion = :itp", "id_agente = :ia", "id_espacio = :ie",
            "fecha_modificacion = NOW()", "id_usuario_modificacion = :uid"]
    params: dict[str, Any] = {
        "id": id_turno, "f": fecha, "hi": hora_inicio, "hf": hora_fin,
        "itp": id_tipo_prestacion, "ia": id_agente_turno, "ie": id_espacio_turno,
        "uid": user["id_usuario"],
    }
    if "observaciones" in data:
        sets.append("observaciones = :obs"); params["obs"] = data["observaciones"]
    await db.execute(text(f"UPDATE turnos SET {', '.join(sets)} WHERE id_turno = :id"), params)

    # Sincronizar ocupacion espejo (recurso puede haber cambiado).
    if turno["id_ocupacion"]:
        await db.execute(text("""
            UPDATE ocupaciones
            SET tipo_recurso = :tr, id_recurso = :ir,
                fecha = :f, hora_inicio = :hi, hora_fin = :hf,
                fecha_modificacion = NOW(), id_usuario_modificacion = :uid
            WHERE id_ocupacion = :io
        """), {"tr": tipo_recurso, "ir": int(id_recurso), "f": fecha,
               "hi": hora_inicio, "hf": hora_fin,
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
