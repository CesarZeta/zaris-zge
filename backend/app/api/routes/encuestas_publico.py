# -*- coding: utf-8 -*-
"""
ZARIS API - Router PÚBLICO del módulo Encuestas (CSAT). Fase 2D.

SIN auth JWT — el ciudadano accede con el token UUID del link del email.
Autorización = posesión del token + rate limiting por IP. Router separado del
admin (§39). Mensajes 4xx genéricos: no filtrar info (§40, repo público).

NUNCA devuelve datos personales del ciudadano (nombre/email/DNI/teléfono/dirección)
ni la descripción del reclamo. Logs: tokens truncados a 8 chars, IP completa OK
(señal anti-abuso), nunca el body de /responder (texto libre del vecino).

Rate limit: 5/min por IP en ambos endpoints (in-memory, ver app/middleware/rate_limit.py).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.services import encuestas_service as svc
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger("zaris.encuestas.publico")

MAX_TEXTO_LIBRE = 1000
MAX_BODY_BYTES = 4096


def _rate_limit_publico(request: Request) -> None:
    check_rate_limit(get_real_ip(request), max_requests=5, window_seconds=60)


router = APIRouter(
    prefix="/api/v1/publico/encuesta",
    tags=["Encuestas Público"],
    dependencies=[Depends(_rate_limit_publico)],
)


def _validar_uuid(token: str) -> None:
    """404 si el token no es un UUID válido (no 400: no filtrar detalle de validación)."""
    try:
        uuid.UUID(token)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, "Encuesta no encontrada")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _branding(db: AsyncSession) -> dict:
    rows = (await db.execute(text("""
        SELECT clave, valor FROM configuracion_general
         WHERE clave IN ('municipio_nombre', 'municipio_logo_url')
    """))).fetchall()
    cfg = {r[0]: (r[1] or "").strip() for r in rows}
    return {
        "municipio_nombre": cfg.get("municipio_nombre", ""),
        "municipio_logo_url": cfg.get("municipio_logo_url", ""),
    }


# ===========================================================================
# GET /{token} — cargar la encuesta para el formulario
# ===========================================================================

@router.get("/{token}")
async def cargar_encuesta(token: str, db: AsyncSession = Depends(get_db)):
    _validar_uuid(token)

    env = (await db.execute(text("""
        SELECT ee.id_encuesta_envio, ee.id_plantilla, ee.estado, ee.fecha_expiracion,
               ee.id_reclamo, ee.id_turno,
               r.nro_reclamo, r.fecha_alta AS reclamo_fecha,
               t.fecha AS turno_fecha, tp.nombre AS prestacion_nombre
          FROM encuesta_envio ee
          LEFT JOIN reclamos r        ON r.id_reclamo = ee.id_reclamo
          LEFT JOIN turnos t          ON t.id_turno = ee.id_turno
          LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
         WHERE ee.token_unico = CAST(:t AS uuid) AND ee.activo = TRUE
         LIMIT 1
    """), {"t": token})).fetchone()
    if env is None:
        logger.info("cargar_encuesta: token=%s inexistente", svc._tok(token))
        raise HTTPException(404, "Encuesta no encontrada")
    env = env._mapping

    if env["estado"] == "completada":
        raise HTTPException(410, "Esta encuesta ya fue respondida")
    if env["fecha_expiracion"] and env["fecha_expiracion"] < _now():
        if env["estado"] in ("enviada", "abierta"):
            await db.execute(text("""
                UPDATE encuesta_envio SET estado='expirada', fecha_modificacion=NOW()
                 WHERE id_encuesta_envio=:id
            """), {"id": env["id_encuesta_envio"]})
            await db.commit()
        raise HTTPException(410, "El link de la encuesta expiró")
    if env["estado"] == "expirada":
        raise HTTPException(410, "El link de la encuesta expiró")

    # marca fecha_apertura si es la primera vez (best-effort, no rompe el GET)
    await svc.registrar_apertura(db, token)

    # plantilla + preguntas + opciones (SOLO lo que el form necesita)
    pl = (await db.execute(text("""
        SELECT id_encuesta_plantilla, nombre FROM encuesta_plantilla
         WHERE id_encuesta_plantilla = :p AND activo = TRUE LIMIT 1
    """), {"p": env["id_plantilla"]})).fetchone()
    if pl is None:
        raise HTTPException(404, "Encuesta no encontrada")

    preguntas = (await db.execute(text("""
        SELECT id_encuesta_pregunta, texto, tipo, rama, orden, obligatoria
          FROM encuesta_pregunta
         WHERE id_plantilla = :p AND activo = TRUE
         ORDER BY rama, orden
    """), {"p": env["id_plantilla"]})).fetchall()
    opciones = (await db.execute(text("""
        SELECT o.id_encuesta_opcion, o.id_pregunta, o.texto, o.valor, o.orden
          FROM encuesta_opcion o
          JOIN encuesta_pregunta p ON p.id_encuesta_pregunta = o.id_pregunta
         WHERE p.id_plantilla = :p AND o.activo = TRUE
         ORDER BY o.id_pregunta, o.orden
    """), {"p": env["id_plantilla"]})).fetchall()

    op_por_q: dict[int, list] = {}
    for o in opciones:
        m = o._mapping
        op_por_q.setdefault(m["id_pregunta"], []).append({
            "id_opcion": m["id_encuesta_opcion"],
            "texto": m["texto"], "valor": m["valor"], "orden": m["orden"],
        })

    preguntas_out = [{
        "id_pregunta": p._mapping["id_encuesta_pregunta"],
        "texto": p._mapping["texto"],
        "tipo": p._mapping["tipo"],
        "rama": p._mapping["rama"],
        "orden": p._mapping["orden"],
        "obligatoria": p._mapping["obligatoria"],
        "opciones": op_por_q.get(p._mapping["id_encuesta_pregunta"], []),
    } for p in preguntas]

    brand = await _branding(db)
    if env["id_turno"] is not None:
        ref = env["prestacion_nombre"] or "Atención"
        fecha = env["turno_fecha"]
        if fecha:
            ref += f" del {fecha.strftime('%d/%m/%Y')}"
    else:
        nro = env["nro_reclamo"] or f"#{env['id_reclamo']}"
        ref = f"Reclamo {nro}"
        fecha = env["reclamo_fecha"]
        if fecha:
            ref += f" del {fecha.strftime('%d/%m/%Y')}"

    return {
        "encuesta": {
            "id_plantilla": env["id_plantilla"],
            "titulo": pl._mapping["nombre"],
            "municipio_nombre": brand["municipio_nombre"],
            "municipio_logo_url": brand["municipio_logo_url"],
            "reclamo_referencia": ref,
            "fecha_expiracion": env["fecha_expiracion"],
        },
        "preguntas": preguntas_out,
    }


# ===========================================================================
# POST /{token}/responder — registrar la respuesta del ciudadano
# ===========================================================================

@router.post("/{token}/responder")
async def responder_encuesta(
    token: str,
    request: Request,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    _validar_uuid(token)

    # tamaño total del body (4 KB)
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "El cuerpo de la solicitud es demasiado grande")

    # validación del body
    clasif = body.get("clasificacion_inicial")
    if not isinstance(clasif, int) or not (1 <= clasif <= 5):
        raise HTTPException(422, "clasificacion_inicial debe ser un entero entre 1 y 5")

    tiempo = body.get("tiempo_completado_seg")
    if tiempo is not None and not isinstance(tiempo, int):
        tiempo = None

    respuestas_in = body.get("respuestas", [])
    if not isinstance(respuestas_in, list):
        raise HTTPException(422, "respuestas debe ser una lista")

    respuestas: list[dict] = []
    for r in respuestas_in:
        if not isinstance(r, dict):
            raise HTTPException(422, "Cada respuesta debe ser un objeto")
        qid = r.get("id_pregunta")
        if not isinstance(qid, int) or qid <= 0:
            raise HTTPException(422, "id_pregunta inválido en una respuesta")
        vt = r.get("valor_texto")
        if isinstance(vt, str) and len(vt) > MAX_TEXTO_LIBRE:
            vt = vt[:MAX_TEXTO_LIBRE]  # truncar, no rechazar
        respuestas.append({
            "id_pregunta": qid,
            "valor_numerico": r.get("valor_numerico"),
            "valor_texto": vt,
            "id_opcion_seleccionada": r.get("id_opcion_seleccionada"),
        })

    ip = get_real_ip(request)
    try:
        res = await svc.registrar_respuesta(
            db, token, clasif, respuestas, tiempo, ip)
    except Exception:
        logger.exception("responder_encuesta error inesperado (token=%s)", svc._tok(token))
        raise HTTPException(500, "No se pudo procesar la respuesta")

    if res.get("ok"):
        return {"ok": True, "mensaje": res.get("mensaje", "¡Gracias por tu respuesta!")}

    # mapear el error del service a un status apropiado
    err = res.get("error", "")
    low = err.lower()
    if "no está disponible" in low or "expir" in low or "inválido" in low:
        raise HTTPException(410, err)
    raise HTTPException(422, err)
