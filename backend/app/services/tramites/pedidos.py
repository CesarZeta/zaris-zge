"""
Pedidos del municipio al vecino que inició un trámite (spec 2026-11-21 §5.6).

El pedido es una marca PARALELA al circuito: no cambia el estado del FSM ni frena las transiciones.
Hay a lo sumo UN pedido abierto por trámite (índice único parcial `uq_tramite_pedido_abierto`).

Este módulo no commitea: lo hace el llamador (como el resto de `services/tramites/`). Las dos
funciones `avisar_*` son POST-commit y best-effort (sesión propia, nunca levantan).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.urls import url_portal_vecino
from app.services.tramites import alta as svc_alta
from app.services.tramites import movimientos as svc_mov

logger = logging.getLogger("zaris.tramites.pedidos")

NO_ENCONTRADO_PEDIDO = "Pedido no encontrado"


async def crear_pedido(
    db: AsyncSession,
    tramite: dict,
    agente: dict,
    id_usuario: int,
    texto: str,
    pide_archivo: bool,
    request: Optional[Request] = None,
) -> int:
    """Valida las reglas de negocio e inserta el pedido con su movimiento `pedido_iniciador`.
    `tramite` es la fila (ya bloqueada por el llamador) con `es_final` del estado actual.
    422 si el iniciador no es un ciudadano con cuenta, si está archivado, en estado final o ya hay
    un pedido abierto. Devuelve el id del pedido."""
    if tramite.get("iniciador_tipo") != "ciudadano" or not tramite.get("id_ciudadano_iniciador"):
        raise HTTPException(422, "Solo se puede pedir algo al vecino cuando el trámite lo inició un ciudadano.")
    if not await svc_alta.vecino_tiene_cuenta(db, tramite["id_ciudadano_iniciador"]):
        raise HTTPException(422, svc_alta.MSJ_SIN_CUENTA)
    if tramite.get("fecha_archivado") is not None:
        raise HTTPException(422, "El trámite está archivado.")
    if tramite.get("es_final"):
        raise HTTPException(422, "El trámite está en un estado final.")
    abierto = (await db.execute(
        text("SELECT 1 FROM tramite_pedido_iniciador WHERE id_tramite = :t AND estado = 'abierto' AND activo = TRUE LIMIT 1"),
        {"t": tramite["id_tramite"]})).fetchone()
    if abierto:
        raise HTTPException(422, "Ya hay un pedido abierto al vecino: esperá su respuesta o cancelalo.")

    try:
        id_pedido = (await db.execute(
            text("""
                INSERT INTO tramite_pedido_iniciador
                    (id_tramite, texto, pide_archivo, id_agente_pide, id_municipio,
                     id_usuario_alta, id_usuario_modificacion)
                VALUES (:t, :texto, :pa, :ag, :mun, :uid, :uid)
                RETURNING id_tramite_pedido
            """),
            {"t": tramite["id_tramite"], "texto": texto, "pa": pide_archivo,
             "ag": agente["id_agente"], "mun": tramite["id_municipio"], "uid": id_usuario},
        )).scalar_one()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(422, "Ya hay un pedido abierto al vecino: esperá su respuesta o cancelalo.")
    await svc_mov.registrar_movimiento(
        db, tramite["id_tramite"], "pedido_iniciador", id_usuario, agente["id_agente"],
        tramite["id_municipio"], request, comentario=texto,
        metadata_jsonb={"id_tramite_pedido": id_pedido, "pide_archivo": pide_archivo},
    )
    return id_pedido


async def cancelar_pedido(
    db: AsyncSession,
    tramite: dict,
    id_pedido: int,
    agente: dict,
    id_usuario: int,
    motivo: str,
    request: Optional[Request] = None,
) -> None:
    """Cancela un pedido ABIERTO del trámite (lo toma con FOR UPDATE). 404 si no es de este trámite,
    409 si ya no está abierto."""
    ped = (await db.execute(
        text("SELECT estado FROM tramite_pedido_iniciador WHERE id_tramite_pedido = :p AND id_tramite = :t "
             "AND activo = TRUE FOR UPDATE"),
        {"p": id_pedido, "t": tramite["id_tramite"]})).mappings().first()
    if not ped:
        raise HTTPException(404, NO_ENCONTRADO_PEDIDO)
    if ped["estado"] != "abierto":
        raise HTTPException(409, "El pedido ya no está abierto.")
    await db.execute(
        text("""
            UPDATE tramite_pedido_iniciador
               SET estado = 'cancelado', motivo_cancelacion = :m, id_agente_cancela = :ag,
                   fecha_modificacion = NOW(), id_usuario_modificacion = :uid
             WHERE id_tramite_pedido = :p
        """),
        {"m": motivo, "ag": agente["id_agente"], "uid": id_usuario, "p": id_pedido})
    await svc_mov.registrar_movimiento(
        db, tramite["id_tramite"], "pedido_cancelado", id_usuario, agente["id_agente"],
        tramite["id_municipio"], request, comentario=motivo,
        metadata_jsonb={"id_tramite_pedido": id_pedido},
    )


async def cancelar_pedido_abierto_por_cierre(db: AsyncSession, id_tramite: int, motivo: str,
                                             id_municipio: int) -> bool:
    """El trámite se cierra (estado final, desistimiento, archivo por inactividad): el pedido abierto,
    si hay, queda `cancelado` con `motivo` y un movimiento `pedido_cancelado` automático (actor sistema).
    NO avisa al vecino: el aviso del cierre ya lo cubre. Va en la transacción del cierre; no commitea.
    Devuelve True si había un pedido abierto."""
    ped = (await db.execute(
        text("UPDATE tramite_pedido_iniciador SET estado = 'cancelado', motivo_cancelacion = :m, "
             "fecha_modificacion = NOW() WHERE id_tramite = :t AND estado = 'abierto' AND activo = TRUE "
             "RETURNING id_tramite_pedido"),
        {"m": motivo, "t": id_tramite})).fetchone()
    if not ped:
        return False
    await svc_mov.registrar_movimiento(
        db, id_tramite, "pedido_cancelado", None, None, id_municipio, None, comentario=motivo,
        metadata_jsonb={"id_tramite_pedido": ped[0], "automatico": True},
    )
    return True


async def marcar_visto(db: AsyncSession, id_tramite: int, id_pedido: int, id_usuario: int) -> None:
    """Marca la respuesta como vista (solo la primera vez). 404 si el pedido no es del trámite."""
    existe = (await db.execute(
        text("SELECT 1 FROM tramite_pedido_iniciador WHERE id_tramite_pedido = :p AND id_tramite = :t AND activo = TRUE"),
        {"p": id_pedido, "t": id_tramite})).fetchone()
    if not existe:
        raise HTTPException(404, NO_ENCONTRADO_PEDIDO)
    await db.execute(
        text("""
            UPDATE tramite_pedido_iniciador
               SET respuesta_vista_en = NOW(), fecha_modificacion = NOW(), id_usuario_modificacion = :uid
             WHERE id_tramite_pedido = :p AND estado = 'respondido' AND respuesta_vista_en IS NULL
        """),
        {"p": id_pedido, "uid": id_usuario})


async def tomar_abierto_para_responder(db: AsyncSession, id_tramite: int, id_pedido: int) -> dict:
    """Toma el pedido con FOR UPDATE y exige `estado='abierto'`: de dos respuestas simultáneas,
    la segunda espera el commit de la primera, ve `respondido` y recibe 409. 404 si no es del trámite."""
    ped = (await db.execute(
        text("SELECT id_tramite_pedido, texto, pide_archivo, estado, id_municipio FROM tramite_pedido_iniciador "
             "WHERE id_tramite_pedido = :p AND id_tramite = :t AND activo = TRUE FOR UPDATE"),
        {"p": id_pedido, "t": id_tramite})).mappings().first()
    if not ped:
        raise HTTPException(404, NO_ENCONTRADO_PEDIDO)
    if ped["estado"] != "abierto":
        raise HTTPException(409, "Este pedido ya no está abierto.")
    return dict(ped)


async def listar_pedidos(db: AsyncSession, id_tramite: int) -> list[dict]:
    """Pedidos del trámite (el más nuevo primero) con la respuesta y sus documentos, para el
    backoffice. Lleva el nombre del agente: NO usar en el portal del vecino."""
    filas = (await db.execute(
        text("""
            SELECT p.id_tramite_pedido, p.texto, p.pide_archivo, p.estado, p.fecha_pedido,
                   TRIM(COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, ''), ', ') AS agente_pide,
                   p.respuesta_texto, p.fecha_respuesta, p.respuesta_vista_en, p.motivo_cancelacion
              FROM tramite_pedido_iniciador p
              LEFT JOIN agentes a ON a.id_agente = p.id_agente_pide
             WHERE p.id_tramite = :t AND p.activo = TRUE
             ORDER BY p.fecha_pedido DESC, p.id_tramite_pedido DESC
        """),
        {"t": id_tramite})).mappings().all()
    docs = (await db.execute(
        text("""
            SELECT id_tramite_pedido, id_tramite_documento, nombre, nombre_archivo_original, fecha_alta, binario_purgado
              FROM tramite_documento
             WHERE id_tramite = :t AND id_tramite_pedido IS NOT NULL AND activo = TRUE
             ORDER BY posicion_orden, id_tramite_documento
        """),
        {"t": id_tramite})).mappings().all()
    por_pedido: dict[int, list[dict]] = {}
    for d in docs:
        por_pedido.setdefault(d["id_tramite_pedido"], []).append(
            {k: d[k] for k in ("id_tramite_documento", "nombre", "nombre_archivo_original", "fecha_alta", "binario_purgado")})
    return [{**dict(f), "documentos_respuesta": por_pedido.get(f["id_tramite_pedido"], [])} for f in filas]


# ---------------------------------------------------------------------------
# Avisos al vecino (post-commit, best-effort)
# ---------------------------------------------------------------------------

async def _avisar(id_tramite: int, titulo_fn) -> None:
    from app.services.tramites import ciclo_vida as svc_ciclo  # import tardio: ciclo_vida/retencion importan este modulo
    try:
        async with AsyncSessionLocal() as db:
            d = await svc_ciclo._datos_para_vecino(db, id_tramite)
            if not d or d.get("iniciador_tipo") != "ciudadano":
                return
            url = await url_portal_vecino(db, d["id_municipio"])
        titulo, cuerpo = titulo_fn(d)
        await svc_ciclo._avisar_vecino(d, "tramite_pedido", titulo, cuerpo, con_email=True, url_portal=url)
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.warning("pedidos: aviso al vecino (tramite=%s) fallo: %s", id_tramite, e)


async def avisar_pedido_nuevo(id_tramite: int, texto: str) -> None:
    def _t(d: dict) -> tuple[str, str]:
        n, tipo = d["numero_expediente"], d.get("tipo_nombre") or "Trámite"
        return (f"Tenés un pedido en tu trámite {n}",
                f"{tipo}: el municipio te pidió lo siguiente: {texto}. "
                "Respondelo desde el Portal del Ciudadano.")
    await _avisar(id_tramite, _t)


async def avisar_pedido_cancelado(id_tramite: int) -> None:
    def _t(d: dict) -> tuple[str, str]:
        n, tipo = d["numero_expediente"], d.get("tipo_nombre") or "Trámite"
        return (f"El pedido de tu trámite {n} se canceló",
                f"{tipo}: el municipio canceló el pedido que te había hecho. Ya no tenés que responderlo.")
    await _avisar(id_tramite, _t)
