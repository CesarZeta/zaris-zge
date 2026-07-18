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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.turnos import (
    TipoPrestacionCreate,
    TipoPrestacionOut,
    TipoPrestacionUpdate,
    TurnoAtencionOut,
    TurnoCreate,
    TurnoCumplir,
    TurnoOut,
    TurnoUpdate,
)
from app.services.agenda import (
    advisory_lock_tx,
    disponibilidad_efectiva,
    turnos_respeta_disponibilidad,
)
from app.services import encuestas_service


router = APIRouter(prefix="/api/v1/turnos", tags=["turnos"])


def _require_gestion(user: dict) -> None:
    """Nivel 1-4 puede gestionar turnos (mig 92: 4=Gestión, agente que atiende).
    Nivel 5 (consultor) solo lee."""
    if int(user.get("nivel_acceso", 99)) > 4:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 4)")


def _require_supervisor(user: dict) -> None:
    """Nivel 1-2 (admin/supervisor) puede gestionar el catalogo de prestaciones."""
    if int(user.get("nivel_acceso", 99)) > 2:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 2)")


async def _scope_turnos_para_usuario(db: AsyncSession, user: dict) -> Optional[dict[str, Any]]:
    """Resuelve el alcance de visibilidad de turnos del usuario.

    - Nivel <= 2 (admin/supervisor): None -> ve TODOS los turnos.
    - Nivel 3-4 (operador/consultor): dict con su id_agente + id_subarea.
      Solo ve los turnos donde es el agente involucrado, o los de un lugar de
      atencion (espacio) de su misma subarea. Si el usuario no esta vinculado a
      un agente, queda con id_agente=-1 y id_subarea=None (no ve nada propio).
    """
    if int(user.get("nivel_acceso", 99)) <= 2:
        return None
    row = (await db.execute(text(
        "SELECT id_agente, id_subarea FROM agentes WHERE id_usuario = :u AND activo = TRUE LIMIT 1"
    ), {"u": user["id_usuario"]})).mappings().first()
    if not row:
        return {"id_agente": -1, "id_subarea": None}
    return {"id_agente": row["id_agente"], "id_subarea": row["id_subarea"]}


# =============================================================================
# Helpers de prestaciones
# =============================================================================
_PRESTACION_SELECT = """
    SELECT tp.id_tipo_prestacion, tp.nombre, tp.descripcion, tp.clase,
           tp.duracion_min, tp.tipo_recurso, tp.id_agente, tp.id_espacio,
           CASE WHEN tp.tipo_recurso = 'espacio' THEN e.nombre
                ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
           tp.id_subarea, sa.nombre AS subarea_nombre,
           ar.id_area, ar.nombre AS area_nombre,
           tp.registra_atencion, tp.activo
    FROM tipo_prestacion tp
    LEFT JOIN agentes         a  ON a.id_agente   = tp.id_agente
    LEFT JOIN espacios_agenda e  ON e.id_espacio  = tp.id_espacio
    LEFT JOIN subarea         sa ON sa.id_subarea = tp.id_subarea
    LEFT JOIN area            ar ON ar.id_area    = sa.id_area
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
            id_agente, id_espacio, id_municipio, id_subarea, registra_atencion,
            id_usuario_alta, id_usuario_modificacion
        ) VALUES (
            :nom, :desc, :clase, :dur, :tr, :ia, :ie, :mun, :isa, :reg, :uid, :uid
        ) RETURNING id_tipo_prestacion
    """), {
        "nom": payload.nombre, "desc": payload.descripcion, "clase": payload.clase,
        "dur": payload.duracion_min, "tr": payload.tipo_recurso,
        "ia": payload.id_agente, "ie": payload.id_espacio,
        "mun": payload.id_municipio, "isa": payload.id_subarea,
        "reg": payload.registra_atencion and payload.clase == "atencion",
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
            registra_atencion = :reg,
            fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_tipo_prestacion = :id
    """), {
        "id": id_prestacion, "nom": payload.nombre, "desc": payload.descripcion,
        "clase": payload.clase, "dur": payload.duracion_min, "tr": payload.tipo_recurso,
        "ia": payload.id_agente, "ie": payload.id_espacio, "isa": payload.id_subarea,
        "reg": payload.registra_atencion and payload.clase == "atencion",
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
               tp.registra_atencion,
               pa.id_area AS prestacion_id_area, pa.nombre AS prestacion_area_nombre,
               t.id_ocupacion, t.fecha, t.hora_inicio, t.hora_fin, t.estado,
               t.observaciones, t.activo, t.id_municipio, t.id_subarea,
               t.fecha_alta, t.fecha_modificacion
        FROM turnos t
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano        = t.id_ciudadano
        LEFT JOIN agentes         a  ON a.id_agente           = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio          = t.id_espacio
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN subarea         ps ON ps.id_subarea         = tp.id_subarea
        LEFT JOIN area            pa ON pa.id_area            = ps.id_area
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
    user: dict = Depends(get_current_user),
):
    where = ["t.activo = TRUE", "t.id_municipio = :m"]
    params: dict[str, Any] = {"m": id_municipio}

    # Scope por nivel: el operador solo ve sus turnos + los de lugares de su
    # subarea; supervisor+ ve todo. El guard es backend (no evadible por curl).
    scope = await _scope_turnos_para_usuario(db, user)
    if scope is not None:
        where.append(
            "(t.id_agente = :scope_agente OR t.id_espacio IN "
            "(SELECT id_espacio FROM espacios_agenda WHERE id_subarea = :scope_subarea AND activo = TRUE))"
        )
        params["scope_agente"] = scope["id_agente"]
        params["scope_subarea"] = scope["id_subarea"]

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
               tp.registra_atencion,
               pa.id_area AS prestacion_id_area, pa.nombre AS prestacion_area_nombre,
               t.id_ocupacion, t.fecha, t.hora_inicio, t.hora_fin, t.estado,
               t.observaciones, t.activo, t.id_municipio, t.id_subarea,
               t.fecha_alta, t.fecha_modificacion
        FROM turnos t
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano        = t.id_ciudadano
        LEFT JOIN agentes         a  ON a.id_agente           = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio          = t.id_espacio
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN subarea         ps ON ps.id_subarea         = tp.id_subarea
        LEFT JOIN area            pa ON pa.id_area            = ps.id_area
        WHERE {where_sql}
        ORDER BY t.fecha DESC, t.hora_inicio
        LIMIT :lim OFFSET :off
    """), params_page)).mappings().all()
    response.headers["X-Total-Count"] = str(int(total or 0))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [dict(r) for r in rows]


# Segmento fijo: registrado ANTES de GET /{id_turno} (param greedy, §5).
@router.get("/atenciones", response_model=list[TurnoAtencionOut])
async def historial_atenciones(
    id_ciudadano: int = Query(..., description="Ciudadano cuya historia de atenciones se consulta"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Historia de atenciones registradas de un ciudadano (turnos cumplidos de
    prestaciones con registra_atencion, mig 86). Dato de salud sensible (Ley
    25.326): aplica el mismo scope por nivel que los turnos — supervisor+ ve
    todo; el operador solo las atenciones de turnos a su alcance (agente propio
    o espacio de su subarea)."""
    where = ["ta.activo = TRUE", "ta.id_ciudadano = :ic"]
    params: dict[str, Any] = {"ic": id_ciudadano, "lim": limit}
    scope = await _scope_turnos_para_usuario(db, user)
    if scope is not None:
        where.append(
            "(t.id_agente = :scope_agente OR t.id_espacio IN "
            "(SELECT id_espacio FROM espacios_agenda WHERE id_subarea = :scope_subarea AND activo = TRUE))"
        )
        params["scope_agente"] = scope["id_agente"]
        params["scope_subarea"] = scope["id_subarea"]
    rows = (await db.execute(text(f"""
        SELECT ta.id_turno_atencion, ta.id_turno, ta.id_ciudadano,
               t.fecha, tp.nombre AS prestacion_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               ta.intervencion, ta.recomendaciones,
               u.nombre AS atendido_por,
               ta.fecha_alta
        FROM turno_atencion ta
        JOIN turnos t ON t.id_turno = ta.id_turno
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN agentes         a  ON a.id_agente           = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio          = t.id_espacio
        LEFT JOIN usuarios        u  ON u.id_usuario          = ta.id_usuario_alta
        WHERE {' AND '.join(where)}
        ORDER BY t.fecha DESC, t.hora_inicio DESC
        LIMIT :lim
    """), params)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{id_turno}", response_model=TurnoOut)
async def detalle_turno(
    id_turno: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    out = await _turno_to_out(db, id_turno)
    if out is None:
        raise HTTPException(404, "Turno no encontrado")
    # Scope por nivel: operador no puede ver turnos fuera de su alcance.
    scope = await _scope_turnos_para_usuario(db, user)
    if scope is not None and not await _turno_en_scope(db, out, scope):
        raise HTTPException(404, "Turno no encontrado")
    return out


async def _turno_en_scope(db: AsyncSession, turno: dict[str, Any], scope: dict[str, Any]) -> bool:
    """True si el turno cae dentro del alcance del usuario (agente propio o
    espacio de su subarea)."""
    if turno.get("id_agente") is not None and turno["id_agente"] == scope["id_agente"]:
        return True
    if turno.get("id_espacio") is not None and scope.get("id_subarea") is not None:
        ok = (await db.execute(text(
            "SELECT 1 FROM espacios_agenda WHERE id_espacio = :ie AND id_subarea = :sub AND activo = TRUE"
        ), {"ie": turno["id_espacio"], "sub": scope["id_subarea"]})).first()
        return bool(ok)
    return False


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

    # Anti-carrera (mig 95): serializa las reservas concurrentes del mismo
    # recurso+dia ANTES de los checks — el segundo request espera el commit del
    # primero y su anti-solape ya ve la ocupacion nueva. Se libera al commit.
    await advisory_lock_tx(db, f"turno:{tipo_recurso}:{int(id_recurso)}:{payload.fecha}")

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

    # Copiar el recurso de la prestacion al turno (turno autocontenido).
    id_agente_turno = int(id_recurso) if tipo_recurso == "agente" else None
    id_espacio_turno = int(id_recurso) if tipo_recurso == "espacio" else None

    # UNIQUE parcial de slot (mig 95): si otra reserva gano la carrera pese al
    # lock (p.ej. una via futura sin lock), el INSERT viola el indice -> 409.
    try:
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
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "El horario acaba de ser tomado por otra reserva")
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

    # Anti-carrera (mig 95): lock sobre el recurso NUEVO resuelto de la
    # prestacion (si cambio la prestacion, cambia el recurso a serializar).
    await advisory_lock_tx(db, f"turno:{tipo_recurso}:{int(id_recurso)}:{fecha}")

    # Switch global: el nuevo horario debe caer en la disponibilidad efectiva.
    if await turnos_respeta_disponibilidad(db):
        rangos = await disponibilidad_efectiva(db, tipo_recurso, int(id_recurso), fecha)
        if not any(r["hora_inicio"] <= hora_inicio and hora_fin <= r["hora_fin"] for r in rangos):
            raise HTTPException(409, "El nuevo horario no esta dentro de la disponibilidad del recurso")

    # Solapamiento contra la ocupacion del mismo recurso (excluyendo la propia).
    # CAST obligatorio: asyncpg no infiere el tipo de :io usado en "IS NULL"
    # (AmbiguousParameterError -> 500; bug de Roy "Failed to fetch", 2026-06-11).
    # Familia de feedback_asyncpg_extract_cast_date.
    solapado = await db.scalar(text("""
        SELECT 1 FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir
          AND fecha = :f AND hora_inicio < :hf AND hora_fin > :hi
          AND (CAST(:io AS integer) IS NULL OR id_ocupacion <> CAST(:io AS integer))
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
    try:
        # CAS de estado (mig 95): el WHERE repite estado='reservado' para que un
        # cancelar/cumplir concurrente no quede pisado (el SELECT de arriba pudo
        # leer un estado ya viejo). rowcount 0 => el estado cambio en el medio.
        res = await db.execute(text(
            f"UPDATE turnos SET {', '.join(sets)} WHERE id_turno = :id AND estado = 'reservado'"
        ), params)
        if res.rowcount == 0:
            await db.rollback()
            raise HTTPException(409, "El turno cambio de estado mientras se reprogramaba; actualiza la lista")

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
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "El horario acaba de ser tomado por otra reserva")
    out = await _turno_to_out(db, id_turno)
    return out  # type: ignore


@router.patch("/{id_turno}/cumplir", response_model=TurnoOut)
async def cumplir_turno(
    id_turno: int,
    payload: Optional[TurnoCumplir] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Marca el turno como cumplido (el ciudadano se presento y se atendio).

    Acepta una observacion opcional de la atencion (se anexa a la observacion
    del turno). Si la prestacion del turno tiene registra_atencion=TRUE
    (mig 86), exige `intervencion` (422 si falta) y registra la atencion en
    turno_atencion (historia del ciudadano) en la misma transaccion.
    Al cumplir dispara la encuesta de satisfaccion de turnos (best-effort,
    no bloquea el cumplimiento)."""
    _require_gestion(user)
    turno = (await db.execute(text("""
        SELECT t.estado, t.observaciones, t.id_ciudadano, t.id_municipio, t.id_subarea,
               COALESCE(tp.registra_atencion, FALSE) AS registra_atencion
        FROM turnos t
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        WHERE t.id_turno = :id AND t.activo = TRUE
    """), {"id": id_turno})).mappings().first()
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    if turno["estado"] == "cumplido":
        out = await _turno_to_out(db, id_turno)
        return out  # type: ignore
    if turno["estado"] != "reservado":
        raise HTTPException(409, f"Solo se puede cumplir un turno 'reservado' (estado actual: '{turno['estado']}')")

    # Prestacion con historia de atencion: la intervencion es OBLIGATORIA
    # (decidido con el usuario 2026-06-11 — la historia nunca queda con huecos).
    intervencion = (payload.intervencion or "").strip() if payload else ""
    recomendaciones = (payload.recomendaciones or "").strip() if payload else ""
    if turno["registra_atencion"] and not intervencion:
        raise HTTPException(422, "Esta prestación registra historia de atención: la intervención es obligatoria para cumplir el turno")

    obs_nueva = (payload.observaciones or "").strip() if payload else ""
    sets = ["estado = 'cumplido'", "fecha_modificacion = NOW()", "id_usuario_modificacion = :uid"]
    params: dict[str, Any] = {"id": id_turno, "uid": user["id_usuario"]}
    if obs_nueva:
        prev = (turno["observaciones"] or "").strip()
        obs_final = f"{prev}\nAtención: {obs_nueva}" if prev else obs_nueva
        sets.append("observaciones = :obs"); params["obs"] = obs_final
    # CAS de estado (mig 95): sin repetir estado='reservado' en el WHERE, un
    # cancelar concurrente quedaba pisado (last-write-wins).
    res = await db.execute(text(
        f"UPDATE turnos SET {', '.join(sets)} WHERE id_turno = :id AND estado = 'reservado'"
    ), params)
    if res.rowcount == 0:
        await db.rollback()
        estado_actual = await db.scalar(text(
            "SELECT estado FROM turnos WHERE id_turno = :id"
        ), {"id": id_turno})
        if estado_actual == "cumplido":
            out = await _turno_to_out(db, id_turno)
            return out  # type: ignore
        raise HTTPException(409, f"Solo se puede cumplir un turno 'reservado' (estado actual: '{estado_actual}')")

    if turno["registra_atencion"]:
        await db.execute(text("""
            INSERT INTO turno_atencion (
                id_turno, id_ciudadano, intervencion, recomendaciones,
                id_municipio, id_subarea, id_usuario_alta, id_usuario_modificacion
            ) VALUES (:it, :ic, :inter, :reco, :mun, :isa, :uid, :uid)
            ON CONFLICT (id_turno) DO NOTHING
        """), {
            "it": id_turno, "ic": turno["id_ciudadano"], "inter": intervencion,
            "reco": recomendaciones or None, "mun": turno["id_municipio"],
            "isa": turno["id_subarea"], "uid": user["id_usuario"],
        })
    await db.commit()

    # Dispara la encuesta de turnos (delay 24h lo maneja el dispatcher).
    # Best-effort: el cumplimiento del turno nunca falla por la encuesta.
    try:
        await encuestas_service.crear_envio_para_turno(db, id_turno)
    except Exception:
        pass

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
    # CAS de estado (mig 95): un cumplir concurrente no debe quedar pisado.
    res = await db.execute(text("""
        UPDATE turnos
        SET estado = 'cancelado', fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_turno = :id AND estado = 'reservado'
    """), {"id": id_turno, "uid": user["id_usuario"]})
    if res.rowcount == 0:
        await db.rollback()
        estado_actual = await db.scalar(text(
            "SELECT estado FROM turnos WHERE id_turno = :id"
        ), {"id": id_turno})
        if estado_actual == "cancelado":
            out = await _turno_to_out(db, id_turno)
            return out  # type: ignore
        raise HTTPException(409, f"Solo se puede cancelar un turno 'reservado' (estado actual: '{estado_actual}')")
    if turno["id_ocupacion"]:
        await db.execute(text("""
            UPDATE ocupaciones
            SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
            WHERE id_ocupacion = :io
        """), {"io": turno["id_ocupacion"], "uid": user["id_usuario"]})
    await db.commit()
    out = await _turno_to_out(db, id_turno)
    return out  # type: ignore
