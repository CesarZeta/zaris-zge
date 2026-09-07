"""
Guardia de emergencias (proyecto ATENCION F4, mig 106).

Helpers compartidos por dos routers:
  - emergencias.py: POST /eventos/{id}/derivar-guardia (el COM deriva).
  - turnos.py: GET/PATCH /turnos/guardia/atenciones (la Guardia atiende).

La Guardia es una UBICACION (espacios_agenda) senalada por la clave
`configuracion_general.id_espacio_guardia` (seed 106b). Sin la clave, derivar
devuelve 422: la Guardia no se adivina.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CLAVE_GUARDIA = "id_espacio_guardia"


async def espacio_guardia(db: AsyncSession) -> Optional[dict[str, Any]]:
    """Devuelve la ubicacion Guardia activa (id, nombre, id_subarea, prefijo)
    o None si la clave no esta cargada / apunta a un espacio inactivo."""
    row = (await db.execute(text("""
        SELECT e.id_espacio, e.nombre, e.id_subarea, e.direccion,
               token_pantalla::text AS token_pantalla
          FROM configuracion_general cg
          JOIN espacios_agenda e ON e.id_espacio = NULLIF(TRIM(cg.valor), '')::int
         WHERE cg.clave = :k AND cg.activo = TRUE AND e.activo = TRUE
         LIMIT 1
    """), {"k": CLAVE_GUARDIA})).mappings().first()
    return dict(row) if row else None


async def id_espacio_guardia(db: AsyncSession) -> Optional[int]:
    g = await espacio_guardia(db)
    return int(g["id_espacio"]) if g else None


async def registrar_log_evento(
    db: AsyncSession,
    id_evento: int,
    id_usuario: Optional[int],
    tipo_accion: str,
    estado: Optional[str] = None,
    payload: Optional[dict] = None,
    observaciones: Optional[str] = None,
    id_municipio: Optional[int] = None,
) -> None:
    """Fila en `emergencia_log` (append-only, mismo SQL que emergencias.py::
    _registrar_log — se duplica aca para que turnos.py no importe un router).
    Las acciones de Guardia NO cambian el estado del evento: estado_anterior =
    estado_nuevo = el actual, para que el historial muestre en que momento del
    ciclo paso."""
    await db.execute(text("""
        INSERT INTO emergencia_log
            (id_evento, id_usuario, tipo_accion, estado_anterior, estado_nuevo,
             payload_json, observaciones, id_municipio)
        VALUES (:e, :u, :t, :ea, :en, CAST(:p AS jsonb), :o, :m)
    """), {
        "e": id_evento, "u": id_usuario, "t": tipo_accion,
        "ea": estado, "en": estado,
        "p": json.dumps(payload) if payload is not None else None,
        "o": observaciones, "m": id_municipio,
    })


# SELECT unico de la atencion (todos los endpoints salen de aca — regla
# "columna nueva => auditar todos los SELECT").
SELECT_ATENCION = """
    SELECT ea.id_emergencia_atencion, ea.id_emergencia_evento, ea.id_espacio_ubicacion,
           ev.numero_operativo, ev.direccion_evento,
           t.nombre AS tipo_nombre, st.nombre AS subtipo_nombre,
           p.codigo AS prioridad_codigo, p.color_token AS prioridad_color_token,
           est.codigo AS estado_evento,
           ea.id_ciudadano,
           CASE WHEN ea.id_ciudadano IS NOT NULL
                THEN COALESCE(c.apellido, '') || ', ' || COALESCE(c.nombre, '')
                ELSE ea.paciente_nombre END AS paciente_nombre,
           c.doc_nro AS ciudadano_dni,
           ea.motivo_derivacion, ea.estado, ea.derivado_en,
           ud.nombre AS derivado_por,
           ea.id_agente_atiende,
           CASE WHEN ea.id_agente_atiende IS NOT NULL
                THEN COALESCE(ag.apellido, '') || ', ' || COALESCE(ag.nombre, '') END AS agente_atiende_nombre,
           ea.intervencion, ea.recomendaciones, ea.atendido_en, ea.fecha_modificacion
      FROM emergencia_atencion ea
      JOIN emergencia_evento ev ON ev.id_emergencia_evento = ea.id_emergencia_evento
      JOIN emergencia_tipo t ON t.id_emergencia_tipo = ev.id_tipo
      LEFT JOIN emergencia_subtipo st ON st.id_emergencia_subtipo = ev.id_subtipo
      JOIN emergencia_prioridad p ON p.id_emergencia_prioridad = ev.id_prioridad
      JOIN emergencia_estado est ON est.id_emergencia_estado = ev.id_estado
      LEFT JOIN ciudadanos c ON c.id_ciudadano = ea.id_ciudadano
      LEFT JOIN usuarios ud ON ud.id_usuario = ea.id_usuario_deriva
      LEFT JOIN agentes ag ON ag.id_agente = ea.id_agente_atiende
"""


async def atencion_out(db: AsyncSession, id_atencion: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text(
        SELECT_ATENCION + " WHERE ea.id_emergencia_atencion = :id AND ea.activo = TRUE"
    ), {"id": id_atencion})).mappings().first()
    return dict(row) if row else None
