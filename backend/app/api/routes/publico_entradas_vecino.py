"""
ZARIS API - ENTRADAS del vecino logueado (App Vecinos, etapa D del plan).

Bajo /api/v1/publico/entradas/*. Guard get_current_ciudadano (JWT scope 'publico').

Espejo de la etapa C (turnos): el vecino opera desde su CUENTA — el id_ciudadano
SIEMPRE sale del token, nunca del body. A diferencia del autoservicio anonimo por
token de evento (agenda_publico), aca los eventos son DESCUBRIBLES (cartelera) y
las reservas quedan en "Mis entradas" con el QR para acreditarse en puerta
(el operador lo escanea con POST /agenda/reservas/acreditar-qr, que ya existe).

  - GET    /api/v1/publico/entradas                      -> mis entradas (token)
  - GET    /api/v1/publico/entradas/eventos              -> cartelera (proximos, con cupo)
  - POST   /api/v1/publico/entradas/eventos/{id}/reservar -> reservar a mi nombre
  - PATCH  /api/v1/publico/entradas/{id}/cancelar        -> cancelar una entrada MIA

Reusa helpers de services.agenda (cupo_disponible, lookup_estado_reserva,
generar_qr_codigo, registrar_audit) — misma logica de negocio que agenda_publico,
distinta identidad. Reserva ajena -> 404 con cuerpo generico (no filtrar terceros).
La cartelera computa el cupo EN SQL (un solo query, sin N+1 — latencia §27).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip
from app.services.agenda import (
    cupo_disponible,
    generar_qr_codigo,
    lookup_estado_reserva,
    registrar_audit,
)

router = APIRouter(prefix="/api/v1/publico/entradas", tags=["publico-entradas"])
logger = logging.getLogger("zaris.publico_entradas")


def _to_dict(row) -> dict:
    d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# ─── GET /publico/entradas — mis entradas ────────────────────────────────────

@router.get("")
async def listar_mis_entradas(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Reservas de eventos del vecino logueado (vigentes + historico).
    Incluye qr_codigo: la PWA lo renderiza para acreditarse en puerta."""
    rows = (await db.execute(text("""
        SELECT r.id_evento_reserva, r.qr_codigo, r.fecha_alta,
               er.codigo AS estado_codigo,
               e.id_evento, e.nombre AS evento_nombre, e.descripcion AS evento_descripcion,
               e.fecha, e.hora_inicio, e.hora_fin, e.tipo_qr,
               esp.nombre AS espacio_nombre
        FROM evento_reservas r
        JOIN eventos e                ON e.id_evento = r.id_evento
        LEFT JOIN estado_reserva er   ON er.id_estado_reserva = r.id_estado_reserva
        LEFT JOIN espacios_agenda esp ON esp.id_espacio = e.id_espacio
        WHERE r.activo = TRUE AND r.id_ciudadano = :c
        ORDER BY e.fecha DESC, e.hora_inicio DESC
        LIMIT 100
    """), {"c": current["id_ciudadano"]})).mappings().all()
    return [_to_dict(r) for r in rows]


# ─── GET /publico/entradas/eventos — cartelera ───────────────────────────────

@router.get("/eventos")
async def cartelera_eventos(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Eventos proximos con autoservicio abierto, su cupo disponible y si el
    vecino ya tiene reserva (para deshabilitar el boton en la cartelera).
    Cupo agregado en SQL (sin N+1)."""
    rows = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.descripcion,
               e.fecha, e.hora_inicio, e.hora_fin, e.tipo_qr,
               esp.nombre AS espacio_nombre,
               GREATEST(0, e.capacidad_ciudadanos - COALESCE(res.ocupadas, 0)) AS cupo_disponible,
               (mia.id_evento_reserva IS NOT NULL) AS ya_reservado
        FROM eventos e
        JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento AND ee.codigo = 'activo'
        LEFT JOIN espacios_agenda esp ON esp.id_espacio = e.id_espacio
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS ocupadas
            FROM evento_reservas r
            JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
            WHERE r.id_evento = e.id_evento AND r.activo = TRUE AND er.codigo <> 'cancelada'
        ) res ON TRUE
        LEFT JOIN LATERAL (
            SELECT r2.id_evento_reserva
            FROM evento_reservas r2
            JOIN estado_reserva er2 ON er2.id_estado_reserva = r2.id_estado_reserva
            WHERE r2.id_evento = e.id_evento AND r2.id_ciudadano = :c
              AND r2.activo = TRUE AND er2.codigo <> 'cancelada'
            LIMIT 1
        ) mia ON TRUE
        WHERE e.activo = TRUE
          AND e.admite_autoservicio = TRUE
          AND e.fecha >= CURRENT_DATE
        ORDER BY e.fecha, e.hora_inicio
        LIMIT 50
    """), {"c": current["id_ciudadano"]})).mappings().all()
    return [_to_dict(r) for r in rows]


# ─── POST /publico/entradas/eventos/{id}/reservar ────────────────────────────

@router.post("/eventos/{id_evento}/reservar", status_code=201)
async def reservar_entrada_vecino(
    id_evento: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Reserva una entrada A NOMBRE del vecino del token. Mismas validaciones
    que el autoservicio anonimo (evento activo, cupo, no duplicar)."""
    check_rate_limit(f"entrvec:{get_real_ip(request)}", max_requests=5, window_seconds=60)
    id_ciudadano = current["id_ciudadano"]

    ev = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.fecha, e.hora_inicio, e.hora_fin,
               e.tipo_qr, e.admite_autoservicio, e.activo,
               ee.codigo AS estado_codigo
        FROM eventos e
        LEFT JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
        WHERE e.id_evento = :e
    """), {"e": id_evento})).mappings().first()
    if not ev or not ev["activo"] or not ev["admite_autoservicio"]:
        raise HTTPException(404, "Evento no encontrado o no disponible")
    if ev["estado_codigo"] != "activo":
        raise HTTPException(409, "El evento no acepta reservas en este momento")

    cupo = await cupo_disponible(db, id_evento)
    if cupo <= 0:
        raise HTTPException(409, "Sin cupo disponible para este evento")

    dup = await db.scalar(text("""
        SELECT 1 FROM evento_reservas r
        JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
        WHERE r.id_evento = :e AND r.id_ciudadano = :c
          AND r.activo = TRUE AND er.codigo <> 'cancelada'
        LIMIT 1
    """), {"e": id_evento, "c": id_ciudadano})
    if dup:
        raise HTTPException(409, "Ya tenes una entrada reservada para este evento")

    id_reservada = await lookup_estado_reserva(db, "reservada")
    if not id_reservada:
        raise HTTPException(500, "Falta seed de estado_reserva (codigo='reservada').")

    row = (await db.execute(text("""
        INSERT INTO evento_reservas (
            id_evento, id_ciudadano, id_estado_reserva, origen,
            token_reserva, id_municipio, id_usuario_alta
        ) VALUES (
            :e, :c, :er, 'autoservicio', gen_random_uuid(), 1, NULL
        )
        RETURNING id_evento_reserva
    """), {"e": id_evento, "c": id_ciudadano, "er": id_reservada})).first()
    new_id = int(row[0])

    qr = None
    if ev["tipo_qr"] != "ninguno":
        qr = generar_qr_codigo(id_evento, new_id)
        await db.execute(text(
            "UPDATE evento_reservas SET qr_codigo = :q WHERE id_evento_reserva = :i"
        ), {"q": qr, "i": new_id})

    await registrar_audit(
        db, None, "reserva", new_id, "crear",
        None,
        {
            "id_evento": id_evento,
            "id_ciudadano": id_ciudadano,
            "origen": "app_vecinos",
            "qr_codigo": qr,
        },
        1,
    )
    await db.commit()

    return {
        "id_evento_reserva": new_id,
        "estado_codigo": "reservada",
        "qr_codigo": qr,
        "evento_nombre": ev["nombre"],
        "fecha": ev["fecha"].isoformat(),
        "hora_inicio": ev["hora_inicio"].isoformat() if ev["hora_inicio"] else None,
        "hora_fin": ev["hora_fin"].isoformat() if ev["hora_fin"] else None,
    }


# ─── PATCH /publico/entradas/{id}/cancelar ───────────────────────────────────

@router.patch("/{id_evento_reserva}/cancelar")
async def cancelar_mi_entrada(
    id_evento_reserva: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Cancela una entrada PROPIA en estado 'reservada' (libera el cupo).
    Reserva ajena o inexistente -> 404 generico."""
    r = (await db.execute(text("""
        SELECT r.id_evento_reserva, er.codigo AS estado_codigo
        FROM evento_reservas r
        LEFT JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
        WHERE r.id_evento_reserva = :id AND r.activo = TRUE AND r.id_ciudadano = :c
    """), {"id": id_evento_reserva, "c": current["id_ciudadano"]})).mappings().first()
    if not r:
        raise HTTPException(404, "Reserva no encontrada")
    if r["estado_codigo"] == "cancelada":
        return {"id_evento_reserva": id_evento_reserva, "estado_codigo": "cancelada", "ya_cancelada": True}
    if r["estado_codigo"] != "reservada":
        raise HTTPException(409, "La entrada ya fue utilizada y no se puede cancelar")

    id_cancelada = await lookup_estado_reserva(db, "cancelada")
    if not id_cancelada:
        raise HTTPException(500, "Falta seed de estado_reserva (codigo='cancelada').")
    await db.execute(text("""
        UPDATE evento_reservas
           SET id_estado_reserva = :er, fecha_modificacion = NOW()
         WHERE id_evento_reserva = :i
    """), {"er": id_cancelada, "i": id_evento_reserva})
    await registrar_audit(
        db, None, "reserva", id_evento_reserva, "cancelar",
        {"estado_codigo": r["estado_codigo"]},
        {"estado_codigo": "cancelada", "origen": "app_vecinos"},
        1,
    )
    await db.commit()
    return {"id_evento_reserva": id_evento_reserva, "estado_codigo": "cancelada"}
