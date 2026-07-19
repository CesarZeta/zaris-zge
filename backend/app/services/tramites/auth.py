"""
Helpers de autenticacion e identidad para el modulo Tramites.

Resolucion: id_usuario (JWT) -> agente + subarea + equipos.
Validaciones de toma y operacion.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def resolver_agente_desde_usuario(
    id_usuario: int,
    db: AsyncSession,
) -> dict | None:
    """
    Devuelve {id_agente, id_subarea, ids_equipos: list[int], id_municipio, nivel_acceso}
    o None si el usuario no tiene agente asociado.
    """
    row = (await db.execute(
        text("""
            SELECT a.id_agente, a.id_subarea, a.id_municipio,
                   u.nivel_acceso
            FROM agentes a
            JOIN usuarios u ON u.id_usuario = :uid
            WHERE a.id_usuario = :uid AND a.activo = TRUE
        """),
        {"uid": id_usuario},
    )).fetchone()

    if not row:
        return None

    equipos_rows = (await db.execute(
        text("SELECT id_equipo FROM equipo_agentes WHERE id_agente = :ag"),
        {"ag": row.id_agente},
    )).fetchall()

    return {
        "id_agente": row.id_agente,
        "id_subarea": row.id_subarea,
        "id_municipio": row.id_municipio,
        "nivel_acceso": row.nivel_acceso,
        "ids_equipos": [r.id_equipo for r in equipos_rows],
    }


def es_admin(nivel_acceso: int) -> bool:
    return nivel_acceso <= 2


async def agente_pertenece_al_colectivo(
    agente_info: dict,
    destinatario_tipo: str,
    destinatario_id: int,
) -> bool:
    """True si el agente es el destinatario directo (agente) o pertenece a la
    subarea/equipo destinatario."""
    if destinatario_tipo == "agente":
        return agente_info["id_agente"] == destinatario_id
    if destinatario_tipo == "subarea":
        return agente_info["id_subarea"] == destinatario_id
    if destinatario_tipo == "equipo":
        return destinatario_id in agente_info["ids_equipos"]
    return False


async def agente_puede_tomar(
    agente_info: dict,
    tramite: dict,
) -> tuple[bool, str | None]:
    """
    Reglas (scope-subarea 2026-07-18):
    - Nivel 1 (admin): bypass total.
    - Nivel 2 (supervisor): puede desplazar una toma ajena y tomar sin ser el
      destinatario directo, pero SOLO si pertenece al colectivo destinatario
      actual (antes bypasseaba todo, incluido tomar cross-subarea).
    - Nivel 3+: tramite tomado por OTRO agente -> no; debe pertenecer al
      colectivo destinatario actual.
    - Sin destinatario actual -> no se puede tomar.
    """
    # Scope-subarea 2026-07-18: el bypass total queda solo para nivel 1.
    nivel = agente_info["nivel_acceso"]
    if nivel <= 1:
        return True, None

    tomado_por = tramite.get("id_agente_tomado_por")
    # El supervisor (nivel 2) conserva la capacidad de desplazar una toma
    # ajena; los niveles 3+ no pueden tomar un tramite tomado por otro.
    if nivel >= 3 and tomado_por and tomado_por != agente_info["id_agente"]:
        return False, "El tramite ya fue tomado por otro agente"

    dest_tipo = tramite.get("destinatario_actual_tipo")

    if not dest_tipo:
        return False, "El tramite no tiene destinatario asignado"

    dest_id = {
        "subarea": tramite.get("id_subarea_actual"),
        "equipo": tramite.get("id_equipo_actual"),
        "agente": tramite.get("id_agente_actual"),
    }.get(dest_tipo)
    if dest_id is None:
        return False, "El tramite no tiene destinatario asignado"

    if not await agente_pertenece_al_colectivo(agente_info, dest_tipo, dest_id):
        # Scope-subarea 2026-07-18: el nivel 2 ya no bypassea el scope — solo
        # puede tomar tramites destinados a su propio colectivo.
        if nivel == 2:
            return False, "El trámite está destinado a otra área. Solo podés gestionarlo si pertenece a tu subárea o equipos."
        return False, "No perteneces al colectivo destinatario del tramite"

    return True, None


async def agente_puede_operar(
    agente_info: dict,
    tramite: dict,
) -> tuple[bool, str | None]:
    """
    Operar = ejecutar transiciones, pasar, adjuntar, firmar, liberar.
    - Trámite tomado por el agente -> si
    - Trámite tomado por otro -> solo admin
    - Trámite no tomado -> no (tomar primero)
    """
    tomado_por = tramite.get("id_agente_tomado_por")

    if tomado_por == agente_info["id_agente"]:
        return True, None

    if es_admin(agente_info["nivel_acceso"]):
        return True, None

    if tomado_por is None:
        return False, "Debes tomar el tramite antes de operarlo"

    return False, "El tramite esta tomado por otro agente"
