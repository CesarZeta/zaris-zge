"""
Alta de un trámite — servicio común del backoffice y del portal del vecino.

`crear_tramite_en_db` numera, inserta el trámite, registra los movimientos `creacion` y
`numeracion` e instancia las aprobaciones del estado inicial. NO commitea: el llamador
commitea y recién después dispara las notificaciones (que son del route).

Regla de César: un trámite de iniciador ciudadano exige que el vecino tenga cuenta en el
portal (`ciudadano_credencial` activa, ya activada o pendiente de activación). El chequeo
va antes de consumir el numerador: un 422 no deja huecos en la numeración ni filas.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tramites import aprobaciones as svc_aprob
from app.services.tramites import movimientos as svc_mov
from app.services.tramites import numerador as svc_num

MSJ_SIN_CUENTA = "El vecino no tiene cuenta en el portal: dale de alta la cuenta desde su ficha"


async def vecino_tiene_cuenta(db: AsyncSession, id_ciudadano: int) -> bool:
    """True si el ciudadano tiene una credencial del portal activa (activada o pendiente)."""
    fila = (await db.execute(
        text("SELECT 1 FROM ciudadano_credencial WHERE id_ciudadano = :c AND activo = TRUE LIMIT 1"),
        {"c": id_ciudadano},
    )).fetchone()
    return fila is not None


async def crear_tramite_en_db(
    db: AsyncSession,
    *,
    tipo: dict,
    datos: dict,
    asunto: str | None,
    iniciador_fks: dict,
    iniciador_tipo: str,
    id_municipio: int,
    actor_agente: dict | None,
    id_ciudadano_actor: int | None,
    id_usuario: int | None,
    destinatario: tuple[str, int],
    request: Request | None,
) -> int:
    """Crea el trámite y devuelve su id_tramite. No commitea."""
    id_version = tipo["id_version_publicada"]

    if iniciador_tipo == "ciudadano":
        id_cid = iniciador_fks.get("id_ciudadano_iniciador")
        if not id_cid or not await vecino_tiene_cuenta(db, id_cid):
            raise HTTPException(422, MSJ_SIN_CUENTA)

    estado_inicial = (await db.execute(
        text("""
            SELECT id_tipo_tramite_estado FROM tipo_tramite_estado
            WHERE id_tipo_tramite_version=:ver AND es_inicial=TRUE AND activo=TRUE
        """),
        {"ver": id_version},
    )).fetchone()
    if not estado_inicial:
        raise HTTPException(500, "El tipo de tramite no tiene estado inicial configurado")

    dest_tipo, dest_id = destinatario
    id_agente = actor_agente["id_agente"] if actor_agente else None

    # Numero correlativo atomico
    anio = datetime.now(timezone.utc).year
    correlativo = await svc_num.proximo_numero(db, tipo["id_tipo_tramite"], id_municipio, anio)
    numero_expediente = svc_num.formatear_numero(
        prefijo=tipo["prefijo"],
        separador=tipo["separador"],
        incluye_municipio=tipo["incluye_municipio"],
        incluye_anio=tipo["incluye_anio"],
        codigo_municipio=tipo.get("codigo_corto") or "",
        anio=anio,
        correlativo=correlativo,
        largo_correlativo=tipo["largo_correlativo"],
    )

    t_row = (await db.execute(
        text("""
            INSERT INTO tramite (
                numero_expediente, id_tipo_tramite_version, asunto,
                datos_jsonb, iniciador_tipo,
                id_ciudadano_iniciador, id_empresa_iniciadora,
                id_ciudadano_representante, id_subarea_iniciadora,
                id_agente_iniciador,
                id_tipo_tramite_estado_actual, fecha_entrada_estado_actual,
                destinatario_actual_tipo,
                id_subarea_actual, id_equipo_actual,
                id_municipio,
                id_usuario_alta, id_usuario_modificacion
            ) VALUES (
                :num, :ver, :asunto,
                CAST(:datos AS jsonb), :ini_tipo,
                :cid, :eid, :crep, :sub_ini,
                :ag_ini,
                :estado, NOW(),
                :dest_tipo,
                :dest_sa, :dest_eq,
                :mun,
                :uid, :uid
            )
            RETURNING id_tramite
        """),
        {
            "num": numero_expediente,
            "ver": id_version,
            "asunto": asunto,
            "datos": json.dumps(datos),
            "ini_tipo": iniciador_tipo,
            "cid": iniciador_fks.get("id_ciudadano_iniciador"),
            "eid": iniciador_fks.get("id_empresa_iniciadora"),
            "crep": iniciador_fks.get("id_ciudadano_representante"),
            "sub_ini": iniciador_fks.get("id_subarea_iniciadora"),
            "ag_ini": id_agente,
            "estado": estado_inicial.id_tipo_tramite_estado,
            "dest_tipo": dest_tipo,
            "dest_sa": dest_id if dest_tipo == "subarea" else None,
            "dest_eq": dest_id if dest_tipo == "equipo" else None,
            "mun": id_municipio,
            "uid": id_usuario,
        },
    )).fetchone()
    id_tramite = t_row.id_tramite

    await svc_mov.registrar_movimiento(
        db, id_tramite, "creacion", id_usuario, id_agente,
        id_municipio, request,
        id_estado_destino=estado_inicial.id_tipo_tramite_estado,
        destino_jsonb={"tipo": dest_tipo, "id": dest_id},
        metadata_jsonb={"datos_iniciales": datos},
        id_ciudadano_actor=id_ciudadano_actor,
    )
    await svc_mov.registrar_movimiento(
        db, id_tramite, "numeracion", id_usuario, id_agente,
        id_municipio, request,
        metadata_jsonb={"numero_expediente": numero_expediente, "correlativo": correlativo, "anio": anio},
        id_ciudadano_actor=id_ciudadano_actor,
    )

    await svc_aprob.instanciar_aprobaciones_de_estado(
        db, id_tramite, id_version, estado_inicial.id_tipo_tramite_estado,
    )
    return id_tramite
