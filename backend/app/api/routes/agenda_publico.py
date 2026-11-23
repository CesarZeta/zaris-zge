"""
Router publico del modulo Agenda — endpoints sin JWT para autoservicio.

Acceso por token UUID (no enumerable):
  - eventos.token_publico     : abre el form de reserva del evento.
  - evento_reservas.token_reserva : permite ver/cancelar una reserva individual.

La entrada se reserva desde el portal del vecino (`publico_entradas_vecino.py`): toda transacción
empieza por el registro de la persona (César, 2026-11-23). `POST /reservar` responde 410.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.sistema import fijar_por_token
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agenda_v2 import (
    EventoPublicoOut,
    ReservaPublicaOut,
)
from app.services.agenda import (
    cupo_disponible,
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
    await fijar_por_token(db, token, "evento")  # segunda barrera (IT-01 F6): municipio del token
    row = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.descripcion,
               e.fecha, e.hora_inicio, e.hora_fin,
               e.capacidad_ciudadanos, e.tipo_qr, e.admite_autoservicio,
               e.activo, ee.codigo AS estado_codigo, e.id_municipio
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
@router.post("/evento/{token_publico}/reservar", status_code=410)
async def reservar_publico(token_publico: str):
    """Cerrado: la reserva sin cuenta creaba personas con solo el DNI y datos de relleno."""
    raise HTTPException(410, "Para reservar tu entrada ingresá al portal del vecino con tu cuenta.")


# =============================================================================
# GET reserva publica (por token_reserva)
# =============================================================================
async def _reserva_publica_por_token(
    db: AsyncSession, token_reserva: str,
) -> Optional[dict[str, Any]]:
    _validate_uuid(token_reserva, "Token")
    await fijar_por_token(db, token_reserva, "reserva")  # segunda barrera (IT-01 F6): municipio del token
    row = (await db.execute(text("""
        SELECT r.id_evento_reserva, r.id_evento, r.id_ciudadano,
               r.token_reserva, r.qr_codigo, r.origen, r.activo, r.id_municipio,
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
    # Guard de estado (mig 95): una reserva ya acreditada no se cancela por la
    # via publica (espejo de publico_entradas_vecino; antes se pisaba en silencio).
    if rsv["estado_codigo"] != "reservada":
        raise HTTPException(409, "La reserva ya fue utilizada, no se puede cancelar")

    id_cancelada = await lookup_estado_reserva(db, "cancelada")
    if not id_cancelada:
        raise HTTPException(500, "Falta seed de estado_reserva (codigo='cancelada').")
    id_reservada = await lookup_estado_reserva(db, "reservada")
    # CAS de estado (mig 95): no pisar un acreditar-QR concurrente del backoffice.
    res = await db.execute(text("""
        UPDATE evento_reservas
           SET id_estado_reserva = :er,
               fecha_modificacion = NOW()
         WHERE id_evento_reserva = :i AND id_estado_reserva = :er_prev
    """), {"er": id_cancelada, "i": int(rsv["id_evento_reserva"]), "er_prev": id_reservada})
    if res.rowcount == 0:
        await db.rollback()
        rsv2 = await _reserva_publica_por_token(db, token_reserva)
        if rsv2 and rsv2["estado_codigo"] == "cancelada":
            return await obtener_reserva_publica(token_reserva, db)  # idempotente
        raise HTTPException(409, "La reserva ya fue utilizada, no se puede cancelar")
    await registrar_audit(
        db, None, "reserva", int(rsv["id_evento_reserva"]), "cancelar",
        {"estado_codigo": rsv["estado_codigo"]},
        {"estado_codigo": "cancelada", "origen": "autoservicio_publico"},
        id_municipio=int(rsv["id_municipio"]),
    )
    await db.commit()
    return await obtener_reserva_publica(token_reserva, db)
