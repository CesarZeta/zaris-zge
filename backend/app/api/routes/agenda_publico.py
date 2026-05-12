"""
Router publico del modulo Agenda — endpoints sin JWT para autoservicio.

Acceso por token UUID (no enumerable):
  - eventos.token_publico     : abre el form de reserva del evento.
  - evento_reservas.token_reserva : permite ver/cancelar una reserva individual.

Validaciones del POST /reservar:
  - evento.admite_autoservicio = TRUE
  - estado_evento.codigo = 'activo'
  - cupo_disponible > 0
  - mismo DNI no tiene reserva activa no-cancelada en el mismo evento
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agenda_v2 import (
    EventoPublicoOut,
    ReservaPublicaCreate,
    ReservaPublicaOut,
)
from app.services.agenda import (
    buscar_o_crear_ciudadano_por_dni,
    cupo_disponible,
    generar_qr_codigo,
    lookup_estado_reserva,
    registrar_audit,
)


router = APIRouter(prefix="/api/v1/agenda/publico", tags=["agenda-publico"])
logger = logging.getLogger("zaris.agenda_publico")

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _validate_uuid(token: str, label: str) -> None:
    if not UUID_RE.match(token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} invalido")


async def _evento_publico_por_token(db: AsyncSession, token: str) -> Optional[dict[str, Any]]:
    """Devuelve el evento (vista publica) si el token es valido + autoservicio
    abierto + evento activo. Si algo falla, None — el caller decide el error
    (404 generico para no filtrar si existe o no)."""
    _validate_uuid(token, "Token")
    row = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.descripcion,
               e.fecha, e.hora_inicio, e.hora_fin,
               e.capacidad_ciudadanos, e.tipo_qr, e.admite_autoservicio,
               e.activo, ee.codigo AS estado_codigo
          FROM eventos e
          LEFT JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
         WHERE e.token_publico = CAST(:t AS UUID)
    """), {"t": token})).mappings().first()
    if not row:
        return None
    return dict(row)


async def _build_evento_publico_out(db: AsyncSession, evento: dict[str, Any]) -> EventoPublicoOut:
    cupo = await cupo_disponible(db, int(evento["id_evento"]))
    return EventoPublicoOut(
        id_evento=int(evento["id_evento"]),
        nombre=evento["nombre"],
        descripcion=evento.get("descripcion"),
        fecha=evento["fecha"],
        hora_inicio=evento["hora_inicio"],
        hora_fin=evento["hora_fin"],
        cupo_disponible=cupo,
        estado_codigo=evento["estado_codigo"] or "",
        admite_autoservicio=bool(evento["admite_autoservicio"]),
        tipo_qr=evento["tipo_qr"],
    )


# =============================================================================
# GET evento publico
# =============================================================================
@router.get("/evento/{token_publico}", response_model=EventoPublicoOut)
async def obtener_evento_publico(
    token_publico: str,
    db: AsyncSession = Depends(get_db),
):
    """Datos minimos del evento para mostrar al ciudadano antes de reservar.
    Devuelve 404 si el token no existe, si el evento esta inactivo o si
    `admite_autoservicio=FALSE` (no se filtra el motivo a proposito)."""
    ev = await _evento_publico_por_token(db, token_publico)
    if not ev or not ev["activo"] or not ev["admite_autoservicio"]:
        raise HTTPException(404, "Evento no encontrado o no disponible")
    return await _build_evento_publico_out(db, ev)


# =============================================================================
# POST reservar
# =============================================================================
@router.post(
    "/evento/{token_publico}/reservar",
    response_model=ReservaPublicaOut,
    status_code=201,
)
async def reservar_publico(
    token_publico: str,
    payload: ReservaPublicaCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crea una reserva por autoservicio.
    Busca ciudadano por DNI; si no existe lo crea con datos minimos."""
    ev = await _evento_publico_por_token(db, token_publico)
    if not ev or not ev["activo"] or not ev["admite_autoservicio"]:
        raise HTTPException(404, "Evento no encontrado o no disponible")
    if ev["estado_codigo"] != "activo":
        raise HTTPException(409, f"Evento en estado '{ev['estado_codigo']}', no acepta reservas")

    cupo = await cupo_disponible(db, int(ev["id_evento"]))
    if cupo <= 0:
        raise HTTPException(409, "Sin cupo disponible para este evento")

    # Busca o crea ciudadano por DNI
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

    # No duplicar reserva (mismo DNI, mismo evento, no cancelada)
    dup = await db.scalar(text("""
        SELECT 1 FROM evento_reservas r
        JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
        WHERE r.id_evento = :e
          AND r.id_ciudadano = :c
          AND r.activo = TRUE
          AND er.codigo <> 'cancelada'
        LIMIT 1
    """), {"e": int(ev["id_evento"]), "c": int(ciu["id_ciudadano"])})
    if dup:
        raise HTTPException(409, "Ya existe una reserva activa para este DNI en el evento")

    id_reservada = await lookup_estado_reserva(db, "reservada")
    if not id_reservada:
        raise HTTPException(500, "Falta seed de estado_reserva (codigo='reservada').")

    row = (await db.execute(text("""
        INSERT INTO evento_reservas (
            id_evento, id_ciudadano, id_estado_reserva, origen,
            token_reserva,
            id_municipio, id_usuario_alta
        ) VALUES (
            :e, :c, :er, 'autoservicio',
            gen_random_uuid(),
            1, NULL
        )
        RETURNING id_evento_reserva, token_reserva
    """), {
        "e": int(ev["id_evento"]), "c": int(ciu["id_ciudadano"]), "er": id_reservada,
    })).first()
    new_id = int(row[0])
    token_reserva = str(row[1])

    qr = None
    if ev["tipo_qr"] != "ninguno":
        qr = generar_qr_codigo(int(ev["id_evento"]), new_id)
        await db.execute(text(
            "UPDATE evento_reservas SET qr_codigo = :q WHERE id_evento_reserva = :i"
        ), {"q": qr, "i": new_id})

    await registrar_audit(
        db, None, "reserva", new_id, "crear",
        None,
        {
            "id_evento": int(ev["id_evento"]),
            "id_ciudadano": int(ciu["id_ciudadano"]),
            "origen": "autoservicio",
            "ciudadano_creado": bool(ciu["creado"]),
            "qr_codigo": qr,
        },
        1,
    )
    await db.commit()

    return ReservaPublicaOut(
        id_evento_reserva=new_id,
        token_reserva=token_reserva,
        qr_codigo=qr,
        estado_codigo="reservada",
        origen="autoservicio",
        ciudadano_apellido=ciu.get("apellido"),
        ciudadano_nombre=ciu.get("nombre"),
        ciudadano_dni=ciu.get("doc_nro"),
        evento=await _build_evento_publico_out(db, ev),
    )


# =============================================================================
# GET reserva publica (por token_reserva)
# =============================================================================
async def _reserva_publica_por_token(
    db: AsyncSession, token_reserva: str,
) -> Optional[dict[str, Any]]:
    _validate_uuid(token_reserva, "Token")
    row = (await db.execute(text("""
        SELECT r.id_evento_reserva, r.id_evento, r.id_ciudadano,
               r.token_reserva, r.qr_codigo, r.origen, r.activo,
               er.codigo AS estado_codigo,
               c.apellido AS ciudadano_apellido,
               c.nombre   AS ciudadano_nombre,
               c.doc_nro  AS ciudadano_dni
          FROM evento_reservas r
          LEFT JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
          LEFT JOIN ciudadanos     c  ON c.id_ciudadano       = r.id_ciudadano
         WHERE r.token_reserva = CAST(:t AS UUID)
    """), {"t": token_reserva})).mappings().first()
    return dict(row) if row else None


@router.get("/reserva/{token_reserva}", response_model=ReservaPublicaOut)
async def obtener_reserva_publica(
    token_reserva: str,
    db: AsyncSession = Depends(get_db),
):
    """Devuelve los datos de la reserva (incluyendo QR) y el evento."""
    rsv = await _reserva_publica_por_token(db, token_reserva)
    if not rsv or not rsv["activo"]:
        raise HTTPException(404, "Reserva no encontrada")
    ev_row = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.descripcion,
               e.fecha, e.hora_inicio, e.hora_fin,
               e.capacidad_ciudadanos, e.tipo_qr, e.admite_autoservicio,
               e.activo, ee.codigo AS estado_codigo
          FROM eventos e
          LEFT JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
         WHERE e.id_evento = :e
    """), {"e": int(rsv["id_evento"])})).mappings().first()
    if not ev_row:
        raise HTTPException(404, "Evento no encontrado")
    evento_dict = dict(ev_row)
    return ReservaPublicaOut(
        id_evento_reserva=int(rsv["id_evento_reserva"]),
        token_reserva=str(rsv["token_reserva"]),
        qr_codigo=rsv.get("qr_codigo"),
        estado_codigo=rsv["estado_codigo"] or "",
        origen=rsv["origen"],
        ciudadano_apellido=rsv.get("ciudadano_apellido"),
        ciudadano_nombre=rsv.get("ciudadano_nombre"),
        ciudadano_dni=rsv.get("ciudadano_dni"),
        evento=await _build_evento_publico_out(db, evento_dict),
    )


# =============================================================================
# DELETE reserva publica (cancelar)
# =============================================================================
@router.delete("/reserva/{token_reserva}", response_model=ReservaPublicaOut)
async def cancelar_reserva_publica(
    token_reserva: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancela la reserva del ciudadano. No la elimina fisicamente."""
    rsv = await _reserva_publica_por_token(db, token_reserva)
    if not rsv or not rsv["activo"]:
        raise HTTPException(404, "Reserva no encontrada")
    if rsv["estado_codigo"] == "cancelada":
        # idempotente — devolver estado actual
        return await obtener_reserva_publica(token_reserva, db)

    id_cancelada = await lookup_estado_reserva(db, "cancelada")
    if not id_cancelada:
        raise HTTPException(500, "Falta seed de estado_reserva (codigo='cancelada').")
    await db.execute(text("""
        UPDATE evento_reservas
           SET id_estado_reserva = :er,
               fecha_modificacion = NOW()
         WHERE id_evento_reserva = :i
    """), {"er": id_cancelada, "i": int(rsv["id_evento_reserva"])})
    await registrar_audit(
        db, None, "reserva", int(rsv["id_evento_reserva"]), "cancelar",
        {"estado_codigo": rsv["estado_codigo"]},
        {"estado_codigo": "cancelada", "origen": "autoservicio_publico"},
        1,
    )
    await db.commit()
    return await obtener_reserva_publica(token_reserva, db)
