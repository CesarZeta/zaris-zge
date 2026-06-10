"""
ZARIS API - Modulo Emergencias (COM): catalogos de lectura (Fase 2).

Plan: PLAN_MODULO_EMERGENCIAS.md seccion 4.1. Endpoints de escritura
(eventos, contactos eventuales, denunciantes) llegan en Fase 3.

Permisos: cualquier autenticado con scope agente lee (guard JWT a nivel
router, patron s39 — get_current_user ya rechaza scope publico).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter(
    prefix="/api/v1/emergencias",
    tags=["emergencias"],
    dependencies=[Depends(get_current_user)],
)


# =============================================================================
# Schemas (lectura)
# =============================================================================
class OrganismoOut(BaseModel):
    id_emergencia_organismo_derivacion: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    telefono_contacto: Optional[str] = None
    es_municipal: bool
    activo: bool


class CanalOut(BaseModel):
    id_emergencia_canal_ingreso: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    requiere_operador: bool
    activo: bool


class PrioridadOut(BaseModel):
    id_emergencia_prioridad: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    sla_minutos_arribo: int
    color_token: str
    orden_visual: int
    activo: bool


class EstadoOut(BaseModel):
    id_emergencia_estado: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    es_inicial: bool
    es_terminal: bool
    es_terminal_positivo: bool
    orden_visual: int
    activo: bool


class TipoOut(BaseModel):
    id_emergencia_tipo: int
    id_subarea: int
    subarea_nombre: Optional[str] = None
    codigo_oficial: Optional[int] = None
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    id_prioridad_default: int
    prioridad_codigo: Optional[str] = None
    id_organismo_derivacion_default: Optional[int] = None
    organismo_default_codigo: Optional[str] = None
    requiere_911: bool
    es_emergencia: bool
    activo: bool


class SubtipoOut(BaseModel):
    id_emergencia_subtipo: int
    id_tipo: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    id_prioridad_override: Optional[int] = None
    prioridad_override_codigo: Optional[str] = None
    activo: bool


# =============================================================================
# Catalogos simples
# =============================================================================
@router.get("/organismos", response_model=list[OrganismoOut])
async def listar_organismos(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_organismo_derivacion, codigo, nombre, descripcion,
               telefono_contacto, es_municipal, activo
        FROM emergencia_organismo_derivacion
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY nombre
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/canales", response_model=list[CanalOut])
async def listar_canales(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_canal_ingreso, codigo, nombre, descripcion,
               requiere_operador, activo
        FROM emergencia_canal_ingreso
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY nombre
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/prioridades", response_model=list[PrioridadOut])
async def listar_prioridades(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_prioridad, codigo, nombre, descripcion,
               sla_minutos_arribo, color_token, orden_visual, activo
        FROM emergencia_prioridad
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY orden_visual
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/estados", response_model=list[EstadoOut])
async def listar_estados(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_estado, codigo, nombre, descripcion,
               es_inicial, es_terminal, es_terminal_positivo, orden_visual, activo
        FROM emergencia_estado
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY orden_visual
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# Tipos y subtipos
# =============================================================================
_SELECT_TIPOS = """
    SELECT t.id_emergencia_tipo, t.id_subarea, s.nombre AS subarea_nombre,
           t.codigo_oficial, t.codigo, t.nombre, t.descripcion,
           t.id_prioridad_default, p.codigo AS prioridad_codigo,
           t.id_organismo_derivacion_default, o.codigo AS organismo_default_codigo,
           t.requiere_911, t.es_emergencia, t.activo
    FROM emergencia_tipo t
    JOIN subarea s ON s.id_subarea = t.id_subarea
    JOIN emergencia_prioridad p ON p.id_emergencia_prioridad = t.id_prioridad_default
    LEFT JOIN emergencia_organismo_derivacion o
           ON o.id_emergencia_organismo_derivacion = t.id_organismo_derivacion_default
"""


@router.get("/tipos", response_model=list[TipoOut])
async def listar_tipos(
    id_subarea: Optional[int] = Query(None),
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text(_SELECT_TIPOS + """
        WHERE (CAST(:id_subarea AS integer) IS NULL OR t.id_subarea = :id_subarea)
          AND (CAST(:activo AS boolean) IS NULL OR t.activo = :activo)
        ORDER BY t.nombre
    """), {"id_subarea": id_subarea, "activo": activo})).mappings().all()
    return [dict(r) for r in rows]


_SELECT_SUBTIPOS = """
    SELECT st.id_emergencia_subtipo, st.id_tipo, st.codigo, st.nombre,
           st.descripcion, st.id_prioridad_override,
           p.codigo AS prioridad_override_codigo, st.activo
    FROM emergencia_subtipo st
    LEFT JOIN emergencia_prioridad p
           ON p.id_emergencia_prioridad = st.id_prioridad_override
"""


@router.get("/tipos/{id_tipo}/subtipos", response_model=list[SubtipoOut])
async def listar_subtipos_de_tipo(
    id_tipo: int,
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    existe = (await db.execute(text(
        "SELECT 1 FROM emergencia_tipo WHERE id_emergencia_tipo = :id"
    ), {"id": id_tipo})).scalar()
    if not existe:
        raise HTTPException(404, "Tipo de emergencia no encontrado")
    rows = (await db.execute(text(_SELECT_SUBTIPOS + """
        WHERE st.id_tipo = :id_tipo
          AND (CAST(:activo AS boolean) IS NULL OR st.activo = :activo)
        ORDER BY st.nombre
    """), {"id_tipo": id_tipo, "activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/subtipos", response_model=list[SubtipoOut])
async def listar_subtipos(
    id_tipo: Optional[int] = Query(None),
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text(_SELECT_SUBTIPOS + """
        WHERE (CAST(:id_tipo AS integer) IS NULL OR st.id_tipo = :id_tipo)
          AND (CAST(:activo AS boolean) IS NULL OR st.activo = :activo)
        ORDER BY st.id_tipo, st.nombre
    """), {"id_tipo": id_tipo, "activo": activo})).mappings().all()
    return [dict(r) for r in rows]
