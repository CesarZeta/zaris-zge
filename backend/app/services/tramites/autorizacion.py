"""
Logica de autorizacion de transiciones para el modulo Tramites.

Interpreta quien_puede_jsonb y devuelve si el agente puede ejecutar
cada transicion desde el estado actual del tramite.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tramites.auth import (
    es_admin,
    agente_puede_operar,
    agente_pertenece_al_colectivo,
)


async def agente_puede_ejecutar_transicion(
    agente_info: dict,
    transicion: dict,
    tramite: dict,
) -> tuple[bool, str | None]:
    """
    Valida quien_puede_jsonb contra el agente.

    Estructura de quien_puede_jsonb:
      {} -> cualquier agente que pueda operar el tramite
      {"subareas": [3,5]} -> agente debe pertenecer a una de esas subareas
      {"equipos": [2]} -> agente debe pertenecer a uno de esos equipos
      {"iniciador": true} -> solo el id_agente_iniciador del tramite
      {"roles": ["supervisor"]} -> nivel_acceso <= 2

    Combinaciones se interpretan como OR.
    Admin siempre puede.
    """
    puede_op, motivo_op = await agente_puede_operar(agente_info, tramite)
    if not puede_op:
        return False, motivo_op

    if es_admin(agente_info["nivel_acceso"]):
        return True, None

    quien = transicion.get("quien_puede_jsonb") or {}

    # Vacío = cualquier operador puede
    if not quien:
        return True, None

    checks: list[tuple[bool, str]] = []

    if "subareas" in quien:
        subareas = quien["subareas"]
        ok = agente_info["id_subarea"] in subareas
        checks.append((ok, f"Tu subarea no esta en la lista permitida {subareas}"))

    if "equipos" in quien:
        equipos = quien["equipos"]
        ok = any(eq in agente_info["ids_equipos"] for eq in equipos)
        checks.append((ok, f"No perteneces a los equipos requeridos {equipos}"))

    if quien.get("iniciador"):
        ok = agente_info["id_agente"] == tramite.get("id_agente_iniciador")
        checks.append((ok, "Solo el agente que inicio el tramite puede ejecutar esta accion"))

    if "roles" in quien:
        roles = quien["roles"]
        ok = "supervisor" in roles and es_admin(agente_info["nivel_acceso"])
        checks.append((ok, "Solo supervisores pueden ejecutar esta accion"))

    if not checks:
        return True, None

    # OR entre todos los checks
    for ok, msg in checks:
        if ok:
            return True, None

    return False, checks[0][1]


async def listar_transiciones_permitidas(
    tramite: dict,
    agente_info: dict | None,
    db: AsyncSession,
) -> list[dict]:
    """
    Devuelve la lista de transiciones desde el estado actual del tramite,
    cada una con flags disponible y motivo_no_disponible.
    """
    rows = (await db.execute(
        text("""
            SELECT
                t.id_tipo_tramite_transicion,
                t.etiqueta_accion,
                t.id_estado_destino,
                ed.etiqueta AS etiqueta_destino,
                t.requiere_comentario,
                t.requiere_adjunto,
                t.quien_puede_jsonb,
                t.notifica_iniciador,
                t.destino_automatico_jsonb,
                t.orden
            FROM tipo_tramite_transicion t
            JOIN tipo_tramite_estado ed ON ed.id_tipo_tramite_estado = t.id_estado_destino
            WHERE t.id_tipo_tramite_version = :ver
              AND t.id_estado_origen = :estado
              AND t.activo = TRUE
            ORDER BY t.orden
        """),
        {
            "ver": tramite["id_tipo_tramite_version"],
            "estado": tramite["id_tipo_tramite_estado_actual"],
        },
    )).fetchall()

    resultado = []
    for r in rows:
        trans = {
            "id_tipo_tramite_transicion": r.id_tipo_tramite_transicion,
            "quien_puede_jsonb": r.quien_puede_jsonb,
        }
        if agente_info is None:
            disponible = False
            motivo = "Sin agente asociado al usuario"
        else:
            disponible, motivo = await agente_puede_ejecutar_transicion(
                agente_info, trans, tramite
            )

        resultado.append({
            "id_tipo_tramite_transicion": r.id_tipo_tramite_transicion,
            "etiqueta_accion": r.etiqueta_accion,
            "id_estado_destino": r.id_estado_destino,
            "etiqueta_destino": r.etiqueta_destino,
            "requiere_comentario": r.requiere_comentario,
            "requiere_adjunto": r.requiere_adjunto,
            "quien_puede_jsonb": r.quien_puede_jsonb,
            "notifica_iniciador": r.notifica_iniciador,
            "destino_automatico_jsonb": r.destino_automatico_jsonb,
            "disponible": disponible,
            "motivo_no_disponible": motivo,
        })

    return resultado
