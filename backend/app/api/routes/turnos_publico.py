"""
Router publico del modulo Turnos — endpoints sin JWT para autoservicio
(replanteado en mig 71).

El ciudadano elige una PRESTACION (que ya define el recurso fijo: un agente o
un lugar de atencion) y un slot libre. El backend calcula los slots cruzando la
disponibilidad efectiva del recurso de la prestacion con sus ocupaciones.

Flujo del ciudadano:
  1. GET    /api/v1/turnos/publico/prestaciones          -> elige la prestacion
  2. GET    /api/v1/turnos/publico/slots?id_tipo_prestacion= -> elige dia y hora
  3. POST   /api/v1/turnos/publico/reservar              -> crea el turno
  4. GET    /api/v1/turnos/publico/turno/{token}         -> consulta despues
  5. DELETE /api/v1/turnos/publico/turno/{token}         -> cancela

Validaciones del POST /reservar:
  - prestacion activa con recurso valido
  - el slot pedido cae dentro de la disponibilidad efectiva del recurso ese dia
  - el slot no se solapa con ninguna ocupacion existente del recurso
  - el ciudadano (por DNI) no tiene otro turno no-cancelado el mismo dia
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
    PrestacionPublicaOut,
    SlotLibreOut,
    TurnoPublicoCreate,
    TurnoPublicoOut,
)
from app.services.agenda import (
    buscar_o_crear_ciudadano_por_dni,
    disponibilidad_efectiva,
    turnos_respeta_disponibilidad,
)


router = APIRouter(prefix="/api/v1/turnos/publico", tags=["turnos-publico"])
logger = logging.getLogger("zaris.turnos_publico")

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

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


async def _resolver_prestacion(
    db: AsyncSession, id_tipo_prestacion: int,
) -> dict[str, Any]:
    """Devuelve la prestacion activa con su recurso resuelto, o 404."""
    prest = (await db.execute(text("""
        SELECT tp.id_tipo_prestacion, tp.tipo_recurso, tp.id_agente, tp.id_espacio,
               tp.duracion_min,
               CASE WHEN tp.tipo_recurso = 'espacio' THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               tp.id_subarea
        FROM tipo_prestacion tp
        LEFT JOIN agentes         a ON a.id_agente  = tp.id_agente
        LEFT JOIN espacios_agenda e ON e.id_espacio = tp.id_espacio
        WHERE tp.id_tipo_prestacion = :id AND tp.activo = TRUE
    """), {"id": id_tipo_prestacion})).mappings().first()
    if not prest:
        raise HTTPException(404, "Prestacion no encontrada o inactiva")
    tr = prest["tipo_recurso"]
    id_recurso = prest["id_agente"] if tr == "agente" else prest["id_espacio"]
    if id_recurso is None:
        raise HTTPException(422, "La prestacion no tiene un recurso valido asignado")
    return {
        "tipo_recurso": tr,
        "id_recurso": int(id_recurso),
        "recurso_nombre": prest["recurso_nombre"],
        "duracion_min": int(prest["duracion_min"]),
        "id_subarea": prest["id_subarea"],
    }


# =============================================================================
# 1. Prestaciones publicables
# =============================================================================
@router.get("/prestaciones", response_model=list[PrestacionPublicaOut])
async def listar_prestaciones_publico(
    id_municipio: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Prestaciones activas cuyo recurso tiene disponibilidad cargada. Una
    prestacion sin disponibilidad no genera slots, asi que no se ofrece."""
    rows = (await db.execute(text("""
        SELECT tp.id_tipo_prestacion, tp.nombre, tp.descripcion, tp.clase, tp.duracion_min,
               CASE WHEN tp.tipo_recurso = 'espacio' THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre
        FROM tipo_prestacion tp
        LEFT JOIN agentes         a ON a.id_agente  = tp.id_agente
        LEFT JOIN espacios_agenda e ON e.id_espacio = tp.id_espacio
        WHERE tp.activo = TRUE AND tp.id_municipio = :m
          AND (
            -- recurso agente con disponibilidad propia
            (tp.tipo_recurso = 'agente' AND EXISTS (
              SELECT 1 FROM disponibilidad_recurso d
              WHERE d.tipo_recurso = 'agente' AND d.id_recurso = tp.id_agente AND d.activo = TRUE
            ))
            OR
            -- recurso espacio: desatendido con disponibilidad propia, o atendido
            -- con al menos un agente vinculado con disponibilidad.
            (tp.tipo_recurso = 'espacio' AND (
              EXISTS (
                SELECT 1 FROM disponibilidad_recurso d
                WHERE d.tipo_recurso = 'espacio' AND d.id_recurso = tp.id_espacio AND d.activo = TRUE
              )
              OR EXISTS (
                SELECT 1 FROM espacio_agentes ea
                JOIN disponibilidad_recurso d
                  ON d.tipo_recurso = 'agente' AND d.id_recurso = ea.id_agente AND d.activo = TRUE
                WHERE ea.id_espacio = tp.id_espacio AND ea.activo = TRUE
              )
            ))
          )
        ORDER BY tp.nombre
    """), {"m": id_municipio})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# 2. Slots libres de la prestacion
# =============================================================================
async def _slots_libres_recurso(
    db: AsyncSession,
    tipo_recurso: str,
    id_recurso: int,
    recurso_nombre: str,
    duracion_min: int,
    fecha: date,
) -> list[dict[str, Any]]:
    """Slots libres de un recurso para una fecha: parte su disponibilidad
    efectiva en bloques de `duracion_min` y descarta los que se solapan con una
    ocupacion existente del mismo recurso."""
    rangos = await disponibilidad_efectiva(db, tipo_recurso, id_recurso, fecha)
    if not rangos:
        return []

    ocup = (await db.execute(text("""
        SELECT hora_inicio, hora_fin
        FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir AND fecha = :f
    """), {"tr": tipo_recurso, "ir": id_recurso, "f": fecha})).mappings().all()
    ocupadas = [(o["hora_inicio"], o["hora_fin"]) for o in ocup]

    out: list[dict[str, Any]] = []
    for r in rangos:
        for (s_ini, s_fin) in _slots_de_rango(r["hora_inicio"], r["hora_fin"], duracion_min):
            if any(_solapa(s_ini, s_fin, o_ini, o_fin) for (o_ini, o_fin) in ocupadas):
                continue
            out.append({
                "tipo_recurso": tipo_recurso,
                "id_recurso": id_recurso,
                "recurso_nombre": recurso_nombre,
                "fecha": fecha,
                "hora_inicio": s_ini,
                "hora_fin": s_fin,
            })
    return out


@router.get("/slots", response_model=list[SlotLibreOut])
async def listar_slots_publico(
    id_tipo_prestacion: int = Query(..., description="Prestacion: define recurso + duracion"),
    fecha_desde: Optional[date] = Query(None, description="Default: hoy"),
    dias: int = Query(DIAS_VENTANA_DEFAULT, ge=1, le=DIAS_VENTANA_MAX),
    db: AsyncSession = Depends(get_db),
):
    """Slots libres del recurso de la prestacion en una ventana de `dias`."""
    prest = await _resolver_prestacion(db, id_tipo_prestacion)
    desde = fecha_desde or date.today()
    out: list[dict[str, Any]] = []
    for offset in range(dias):
        f = desde + timedelta(days=offset)
        out.extend(await _slots_libres_recurso(
            db, prest["tipo_recurso"], prest["id_recurso"],
            prest["recurso_nombre"] or "", prest["duracion_min"], f,
        ))
    return out


# =============================================================================
# 3. Reservar turno
# =============================================================================
async def _turno_publico_out(db: AsyncSession, id_turno: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT t.id_turno, CAST(t.token_turno AS TEXT) AS token_turno,
               t.estado, t.fecha, t.hora_inicio, t.hora_fin,
               tp.nombre AS prestacion_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               c.apellido AS ciudadano_apellido,
               c.nombre   AS ciudadano_nombre,
               c.doc_nro  AS ciudadano_dni
        FROM turnos t
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN agentes         a  ON a.id_agente            = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio           = t.id_espacio
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano         = t.id_ciudadano
        WHERE t.id_turno = :id
    """), {"id": id_turno})).mappings().first()
    return dict(row) if row else None


@router.post("/reservar", response_model=TurnoPublicoOut, status_code=201)
async def reservar_turno_publico(
    payload: TurnoPublicoCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crea un turno por autoservicio. El recurso lo trae la prestacion.
    Busca/crea el ciudadano por DNI."""
    prest = await _resolver_prestacion(db, payload.id_tipo_prestacion)
    tipo_recurso = prest["tipo_recurso"]
    id_recurso = prest["id_recurso"]
    duracion_min = prest["duracion_min"]
    id_subarea = prest["id_subarea"]

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

    dup = await db.scalar(text("""
        SELECT 1 FROM turnos
        WHERE id_ciudadano = :ic AND fecha = :f AND activo = TRUE AND estado <> 'cancelado'
        LIMIT 1
    """), {"ic": int(ciu["id_ciudadano"]), "f": payload.fecha})
    if dup:
        raise HTTPException(409, "El ciudadano ya tiene un turno reservado para ese dia")

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
        "hi": hora_inicio, "hf": hora_fin, "ic": int(ciu["id_ciudadano"]),
        "mot": f"Turno (autoservicio): {payload.observaciones}" if payload.observaciones else "Turno (autoservicio)",
    })

    id_agente_turno = id_recurso if tipo_recurso == "agente" else None
    id_espacio_turno = id_recurso if tipo_recurso == "espacio" else None

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
        RETURNING id_turno, CAST(token_turno AS TEXT) AS token_turno
    """), {
        "ic": int(ciu["id_ciudadano"]), "ia": id_agente_turno, "ie": id_espacio_turno,
        "itp": payload.id_tipo_prestacion, "iocup": id_ocupacion,
        "f": payload.fecha, "hi": hora_inicio, "hf": hora_fin,
        "obs": payload.observaciones, "isa": id_subarea,
    })).mappings().first()
    await db.commit()

    out = await _turno_publico_out(db, int(row["id_turno"]))
    if out is None:
        raise HTTPException(500, "Turno creado pero no se pudo releer")
    return out


# =============================================================================
# 4 + 5. Consultar / cancelar por token
# =============================================================================
async def _turno_por_token(db: AsyncSession, token: str) -> Optional[dict[str, Any]]:
    _validate_uuid(token)
    row = (await db.execute(text("""
        SELECT t.id_turno, CAST(t.token_turno AS TEXT) AS token_turno,
               t.id_ocupacion, t.estado, t.fecha, t.hora_inicio, t.hora_fin, t.activo,
               tp.nombre AS prestacion_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               c.apellido AS ciudadano_apellido,
               c.nombre   AS ciudadano_nombre,
               c.doc_nro  AS ciudadano_dni
        FROM turnos t
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN agentes         a  ON a.id_agente            = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio           = t.id_espacio
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano         = t.id_ciudadano
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
