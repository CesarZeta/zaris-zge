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
    """Nivel 1 = Administrador (§3). Hasta 2026-07-19 devolvia nivel <= 2 (el
    Supervisor bypasseaba operar y quien_puede_jsonb en todo el modulo); el
    cierre del residuo de la auditoria 2026-07 lo bajo a nivel 1 — el
    supervisor ahora opera solo dentro de su colectivo (agente_puede_operar).
    Fail-closed ante nivel NULL."""
    return (nivel_acceso or 99) <= 1


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


def _destinatario_actual(tramite: dict) -> tuple[str | None, int | None]:
    """Resuelve (tipo, id) del destinatario actual del tramite, o (None, None)."""
    dest_tipo = tramite.get("destinatario_actual_tipo")
    if not dest_tipo:
        return None, None
    dest_id = {
        "subarea": tramite.get("id_subarea_actual"),
        "equipo": tramite.get("id_equipo_actual"),
        "agente": tramite.get("id_agente_actual"),
    }.get(dest_tipo)
    return dest_tipo, dest_id


async def pertenece_al_colectivo_actual(
    agente_info: dict,
    tramite: dict,
    db: AsyncSession,
) -> bool:
    """FUENTE UNICA de "¿el agente pertenece al colectivo destinatario actual?".

    La usan tomar/operar (aca) y los guards de liberar/resultado/comentar en
    routes/tramites.py — no duplicar la resolucion: las copias divergen en
    silencio. Reglas:
    - subarea: la subarea del agente coincide
    - equipo: el agente integra el equipo
    - agente (bandeja personal): identidad; ademas el supervisor (nivel 2)
      califica si el agente destinatario pertenece a SU subarea (rescate de
      bandejas personales — sin esto un tramite destinado a un agente de
      licencia queda destrabable solo por nivel 1).
    """
    dest_tipo, dest_id = _destinatario_actual(tramite)
    if dest_tipo is None or dest_id is None:
        return False
    if await agente_pertenece_al_colectivo(agente_info, dest_tipo, dest_id):
        return True
    if dest_tipo == "agente" and (agente_info.get("nivel_acceso") or 99) == 2:
        sub_dest = (await db.execute(
            text("SELECT id_subarea FROM agentes WHERE id_agente = :ag AND activo = TRUE"),
            {"ag": dest_id},
        )).scalar()
        return sub_dest is not None and sub_dest == agente_info.get("id_subarea")
    return False


async def agente_puede_tomar(
    agente_info: dict,
    tramite: dict,
    db: AsyncSession,
) -> tuple[bool, str | None]:
    """
    Reglas (scope-subarea 2026-07-18):
    - Nivel 1 (admin): bypass total.
    - Nivel 2 (supervisor): puede desplazar una toma ajena y tomar sin ser el
      destinatario directo, pero SOLO si pertenece al colectivo destinatario
      actual (incluye bandeja personal de un agente de su subarea, ver
      pertenece_al_colectivo_actual).
    - Nivel 3+: tramite tomado por OTRO agente -> no; debe pertenecer al
      colectivo destinatario actual.
    - Sin destinatario actual -> no se puede tomar.
    """
    nivel = agente_info["nivel_acceso"]
    if nivel <= 1:
        return True, None

    tomado_por = tramite.get("id_agente_tomado_por")
    # El supervisor (nivel 2) conserva la capacidad de desplazar una toma
    # ajena; los niveles 3+ no pueden tomar un tramite tomado por otro.
    if nivel >= 3 and tomado_por and tomado_por != agente_info["id_agente"]:
        return False, "El tramite ya fue tomado por otro agente"

    dest_tipo, dest_id = _destinatario_actual(tramite)
    if dest_tipo is None or dest_id is None:
        return False, "El tramite no tiene destinatario asignado"

    if not await pertenece_al_colectivo_actual(agente_info, tramite, db):
        if nivel == 2:
            return False, "El trámite está destinado a otra área. Solo podés gestionarlo si pertenece a tu subárea o equipos."
        return False, "No perteneces al colectivo destinatario del tramite"

    return True, None


async def agente_puede_operar(
    agente_info: dict,
    tramite: dict,
    db: AsyncSession,
) -> tuple[bool, str | None]:
    """
    Operar = ejecutar transiciones, pasar, adjuntar documentos, relacionar.
    (Firmar tiene politica propia en firmas.py y liberar guard propio en routes.)
    - Tramite tomado por el agente -> si
    - Nivel 1 (admin) -> si (bypass total)
    - Nivel 2 (supervisor) -> solo si pertenece al colectivo destinatario
      actual (puede operar sin toma o sobre toma ajena, igual que en
      tomar/liberar). Cierre del residuo de la auditoria 2026-07: antes
      bypasseaba todo con nivel <= 2.
    - Nivel 3+: tomado por otro -> no; no tomado -> no (tomar primero)
    """
    tomado_por = tramite.get("id_agente_tomado_por")

    if tomado_por == agente_info["id_agente"]:
        return True, None

    if es_admin(agente_info["nivel_acceso"]):
        return True, None

    if (agente_info.get("nivel_acceso") or 99) == 2:
        if await pertenece_al_colectivo_actual(agente_info, tramite, db):
            return True, None
        return False, "El trámite está destinado a otra área. Solo podés gestionarlo si pertenece a tu subárea o equipos."

    if tomado_por is None:
        return False, "Debes tomar el tramite antes de operarlo"

    return False, "El tramite esta tomado por otro agente"
