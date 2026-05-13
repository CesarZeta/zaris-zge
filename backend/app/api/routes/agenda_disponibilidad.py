"""
ZARIS API - Router de disponibilidad de recursos de agenda (mig 41).

CRUD multi-rango de `disponibilidad_recurso`. Permite definir horarios de
trabajo / atencion de agentes, equipos y espacios. Multiples filas por recurso
soportan turnos rotativos.

Permisos: nivel 1-2 puede mutar; cualquier nivel autenticado puede leer.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.agenda_v2 import (
    DisponibilidadRangoEfectivo,
    DisponibilidadRecursoCreate,
    DisponibilidadRecursoOut,
    DisponibilidadRecursoUpdate,
)
from app.services.agenda import disponibilidad_efectiva


router = APIRouter(prefix="/api/v1/agenda/disponibilidad", tags=["agenda-disponibilidad"])


def _require_admin(user: dict) -> None:
    if int(user.get("nivel_acceso", 99)) > 2:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 2)")


async def _disp_to_out(db: AsyncSession, id_disponibilidad: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT id_disponibilidad, tipo_recurso, id_recurso, dias_semana,
               hora_inicio, hora_fin, vigente_desde, vigente_hasta, etiqueta,
               activo, id_municipio, fecha_alta, fecha_modificacion
        FROM disponibilidad_recurso
        WHERE id_disponibilidad = :id
    """), {"id": id_disponibilidad})).mappings().first()
    return dict(row) if row else None


@router.get("", response_model=list[DisponibilidadRecursoOut])
async def listar_disponibilidad(
    tipo_recurso: Optional[Literal["agente", "equipo", "espacio"]] = None,
    id_recurso: Optional[int] = None,
    id_municipio: int = 1,
    activo: bool = True,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    where = ["id_municipio = :m", "activo = :ac"]
    params: dict[str, Any] = {"m": id_municipio, "ac": activo}
    if tipo_recurso:
        where.append("tipo_recurso = :tr"); params["tr"] = tipo_recurso
    if id_recurso is not None:
        where.append("id_recurso = :ir"); params["ir"] = id_recurso
    where_sql = " AND ".join(where)
    rows = (await db.execute(text(f"""
        SELECT id_disponibilidad, tipo_recurso, id_recurso, dias_semana,
               hora_inicio, hora_fin, vigente_desde, vigente_hasta, etiqueta,
               activo, id_municipio, fecha_alta, fecha_modificacion
        FROM disponibilidad_recurso
        WHERE {where_sql}
        ORDER BY tipo_recurso, id_recurso, hora_inicio
    """), params)).mappings().all()
    return [dict(r) for r in rows]


@router.post("", response_model=DisponibilidadRecursoOut, status_code=201)
async def crear_disponibilidad(
    payload: DisponibilidadRecursoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    # Validar que el recurso exista (importante: id_recurso es polimorfica).
    await _validar_recurso_existe(db, payload.tipo_recurso, payload.id_recurso)

    row = (await db.execute(text("""
        INSERT INTO disponibilidad_recurso (
            tipo_recurso, id_recurso, dias_semana, hora_inicio, hora_fin,
            vigente_desde, vigente_hasta, etiqueta, id_municipio, id_subarea,
            id_usuario_alta, id_usuario_modificacion
        ) VALUES (
            :tr, :ir, :ds, :hi, :hf,
            :vd, :vh, :et, :im, :isa,
            :uid, :uid
        )
        RETURNING id_disponibilidad
    """), {
        "tr": payload.tipo_recurso,
        "ir": payload.id_recurso,
        "ds": payload.dias_semana,
        "hi": payload.hora_inicio,
        "hf": payload.hora_fin,
        "vd": payload.vigente_desde,
        "vh": payload.vigente_hasta,
        "et": payload.etiqueta,
        "im": payload.id_municipio,
        "isa": payload.id_subarea,
        "uid": user["id_usuario"],
    })).first()
    await db.commit()
    out = await _disp_to_out(db, int(row[0]))
    if out is None:
        raise HTTPException(500, "Disponibilidad creada pero no se pudo releer")
    return out


@router.put("/{id_disponibilidad}", response_model=DisponibilidadRecursoOut)
async def actualizar_disponibilidad(
    id_disponibilidad: int,
    payload: DisponibilidadRecursoUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    row = (await db.execute(text("""
        SELECT hora_inicio, hora_fin FROM disponibilidad_recurso WHERE id_disponibilidad = :id
    """), {"id": id_disponibilidad})).mappings().first()
    if not row:
        raise HTTPException(404, "Disponibilidad no encontrada")

    sets = []
    params: dict[str, Any] = {"id": id_disponibilidad, "uid": user["id_usuario"]}
    data = payload.model_dump(exclude_unset=True)

    # Validar coherencia hora_fin > hora_inicio cuando se actualizan horas.
    if "hora_inicio" in data or "hora_fin" in data:
        nhi = data.get("hora_inicio", row["hora_inicio"])
        nhf = data.get("hora_fin", row["hora_fin"])
        if nhf <= nhi:
            raise HTTPException(422, "hora_fin debe ser mayor que hora_inicio")

    for col in ("dias_semana", "hora_inicio", "hora_fin", "vigente_desde", "vigente_hasta", "etiqueta", "activo"):
        if col in data:
            sets.append(f"{col} = :{col}")
            params[col] = data[col]
    if not sets:
        return await _disp_to_out(db, id_disponibilidad)  # type: ignore

    sets.append("fecha_modificacion = NOW()")
    sets.append("id_usuario_modificacion = :uid")
    await db.execute(text(f"UPDATE disponibilidad_recurso SET {', '.join(sets)} WHERE id_disponibilidad = :id"), params)
    await db.commit()
    return await _disp_to_out(db, id_disponibilidad)


@router.delete("/{id_disponibilidad}", status_code=204)
async def eliminar_disponibilidad(
    id_disponibilidad: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    row = (await db.execute(text("SELECT 1 FROM disponibilidad_recurso WHERE id_disponibilidad = :id AND activo = TRUE"), {"id": id_disponibilidad})).first()
    if not row:
        raise HTTPException(404, "Disponibilidad no encontrada o ya inactiva")
    await db.execute(text("""
        UPDATE disponibilidad_recurso
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_disponibilidad = :id
    """), {"id": id_disponibilidad, "uid": user["id_usuario"]})
    await db.commit()


@router.get("/efectiva", response_model=list[DisponibilidadRangoEfectivo])
async def consultar_disponibilidad_efectiva(
    tipo_recurso: Literal["agente", "equipo", "espacio"],
    id_recurso: int,
    fecha: date = Query(..., description="Fecha contra la cual resolver bitmask + vigencias"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Devuelve los rangos de disponibilidad efectiva para un recurso en una
    fecha puntual. Aplica las reglas de espacio atendido (union con agentes
    vinculados, interseccion con horario propio del espacio)."""
    return await disponibilidad_efectiva(db, tipo_recurso, id_recurso, fecha)


async def _validar_recurso_existe(db: AsyncSession, tipo: str, id_recurso: int) -> None:
    if tipo == "agente":
        row = (await db.execute(text("SELECT 1 FROM agentes WHERE id_agente = :id AND activo = TRUE"), {"id": id_recurso})).first()
    elif tipo == "equipo":
        row = (await db.execute(text("SELECT 1 FROM equipos WHERE id_equipo = :id AND activo = TRUE"), {"id": id_recurso})).first()
    elif tipo == "espacio":
        row = (await db.execute(text("SELECT 1 FROM espacios_agenda WHERE id_espacio = :id AND activo = TRUE"), {"id": id_recurso})).first()
    else:
        raise HTTPException(422, f"tipo_recurso invalido: {tipo}")
    if not row:
        raise HTTPException(404, f"Recurso {tipo}/{id_recurso} no encontrado o inactivo")
