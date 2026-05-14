"""
Router publico del modulo Turnos — endpoints sin JWT para autoservicio.

A diferencia de los eventos (fecha/hora fija), un turno requiere que el
ciudadano elija un slot libre. El backend lo calcula cruzando la
disponibilidad del agente (disponibilidad_recurso) con sus ocupaciones del
dia (turnos reservados/cumplidos + cualquier otra fila en `ocupaciones`).

Flujo del ciudadano:
  1. GET  /api/v1/turnos/publico/tipos-servicio       -> elige el tramite
  2. GET  /api/v1/turnos/publico/agentes?id_tipo=     -> elige a quien
  3. GET  /api/v1/turnos/publico/slots?...            -> elige dia y hora
  4. POST /api/v1/turnos/publico/reservar             -> crea el turno
  5. GET  /api/v1/turnos/publico/turno/{token}        -> consulta despues
  6. DELETE /api/v1/turnos/publico/turno/{token}      -> cancela

Validaciones del POST /reservar:
  - tipo de servicio + agente activos
  - el slot pedido (fecha, hora_inicio) cae dentro de la disponibilidad
    efectiva del agente para ese dia
  - el slot no se solapa con ninguna ocupacion existente del agente
  - el ciudadano (por DNI) no tiene otro turno reservado el mismo dia
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.turnos import (
    AgenteDisponibleOut,
    SlotLibreOut,
    TipoServicioTurnoOut,
    TurnoPublicoCreate,
    TurnoPublicoOut,
)
from app.services.agenda import (
    buscar_o_crear_ciudadano_por_dni,
    disponibilidad_efectiva,
)


router = APIRouter(prefix="/api/v1/turnos/publico", tags=["turnos-publico"])
logger = logging.getLogger("zaris.turnos_publico")

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

# Cuantos dias hacia adelante se ofrecen slots por defecto.
DIAS_VENTANA_DEFAULT = 14
DIAS_VENTANA_MAX = 30


def _validate_uuid(token: str) -> None:
    if not UUID_RE.match(token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado")


def _slots_de_rango(
    rango_ini: time, rango_fin: time, duracion_min: int,
) -> list[tuple[time, time]]:
    """Parte un rango horario en slots consecutivos de `duracion_min`.
    Descarta el ultimo slot si no entra completo."""
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


# =============================================================================
# 1. Tipos de servicio (catalogo publico)
# =============================================================================
@router.get("/tipos-servicio", response_model=list[TipoServicioTurnoOut])
async def listar_tipos_servicio_publico(
    id_municipio: int = 1,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(text("""
        SELECT id_tipo_servicio_turno, nombre, descripcion, duracion_min, activo
        FROM tipo_servicio_turno
        WHERE activo = TRUE AND id_municipio = :m
        ORDER BY nombre
    """), {"m": id_municipio})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# 2. Agentes que pueden atender (tienen disponibilidad cargada)
# =============================================================================
@router.get("/agentes", response_model=list[AgenteDisponibleOut])
async def listar_agentes_publico(
    id_municipio: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Agentes activos que tienen al menos un rango de disponibilidad cargado.
    Sin disponibilidad no hay slots posibles, asi que no se ofrecen."""
    rows = (await db.execute(text("""
        SELECT DISTINCT a.id_agente,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS nombre
        FROM agentes a
        JOIN disponibilidad_recurso d
          ON d.tipo_recurso = 'agente' AND d.id_recurso = a.id_agente AND d.activo = TRUE
        WHERE a.activo = TRUE
          AND (a.id_municipio IS NULL OR a.id_municipio = :m)
        ORDER BY nombre
    """), {"m": id_municipio})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# 3. Slots libres
# =============================================================================
async def _slots_libres_agente(
    db: AsyncSession,
    id_agente: int,
    agente_nombre: str,
    duracion_min: int,
    fecha: date,
) -> list[dict[str, Any]]:
    """Slots libres de un agente para una fecha: parte su disponibilidad
    efectiva en bloques de `duracion_min` y descarta los que se solapan con
    una ocupacion existente."""
    rangos = await disponibilidad_efectiva(db, "agente", id_agente, fecha)
    if not rangos:
        return []

    # Ocupaciones del agente ese dia (incluye turnos espejo + OTs + lo que sea).
    ocup = (await db.execute(text("""
        SELECT hora_inicio, hora_fin
        FROM ocupaciones
        WHERE activo = TRUE
          AND tipo_recurso = 'agente'
          AND id_recurso = :ia
          AND fecha = :f
    """), {"ia": id_agente, "f": fecha})).mappings().all()
    ocupadas = [(o["hora_inicio"], o["hora_fin"]) for o in ocup]

    out: list[dict[str, Any]] = []
    for r in rangos:
        for (s_ini, s_fin) in _slots_de_rango(r["hora_inicio"], r["hora_fin"], duracion_min):
            if any(_solapa(s_ini, s_fin, o_ini, o_fin) for (o_ini, o_fin) in ocupadas):
                continue
            out.append({
                "id_agente": id_agente,
                "agente_nombre": agente_nombre,
                "fecha": fecha,
                "hora_inicio": s_ini,
                "hora_fin": s_fin,
            })
    return out


@router.get("/slots", response_model=list[SlotLibreOut])
async def listar_slots_publico(
    id_tipo_servicio_turno: int = Query(..., description="Define la duracion del slot"),
    id_agente: Optional[int] = Query(None, description="Si se omite, busca en todos los agentes"),
    fecha_desde: Optional[date] = Query(None, description="Default: hoy"),
    dias: int = Query(DIAS_VENTANA_DEFAULT, ge=1, le=DIAS_VENTANA_MAX),
    id_municipio: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Slots libres para un tipo de servicio, opcionalmente filtrando por agente,
    en una ventana de `dias` a partir de `fecha_desde` (default hoy)."""
    tipo = (await db.execute(text("""
        SELECT duracion_min FROM tipo_servicio_turno
        WHERE id_tipo_servicio_turno = :id AND activo = TRUE
    """), {"id": id_tipo_servicio_turno})).mappings().first()
    if not tipo:
        raise HTTPException(404, "Tipo de servicio no encontrado o inactivo")
    duracion_min = int(tipo["duracion_min"])

    # Resolver el set de agentes a consultar.
    if id_agente is not None:
        ag = (await db.execute(text("""
            SELECT id_agente,
                   COALESCE(apellido, '') || ', ' || COALESCE(nombre, '') AS nombre
            FROM agentes WHERE id_agente = :id AND activo = TRUE
        """), {"id": id_agente})).mappings().first()
        if not ag:
            raise HTTPException(404, "Agente no encontrado o inactivo")
        agentes = [dict(ag)]
    else:
        agentes = [dict(r) for r in (await db.execute(text("""
            SELECT DISTINCT a.id_agente,
                   COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS nombre
            FROM agentes a
            JOIN disponibilidad_recurso d
              ON d.tipo_recurso = 'agente' AND d.id_recurso = a.id_agente AND d.activo = TRUE
            WHERE a.activo = TRUE
              AND (a.id_municipio IS NULL OR a.id_municipio = :m)
            ORDER BY nombre
        """), {"m": id_municipio})).mappings().all()]

    desde = fecha_desde or date.today()
    out: list[dict[str, Any]] = []
    for offset in range(dias):
        f = desde + timedelta(days=offset)
        for ag in agentes:
            out.extend(await _slots_libres_agente(
                db, int(ag["id_agente"]), ag["nombre"], duracion_min, f,
            ))
    return out


# =============================================================================
# 4. Reservar turno
# =============================================================================
async def _turno_publico_out(db: AsyncSession, id_turno: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT t.id_turno, CAST(t.token_turno AS TEXT) AS token_turno,
               t.estado, t.fecha, t.hora_inicio, t.hora_fin,
               ts.nombre AS tipo_servicio_nombre,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               c.apellido AS ciudadano_apellido,
               c.nombre   AS ciudadano_nombre,
               c.doc_nro  AS ciudadano_dni
        FROM turnos t
        LEFT JOIN tipo_servicio_turno ts ON ts.id_tipo_servicio_turno = t.id_tipo_servicio_turno
        LEFT JOIN agentes             a  ON a.id_agente               = t.id_agente
        LEFT JOIN ciudadanos          c  ON c.id_ciudadano            = t.id_ciudadano
        WHERE t.id_turno = :id
    """), {"id": id_turno})).mappings().first()
    return dict(row) if row else None


@router.post("/reservar", response_model=TurnoPublicoOut, status_code=201)
async def reservar_turno_publico(
    payload: TurnoPublicoCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crea un turno por autoservicio. Busca/crea el ciudadano por DNI."""
    # Validar tipo de servicio
    tipo = (await db.execute(text("""
        SELECT duracion_min FROM tipo_servicio_turno
        WHERE id_tipo_servicio_turno = :id AND activo = TRUE
    """), {"id": payload.id_tipo_servicio_turno})).mappings().first()
    if not tipo:
        raise HTTPException(404, "Tipo de servicio no encontrado o inactivo")
    duracion_min = int(tipo["duracion_min"])

    # Validar agente
    ag = (await db.execute(text("""
        SELECT id_agente, id_subarea,
               COALESCE(apellido, '') || ', ' || COALESCE(nombre, '') AS nombre
        FROM agentes WHERE id_agente = :id AND activo = TRUE
    """), {"id": payload.id_agente})).mappings().first()
    if not ag:
        raise HTTPException(404, "Agente no encontrado o inactivo")

    if payload.fecha < date.today():
        raise HTTPException(422, "No se puede reservar un turno en una fecha pasada")

    hora_inicio = payload.hora_inicio
    hora_fin = (datetime.combine(payload.fecha, hora_inicio)
                + timedelta(minutes=duracion_min)).time()
    if hora_fin <= hora_inicio:
        raise HTTPException(422, "La duracion del tipo de servicio excede el dia")

    # El slot debe caer dentro de la disponibilidad efectiva del agente.
    rangos = await disponibilidad_efectiva(db, "agente", payload.id_agente, payload.fecha)
    dentro = any(
        r["hora_inicio"] <= hora_inicio and hora_fin <= r["hora_fin"]
        for r in rangos
    )
    if not dentro:
        raise HTTPException(409, "El horario solicitado no esta dentro de la disponibilidad del agente")

    # El slot no se debe solapar con una ocupacion existente.
    solapado = await db.scalar(text("""
        SELECT 1 FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = 'agente'
          AND id_recurso = :ia AND fecha = :f
          AND hora_inicio < :hf AND hora_fin > :hi
        LIMIT 1
    """), {"ia": payload.id_agente, "f": payload.fecha, "hi": hora_inicio, "hf": hora_fin})
    if solapado:
        raise HTTPException(409, "El horario solicitado ya no esta disponible")

    # Buscar o crear ciudadano por DNI.
    try:
        ciu = await buscar_o_crear_ciudadano_por_dni(
            db,
            dni=payload.dni,
            apellido=payload.apellido,
            nombre=payload.nombre,
            telefono=payload.telefono,
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    # No duplicar: mismo ciudadano, mismo dia, turno no cancelado.
    dup = await db.scalar(text("""
        SELECT 1 FROM turnos
        WHERE id_ciudadano = :ic AND fecha = :f
          AND activo = TRUE AND estado <> 'cancelado'
        LIMIT 1
    """), {"ic": int(ciu["id_ciudadano"]), "f": payload.fecha})
    if dup:
        raise HTTPException(409, "El ciudadano ya tiene un turno reservado para ese dia")

    # Ocupacion espejo en la grilla de Agenda.
    id_ocupacion = await db.scalar(text("""
        INSERT INTO ocupaciones (
            tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
            id_ciudadano, motivo, id_municipio, id_usuario_alta
        ) VALUES (
            'turno', 'agente', :ia, :f, :hi, :hf,
            :ic, :mot, 1, NULL
        )
        RETURNING id_ocupacion
    """), {
        "ia": payload.id_agente, "f": payload.fecha,
        "hi": hora_inicio, "hf": hora_fin, "ic": int(ciu["id_ciudadano"]),
        "mot": f"Turno (autoservicio): {payload.observaciones}" if payload.observaciones else "Turno (autoservicio)",
    })

    row = (await db.execute(text("""
        INSERT INTO turnos (
            id_ciudadano, id_agente, id_tipo_servicio_turno, id_ocupacion,
            fecha, hora_inicio, hora_fin, estado, observaciones,
            origen, id_municipio, id_subarea
        ) VALUES (
            :ic, :ia, :its, :iocup,
            :f, :hi, :hf, 'reservado', :obs,
            'autoservicio', 1, :isa
        )
        RETURNING id_turno, CAST(token_turno AS TEXT) AS token_turno
    """), {
        "ic": int(ciu["id_ciudadano"]), "ia": payload.id_agente,
        "its": payload.id_tipo_servicio_turno, "iocup": id_ocupacion,
        "f": payload.fecha, "hi": hora_inicio, "hf": hora_fin,
        "obs": payload.observaciones, "isa": ag["id_subarea"],
    })).mappings().first()
    await db.commit()

    out = await _turno_publico_out(db, int(row["id_turno"]))
    if out is None:
        raise HTTPException(500, "Turno creado pero no se pudo releer")
    return out


# =============================================================================
# 5 + 6. Consultar / cancelar por token
# =============================================================================
async def _turno_por_token(db: AsyncSession, token: str) -> Optional[dict[str, Any]]:
    _validate_uuid(token)
    row = (await db.execute(text("""
        SELECT t.id_turno, CAST(t.token_turno AS TEXT) AS token_turno,
               t.id_ocupacion, t.estado, t.fecha, t.hora_inicio, t.hora_fin,
               t.activo,
               ts.nombre AS tipo_servicio_nombre,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               c.apellido AS ciudadano_apellido,
               c.nombre   AS ciudadano_nombre,
               c.doc_nro  AS ciudadano_dni
        FROM turnos t
        LEFT JOIN tipo_servicio_turno ts ON ts.id_tipo_servicio_turno = t.id_tipo_servicio_turno
        LEFT JOIN agentes             a  ON a.id_agente               = t.id_agente
        LEFT JOIN ciudadanos          c  ON c.id_ciudadano            = t.id_ciudadano
        WHERE t.token_turno = CAST(:t AS UUID)
    """), {"t": token})).mappings().first()
    return dict(row) if row else None


@router.get("/turno/{token_turno}", response_model=TurnoPublicoOut)
async def obtener_turno_publico(
    token_turno: str,
    db: AsyncSession = Depends(get_db),
):
    t = await _turno_por_token(db, token_turno)
    if not t or not t["activo"]:
        raise HTTPException(404, "Turno no encontrado")
    return t


@router.delete("/turno/{token_turno}", response_model=TurnoPublicoOut)
async def cancelar_turno_publico(
    token_turno: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancela el turno del ciudadano y libera la ocupacion espejo."""
    t = await _turno_por_token(db, token_turno)
    if not t or not t["activo"]:
        raise HTTPException(404, "Turno no encontrado")
    if t["estado"] == "cancelado":
        return t  # idempotente
    if t["estado"] != "reservado":
        raise HTTPException(409, f"No se puede cancelar un turno '{t['estado']}'")

    await db.execute(text("""
        UPDATE turnos SET estado = 'cancelado', fecha_modificacion = NOW()
        WHERE id_turno = :id
    """), {"id": int(t["id_turno"])})
    if t["id_ocupacion"]:
        await db.execute(text("""
            UPDATE ocupaciones SET activo = FALSE, fecha_modificacion = NOW()
            WHERE id_ocupacion = :io
        """), {"io": int(t["id_ocupacion"])})
    await db.commit()

    out = await _turno_por_token(db, token_turno)
    return out  # type: ignore
