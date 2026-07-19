"""Aprobaciones por etapa (visados) de trámites.

Marca paralela a los estados FSM que indica que un área aprobó/rechazó una
etapa. Bloquea el avance si hay marcas bloqueantes sin aprobar.

Patrón catálogo+instancia (§35):
- tipo_tramite_aprobacion_requerida: catálogo versionado (qué aprobaciones
  exige cada estado de cada versión del circuito).
- tramite_aprobacion: instancia (la marca real, pendiente/aprobada/rechazada).
"""
from __future__ import annotations

from typing import Mapping, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def instanciar_aprobaciones_de_estado(
    db: AsyncSession, id_tramite: int, id_version: int, id_estado: Optional[int]
) -> int:
    """Crea como 'pendiente' las aprobaciones requeridas del estado dado.

    Idempotente: el UNIQUE (id_tramite, id_tipo_tramite_aprobacion_requerida)
    + ON CONFLICT DO NOTHING evita duplicar al re-entrar a una etapa. Devuelve
    cuántas filas nuevas se crearon. No commitea (lo hace el caller).
    """
    if id_estado is None:
        return 0
    res = await db.execute(
        text("""
            INSERT INTO tramite_aprobacion
                (id_tramite, id_tipo_tramite_aprobacion_requerida, id_tipo_tramite_estado,
                 estado, id_municipio, fecha_alta, fecha_modificacion)
            SELECT :t, ttar.id_tipo_tramite_aprobacion_requerida, ttar.id_tipo_tramite_estado,
                   'pendiente', 1, NOW(), NOW()
            FROM tipo_tramite_aprobacion_requerida ttar
            WHERE ttar.id_tipo_tramite_version = :v
              AND ttar.id_tipo_tramite_estado = :e
              AND ttar.activo = TRUE
            ON CONFLICT (id_tramite, id_tipo_tramite_aprobacion_requerida) DO NOTHING
            RETURNING id_tramite_aprobacion
        """),
        {"t": id_tramite, "v": id_version, "e": id_estado},
    )
    return len(res.fetchall())


async def rependientizar_rechazadas_de_estado(
    db: AsyncSession, id_tramite: int, id_estado: Optional[int]
) -> list[Mapping]:
    """Vuelve a 'pendiente' los visados RECHAZADOS de un estado al re-entrar a él.

    Cuando un trámite vuelve a la etapa del visado (típicamente tras una
    subsanación: el visado se rechazó, el trámite fue a 'subsanacion' y luego
    se reenvió a la etapa de revisión), las marcas que habían quedado
    'rechazada' deben re-evaluarse desde cero. Se limpia la resolución anterior
    (comentario/documento/quién/cuándo) para que el área vise de nuevo el
    material corregido. Las 'aprobada' NO se tocan (ya estaban OK).

    Devuelve las marcas reseteadas (para registrar movimiento/notificar).
    No commitea (lo hace el caller).
    """
    if id_estado is None:
        return []
    res = await db.execute(
        text("""
            UPDATE tramite_aprobacion ta SET
                estado = 'pendiente',
                comentario = NULL,
                id_tramite_documento = NULL,
                resuelto_por_agente = NULL,
                resuelto_en = NULL,
                fecha_modificacion = NOW()
            FROM tipo_tramite_aprobacion_requerida ttar
            WHERE ta.id_tipo_tramite_aprobacion_requerida = ttar.id_tipo_tramite_aprobacion_requerida
              AND ta.id_tramite = :t
              AND ta.id_tipo_tramite_estado = :e
              AND ta.activo = TRUE
              AND ta.estado = 'rechazada'
            RETURNING ta.id_tramite_aprobacion, ttar.etiqueta
        """),
        {"t": id_tramite, "e": id_estado},
    )
    return res.mappings().all()


async def aprobaciones_bloqueantes_pendientes(
    db: AsyncSession, id_tramite: int, id_estado: Optional[int]
) -> list[Mapping]:
    """Devuelve las marcas BLOQUEANTES del estado actual que no están 'aprobada'.

    Si la lista no está vacía, el trámite no puede avanzar de la etapa.
    """
    if id_estado is None:
        return []
    res = await db.execute(
        text("""
            SELECT ta.id_tramite_aprobacion, ta.estado, ttar.etiqueta
            FROM tramite_aprobacion ta
            JOIN tipo_tramite_aprobacion_requerida ttar
              ON ttar.id_tipo_tramite_aprobacion_requerida = ta.id_tipo_tramite_aprobacion_requerida
            WHERE ta.id_tramite = :t
              AND ta.id_tipo_tramite_estado = :e
              AND ta.activo = TRUE
              AND ttar.bloqueante = TRUE
              AND ta.estado <> 'aprobada'
            ORDER BY ttar.orden, ta.id_tramite_aprobacion
        """),
        {"t": id_tramite, "e": id_estado},
    )
    return res.mappings().all()


def agente_puede_resolver(requisito: Mapping, info: dict) -> bool:
    """¿El agente logueado pertenece al área aprobadora de la marca?

    Polimórfico (subarea/equipo/agente). Admin (nivel 1) siempre puede; el
    supervisor (nivel 2) resuelve SOLO por membresía del aprobador desde el
    cierre del residuo de la auditoría 2026-07 (antes bypasseaba con <= 2).
    El aprobador NO necesita operar/tomar el trámite (tercero no-destinatario).
    """
    if (info.get("nivel_acceso") or 99) <= 1:
        return True
    tipo = requisito.get("aprobador_tipo")
    if tipo == "subarea":
        return info.get("id_subarea") is not None and info["id_subarea"] == requisito.get("id_subarea_aprobadora")
    if tipo == "equipo":
        return requisito.get("id_equipo_aprobador") in (info.get("ids_equipos") or [])
    if tipo == "agente":
        return info.get("id_agente") is not None and info["id_agente"] == requisito.get("id_agente_aprobador")
    return False


async def aprobaciones_de_tramite(db: AsyncSession, id_tramite: int) -> list[dict]:
    """Todas las marcas del trámite con datos del requisito + nombre del área aprobadora.

    Para el panel del detalle. No filtra por estado del FSM (muestra el historial
    de visados de todas las etapas instanciadas).
    """
    res = await db.execute(
        text("""
            SELECT
                ta.id_tramite_aprobacion,
                ta.estado,
                ta.comentario,
                ta.resuelto_en,
                ta.id_tipo_tramite_estado,
                ta.id_tramite_documento,
                ttar.id_tipo_tramite_aprobacion_requerida,
                ttar.etiqueta,
                ttar.bloqueante,
                ttar.aprobador_tipo,
                ttar.id_subarea_aprobadora,
                ttar.id_equipo_aprobador,
                ttar.id_agente_aprobador,
                ttar.orden,
                tte.codigo   AS estado_codigo,
                tte.etiqueta AS estado_etiqueta,
                s.nombre     AS subarea_nombre,
                eq.nombre    AS equipo_nombre,
                (ag.nombre || ' ' || ag.apellido) AS agente_nombre,
                (ra.nombre || ' ' || ra.apellido) AS resuelto_por_nombre
            FROM tramite_aprobacion ta
            JOIN tipo_tramite_aprobacion_requerida ttar
              ON ttar.id_tipo_tramite_aprobacion_requerida = ta.id_tipo_tramite_aprobacion_requerida
            JOIN tipo_tramite_estado tte
              ON tte.id_tipo_tramite_estado = ta.id_tipo_tramite_estado
            LEFT JOIN subarea s  ON s.id_subarea = ttar.id_subarea_aprobadora
            LEFT JOIN equipos eq ON eq.id_equipo  = ttar.id_equipo_aprobador
            LEFT JOIN agentes ag ON ag.id_agente  = ttar.id_agente_aprobador
            LEFT JOIN agentes ra ON ra.id_agente  = ta.resuelto_por_agente
            WHERE ta.id_tramite = :t AND ta.activo = TRUE
            ORDER BY ta.id_tipo_tramite_estado, ttar.orden, ta.id_tramite_aprobacion
        """),
        {"t": id_tramite},
    )
    out: list[dict] = []
    for r in res.mappings().all():
        if r["aprobador_tipo"] == "subarea":
            aprobador_nombre = r["subarea_nombre"]
        elif r["aprobador_tipo"] == "equipo":
            aprobador_nombre = r["equipo_nombre"]
        else:
            aprobador_nombre = r["agente_nombre"]
        out.append({
            "id_tramite_aprobacion": r["id_tramite_aprobacion"],
            "id_tipo_tramite_aprobacion_requerida": r["id_tipo_tramite_aprobacion_requerida"],
            "etiqueta": r["etiqueta"],
            "estado": r["estado"],
            "bloqueante": r["bloqueante"],
            "comentario": r["comentario"],
            "resuelto_en": r["resuelto_en"],
            "resuelto_por_nombre": r["resuelto_por_nombre"],
            "id_tipo_tramite_estado": r["id_tipo_tramite_estado"],
            "estado_codigo": r["estado_codigo"],
            "estado_etiqueta": r["estado_etiqueta"],
            "aprobador_tipo": r["aprobador_tipo"],
            "aprobador_nombre": aprobador_nombre,
            "id_tramite_documento": r["id_tramite_documento"],
        })
    return out


async def requisito_de_aprobacion(db: AsyncSession, id_tramite_aprobacion: int) -> Optional[Mapping]:
    """Trae la marca + su requisito (para validar permiso y pertenencia al trámite)."""
    res = await db.execute(
        text("""
            SELECT
                ta.id_tramite_aprobacion, ta.id_tramite, ta.estado AS estado_marca,
                ttar.aprobador_tipo, ttar.id_subarea_aprobadora,
                ttar.id_equipo_aprobador, ttar.id_agente_aprobador, ttar.etiqueta
            FROM tramite_aprobacion ta
            JOIN tipo_tramite_aprobacion_requerida ttar
              ON ttar.id_tipo_tramite_aprobacion_requerida = ta.id_tipo_tramite_aprobacion_requerida
            WHERE ta.id_tramite_aprobacion = :id AND ta.activo = TRUE
        """),
        {"id": id_tramite_aprobacion},
    )
    return res.mappings().first()
