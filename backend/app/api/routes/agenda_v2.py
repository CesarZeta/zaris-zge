"""
ZARIS API - Router del modulo Agenda sub-fase 1.A.

Endpoints montados sobre las tablas creadas en migraciones 30-34
(eventos, evento_encargados, evento_reservas, ocupaciones, conflictos_log,
agenda_audit_log, estado_evento, estado_reserva, municipios).

Convive con el router legacy (routes/agenda.py) — los paths no colisionan.
Toda autoria via JWT (id_usuario_alta / id_usuario_modificacion).
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.agenda_v2 import (
    AusenciaOut,
    CalendarioDiaOut,
    CalendarioMesDia,
    CalendarioMesOut,
    CalendarioRecurso,
    CalendarioSemanaDiaOut,
    CalendarioSemanaOut,
    ConflictoOut,
    ConflictoResolverIn,
    DisponibilidadRangoEfectivo,
    EncargadoConflictoWarning,
    EstadoCatalogoOut,
    EventoBusquedaOut,
    EventoCreate,
    EventoDetalleOut,
    EventoEncargadoCreate,
    EventoEncargadoOut,
    EventoEnCalendarioOut,
    EventoOut,
    EventoUpdate,
    OcupacionCreate,
    OcupacionCreatedOut,
    OcupacionOut,
    OcupacionUpdate,
    OTBusquedaOut,
    RecursoAgendaOut,
    RecursoOut,
    RecursosConteosOut,
    ReservaCreate,
    ReservaOut,
    SubareaOut,
)
from app.services.agenda import (
    cupo_disponible,
    descripcion_corta_sql,
    detectar_conflictos,
    disponibilidad_efectiva,
    disponibilidad_efectiva_batch,
    existe_recurso,
    generar_qr_codigo,
    lookup_estado_evento,
    lookup_estado_reserva,
    registrar_audit,
    registrar_conflictos,
    subarea_del_usuario,
)


router = APIRouter(prefix="/api/v1/agenda", tags=["agenda-v2"])
logger = logging.getLogger("zaris.agenda_v2")


# =============================================================================
# Catalogos
# =============================================================================
@router.get("/catalogos/estados-evento", response_model=list[EstadoCatalogoOut])
async def listar_estados_evento(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Estados validos para `eventos.id_estado_evento` (activo/finalizado/cancelado)."""
    rows = (await db.execute(text("""
        SELECT id_estado_evento AS id, codigo, descripcion, orden
        FROM estado_evento
        WHERE activo = TRUE
        ORDER BY COALESCE(orden, id_estado_evento)
    """))).mappings().all()
    return [dict(r) for r in rows]


@router.get("/catalogos/estados-reserva", response_model=list[EstadoCatalogoOut])
async def listar_estados_reserva(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Estados validos para `evento_reservas.id_estado_reserva` (reservada/asistio/cancelada)."""
    rows = (await db.execute(text("""
        SELECT id_estado_reserva AS id, codigo, descripcion, orden
        FROM estado_reserva
        WHERE activo = TRUE
        ORDER BY COALESCE(orden, id_estado_reserva)
    """))).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# Catalogos extra (sub-fase 3.B — autocompletar / filtros)
# =============================================================================
@router.get("/catalogos/subareas", response_model=list[SubareaOut])
async def listar_subareas_agenda(
    q: Optional[str] = Query(None, max_length=80),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Subareas activas con nombre del area padre. Filtro opcional `q` (ILIKE en nombre)."""
    conds = ["s.activo = TRUE"]
    params: dict[str, Any] = {"lim": limit}
    if q:
        conds.append("s.nombre ILIKE :q")
        params["q"] = f"%{q}%"
    where = " AND ".join(conds)
    rows = (await db.execute(text(f"""
        SELECT s.id_subarea, s.nombre,
               s.id_area, a.nombre AS area_nombre
        FROM subarea s
        LEFT JOIN area a ON a.id_area = s.id_area
        WHERE {where}
        ORDER BY s.nombre
        LIMIT :lim
    """), params)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/catalogos/recursos", response_model=list[RecursoOut])
async def listar_recursos_agenda(
    tipo: Optional[Literal["agente", "equipo"]] = Query(None),
    q: Optional[str] = Query(None, max_length=80),
    id_municipio: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Lista agentes y equipos activos con nombre. Para selectores por nombre."""
    out: list[dict[str, Any]] = []
    if tipo in (None, "agente"):
        conds = ["activo = TRUE"]
        params: dict[str, Any] = {"lim": limit}
        if q:
            conds.append("(apellido ILIKE :q OR nombre ILIKE :q)")
            params["q"] = f"%{q}%"
        if id_municipio is not None:
            conds.append("id_municipio = :im")
            params["im"] = id_municipio
        where = " AND ".join(conds)
        rows = (await db.execute(text(f"""
            SELECT id_agente AS id, apellido || ', ' || nombre AS nombre
            FROM agentes WHERE {where}
            ORDER BY apellido, nombre LIMIT :lim
        """), params)).mappings().all()
        out.extend({"tipo_recurso": "agente", "id_recurso": r["id"], "nombre": r["nombre"]} for r in rows)
    if tipo in (None, "equipo"):
        conds = ["activo = TRUE"]
        params = {"lim": limit}
        if q:
            conds.append("nombre ILIKE :q")
            params["q"] = f"%{q}%"
        if id_municipio is not None:
            conds.append("id_municipio = :im")
            params["im"] = id_municipio
        where = " AND ".join(conds)
        rows = (await db.execute(text(f"""
            SELECT id_equipo AS id, nombre
            FROM equipos WHERE {where}
            ORDER BY nombre LIMIT :lim
        """), params)).mappings().all()
        out.extend({"tipo_recurso": "equipo", "id_recurso": r["id"], "nombre": r["nombre"]} for r in rows)
    return out


@router.get("/recursos/conteos", response_model=RecursosConteosOut)
async def conteos_recursos_agenda(
    id_municipio: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Cantidad de recursos activos por tipo. Alimenta los pills del toggle en Agenda B2."""
    params: dict[str, Any] = {}
    # Misma regla que /calendario y /semana: id_municipio NULL se trata como
    # del municipio actual. Sin el OR NULL, agentes/equipos legacy sin
    # municipio aparecen en la grilla pero no en el conteo del pill.
    where_mun = ""
    if id_municipio is not None:
        params["im"] = id_municipio
        where_mun = " AND (id_municipio IS NULL OR id_municipio = :im)"

    agentes = (await db.execute(
        text(f"SELECT COUNT(*) FROM agentes WHERE activo = TRUE{where_mun}"), params
    )).scalar_one()
    equipos = (await db.execute(
        text(f"SELECT COUNT(*) FROM equipos WHERE activo = TRUE{where_mun}"), params
    )).scalar_one()
    esp_atendidos = (await db.execute(
        text(f"SELECT COUNT(*) FROM espacios_agenda WHERE activo = TRUE AND atendido = TRUE{where_mun}"), params
    )).scalar_one()
    esp_desatendidos = (await db.execute(
        text(f"SELECT COUNT(*) FROM espacios_agenda WHERE activo = TRUE AND atendido = FALSE{where_mun}"), params
    )).scalar_one()
    return {
        "agentes": agentes or 0,
        "equipos": equipos or 0,
        "espacios_atendidos": esp_atendidos or 0,
        "espacios_desatendidos": esp_desatendidos or 0,
    }


@router.get("/catalogos/ot-busqueda", response_model=list[OTBusquedaOut])
async def buscar_ots_agenda(
    q: Optional[str] = Query(None, max_length=80),
    estado: Optional[str] = Query(None, description="Filtro por estado nombre (ej: Pendiente)"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Busqueda liviana de OTs para autocompletar. q matchea nro_ot, nro_reclamo o descripcion."""
    conds = ["ot.activo = TRUE"]
    params: dict[str, Any] = {"lim": limit}
    if q:
        conds.append("(ot.nro_ot ILIKE :q OR r.nro_reclamo ILIKE :q OR r.descripcion ILIKE :q)")
        params["q"] = f"%{q}%"
    if estado:
        conds.append("eot.nombre = :est")
        params["est"] = estado
    where = " AND ".join(conds)
    rows = (await db.execute(text(f"""
        SELECT ot.id_ot, ot.nro_ot,
               eot.nombre AS estado_nombre,
               r.descripcion AS reclamo_descripcion, r.nro_reclamo,
               ot.id_agente, ot.id_equipo
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        WHERE {where}
        ORDER BY ot.fecha_creacion DESC
        LIMIT :lim
    """), params)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/catalogos/evento-busqueda", response_model=list[EventoBusquedaOut])
async def buscar_eventos_agenda(
    q: Optional[str] = Query(None, max_length=80),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    id_municipio: Optional[int] = Query(None),
    solo_activos: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Busqueda liviana de eventos para autocompletar (nombre)."""
    conds: list[str] = []
    params: dict[str, Any] = {"lim": limit}
    if solo_activos:
        conds.append("e.activo = TRUE")
    if q:
        conds.append("e.nombre ILIKE :q")
        params["q"] = f"%{q}%"
    if fecha_desde is not None:
        conds.append("e.fecha >= :fd"); params["fd"] = fecha_desde
    if fecha_hasta is not None:
        conds.append("e.fecha <= :fh"); params["fh"] = fecha_hasta
    if id_municipio is not None:
        conds.append("e.id_municipio = :im"); params["im"] = id_municipio
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    rows = (await db.execute(text(f"""
        SELECT e.id_evento, e.nombre, e.fecha, e.hora_inicio, e.hora_fin,
               ee.codigo AS estado_codigo
        FROM eventos e
        LEFT JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
        {where}
        ORDER BY e.fecha DESC, e.hora_inicio
        LIMIT :lim
    """), params)).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# Eventos
# =============================================================================
async def _evento_to_out(db: AsyncSession, id_evento: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.descripcion, e.id_subarea, e.fecha,
               e.hora_inicio, e.hora_fin, e.capacidad_ciudadanos, e.cantidad_encargados,
               e.tipo_qr, e.admite_autoservicio,
               CAST(e.token_publico AS TEXT) AS token_publico, e.id_espacio,
               e.id_estado_evento, ee.codigo AS estado_codigo,
               e.activo, e.id_municipio, e.fecha_alta, e.fecha_modificacion
        FROM eventos e
        LEFT JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
        WHERE e.id_evento = :i
    """), {"i": id_evento})).mappings().first()
    return dict(row) if row else None


@router.post("/eventos", response_model=EventoOut, status_code=201)
async def crear_evento(
    payload: EventoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Crea un evento con estado inicial = `activo`."""
    id_estado = await lookup_estado_evento(db, "activo")
    if not id_estado:
        raise HTTPException(500, "Falta seed de estado_evento (codigo='activo').")
    row = (await db.execute(text("""
        INSERT INTO eventos (
            nombre, descripcion, id_subarea, fecha, hora_inicio, hora_fin,
            capacidad_ciudadanos, cantidad_encargados, tipo_qr, admite_autoservicio,
            token_publico, id_espacio,
            id_estado_evento, id_municipio, id_usuario_alta
        ) VALUES (
            :n, :d, :sa, :f, :hi, :hf,
            :cap, :enc, :qr, :auto,
            CASE WHEN :auto = TRUE THEN gen_random_uuid() ELSE NULL END, :esp,
            :es, :mun, :uid
        )
        RETURNING id_evento
    """), {
        "n": payload.nombre, "d": payload.descripcion, "sa": payload.id_subarea,
        "f": payload.fecha, "hi": payload.hora_inicio, "hf": payload.hora_fin,
        "cap": payload.capacidad_ciudadanos, "enc": payload.cantidad_encargados,
        "qr": payload.tipo_qr, "auto": payload.admite_autoservicio,
        "esp": payload.id_espacio,
        "es": id_estado, "mun": payload.id_municipio,
        "uid": current_user["id_usuario"],
    })).first()
    id_evento = int(row[0])
    await registrar_audit(
        db, current_user["id_usuario"], "evento", id_evento, "crear",
        None, payload.model_dump(mode="json"), payload.id_municipio,
    )
    await db.commit()
    out = await _evento_to_out(db, id_evento)
    return out  # type: ignore[return-value]


@router.get("/eventos", response_model=list[EventoOut])
async def listar_eventos(
    response: Response,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    id_estado_evento: Optional[int] = None,
    id_subarea: Optional[int] = None,
    id_municipio: Optional[int] = None,
    con_espacio: Optional[bool] = Query(None, description="True=solo eventos con id_espacio (modulo Entradas), False=solo sin espacio, omitir=todos"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Lista paginada de eventos activos. Header `X-Total-Count` para el front."""
    where: list[str] = ["e.activo = TRUE"]
    params: dict[str, Any] = {}
    if fecha_desde:
        where.append("e.fecha >= :fd"); params["fd"] = fecha_desde
    if fecha_hasta:
        where.append("e.fecha <= :fh"); params["fh"] = fecha_hasta
    if id_estado_evento is not None:
        where.append("e.id_estado_evento = :ies"); params["ies"] = id_estado_evento
    if id_subarea is not None:
        where.append("e.id_subarea = :isa"); params["isa"] = id_subarea
    if id_municipio is not None:
        where.append("e.id_municipio = :imu"); params["imu"] = id_municipio
    if con_espacio is True:
        where.append("e.id_espacio IS NOT NULL")
    elif con_espacio is False:
        where.append("e.id_espacio IS NULL")
    where_sql = " AND ".join(where)

    total = await db.scalar(text(f"SELECT COUNT(*) FROM eventos e WHERE {where_sql}"), params)
    params_page = {**params, "lim": limit, "off": offset}
    rows = (await db.execute(text(f"""
        SELECT e.id_evento, e.nombre, e.descripcion, e.id_subarea, e.fecha,
               e.hora_inicio, e.hora_fin, e.capacidad_ciudadanos, e.cantidad_encargados,
               e.tipo_qr, e.admite_autoservicio,
               CAST(e.token_publico AS TEXT) AS token_publico, e.id_espacio,
               e.id_estado_evento, ee.codigo AS estado_codigo,
               e.activo, e.id_municipio, e.fecha_alta, e.fecha_modificacion
        FROM eventos e
        LEFT JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
        WHERE {where_sql}
        ORDER BY e.fecha DESC, e.hora_inicio
        LIMIT :lim OFFSET :off
    """), params_page)).mappings().all()
    response.headers["X-Total-Count"] = str(int(total or 0))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [dict(r) for r in rows]


@router.get("/eventos/{id_evento}", response_model=EventoDetalleOut)
async def detalle_evento(
    id_evento: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Detalle del evento + encargados activos + reservas activas + cupo disponible."""
    base = await _evento_to_out(db, id_evento)
    if not base:
        raise HTTPException(404, f"Evento {id_evento} no encontrado")
    cupo = await cupo_disponible(db, id_evento)
    reservas = int(await db.scalar(text("""
        SELECT COUNT(*) FROM evento_reservas r
        JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
        WHERE r.id_evento = :e AND r.activo = TRUE AND er.codigo <> 'cancelada'
    """), {"e": id_evento}) or 0)
    encargados = await _listar_encargados(db, id_evento)
    base.update({
        "cupo_disponible": cupo,
        "reservas_activas": reservas,
        "encargados": encargados,
    })
    return base  # type: ignore[return-value]


@router.put("/eventos/{id_evento}", response_model=EventoOut)
async def actualizar_evento(
    id_evento: int,
    payload: EventoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Actualiza campos editables. Si vienen ambas horas, valida horario."""
    actual = await _evento_to_out(db, id_evento)
    if not actual:
        raise HTTPException(404, f"Evento {id_evento} no encontrado")

    cambios = payload.model_dump(exclude_unset=True)
    if not cambios:
        return actual  # type: ignore[return-value]

    # Validar horario si vienen ambas horas
    new_hi = cambios.get("hora_inicio", actual["hora_inicio"])
    new_hf = cambios.get("hora_fin",    actual["hora_fin"])
    if new_hf <= new_hi:
        raise HTTPException(422, "hora_fin debe ser mayor que hora_inicio")

    sets = [f"{k} = :{k}" for k in cambios.keys()]
    sets.append("fecha_modificacion = NOW()")
    sets.append("id_usuario_modificacion = :uid")
    # Rotacion de token_publico segun cambio de admite_autoservicio
    if "admite_autoservicio" in cambios:
        nuevo = bool(cambios["admite_autoservicio"])
        anterior = bool(actual.get("admite_autoservicio"))
        if nuevo and not anterior:
            # OFF -> ON: generar token si todavia no tiene
            sets.append("token_publico = COALESCE(token_publico, gen_random_uuid())")
        elif anterior and not nuevo:
            # ON -> OFF: invalidar link existente
            sets.append("token_publico = NULL")
    params = {**cambios, "uid": current_user["id_usuario"], "id": id_evento}
    await db.execute(text(f"UPDATE eventos SET {', '.join(sets)} WHERE id_evento = :id"), params)

    nuevo = await _evento_to_out(db, id_evento)
    await registrar_audit(
        db, current_user["id_usuario"], "evento", id_evento, "modificar",
        {k: actual.get(k) for k in cambios.keys()},
        {k: nuevo.get(k)  for k in cambios.keys()},  # type: ignore[union-attr]
        actual["id_municipio"],
    )
    await db.commit()
    return nuevo  # type: ignore[return-value]


@router.patch("/eventos/{id_evento}/cancelar", response_model=EventoOut)
async def cancelar_evento(
    id_evento: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cambia el estado del evento a `cancelado`. NO cancela reservas (decision del operador)."""
    actual = await _evento_to_out(db, id_evento)
    if not actual:
        raise HTTPException(404, f"Evento {id_evento} no encontrado")
    if actual["estado_codigo"] == "cancelado":
        return actual  # type: ignore[return-value]
    id_cancelado = await lookup_estado_evento(db, "cancelado")
    if not id_cancelado:
        raise HTTPException(500, "Falta seed de estado_evento (codigo='cancelado').")
    await db.execute(text("""
        UPDATE eventos SET id_estado_evento = :ec, fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_evento = :i
    """), {"ec": id_cancelado, "uid": current_user["id_usuario"], "i": id_evento})
    nuevo = await _evento_to_out(db, id_evento)
    await registrar_audit(
        db, current_user["id_usuario"], "evento", id_evento, "cancelar",
        {"id_estado_evento": actual["id_estado_evento"]},
        {"id_estado_evento": id_cancelado},
        actual["id_municipio"],
    )
    await db.commit()
    return nuevo  # type: ignore[return-value]


@router.delete("/eventos/{id_evento}", status_code=204)
async def eliminar_evento(
    id_evento: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Baja logica (activo=FALSE). DELETE semantico = baja, NO borra fila."""
    actual = await _evento_to_out(db, id_evento)
    if not actual:
        raise HTTPException(404, f"Evento {id_evento} no encontrado")
    if not actual["activo"]:
        return Response(status_code=204)
    await db.execute(text("""
        UPDATE eventos SET activo = FALSE, fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_evento = :i
    """), {"uid": current_user["id_usuario"], "i": id_evento})
    await registrar_audit(
        db, current_user["id_usuario"], "evento", id_evento, "cancelar",
        {"activo": True}, {"activo": False}, actual["id_municipio"],
    )
    await db.commit()
    return Response(status_code=204)


# =============================================================================
# Encargados de evento
# =============================================================================
async def _listar_encargados(db: AsyncSession, id_evento: int) -> list[dict[str, Any]]:
    rows = (await db.execute(text("""
        SELECT enc.id_evento_encargado, enc.id_evento, enc.tipo_recurso, enc.id_recurso,
               enc.activo, enc.fecha_alta,
               CASE enc.tipo_recurso
                   WHEN 'agente' THEN (SELECT a.apellido || ', ' || a.nombre FROM agentes a WHERE a.id_agente = enc.id_recurso)
                   WHEN 'equipo' THEN (SELECT e.nombre FROM equipos e WHERE e.id_equipo = enc.id_recurso)
               END AS recurso_nombre
        FROM evento_encargados enc
        WHERE enc.id_evento = :e AND enc.activo = TRUE
        ORDER BY enc.id_evento_encargado
    """), {"e": id_evento})).mappings().all()
    return [dict(r) for r in rows]


@router.post("/eventos/{id_evento}/encargados", response_model=EncargadoConflictoWarning, status_code=201)
async def asignar_encargado(
    id_evento: int,
    payload: EventoEncargadoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Asigna un recurso (agente|equipo) como encargado del evento.
    Crea ademas la ocupacion `tipo='evento'` correspondiente.
    Si hay conflicto de agenda en la fecha/hora del evento, NO bloquea —
    registra en conflictos_log y devuelve warning."""
    ev = await _evento_to_out(db, id_evento)
    if not ev:
        raise HTTPException(404, f"Evento {id_evento} no encontrado")
    if not ev["activo"]:
        raise HTTPException(409, "Evento dado de baja")
    if not await existe_recurso(db, payload.tipo_recurso, payload.id_recurso):
        raise HTTPException(404, f"{payload.tipo_recurso} {payload.id_recurso} no encontrado o inactivo")

    # Idempotencia: ya existe encargado activo con ese recurso?
    existe = await db.scalar(text("""
        SELECT id_evento_encargado FROM evento_encargados
        WHERE id_evento = :e AND tipo_recurso = :tr AND id_recurso = :ir AND activo = TRUE
    """), {"e": id_evento, "tr": payload.tipo_recurso, "ir": payload.id_recurso})
    if existe:
        raise HTTPException(409, "El recurso ya esta asignado como encargado de este evento")

    # 1) Insertar encargado
    new_enc_id = await db.scalar(text("""
        INSERT INTO evento_encargados (
            id_evento, tipo_recurso, id_recurso, id_municipio, id_usuario_alta
        ) VALUES (:e, :tr, :ir, :mun, :uid)
        RETURNING id_evento_encargado
    """), {
        "e": id_evento, "tr": payload.tipo_recurso, "ir": payload.id_recurso,
        "mun": ev["id_municipio"], "uid": current_user["id_usuario"],
    })

    # 2) Detectar conflictos de agenda en la fecha/hora del evento
    conflictos = await detectar_conflictos(
        db, payload.tipo_recurso, payload.id_recurso,
        ev["fecha"], ev["hora_inicio"], ev["hora_fin"],
    )

    # 3) Insertar ocupacion tipo='evento'
    id_ocup = await db.scalar(text("""
        INSERT INTO ocupaciones (
            tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
            id_evento, rol_en_evento, id_municipio, id_usuario_alta
        ) VALUES (
            'evento', :tr, :ir, :f, :hi, :hf, :ev, 'encargado', :mun, :uid
        )
        RETURNING id_ocupacion
    """), {
        "tr": payload.tipo_recurso, "ir": payload.id_recurso,
        "f": ev["fecha"], "hi": ev["hora_inicio"], "hf": ev["hora_fin"],
        "ev": id_evento, "mun": ev["id_municipio"], "uid": current_user["id_usuario"],
    })

    if conflictos:
        await registrar_conflictos(
            db, int(id_ocup), payload.tipo_recurso, payload.id_recurso,
            conflictos, ev["id_municipio"], current_user["id_usuario"],
        )

    await registrar_audit(
        db, current_user["id_usuario"], "evento", id_evento, "asignar",
        None, {"encargado": payload.model_dump(), "ocupacion": int(id_ocup)},
        ev["id_municipio"],
    )
    await db.commit()

    # Build response
    enc_row = (await db.execute(text("""
        SELECT enc.id_evento_encargado, enc.id_evento, enc.tipo_recurso, enc.id_recurso,
               enc.activo, enc.fecha_alta,
               CASE enc.tipo_recurso
                   WHEN 'agente' THEN (SELECT a.apellido || ', ' || a.nombre FROM agentes a WHERE a.id_agente = enc.id_recurso)
                   WHEN 'equipo' THEN (SELECT e.nombre FROM equipos e WHERE e.id_equipo = enc.id_recurso)
               END AS recurso_nombre
        FROM evento_encargados enc
        WHERE enc.id_evento_encargado = :i
    """), {"i": new_enc_id})).mappings().first()
    return {
        "encargado": dict(enc_row),  # type: ignore[arg-type]
        "ocupacion_creada_id": int(id_ocup),
        "conflictos": [_jsonable(c) for c in conflictos],
        "mensaje": (
            f"Encargado asignado con {len(conflictos)} conflicto(s) - revisar /agenda/conflictos."
            if conflictos else "Encargado asignado sin conflictos."
        ),
    }


@router.get("/eventos/{id_evento}/encargados", response_model=list[EventoEncargadoOut])
async def listar_encargados(
    id_evento: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Lista encargados activos del evento con nombre del recurso."""
    if not await _evento_to_out(db, id_evento):
        raise HTTPException(404, f"Evento {id_evento} no encontrado")
    return await _listar_encargados(db, id_evento)


@router.delete("/eventos/{id_evento}/encargados/{id_evento_encargado}", status_code=204)
async def desasignar_encargado(
    id_evento: int,
    id_evento_encargado: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Baja logica del encargado + baja logica de la ocupacion de evento asociada."""
    enc = (await db.execute(text("""
        SELECT id_evento, tipo_recurso, id_recurso, activo, id_municipio
        FROM evento_encargados WHERE id_evento_encargado = :i
    """), {"i": id_evento_encargado})).mappings().first()
    if not enc:
        raise HTTPException(404, "Encargado no encontrado")
    if enc["id_evento"] != id_evento:
        raise HTTPException(409, "El encargado pertenece a otro evento")
    if not enc["activo"]:
        return Response(status_code=204)
    await db.execute(text("""
        UPDATE evento_encargados SET activo = FALSE, fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_evento_encargado = :i
    """), {"uid": current_user["id_usuario"], "i": id_evento_encargado})
    # Baja de la ocupacion asociada (matching exacto tipo='evento')
    await db.execute(text("""
        UPDATE ocupaciones SET activo = FALSE, fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE tipo = 'evento' AND id_evento = :e
          AND tipo_recurso = :tr AND id_recurso = :ir AND activo = TRUE
    """), {
        "uid": current_user["id_usuario"], "e": id_evento,
        "tr": enc["tipo_recurso"], "ir": enc["id_recurso"],
    })
    await registrar_audit(
        db, current_user["id_usuario"], "evento", id_evento, "modificar",
        {"encargado": id_evento_encargado, "activo": True},
        {"encargado": id_evento_encargado, "activo": False},
        enc["id_municipio"],
    )
    await db.commit()
    return Response(status_code=204)


# =============================================================================
# Reservas
# =============================================================================
def _jsonable(d: Any) -> Any:
    """Convierte date/time/datetime a iso para serializar a JSON en respuestas."""
    if isinstance(d, dict):
        return {k: _jsonable(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_jsonable(v) for v in d]
    if hasattr(d, "isoformat"):
        return d.isoformat()
    return d


@router.post("/eventos/{id_evento}/reservas", response_model=ReservaOut, status_code=201)
async def crear_reserva(
    id_evento: int,
    payload: ReservaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Crea una reserva si hay cupo + el evento no esta cancelado/finalizado."""
    ev = await _evento_to_out(db, id_evento)
    if not ev:
        raise HTTPException(404, f"Evento {id_evento} no encontrado")
    if not ev["activo"]:
        raise HTTPException(409, "Evento dado de baja")
    if ev["estado_codigo"] in ("cancelado", "finalizado"):
        raise HTTPException(409, f"Evento en estado {ev['estado_codigo']}, no acepta reservas")
    # Cupo
    cupo = await cupo_disponible(db, id_evento)
    if cupo <= 0:
        raise HTTPException(409, "Sin cupo disponible para este evento")
    # Ciudadano existe?
    n = await db.scalar(text(
        "SELECT 1 FROM ciudadanos WHERE id_ciudadano = :i AND activo = TRUE"
    ), {"i": payload.id_ciudadano})
    if not n:
        raise HTTPException(404, f"Ciudadano {payload.id_ciudadano} no encontrado")
    # Estado inicial
    id_reservada = await lookup_estado_reserva(db, "reservada")
    if not id_reservada:
        raise HTTPException(500, "Falta seed de estado_reserva (codigo='reservada').")
    # Insert
    new_id = await db.scalar(text("""
        INSERT INTO evento_reservas (
            id_evento, id_ciudadano, id_estado_reserva, origen,
            id_municipio, id_usuario_alta
        ) VALUES (:e, :c, :er, :o, :mun, :uid)
        RETURNING id_evento_reserva
    """), {
        "e": id_evento, "c": payload.id_ciudadano, "er": id_reservada,
        "o": payload.origen, "mun": ev["id_municipio"],
        "uid": current_user["id_usuario"],
    })
    qr = None
    if ev["tipo_qr"] != "ninguno":
        qr = generar_qr_codigo(id_evento, int(new_id))
        await db.execute(text("""
            UPDATE evento_reservas SET qr_codigo = :q WHERE id_evento_reserva = :i
        """), {"q": qr, "i": new_id})
    await registrar_audit(
        db, current_user["id_usuario"], "reserva", int(new_id), "crear",
        None, {"id_evento": id_evento, "id_ciudadano": payload.id_ciudadano, "origen": payload.origen, "qr_codigo": qr},
        ev["id_municipio"],
    )
    await db.commit()
    out = await _reserva_to_out(db, int(new_id))
    return out  # type: ignore[return-value]


async def _reserva_to_out(db: AsyncSession, id_reserva: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT r.id_evento_reserva, r.id_evento, r.id_ciudadano,
               c.apellido AS ciudadano_apellido, c.nombre AS ciudadano_nombre, c.doc_nro AS ciudadano_dni,
               r.id_estado_reserva, er.codigo AS estado_codigo,
               r.origen, r.qr_codigo, r.activo, r.fecha_alta
        FROM evento_reservas r
        LEFT JOIN ciudadanos     c  ON c.id_ciudadano       = r.id_ciudadano
        LEFT JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
        WHERE r.id_evento_reserva = :i
    """), {"i": id_reserva})).mappings().first()
    return dict(row) if row else None


@router.get("/eventos/{id_evento}/reservas", response_model=list[ReservaOut])
async def listar_reservas(
    id_evento: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Lista reservas activas del evento (incluyendo canceladas para auditar)."""
    if not await _evento_to_out(db, id_evento):
        raise HTTPException(404, f"Evento {id_evento} no encontrado")
    rows = (await db.execute(text("""
        SELECT r.id_evento_reserva, r.id_evento, r.id_ciudadano,
               c.apellido AS ciudadano_apellido, c.nombre AS ciudadano_nombre, c.doc_nro AS ciudadano_dni,
               r.id_estado_reserva, er.codigo AS estado_codigo,
               r.origen, r.qr_codigo, r.activo, r.fecha_alta
        FROM evento_reservas r
        LEFT JOIN ciudadanos     c  ON c.id_ciudadano       = r.id_ciudadano
        LEFT JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
        WHERE r.id_evento = :e AND r.activo = TRUE
        ORDER BY r.fecha_alta DESC
    """), {"e": id_evento})).mappings().all()
    return [dict(r) for r in rows]


async def _patch_reserva_estado(
    db: AsyncSession, id_evento_reserva: int, nuevo_codigo: str, id_usuario: int,
) -> Optional[dict[str, Any]]:
    actual = await _reserva_to_out(db, id_evento_reserva)
    if not actual:
        return None
    id_nuevo = await lookup_estado_reserva(db, nuevo_codigo)
    if not id_nuevo:
        raise HTTPException(500, f"Falta seed de estado_reserva (codigo='{nuevo_codigo}')")
    if actual["estado_codigo"] == nuevo_codigo:
        return actual
    await db.execute(text("""
        UPDATE evento_reservas SET id_estado_reserva = :er,
            fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_evento_reserva = :i
    """), {"er": id_nuevo, "uid": id_usuario, "i": id_evento_reserva})
    nueva = await _reserva_to_out(db, id_evento_reserva)
    accion = "modificar" if nuevo_codigo != "cancelada" else "cancelar"
    await registrar_audit(
        db, id_usuario, "reserva", id_evento_reserva, accion,
        {"estado_codigo": actual["estado_codigo"]},
        {"estado_codigo": nuevo_codigo},
        actual.get("id_municipio", 1) if isinstance(actual.get("id_municipio"), int) else 1,
    )
    await db.commit()
    return nueva


@router.patch("/reservas/{id_evento_reserva}/asistio", response_model=ReservaOut)
async def reserva_asistio(
    id_evento_reserva: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Marca la reserva como `asistio`."""
    nueva = await _patch_reserva_estado(db, id_evento_reserva, "asistio", current_user["id_usuario"])
    if not nueva:
        raise HTTPException(404, "Reserva no encontrada")
    return nueva


@router.patch("/reservas/{id_evento_reserva}/cancelar", response_model=ReservaOut)
async def reserva_cancelar(
    id_evento_reserva: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Marca la reserva como `cancelada`. Libera cupo automaticamente."""
    nueva = await _patch_reserva_estado(db, id_evento_reserva, "cancelada", current_user["id_usuario"])
    if not nueva:
        raise HTTPException(404, "Reserva no encontrada")
    return nueva


# =============================================================================
# Ocupaciones
# =============================================================================
async def _ocupacion_to_out(db: AsyncSession, id_ocupacion: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text(f"""
        SELECT o.id_ocupacion, o.tipo, o.tipo_recurso, o.id_recurso, o.fecha,
               o.hora_inicio, o.hora_fin, o.id_orden_trabajo, o.id_evento, o.id_ciudadano,
               o.duracion_aplicada_min, o.rol_en_evento, o.motivo,
               o.activo, o.id_municipio, o.fecha_alta,
               {descripcion_corta_sql()} AS descripcion_corta
        FROM ocupaciones o
        LEFT JOIN eventos          ev ON ev.id_evento     = o.id_evento
        LEFT JOIN ordenes_trabajo  ot ON ot.id_ot         = o.id_orden_trabajo
        LEFT JOIN ciudadanos       ci ON ci.id_ciudadano  = o.id_ciudadano
        WHERE o.id_ocupacion = :i
    """), {"i": id_ocupacion})).mappings().first()
    return dict(row) if row else None


@router.post("/ocupaciones", response_model=OcupacionCreatedOut, status_code=201)
async def crear_ocupacion(
    payload: OcupacionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Crea una ocupacion. Detecta conflictos de agenda y los registra en
    conflictos_log sin bloquear."""
    if not await existe_recurso(db, payload.tipo_recurso, payload.id_recurso):
        raise HTTPException(404, f"{payload.tipo_recurso} {payload.id_recurso} no encontrado o inactivo")

    conflictos = await detectar_conflictos(
        db, payload.tipo_recurso, payload.id_recurso,
        payload.fecha, payload.hora_inicio, payload.hora_fin,
    )

    try:
        new_id = await db.scalar(text("""
            INSERT INTO ocupaciones (
                tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
                id_orden_trabajo, id_evento, id_ciudadano,
                duracion_aplicada_min, rol_en_evento, motivo,
                id_municipio, id_usuario_alta
            ) VALUES (
                :t, :tr, :ir, :f, :hi, :hf,
                :ot, :ev, :ci,
                :dur, :rol, :mot,
                :mun, :uid
            )
            RETURNING id_ocupacion
        """), {
            "t": payload.tipo, "tr": payload.tipo_recurso, "ir": payload.id_recurso,
            "f": payload.fecha, "hi": payload.hora_inicio, "hf": payload.hora_fin,
            "ot": payload.id_orden_trabajo, "ev": payload.id_evento, "ci": payload.id_ciudadano,
            "dur": payload.duracion_aplicada_min, "rol": payload.rol_en_evento, "mot": payload.motivo,
            "mun": payload.id_municipio, "uid": current_user["id_usuario"],
        })
    except Exception as e:
        # CHECK constraint de consistencia o FK puede fallar
        raise HTTPException(422, f"No se pudo crear ocupacion: {type(e).__name__}: {e}")

    if conflictos:
        await registrar_conflictos(
            db, int(new_id), payload.tipo_recurso, payload.id_recurso,
            conflictos, payload.id_municipio, current_user["id_usuario"],
        )

    await registrar_audit(
        db, current_user["id_usuario"], "ocupacion", int(new_id), "crear",
        None, payload.model_dump(mode="json"), payload.id_municipio,
    )
    await db.commit()
    out = await _ocupacion_to_out(db, int(new_id))
    return {
        "ocupacion": out,  # type: ignore[arg-type]
        "conflictos": [_jsonable(c) for c in conflictos],
        "mensaje": (
            f"Ocupacion creada con {len(conflictos)} conflicto(s) - revisar /agenda/conflictos."
            if conflictos else "Ocupacion creada sin conflictos."
        ),
    }


@router.get("/ocupaciones", response_model=list[OcupacionOut])
async def listar_ocupaciones(
    response: Response,
    tipo_recurso: Optional[Literal["agente", "equipo"]] = None,
    id_recurso: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    tipo: Optional[Literal["ot", "evento", "turno"]] = None,
    id_municipio: Optional[int] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Listado paginado de ocupaciones activas con filtros."""
    where: list[str] = ["o.activo = TRUE"]
    params: dict[str, Any] = {}
    if tipo_recurso:
        where.append("o.tipo_recurso = :tr"); params["tr"] = tipo_recurso
    if id_recurso is not None:
        where.append("o.id_recurso = :ir"); params["ir"] = id_recurso
    if fecha_desde:
        where.append("o.fecha >= :fd"); params["fd"] = fecha_desde
    if fecha_hasta:
        where.append("o.fecha <= :fh"); params["fh"] = fecha_hasta
    if tipo:
        where.append("o.tipo = :t"); params["t"] = tipo
    if id_municipio is not None:
        where.append("o.id_municipio = :mun"); params["mun"] = id_municipio
    where_sql = " AND ".join(where)
    total = await db.scalar(text(f"SELECT COUNT(*) FROM ocupaciones o WHERE {where_sql}"), params)
    params_page = {**params, "lim": limit, "off": offset}
    rows = (await db.execute(text(f"""
        SELECT o.id_ocupacion, o.tipo, o.tipo_recurso, o.id_recurso, o.fecha,
               o.hora_inicio, o.hora_fin, o.id_orden_trabajo, o.id_evento, o.id_ciudadano,
               o.duracion_aplicada_min, o.rol_en_evento, o.motivo,
               o.activo, o.id_municipio, o.fecha_alta,
               {descripcion_corta_sql()} AS descripcion_corta
        FROM ocupaciones o
        LEFT JOIN eventos         ev ON ev.id_evento    = o.id_evento
        LEFT JOIN ordenes_trabajo ot ON ot.id_ot        = o.id_orden_trabajo
        LEFT JOIN ciudadanos      ci ON ci.id_ciudadano = o.id_ciudadano
        WHERE {where_sql}
        ORDER BY o.fecha DESC, o.hora_inicio
        LIMIT :lim OFFSET :off
    """), params_page)).mappings().all()
    response.headers["X-Total-Count"] = str(int(total or 0))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [dict(r) for r in rows]


@router.put("/ocupaciones/{id_ocupacion}", response_model=OcupacionCreatedOut)
async def actualizar_ocupacion(
    id_ocupacion: int,
    payload: OcupacionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Actualiza fecha/horas/atributos. Re-detecta conflictos excluyendo self."""
    actual = await _ocupacion_to_out(db, id_ocupacion)
    if not actual:
        raise HTTPException(404, "Ocupacion no encontrada")
    if not actual["activo"]:
        raise HTTPException(409, "Ocupacion dada de baja")
    cambios = payload.model_dump(exclude_unset=True)
    if not cambios:
        return {"ocupacion": actual, "conflictos": [], "mensaje": "Sin cambios."}  # type: ignore[return-value]

    new_f  = cambios.get("fecha",       actual["fecha"])
    new_hi = cambios.get("hora_inicio", actual["hora_inicio"])
    new_hf = cambios.get("hora_fin",    actual["hora_fin"])
    new_tr = cambios.get("tipo_recurso", actual["tipo_recurso"])
    new_ir = cambios.get("id_recurso",   actual["id_recurso"])
    if new_hf <= new_hi:
        raise HTTPException(422, "hora_fin debe ser mayor que hora_inicio")

    sets = [f"{k} = :{k}" for k in cambios.keys()]
    sets.append("fecha_modificacion = NOW()")
    sets.append("id_usuario_modificacion = :uid")
    params = {**cambios, "uid": current_user["id_usuario"], "id": id_ocupacion}
    await db.execute(text(f"UPDATE ocupaciones SET {', '.join(sets)} WHERE id_ocupacion = :id"), params)

    # Revalidar conflictos sobre el recurso nuevo (puede haber cambiado)
    conflictos = await detectar_conflictos(
        db, new_tr, new_ir, new_f, new_hi, new_hf,
        id_ocupacion_excluir=id_ocupacion,
    )
    if conflictos:
        await registrar_conflictos(
            db, id_ocupacion, new_tr, new_ir,
            conflictos, actual["id_municipio"], current_user["id_usuario"],
        )
    nuevo = await _ocupacion_to_out(db, id_ocupacion)
    await registrar_audit(
        db, current_user["id_usuario"], "ocupacion", id_ocupacion, "modificar",
        {k: actual.get(k) for k in cambios.keys()},
        {k: nuevo.get(k)  for k in cambios.keys()},  # type: ignore[union-attr]
        actual["id_municipio"],
    )
    await db.commit()
    return {
        "ocupacion": nuevo,  # type: ignore[dict-item]
        "conflictos": [_jsonable(c) for c in conflictos],
        "mensaje": (
            f"Ocupacion actualizada con {len(conflictos)} conflicto(s)."
            if conflictos else "Ocupacion actualizada sin conflictos."
        ),
    }


@router.delete("/ocupaciones/{id_ocupacion}", status_code=204)
async def eliminar_ocupacion(
    id_ocupacion: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Baja logica (activo=FALSE)."""
    actual = await _ocupacion_to_out(db, id_ocupacion)
    if not actual:
        raise HTTPException(404, "Ocupacion no encontrada")
    if not actual["activo"]:
        return Response(status_code=204)
    await db.execute(text("""
        UPDATE ocupaciones SET activo = FALSE, fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_ocupacion = :i
    """), {"uid": current_user["id_usuario"], "i": id_ocupacion})
    await registrar_audit(
        db, current_user["id_usuario"], "ocupacion", id_ocupacion, "cancelar",
        {"activo": True}, {"activo": False}, actual["id_municipio"],
    )
    await db.commit()
    return Response(status_code=204)


# =============================================================================
# Vista del coordinador
# =============================================================================
def _nombre_recurso_sql(alias: str) -> str:
    return f"""
        CASE :tipo_recurso
            WHEN 'agente' THEN (SELECT a.apellido || ', ' || a.nombre FROM agentes a WHERE a.id_agente = {alias})
            WHEN 'equipo' THEN (SELECT e.nombre FROM equipos e WHERE e.id_equipo = {alias})
        END
    """


@router.get("/recurso/{tipo_recurso}/{id_recurso}", response_model=RecursoAgendaOut)
async def agenda_de_recurso(
    tipo_recurso: Literal["agente", "equipo"],
    id_recurso: int,
    desde: date,
    hasta: date,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Agenda completa de un recurso en un rango (max 31 dias).
    Incluye ocupaciones + ausencias del recurso (estas ultimas leyendo la tabla
    `ausencias_agente` introducida en mig 39, solo si el recurso es agente)."""
    if hasta < desde:
        raise HTTPException(422, "hasta debe ser >= desde")
    if (hasta - desde).days > 31:
        raise HTTPException(422, "El rango maximo es de 31 dias")
    if not await existe_recurso(db, tipo_recurso, id_recurso):
        raise HTTPException(404, f"{tipo_recurso} {id_recurso} no encontrado o inactivo")

    # Ocupaciones del recurso
    ocup_rows = (await db.execute(text(f"""
        SELECT o.id_ocupacion, o.tipo, o.tipo_recurso, o.id_recurso, o.fecha,
               o.hora_inicio, o.hora_fin, o.id_orden_trabajo, o.id_evento, o.id_ciudadano,
               o.duracion_aplicada_min, o.rol_en_evento, o.motivo,
               o.activo, o.id_municipio, o.fecha_alta,
               {descripcion_corta_sql()} AS descripcion_corta
        FROM ocupaciones o
        LEFT JOIN eventos         ev ON ev.id_evento    = o.id_evento
        LEFT JOIN ordenes_trabajo ot ON ot.id_ot        = o.id_orden_trabajo
        LEFT JOIN ciudadanos      ci ON ci.id_ciudadano = o.id_ciudadano
        WHERE o.activo = TRUE AND o.tipo_recurso = :tr AND o.id_recurso = :ir
          AND o.fecha BETWEEN :fd AND :fh
        ORDER BY o.fecha, o.hora_inicio
    """), {"tr": tipo_recurso, "ir": id_recurso, "fd": desde, "fh": hasta})).mappings().all()

    # Ausencias (tabla nueva ausencias_agente, mig 39) - solo agentes
    ausencias: list[dict[str, Any]] = []
    if tipo_recurso == "agente":
        ausencias = [dict(r) for r in (await db.execute(text("""
            SELECT id_ausencia_agente AS id_ausencia, fecha_desde, fecha_hasta, motivo
            FROM ausencias_agente
            WHERE activo = TRUE AND id_agente = :i
              AND NOT (fecha_hasta < :fd OR fecha_desde > :fh)
            ORDER BY fecha_desde
        """), {"i": id_recurso, "fd": desde, "fh": hasta})).mappings().all()]

    # Nombre del recurso
    if tipo_recurso == "agente":
        nombre = await db.scalar(text(
            "SELECT apellido || ', ' || nombre FROM agentes WHERE id_agente = :i"
        ), {"i": id_recurso})
    else:
        nombre = await db.scalar(text(
            "SELECT nombre FROM equipos WHERE id_equipo = :i"
        ), {"i": id_recurso})

    return {
        "tipo_recurso": tipo_recurso,
        "id_recurso": id_recurso,
        "nombre": nombre,
        "desde": desde,
        "hasta": hasta,
        "ocupaciones": [dict(r) for r in ocup_rows],
        "ausencias": ausencias,
    }


@router.get("/calendario", response_model=CalendarioDiaOut)
async def calendario_dia(
    fecha: date,
    id_municipio: int = 1,
    tipo_recurso: Literal["agente", "equipo", "espacio", "todos"] = "todos",
    id_subarea: Optional[int] = Query(None, description="Filtra recursos cuyo id_subarea coincida"),
    scope_subarea_propia: bool = Query(False, description="Si True, limita los recursos a la subarea del usuario logueado (resuelta via su agente). Fail-open: si no se puede resolver, no filtra. Pensado para la vista por equipos del supervisor (ver §33 CLAUDE.md)."),
    atendido: Optional[bool] = Query(None, description="Solo aplica a tipo_recurso='espacio'. None=todos, True=atendidos, False=desatendidos"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Timeline del coordinador para una fecha. Devuelve los recursos del
    municipio con ocupaciones, ausencias (solo agentes), disponibilidad
    horaria resuelta para esa fecha, y los eventos del dia.

    Sub-fase B1: agrega tipo_recurso='espacio', filtro 'atendido', disponibilidad
    horaria y eventos en grilla. Compat retro: con defaults se comporta como antes
    salvo que ahora tambien devuelve disponibilidad + eventos."""
    id_subarea = await _resolver_scope_subarea(db, _user, id_subarea, scope_subarea_propia)
    recursos = await _listar_recursos_para_calendario(db, id_municipio, tipo_recurso, id_subarea, atendido)
    eventos_dia = await _eventos_del_dia(db, fecha, id_municipio)

    if not recursos:
        return {"fecha": fecha, "id_municipio": id_municipio, "recursos": [], "eventos": eventos_dia}

    # Ocupaciones del dia
    rows = (await db.execute(text(f"""
        SELECT o.id_ocupacion, o.tipo, o.tipo_recurso, o.id_recurso, o.fecha,
               o.hora_inicio, o.hora_fin, o.id_orden_trabajo, o.id_evento, o.id_ciudadano,
               o.duracion_aplicada_min, o.rol_en_evento, o.motivo,
               o.activo, o.id_municipio, o.fecha_alta,
               {descripcion_corta_sql()} AS descripcion_corta
        FROM ocupaciones o
        LEFT JOIN eventos         ev ON ev.id_evento    = o.id_evento
        LEFT JOIN ordenes_trabajo ot ON ot.id_ot        = o.id_orden_trabajo
        LEFT JOIN ciudadanos      ci ON ci.id_ciudadano = o.id_ciudadano
        WHERE o.activo = TRUE AND o.fecha = :f AND o.id_municipio = :m
        ORDER BY o.tipo_recurso, o.id_recurso, o.hora_inicio
    """), {"f": fecha, "m": id_municipio})).mappings().all()

    ocup_por_recurso: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for r in rows:
        key = (r["tipo_recurso"], r["id_recurso"])
        ocup_por_recurso.setdefault(key, []).append(dict(r))

    # Ausencias del dia (solo aplica a agentes)
    aus_por_agente: dict[int, list[dict[str, Any]]] = {}
    rows_aus = (await db.execute(text("""
        SELECT a.id_agente, au.id_ausencia_agente AS id_ausencia,
               au.fecha_desde, au.fecha_hasta, au.motivo
        FROM ausencias_agente au
        JOIN agentes a ON a.id_agente = au.id_agente
        WHERE au.activo = TRUE
          AND :f BETWEEN au.fecha_desde AND au.fecha_hasta
          AND a.activo = TRUE
          AND (a.id_municipio IS NULL OR a.id_municipio = :m)
    """), {"f": fecha, "m": id_municipio})).mappings().all()
    for r in rows_aus:
        aus_por_agente.setdefault(int(r["id_agente"]), []).append({
            "id_ausencia": r["id_ausencia"],
            "fecha_desde": r["fecha_desde"],
            "fecha_hasta": r["fecha_hasta"],
            "motivo": r["motivo"],
        })

    # Disponibilidad efectiva en BATCH (antes era 1 await por recurso -> N round-trips).
    disp_batch = await disponibilidad_efectiva_batch(
        db,
        [(rec["tipo"], rec["id_recurso"], rec.get("atendido")) for rec in recursos],
        [fecha],
    )

    out_recursos = []
    for rec in recursos:
        out_recursos.append({
            "tipo": rec["tipo"],
            "id_recurso": rec["id_recurso"],
            "nombre": rec["nombre"],
            "atendido": rec.get("atendido"),
            "ocupaciones": ocup_por_recurso.get((rec["tipo"], rec["id_recurso"]), []),
            "ausencias": aus_por_agente.get(rec["id_recurso"], []) if rec["tipo"] == "agente" else [],
            "disponibilidad": disp_batch.get((rec["tipo"], rec["id_recurso"], fecha), []),
        })

    return {"fecha": fecha, "id_municipio": id_municipio, "recursos": out_recursos, "eventos": eventos_dia}


# =============================================================================
# Helpers compartidos para /calendario y /semana
# =============================================================================
async def _resolver_scope_subarea(
    db: AsyncSession,
    user: dict,
    id_subarea: Optional[int],
    scope_subarea_propia: bool,
) -> Optional[int]:
    """Resuelve el filtro de subarea efectivo para la grilla.

    - Si `id_subarea` viene explicito, gana (filtro manual del usuario).
    - Si no, y `scope_subarea_propia=True`, intenta resolver la subarea del
      usuario logueado via su agente. Admin (nivel 1) NO se scopea — ve todo.
    - Fail-open: si no se puede resolver (usuario sin agente / agente sin
      subarea — drift de datos comun en prod), devuelve None y la grilla
      muestra todos los recursos. La vista por equipos del supervisor depende
      de que el municipio seedee `agentes.id_subarea`."""
    if id_subarea is not None:
        return id_subarea
    if not scope_subarea_propia:
        return None
    if int(user.get("nivel_acceso", 99)) <= 1:
        return None  # admin ve todo
    return await subarea_del_usuario(db, int(user["id_usuario"]))


async def _listar_recursos_para_calendario(
    db: AsyncSession,
    id_municipio: int,
    tipo_recurso: str,
    id_subarea: Optional[int],
    atendido: Optional[bool],
) -> list[dict[str, Any]]:
    """Listado de recursos activos del municipio para la grilla. Incluye
    agentes, equipos y/o espacios segun `tipo_recurso`. Para espacios admite
    filtro adicional `atendido`."""
    recursos: list[dict[str, Any]] = []
    sa_clause_simple = " AND id_subarea = :sa" if id_subarea is not None else ""
    base_params: dict[str, Any] = {"m": id_municipio}
    if id_subarea is not None:
        base_params["sa"] = id_subarea

    if tipo_recurso in ("agente", "todos"):
        rows = (await db.execute(text(f"""
            SELECT id_agente AS id_recurso, apellido || ', ' || nombre AS nombre
            FROM agentes
            WHERE activo = TRUE AND (id_municipio IS NULL OR id_municipio = :m){sa_clause_simple}
            ORDER BY apellido, nombre
        """), base_params)).mappings().all()
        for r in rows:
            recursos.append({"tipo": "agente", "id_recurso": r["id_recurso"], "nombre": r["nombre"], "atendido": None})

    if tipo_recurso in ("equipo", "todos"):
        rows = (await db.execute(text(f"""
            SELECT id_equipo AS id_recurso, nombre
            FROM equipos
            WHERE activo = TRUE AND (id_municipio IS NULL OR id_municipio = :m){sa_clause_simple}
            ORDER BY nombre
        """), base_params)).mappings().all()
        for r in rows:
            recursos.append({"tipo": "equipo", "id_recurso": r["id_recurso"], "nombre": r["nombre"], "atendido": None})

    if tipo_recurso in ("espacio", "todos"):
        where = ["activo = TRUE", "id_municipio = :m"]
        params: dict[str, Any] = {"m": id_municipio}
        if id_subarea is not None:
            where.append("id_subarea = :sa"); params["sa"] = id_subarea
        if atendido is not None:
            where.append("atendido = :at"); params["at"] = atendido
        rows = (await db.execute(text(f"""
            SELECT id_espacio AS id_recurso, nombre, atendido
            FROM espacios_agenda
            WHERE {' AND '.join(where)}
            ORDER BY nombre
        """), params)).mappings().all()
        for r in rows:
            recursos.append({"tipo": "espacio", "id_recurso": r["id_recurso"], "nombre": r["nombre"], "atendido": bool(r["atendido"])})

    return recursos


async def _eventos_del_rango(
    db: AsyncSession,
    fecha_desde: date,
    fecha_hasta: date,
    id_municipio: int,
) -> dict[date, list[dict[str, Any]]]:
    """Eventos activos en un rango de fechas, con cupo y encargados resueltos.

    2 queries totales (eventos + encargados) sin importar la longitud del rango.
    Devuelve dict[fecha] -> lista de eventos.
    """
    ev_rows = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.fecha, e.hora_inicio, e.hora_fin,
               e.capacidad_ciudadanos, e.id_espacio, e.id_subarea,
               ee.codigo AS estado_codigo,
               (SELECT COUNT(*) FROM evento_reservas r
                 WHERE r.id_evento = e.id_evento AND r.activo = TRUE
                   AND r.id_estado_reserva IN (
                       SELECT id_estado_reserva FROM estado_reserva
                       WHERE codigo IN ('reservada','asistio')
                   )) AS reservas_activas
        FROM eventos e
        LEFT JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
        WHERE e.activo = TRUE AND e.id_municipio = :m
          AND e.fecha BETWEEN :fd AND :fh
        ORDER BY e.fecha, e.hora_inicio
    """), {"m": id_municipio, "fd": fecha_desde, "fh": fecha_hasta})).mappings().all()

    if not ev_rows:
        return {}

    # Bulk de encargados para todos los eventos del rango.
    ids = [r["id_evento"] for r in ev_rows]
    enc_rows = (await db.execute(text("""
        SELECT id_evento, tipo_recurso, id_recurso
        FROM evento_encargados
        WHERE activo = TRUE AND id_evento = ANY(:ids)
    """), {"ids": ids})).mappings().all()
    enc_por_evento: dict[int, list[tuple[str, int]]] = {}
    for e in enc_rows:
        enc_por_evento.setdefault(int(e["id_evento"]), []).append(
            (e["tipo_recurso"], int(e["id_recurso"]))
        )

    out: dict[date, list[dict[str, Any]]] = {}
    for r in ev_rows:
        cap = int(r["capacidad_ciudadanos"] or 0)
        reservas = int(r["reservas_activas"] or 0)
        out.setdefault(r["fecha"], []).append({
            "id_evento": r["id_evento"],
            "nombre": r["nombre"],
            "fecha": r["fecha"],
            "hora_inicio": r["hora_inicio"],
            "hora_fin": r["hora_fin"],
            "capacidad_ciudadanos": cap,
            "reservas_activas": reservas,
            "cupo_libre": max(0, cap - reservas),
            "estado_codigo": r["estado_codigo"],
            "id_espacio": r["id_espacio"],
            "id_subarea": r["id_subarea"],
            "encargados": enc_por_evento.get(int(r["id_evento"]), []),
        })
    return out


async def _eventos_del_dia(db: AsyncSession, fecha: date, id_municipio: int) -> list[dict[str, Any]]:
    """Wrapper compat retro de _eventos_del_rango para un solo dia."""
    rango = await _eventos_del_rango(db, fecha, fecha, id_municipio)
    return rango.get(fecha, [])


@router.get("/mes", response_model=CalendarioMesOut)
async def calendario_mes(
    anio: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    id_municipio: int = 1,
    tipo_recurso: Literal["agente", "equipo", "espacio", "todos"] = "todos",
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Resumen mensual: por dia, conteos de eventos, ocupaciones por tipo y ausencias.
    Cuando tipo_recurso != 'todos' los conteos de ocupaciones se filtran por
    `ocupaciones.tipo_recurso`."""
    _, ndias = calendar.monthrange(anio, mes)
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, ndias)

    # Eventos por dia
    ev_rows = (await db.execute(text("""
        SELECT fecha, COUNT(*) AS cant
        FROM eventos
        WHERE activo = TRUE AND id_municipio = :m
          AND fecha BETWEEN :fd AND :fh
        GROUP BY fecha
    """), {"m": id_municipio, "fd": primer_dia, "fh": ultimo_dia})).mappings().all()
    eventos_por_dia = {r["fecha"]: int(r["cant"]) for r in ev_rows}

    # Ocupaciones por dia y por tipo (con filtro opcional por tipo_recurso)
    oc_params: dict[str, Any] = {"m": id_municipio, "fd": primer_dia, "fh": ultimo_dia}
    oc_filter = ""
    if tipo_recurso != "todos":
        oc_filter = " AND tipo_recurso = :tr"
        oc_params["tr"] = tipo_recurso
    oc_rows = (await db.execute(text(f"""
        SELECT fecha, tipo, COUNT(*) AS cant
        FROM ocupaciones
        WHERE activo = TRUE AND id_municipio = :m
          AND fecha BETWEEN :fd AND :fh{oc_filter}
        GROUP BY fecha, tipo
    """), oc_params)).mappings().all()
    ocup_por_dia: dict[date, dict[str, int]] = {}
    for r in oc_rows:
        ocup_por_dia.setdefault(r["fecha"], {})[r["tipo"]] = int(r["cant"])

    # Ausencias por dia (tabla nueva ausencias_agente, mig 39)
    ausencias_por_dia: dict[date, int] = {}
    aus_rows = (await db.execute(text("""
        SELECT au.fecha_desde, au.fecha_hasta
        FROM ausencias_agente au
        JOIN agentes a ON a.id_agente = au.id_agente
        WHERE au.activo = TRUE
          AND NOT (au.fecha_hasta < :fd OR au.fecha_desde > :fh)
          AND a.activo = TRUE
          AND (a.id_municipio IS NULL OR a.id_municipio = :m)
    """), {"m": id_municipio, "fd": primer_dia, "fh": ultimo_dia})).mappings().all()
    for r in aus_rows:
        d0 = max(r["fecha_desde"], primer_dia)
        d1 = min(r["fecha_hasta"], ultimo_dia)
        cur = d0
        while cur <= d1:
            ausencias_por_dia[cur] = ausencias_por_dia.get(cur, 0) + 1
            cur += timedelta(days=1)

    dias = []
    for d in range(1, ndias + 1):
        fdia = date(anio, mes, d)
        por_tipo = ocup_por_dia.get(fdia, {})
        dias.append({
            "fecha": fdia,
            "eventos": eventos_por_dia.get(fdia, 0),
            "ocupaciones_total": sum(por_tipo.values()),
            "ocupaciones_por_tipo": por_tipo,
            "ausencias": ausencias_por_dia.get(fdia, 0),
        })

    return {"anio": anio, "mes": mes, "id_municipio": id_municipio, "dias": dias}


# =============================================================================
# Vista semanal (sub-fase B1)
# =============================================================================
@router.get("/semana", response_model=CalendarioSemanaOut)
async def calendario_semana(
    desde: date = Query(..., description="Fecha del primer dia (inclusive)"),
    dias: int = Query(7, ge=1, le=14, description="Cantidad de dias contiguos (default 7)"),
    id_municipio: int = 1,
    tipo_recurso: Literal["agente", "equipo", "espacio", "todos"] = "todos",
    id_subarea: Optional[int] = Query(None),
    scope_subarea_propia: bool = Query(False, description="Si True, limita los recursos a la subarea del usuario logueado. Fail-open. Ver /calendario."),
    atendido: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Vista semanal: 7 dias contiguos (configurable). Los recursos vienen al
    nivel raiz; las ocupaciones/eventos/disponibilidad se desglosan por dia.

    Una sola query a ocupaciones/eventos cubre todo el rango (O(1) round-trips
    contra DB para el bloque transaccional; la disponibilidad si necesita un
    pase por (recurso, dia) por el bitmask + vigencia)."""
    hasta = desde + timedelta(days=dias - 1)

    id_subarea = await _resolver_scope_subarea(db, _user, id_subarea, scope_subarea_propia)
    recursos = await _listar_recursos_para_calendario(db, id_municipio, tipo_recurso, id_subarea, atendido)

    # Ocupaciones de TODO el rango
    rows = (await db.execute(text(f"""
        SELECT o.id_ocupacion, o.tipo, o.tipo_recurso, o.id_recurso, o.fecha,
               o.hora_inicio, o.hora_fin, o.id_orden_trabajo, o.id_evento, o.id_ciudadano,
               o.duracion_aplicada_min, o.rol_en_evento, o.motivo,
               o.activo, o.id_municipio, o.fecha_alta,
               {descripcion_corta_sql()} AS descripcion_corta
        FROM ocupaciones o
        LEFT JOIN eventos         ev ON ev.id_evento    = o.id_evento
        LEFT JOIN ordenes_trabajo ot ON ot.id_ot        = o.id_orden_trabajo
        LEFT JOIN ciudadanos      ci ON ci.id_ciudadano = o.id_ciudadano
        WHERE o.activo = TRUE AND o.id_municipio = :m
          AND o.fecha BETWEEN :fd AND :fh
        ORDER BY o.fecha, o.tipo_recurso, o.id_recurso, o.hora_inicio
    """), {"m": id_municipio, "fd": desde, "fh": hasta})).mappings().all()
    ocup_por_dia: dict[date, list[dict[str, Any]]] = {}
    for r in rows:
        ocup_por_dia.setdefault(r["fecha"], []).append(dict(r))

    # Ausencias activas en el rango (mapeadas dia por dia)
    aus_por_dia: dict[date, list[dict[str, Any]]] = {}
    aus_rows = (await db.execute(text("""
        SELECT a.id_agente, au.id_ausencia_agente AS id_ausencia,
               au.fecha_desde, au.fecha_hasta, au.motivo
        FROM ausencias_agente au
        JOIN agentes a ON a.id_agente = au.id_agente
        WHERE au.activo = TRUE
          AND NOT (au.fecha_hasta < :fd OR au.fecha_desde > :fh)
          AND a.activo = TRUE
          AND (a.id_municipio IS NULL OR a.id_municipio = :m)
    """), {"m": id_municipio, "fd": desde, "fh": hasta})).mappings().all()
    for r in aus_rows:
        d0 = max(r["fecha_desde"], desde)
        d1 = min(r["fecha_hasta"], hasta)
        cur = d0
        item = {
            "id_agente": int(r["id_agente"]),
            "id_ausencia": r["id_ausencia"],
            "fecha_desde": r["fecha_desde"],
            "fecha_hasta": r["fecha_hasta"],
            "motivo": r["motivo"],
        }
        while cur <= d1:
            aus_por_dia.setdefault(cur, []).append(item)
            cur += timedelta(days=1)

    # Eventos del rango (1 query base + 1 bulk de encargados, sin importar la cantidad de dias).
    eventos_por_dia = await _eventos_del_rango(db, desde, hasta, id_municipio)

    # Disponibilidad efectiva en BATCH para todos los recursos x todos los dias.
    # Antes: dias x recursos awaits secuenciales. Con 84 agentes x 7 dias eso
    # eran 588 round-trips contra la DB.
    fechas_rango = [desde + timedelta(days=i) for i in range(dias)]
    disp_batch = await disponibilidad_efectiva_batch(
        db,
        [(rec["tipo"], rec["id_recurso"], rec.get("atendido")) for rec in recursos],
        fechas_rango,
    )

    # Build response por dia
    dias_out: list[dict[str, Any]] = []
    for i in range(dias):
        d = desde + timedelta(days=i)
        disp_por_recurso: dict[str, list[dict[str, Any]]] = {}
        for rec in recursos:
            key = f"{rec['tipo']}:{rec['id_recurso']}"
            disp_por_recurso[key] = disp_batch.get((rec["tipo"], rec["id_recurso"], d), [])

        dias_out.append({
            "fecha": d,
            "ocupaciones": ocup_por_dia.get(d, []),
            "ausencias": aus_por_dia.get(d, []),
            "eventos": eventos_por_dia.get(d, []),
            "disponibilidad_por_recurso": disp_por_recurso,
        })

    # Recursos al nivel raiz: sin disponibilidad ni ocupaciones (ya vienen por dia)
    recursos_raiz = [{
        "tipo": r["tipo"],
        "id_recurso": r["id_recurso"],
        "nombre": r["nombre"],
        "atendido": r.get("atendido"),
        "ocupaciones": [],
        "ausencias": [],
        "disponibilidad": [],
    } for r in recursos]

    return {
        "desde": desde,
        "hasta": hasta,
        "id_municipio": id_municipio,
        "recursos": recursos_raiz,
        "dias": dias_out,
    }


# =============================================================================
# Conflictos
# =============================================================================
@router.get("/conflictos", response_model=list[ConflictoOut])
async def listar_conflictos(
    resuelto: Optional[bool] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Listado de conflictos con detalle de las dos ocupaciones involucradas."""
    where: list[str] = ["1 = 1"]
    params: dict[str, Any] = {}
    if resuelto is not None:
        where.append("cl.resuelto = :r"); params["r"] = resuelto
    if desde:
        where.append("cl.fecha_deteccion >= :fd"); params["fd"] = desde
    if hasta:
        where.append("cl.fecha_deteccion <= :fh"); params["fh"] = hasta
    where_sql = " AND ".join(where)
    params_page = {**params, "lim": limit, "off": offset}
    rows = (await db.execute(text(f"""
        SELECT cl.id_conflicto, cl.fecha_deteccion, cl.tipo_recurso, cl.id_recurso,
               cl.id_ocupacion_origen, cl.id_ocupacion_conflicto, cl.resuelto,
               cl.observaciones,
               (SELECT row_to_json(o)::jsonb FROM (
                    SELECT o.id_ocupacion, o.tipo, o.fecha, o.hora_inicio, o.hora_fin
                    FROM ocupaciones o WHERE o.id_ocupacion = cl.id_ocupacion_origen
                ) o) AS ocupacion_origen_detalle,
               (SELECT row_to_json(o)::jsonb FROM (
                    SELECT o.id_ocupacion, o.tipo, o.fecha, o.hora_inicio, o.hora_fin
                    FROM ocupaciones o WHERE o.id_ocupacion = cl.id_ocupacion_conflicto
                ) o) AS ocupacion_conflicto_detalle
        FROM conflictos_log cl
        WHERE {where_sql}
        ORDER BY cl.fecha_deteccion DESC
        LIMIT :lim OFFSET :off
    """), params_page)).mappings().all()
    return [dict(r) for r in rows]


@router.patch("/conflictos/{id_conflicto}/resolver", response_model=ConflictoOut)
async def resolver_conflicto(
    id_conflicto: int,
    payload: ConflictoResolverIn,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Marca el conflicto como resuelto y agrega observaciones."""
    existe = await db.scalar(text(
        "SELECT 1 FROM conflictos_log WHERE id_conflicto = :i"
    ), {"i": id_conflicto})
    if not existe:
        raise HTTPException(404, "Conflicto no encontrado")
    await db.execute(text("""
        UPDATE conflictos_log
        SET resuelto = TRUE,
            observaciones = COALESCE(:obs, observaciones)
        WHERE id_conflicto = :i
    """), {"obs": payload.observaciones, "i": id_conflicto})
    await db.commit()
    row = (await db.execute(text("""
        SELECT id_conflicto, fecha_deteccion, tipo_recurso, id_recurso,
               id_ocupacion_origen, id_ocupacion_conflicto, resuelto, observaciones
        FROM conflictos_log WHERE id_conflicto = :i
    """), {"i": id_conflicto})).mappings().first()
    return dict(row)  # type: ignore[arg-type]
