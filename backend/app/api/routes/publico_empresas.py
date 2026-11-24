"""
Empresas del vecino logueado (PLAN_REGISTRO_PREVIO.md, F4). Scope `publico`.

    GET /api/v1/publico/empresas            las que representa
    GET /api/v1/publico/empresas/catalogos  actividades y tipos de representación del formulario

El alta es `POST /api/v1/publico/alta/empresa` (el representante SIEMPRE es el del token).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db

router = APIRouter(prefix="/api/v1/publico/empresas", tags=["publico-empresas"])


class EmpresaVecinoOut(BaseModel):
    id_empresa: int
    cuit: str
    nombre: str
    actividad: str | None = None
    tipo_representacion: str | None = None
    calle: str | None = None
    localidad: str | None = None
    provincia: str | None = None
    telefono: str | None = None
    email: str | None = None
    email_verificado: bool = False


class OpcionOut(BaseModel):
    id: int
    nombre: str
    detalle: str | None = None


class CatalogosEmpresaOut(BaseModel):
    actividades: list[OpcionOut]
    tipos_representacion: list[OpcionOut]


@router.get("", response_model=list[EmpresaVecinoOut])
async def mis_empresas(ciudadano: dict = Depends(get_current_ciudadano), db: AsyncSession = Depends(get_db)):
    """Empresas activas que el vecino representa, por nombre."""
    filas = (await db.execute(text("""
        SELECT e.id_empresa, e.cuit, e.nombre, a.descripcion AS actividad, tr.tipo AS tipo_representacion,
               e.calle, e.localidad, e.provincia, e.telefono, e.email, e.email_chk AS email_verificado
          FROM ciudadano_empresa ce
          JOIN empresas e ON e.id_empresa = ce.id_empresa
          LEFT JOIN actividades a ON a.id = e.id_actividad
          LEFT JOIN tipo_representacion tr ON tr.id = ce.id_tipo_representacion
         WHERE ce.id_ciudadano = :c AND ce.activo = TRUE AND e.activo = TRUE
           AND e.id_municipio = :m AND ce.id_municipio = :m
         ORDER BY lower(e.nombre), e.id_empresa
    """), {"c": ciudadano["id_ciudadano"], "m": ciudadano["id_municipio"]})).mappings().all()
    return [dict(f) for f in filas]


@router.get("/catalogos", response_model=CatalogosEmpresaOut)
async def catalogos(ciudadano: dict = Depends(get_current_ciudadano), db: AsyncSession = Depends(get_db)):
    """Los mismos catálogos que ofrece el alta de empresa del backoffice."""
    act = (await db.execute(text(
        "SELECT id, descripcion AS nombre FROM actividades WHERE activo IS NOT FALSE ORDER BY descripcion"
    ))).mappings().all()
    reps = (await db.execute(text(
        "SELECT id, tipo AS nombre, descripcion AS detalle FROM tipo_representacion WHERE activo IS NOT FALSE ORDER BY id"
    ))).mappings().all()
    return {"actividades": [dict(x) for x in act], "tipos_representacion": [dict(x) for x in reps]}
