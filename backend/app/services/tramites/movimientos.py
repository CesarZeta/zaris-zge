"""
Helper unificado de registro de movimientos para el modulo Tramites.

Cada endpoint operativo llama exactamente una vez a `registrar_movimiento`.
El orden_secuencial se calcula dentro de la misma transaccion que tiene
el lock FOR UPDATE sobre el tramite.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def siguiente_orden_secuencial(id_tramite: int, db: AsyncSession) -> int:
    row = (await db.execute(
        text("""
            SELECT COALESCE(MAX(orden_secuencial), 0) + 1
            FROM tramite_movimiento
            WHERE id_tramite = :id
        """),
        {"id": id_tramite},
    )).fetchone()
    return row[0]


def _jsonb(val: Any) -> str | None:
    if val is None:
        return None
    return json.dumps(val)


async def registrar_movimiento(
    db: AsyncSession,
    id_tramite: int,
    tipo: str,
    id_usuario: int,
    id_agente: int,
    id_municipio: int,
    request: Request | None = None,
    id_tipo_tramite_transicion: int | None = None,
    id_estado_origen: int | None = None,
    id_estado_destino: int | None = None,
    origen_jsonb: dict | None = None,
    destino_jsonb: dict | None = None,
    comentario: str | None = None,
    metadata_jsonb: dict | None = None,
) -> dict:
    """
    Inserta una fila en tramite_movimiento y la devuelve.
    Debe llamarse dentro de la misma transaccion que muto el tramite.
    """
    orden = await siguiente_orden_secuencial(id_tramite, db)

    ip = None
    user_agent = None
    if request is not None:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    result = await db.execute(
        text("""
            INSERT INTO tramite_movimiento (
                id_tramite, orden_secuencial, tipo,
                id_tipo_tramite_transicion,
                id_estado_origen, id_estado_destino,
                origen_jsonb, destino_jsonb,
                comentario, metadata_jsonb,
                id_agente, ip, user_agent,
                id_municipio,
                id_usuario_alta, id_usuario_modificacion
            ) VALUES (
                :tramite, :orden, :tipo,
                :transicion,
                :estado_orig, :estado_dest,
                CAST(:orig AS jsonb), CAST(:dest AS jsonb),
                :comentario, CAST(:meta AS jsonb),
                :agente, :ip, :ua,
                :mun,
                :uid, :uid
            )
            RETURNING id_tramite_movimiento, orden_secuencial, tipo, fecha_alta
        """),
        {
            "tramite": id_tramite,
            "orden": orden,
            "tipo": tipo,
            "transicion": id_tipo_tramite_transicion,
            "estado_orig": id_estado_origen,
            "estado_dest": id_estado_destino,
            "orig": _jsonb(origen_jsonb),
            "dest": _jsonb(destino_jsonb),
            "comentario": comentario,
            "meta": _jsonb(metadata_jsonb),
            "agente": id_agente,
            "ip": ip,
            "ua": user_agent,
            "mun": id_municipio,
            "uid": id_usuario,
        },
    )
    row = result.fetchone()
    return {
        "id_tramite_movimiento": row.id_tramite_movimiento,
        "orden_secuencial": row.orden_secuencial,
        "tipo": row.tipo,
        "fecha_alta": row.fecha_alta,
    }
