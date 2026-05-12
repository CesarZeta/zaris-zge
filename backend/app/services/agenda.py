"""
Logica de negocio del modulo Agenda (sub-fase 1.A).

Funciones puras o que operan sobre AsyncSession - sin imports del router.

NO usar acentos en codigo Python ni en strings.
"""
from __future__ import annotations

import json
import time
from datetime import date, time as dtime
from typing import Any, Iterable, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Conflictos
# =============================================================================
async def detectar_conflictos(
    session: AsyncSession,
    tipo_recurso: str,
    id_recurso: int,
    fecha: date,
    hora_inicio: dtime,
    hora_fin: dtime,
    id_ocupacion_excluir: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Devuelve ocupaciones activas del recurso en la fecha que se solapan
    con el rango (hora_inicio, hora_fin). Solape estricto: no toca borde.

    Si id_ocupacion_excluir != None (caso UPDATE), excluye esa fila para que
    una ocupacion no se autoconflicte cuando se edita.
    """
    base = """
        SELECT id_ocupacion, tipo, fecha, hora_inicio, hora_fin,
               id_orden_trabajo, id_evento, id_ciudadano, motivo
        FROM ocupaciones
        WHERE activo = TRUE
          AND tipo_recurso = :tr
          AND id_recurso   = :ir
          AND fecha        = :f
          AND NOT (hora_fin <= :hi OR hora_inicio >= :hf)
    """
    params: dict[str, Any] = {"tr": tipo_recurso, "ir": id_recurso, "f": fecha, "hi": hora_inicio, "hf": hora_fin}
    if id_ocupacion_excluir is not None:
        base += " AND id_ocupacion <> :excl"
        params["excl"] = id_ocupacion_excluir
    rows = (await session.execute(text(base), params)).mappings().all()
    return [dict(r) for r in rows]


async def registrar_conflictos(
    session: AsyncSession,
    id_ocupacion_origen: int,
    tipo_recurso: str,
    id_recurso: int,
    lista_conflictos: list[dict[str, Any]],
    id_municipio: int,
    id_usuario_alta: Optional[int] = None,
) -> int:
    """Inserta N filas en conflictos_log (una por cada solape) y devuelve N."""
    if not lista_conflictos:
        return 0
    sql = text("""
        INSERT INTO conflictos_log (
            tipo_recurso, id_recurso,
            id_ocupacion_origen, id_ocupacion_conflicto,
            resuelto, observaciones,
            id_municipio, id_usuario_alta
        ) VALUES (
            :tr, :ir, :origen, :conflicto, FALSE, :obs, :mun, :uid
        )
    """)
    for c in lista_conflictos:
        await session.execute(sql, {
            "tr": tipo_recurso,
            "ir": id_recurso,
            "origen": id_ocupacion_origen,
            "conflicto": c["id_ocupacion"],
            "obs": f"Solape detectado al insertar/actualizar ocupacion {id_ocupacion_origen}.",
            "mun": id_municipio,
            "uid": id_usuario_alta,
        })
    return len(lista_conflictos)


# =============================================================================
# Cupos / reservas
# =============================================================================
async def cupo_disponible(session: AsyncSession, id_evento: int) -> int:
    """capacidad_ciudadanos - reservas activas NO canceladas. Nunca negativo."""
    row = (await session.execute(text("""
        SELECT e.capacidad_ciudadanos
             - COALESCE((
                 SELECT COUNT(*) FROM evento_reservas r
                 JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
                 WHERE r.id_evento = e.id_evento
                   AND r.activo   = TRUE
                   AND er.codigo <> 'cancelada'
               ), 0) AS cupo
        FROM eventos e
        WHERE e.id_evento = :e
    """), {"e": id_evento})).first()
    if row is None:
        return 0
    return max(0, int(row.cupo))


# =============================================================================
# QR
# =============================================================================
def generar_qr_codigo(id_evento: int, id_evento_reserva: int) -> str:
    """Identificador estable, no criptografico. El render visual del QR queda
    para una fase posterior (frontend/movil)."""
    return f"EVT{id_evento}-RES{id_evento_reserva}-{int(time.time())}"


# =============================================================================
# Auditoria
# =============================================================================
def _to_jsonable(d: Optional[dict[str, Any]]) -> Optional[str]:
    """Convierte un dict a string JSON serializable (date/time/datetime -> isoformat)."""
    if d is None:
        return None
    def default(o: Any) -> Any:
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    return json.dumps(d, default=default, ensure_ascii=False)


async def registrar_audit(
    session: AsyncSession,
    id_usuario: Optional[int],
    entidad: str,
    id_entidad: int,
    accion: str,
    datos_anteriores: Optional[dict[str, Any]] = None,
    datos_nuevos: Optional[dict[str, Any]] = None,
    id_municipio: int = 1,
) -> None:
    """entidad in ('evento','ocupacion','reserva'),
       accion  in ('crear','modificar','cancelar','asignar')."""
    await session.execute(text("""
        INSERT INTO agenda_audit_log (
            id_usuario, entidad, id_entidad, accion,
            datos_anteriores, datos_nuevos, id_municipio
        ) VALUES (
            :uid, :ent, :ide, :acc, CAST(:da AS JSONB), CAST(:dn AS JSONB), :mun
        )
    """), {
        "uid": id_usuario,
        "ent": entidad,
        "ide": id_entidad,
        "acc": accion,
        "da": _to_jsonable(datos_anteriores),
        "dn": _to_jsonable(datos_nuevos),
        "mun": id_municipio,
    })


# =============================================================================
# Helpers de validacion
# =============================================================================
async def existe_recurso(session: AsyncSession, tipo_recurso: str, id_recurso: int) -> bool:
    """Confirma que el agente/equipo existe y esta activo."""
    if tipo_recurso == "agente":
        n = await session.scalar(text(
            "SELECT 1 FROM agentes WHERE id_agente = :i AND activo = TRUE"
        ), {"i": id_recurso})
    elif tipo_recurso == "equipo":
        n = await session.scalar(text(
            "SELECT 1 FROM equipos WHERE id_equipo = :i AND activo = TRUE"
        ), {"i": id_recurso})
    else:
        return False
    return bool(n)


async def lookup_estado_evento(session: AsyncSession, codigo: str) -> Optional[int]:
    return await session.scalar(text(
        "SELECT id_estado_evento FROM estado_evento WHERE codigo = :c AND activo = TRUE"
    ), {"c": codigo})


async def lookup_estado_reserva(session: AsyncSession, codigo: str) -> Optional[int]:
    return await session.scalar(text(
        "SELECT id_estado_reserva FROM estado_reserva WHERE codigo = :c AND activo = TRUE"
    ), {"c": codigo})


# =============================================================================
# Columnas reales de agenda_ausencia (legacy) - cache lazy
# =============================================================================
_AUSENCIA_COLS: Optional[set[str]] = None


async def agenda_ausencia_cols(session: AsyncSession) -> set[str]:
    """agenda_ausencia es legacy: usa modificado_en y posiblemente id_usuario.
    Detectamos columnas reales al primer uso para no asumir."""
    global _AUSENCIA_COLS
    if _AUSENCIA_COLS is not None:
        return _AUSENCIA_COLS
    rows = (await session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'agenda_ausencia'"
    ))).all()
    _AUSENCIA_COLS = {r[0] for r in rows}
    return _AUSENCIA_COLS


# =============================================================================
# Resumen corto por tipo de ocupacion - usado en GET /ocupaciones y /calendario
# =============================================================================
# =============================================================================
# Autoservicio publico — busca-o-crea ciudadano por DNI
# =============================================================================
async def buscar_o_crear_ciudadano_por_dni(
    session: AsyncSession,
    dni: str,
    apellido: str,
    nombre: str,
    telefono: Optional[str] = None,
    email: Optional[str] = None,
    id_municipio: int = 1,
) -> dict[str, Any]:
    """Busca un ciudadano por doc_nro (digits-only). Si existe activo, lo devuelve
    sin tocar. Si no existe, crea uno minimo con datos del form publico de autoservicio.

    Devuelve dict con id_ciudadano + apellido + nombre + doc_nro + creado (bool).

    Defaults para campos NOT NULL no provistos por el form:
      cuil = doc_nro sin formato (sera mejorado cuando un operador complete los datos)
      sexo = 'otro'
      fecha_nac = 1900-01-01 (sentinela visible)
      id_nacionalidad = primer match 'Argentina' o 1
      telefono = '0' si no viene
      email = '<dni>@autoservicio.local' si no viene
      observaciones = 'Creado por autoservicio - datos a completar'
    """
    import re
    dni_clean = re.sub(r"[^\d]", "", dni or "")
    if len(dni_clean) < 6:
        raise ValueError("DNI debe tener al menos 6 digitos numericos")

    # Buscar primero (activos y dados de baja — si esta dado de baja, no recrear)
    row = (await session.execute(text("""
        SELECT id_ciudadano, apellido, nombre, doc_nro, activo
          FROM ciudadanos
         WHERE regexp_replace(doc_nro, '[^0-9]', '', 'g') = :d
         LIMIT 1
    """), {"d": dni_clean})).mappings().first()
    if row:
        return {**dict(row), "creado": False}

    # Crear nuevo
    id_nac = await session.scalar(text(
        "SELECT id FROM nacionalidades WHERE pais ILIKE 'Argentina' LIMIT 1"
    ))
    id_nac = int(id_nac) if id_nac else 1

    tel = telefono.strip() if telefono and telefono.strip() else "0"
    em  = email.strip().lower() if email and email.strip() else f"{dni_clean}@autoservicio.local"

    new_id = await session.scalar(text("""
        INSERT INTO ciudadanos
            (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
             id_nacionalidad, telefono, email,
             activo, ren_chk, email_chk, emp_chk, observaciones,
             fecha_alta, id_municipio)
        VALUES
            ('DNI', :dni, :cuil, :nombre, :apellido, 'otro', '1900-01-01',
             :id_nac, :tel, :email,
             TRUE, FALSE, FALSE, FALSE, 'Creado por autoservicio - datos a completar',
             NOW(), :mun)
        RETURNING id_ciudadano
    """), {
        "dni": dni_clean, "cuil": dni_clean,
        "nombre": nombre[:100], "apellido": apellido[:100],
        "id_nac": id_nac, "tel": tel[:40], "email": em[:200], "mun": id_municipio,
    })
    return {
        "id_ciudadano": int(new_id),
        "apellido": apellido, "nombre": nombre, "doc_nro": dni_clean,
        "activo": True, "creado": True,
    }


def descripcion_corta_sql() -> str:
    """SQL CASE que arma una descripcion legible de la ocupacion segun su tipo.
    Diseñado para usar en JOINs - referencias a tablas: o (ocupaciones),
    ev (eventos), ot (ordenes_trabajo), ci (ciudadanos)."""
    return """
        CASE o.tipo
            WHEN 'evento' THEN COALESCE('Evento: ' || ev.nombre, 'Evento')
            WHEN 'ot'     THEN COALESCE('OT '      || ot.nro_ot || ' - ' || LEFT(ot.observaciones, 60),
                                        'OT '      || ot.nro_ot,
                                        'OT')
            WHEN 'turno'  THEN COALESCE('Turno: '  || ci.apellido || ', ' || ci.nombre, 'Turno')
        END
    """
