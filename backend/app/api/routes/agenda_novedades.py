"""
ZARIS API - Router de novedades de agentes + feriados (mig 69 + agenda_feriado).

Dos recursos que restan disponibilidad efectiva (servicio agenda.py):
  - agente_novedad: ausencias de un agente (inasistencia/licencia/vacaciones/...)
    en un rango de fechas, total (todo el dia) o parcial (rango horario).
  - agenda_feriado: dias no laborables (nacional/provincial/municipal).

Permisos: nivel 1-2 muta; cualquier autenticado lee.
"""
from __future__ import annotations

from datetime import date, time
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db


router = APIRouter(prefix="/api/v1/agenda", tags=["agenda-novedades"])


def _require_admin(user: dict) -> None:
    if int(user.get("nivel_acceso", 99)) > 2:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 2)")


# =============================================================================
# Schemas
# =============================================================================
TipoNovedad = Literal["inasistencia", "licencia", "vacaciones", "comision", "otro"]


class NovedadCreate(BaseModel):
    id_agente: int
    tipo: TipoNovedad = "inasistencia"
    fecha_desde: date
    fecha_hasta: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    motivo: Optional[str] = Field(None, max_length=300)
    id_municipio: int = 1
    id_subarea: Optional[int] = None


class NovedadUpdate(BaseModel):
    tipo: Optional[TipoNovedad] = None
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    motivo: Optional[str] = Field(None, max_length=300)
    activo: Optional[bool] = None


class NovedadOut(BaseModel):
    id_agente_novedad: int
    id_agente: int
    agente_nombre: Optional[str] = None
    tipo: str
    fecha_desde: date
    fecha_hasta: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    motivo: Optional[str] = None
    activo: bool
    fecha_alta: Any


class FeriadoCreate(BaseModel):
    fecha: date
    descripcion: str = Field(..., max_length=200)
    ambito: Literal["NACIONAL", "PROVINCIAL", "MUNICIPAL"] = "MUNICIPAL"
    id_municipio: int = 1


class FeriadoUpdate(BaseModel):
    fecha: Optional[date] = None
    descripcion: Optional[str] = Field(None, max_length=200)
    ambito: Optional[Literal["NACIONAL", "PROVINCIAL", "MUNICIPAL"]] = None
    activo: Optional[bool] = None


class FeriadoOut(BaseModel):
    id_agenda_feriado: int
    fecha: date
    descripcion: Optional[str] = None
    ambito: Optional[str] = None
    activo: bool


def _coherencia_novedad(fecha_desde: date, fecha_hasta: date, hi: Optional[time], hf: Optional[time]) -> None:
    if fecha_hasta < fecha_desde:
        raise HTTPException(422, "fecha_hasta debe ser >= fecha_desde")
    if (hi is None) != (hf is None):
        raise HTTPException(422, "hora_inicio y hora_fin deben venir ambas o ninguna")
    if hi is not None and hf is not None and hf <= hi:
        raise HTTPException(422, "hora_fin debe ser mayor que hora_inicio")


# =============================================================================
# Novedades de agentes
# =============================================================================
async def _novedad_to_out(db: AsyncSession, id_nov: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT n.id_agente_novedad, n.id_agente,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               n.tipo, n.fecha_desde, n.fecha_hasta, n.hora_inicio, n.hora_fin,
               n.motivo, n.activo, n.fecha_alta
        FROM agente_novedad n
        LEFT JOIN agentes a ON a.id_agente = n.id_agente
        WHERE n.id_agente_novedad = :id
    """), {"id": id_nov})).mappings().first()
    return dict(row) if row else None


@router.get("/novedades", response_model=list[NovedadOut])
async def listar_novedades(
    id_agente: Optional[int] = None,
    desde: Optional[date] = Query(None, description="Solo novedades con fecha_hasta >= desde"),
    id_municipio: int = 1,
    activo: bool = True,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    where = ["n.activo = :ac", "(n.id_municipio = :m OR n.id_municipio IS NULL)"]
    params: dict[str, Any] = {"ac": activo, "m": id_municipio}
    if id_agente is not None:
        where.append("n.id_agente = :ia"); params["ia"] = id_agente
    if desde is not None:
        where.append("n.fecha_hasta >= :fd"); params["fd"] = desde
    rows = (await db.execute(text(f"""
        SELECT n.id_agente_novedad, n.id_agente,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               n.tipo, n.fecha_desde, n.fecha_hasta, n.hora_inicio, n.hora_fin,
               n.motivo, n.activo, n.fecha_alta
        FROM agente_novedad n
        LEFT JOIN agentes a ON a.id_agente = n.id_agente
        WHERE {' AND '.join(where)}
        ORDER BY n.fecha_desde DESC, n.id_agente_novedad DESC
    """), params)).mappings().all()
    return [dict(r) for r in rows]


@router.post("/novedades", response_model=NovedadOut, status_code=201)
async def crear_novedad(
    payload: NovedadCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    _coherencia_novedad(payload.fecha_desde, payload.fecha_hasta, payload.hora_inicio, payload.hora_fin)
    ag = (await db.execute(text(
        "SELECT 1 FROM agentes WHERE id_agente = :id AND activo = TRUE"
    ), {"id": payload.id_agente})).first()
    if not ag:
        raise HTTPException(404, "Agente no encontrado o inactivo")
    id_nov = await db.scalar(text("""
        INSERT INTO agente_novedad (
            id_agente, tipo, fecha_desde, fecha_hasta, hora_inicio, hora_fin,
            motivo, id_municipio, id_subarea, id_usuario_alta, id_usuario_modificacion
        ) VALUES (
            :ia, :tipo, :fd, :fh, :hi, :hf, :mot, :im, :isa, :uid, :uid
        )
        RETURNING id_agente_novedad
    """), {
        "ia": payload.id_agente, "tipo": payload.tipo,
        "fd": payload.fecha_desde, "fh": payload.fecha_hasta,
        "hi": payload.hora_inicio, "hf": payload.hora_fin,
        "mot": payload.motivo, "im": payload.id_municipio, "isa": payload.id_subarea,
        "uid": user["id_usuario"],
    })
    await db.commit()
    out = await _novedad_to_out(db, int(id_nov))
    if out is None:
        raise HTTPException(500, "Novedad creada pero no se pudo releer")
    return out


@router.put("/novedades/{id_agente_novedad}", response_model=NovedadOut)
async def actualizar_novedad(
    id_agente_novedad: int,
    payload: NovedadUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    cur = (await db.execute(text("""
        SELECT fecha_desde, fecha_hasta, hora_inicio, hora_fin
        FROM agente_novedad WHERE id_agente_novedad = :id
    """), {"id": id_agente_novedad})).mappings().first()
    if not cur:
        raise HTTPException(404, "Novedad no encontrada")
    data = payload.model_dump(exclude_unset=True)
    fd = data.get("fecha_desde", cur["fecha_desde"])
    fh = data.get("fecha_hasta", cur["fecha_hasta"])
    hi = data.get("hora_inicio", cur["hora_inicio"]) if "hora_inicio" in data else cur["hora_inicio"]
    hf = data.get("hora_fin", cur["hora_fin"]) if "hora_fin" in data else cur["hora_fin"]
    _coherencia_novedad(fd, fh, hi, hf)

    sets, params = [], {"id": id_agente_novedad, "uid": user["id_usuario"]}
    for col in ("tipo", "fecha_desde", "fecha_hasta", "hora_inicio", "hora_fin", "motivo", "activo"):
        if col in data:
            sets.append(f"{col} = :{col}"); params[col] = data[col]
    if not sets:
        return await _novedad_to_out(db, id_agente_novedad)  # type: ignore
    sets += ["fecha_modificacion = NOW()", "id_usuario_modificacion = :uid"]
    await db.execute(text(f"UPDATE agente_novedad SET {', '.join(sets)} WHERE id_agente_novedad = :id"), params)
    await db.commit()
    return await _novedad_to_out(db, id_agente_novedad)


@router.delete("/novedades/{id_agente_novedad}", status_code=204)
async def eliminar_novedad(
    id_agente_novedad: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    row = (await db.execute(text(
        "SELECT 1 FROM agente_novedad WHERE id_agente_novedad = :id AND activo = TRUE"
    ), {"id": id_agente_novedad})).first()
    if not row:
        raise HTTPException(404, "Novedad no encontrada o ya inactiva")
    await db.execute(text("""
        UPDATE agente_novedad
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_agente_novedad = :id
    """), {"id": id_agente_novedad, "uid": user["id_usuario"]})
    await db.commit()


# =============================================================================
# Feriados
# =============================================================================
async def _feriado_to_out(db: AsyncSession, id_fer: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT id_agenda_feriado, fecha, descripcion, ambito, activo
        FROM agenda_feriado WHERE id_agenda_feriado = :id
    """), {"id": id_fer})).mappings().first()
    return dict(row) if row else None


@router.get("/feriados", response_model=list[FeriadoOut])
async def listar_feriados(
    anio: Optional[int] = Query(None, description="Filtra por anio de la fecha"),
    id_municipio: int = 1,
    activo: bool = True,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    where = ["activo = :ac"]
    params: dict[str, Any] = {"ac": activo}
    if anio is not None:
        where.append("EXTRACT(YEAR FROM fecha) = :y"); params["y"] = anio
    rows = (await db.execute(text(f"""
        SELECT id_agenda_feriado, fecha, descripcion, ambito, activo
        FROM agenda_feriado
        WHERE {' AND '.join(where)}
        ORDER BY fecha
    """), params)).mappings().all()
    return [dict(r) for r in rows]


@router.post("/feriados", response_model=FeriadoOut, status_code=201)
async def crear_feriado(
    payload: FeriadoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    dup = await db.scalar(text(
        "SELECT 1 FROM agenda_feriado WHERE fecha = :f AND activo = TRUE LIMIT 1"
    ), {"f": payload.fecha})
    if dup:
        raise HTTPException(409, "Ya existe un feriado activo en esa fecha")
    id_fer = await db.scalar(text("""
        INSERT INTO agenda_feriado (fecha, descripcion, ambito, activo, id_municipio, id_usuario_alta)
        VALUES (:f, :d, :am, TRUE, :im, :uid)
        RETURNING id_agenda_feriado
    """), {"f": payload.fecha, "d": payload.descripcion, "am": payload.ambito,
           "im": payload.id_municipio, "uid": user["id_usuario"]})
    await db.commit()
    out = await _feriado_to_out(db, int(id_fer))
    if out is None:
        raise HTTPException(500, "Feriado creado pero no se pudo releer")
    return out


@router.put("/feriados/{id_agenda_feriado}", response_model=FeriadoOut)
async def actualizar_feriado(
    id_agenda_feriado: int,
    payload: FeriadoUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    cur = (await db.execute(text(
        "SELECT 1 FROM agenda_feriado WHERE id_agenda_feriado = :id"
    ), {"id": id_agenda_feriado})).first()
    if not cur:
        raise HTTPException(404, "Feriado no encontrado")
    data = payload.model_dump(exclude_unset=True)
    sets, params = [], {"id": id_agenda_feriado, "uid": user["id_usuario"]}
    for col in ("fecha", "descripcion", "ambito", "activo"):
        if col in data:
            sets.append(f"{col} = :{col}"); params[col] = data[col]
    if not sets:
        return await _feriado_to_out(db, id_agenda_feriado)  # type: ignore
    sets += ["fecha_modificacion = NOW()", "id_usuario_modificacion = :uid"]
    await db.execute(text(f"UPDATE agenda_feriado SET {', '.join(sets)} WHERE id_agenda_feriado = :id"), params)
    await db.commit()
    return await _feriado_to_out(db, id_agenda_feriado)


@router.delete("/feriados/{id_agenda_feriado}", status_code=204)
async def eliminar_feriado(
    id_agenda_feriado: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    row = (await db.execute(text(
        "SELECT 1 FROM agenda_feriado WHERE id_agenda_feriado = :id AND activo = TRUE"
    ), {"id": id_agenda_feriado})).first()
    if not row:
        raise HTTPException(404, "Feriado no encontrado o ya inactivo")
    await db.execute(text("""
        UPDATE agenda_feriado
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_agenda_feriado = :id
    """), {"id": id_agenda_feriado, "uid": user["id_usuario"]})
    await db.commit()
