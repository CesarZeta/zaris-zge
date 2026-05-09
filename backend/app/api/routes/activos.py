"""
ZARIS API — Endpoints de activos físicos del municipio.
Prefijo: /api/v1/activos/
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/activos", tags=["Activos"])
logger = logging.getLogger("zaris.activos")


def _row(r) -> dict:
    d = dict(r._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


@router.get("/tipos")
async def listar_tipos(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    r = await db.execute(text("""
        SELECT id_tipo_activo, nombre, descripcion, icono, requiere_ciudadano
        FROM tipos_activo WHERE activo = TRUE ORDER BY nombre
    """))
    return [_row(row) for row in r.fetchall()]


@router.get("/buscar")
async def buscar_activos(
    codigo: Optional[str] = Query(None, description="Búsqueda por codigo_unico (ILIKE)"),
    id_tipo_activo: Optional[int] = Query(None),
    id_localidad: Optional[int] = Query(None),
    bbox: Optional[str] = Query(
        None,
        description="Bounding box 'min_lat,min_lon,max_lat,max_lon' para filtro geo",
    ),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    where = ["a.activo = TRUE"]
    params: dict = {"lim": limit}
    if codigo and codigo.strip():
        where.append("a.codigo_unico ILIKE :cod")
        params["cod"] = f"%{codigo.strip()}%"
    if id_tipo_activo:
        where.append("a.id_tipo_activo = :ita")
        params["ita"] = id_tipo_activo
    if id_localidad:
        where.append("a.id_localidad = :il")
        params["il"] = id_localidad
    if bbox:
        try:
            mn_lat, mn_lon, mx_lat, mx_lon = [float(x) for x in bbox.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox inválido")
        where.append(
            "a.latitud BETWEEN :mn_lat AND :mx_lat "
            "AND a.longitud BETWEEN :mn_lon AND :mx_lon"
        )
        params.update({"mn_lat": mn_lat, "mx_lat": mx_lat, "mn_lon": mn_lon, "mx_lon": mx_lon})

    sql = f"""
        SELECT a.id_activo, a.codigo_unico, a.id_tipo_activo, t.nombre AS tipo,
               a.descripcion, a.direccion, a.id_localidad,
               a.latitud, a.longitud
        FROM activos a
        JOIN tipos_activo t ON t.id_tipo_activo = a.id_tipo_activo
        WHERE {' AND '.join(where)}
        ORDER BY a.codigo_unico
        LIMIT :lim
    """
    r = await db.execute(text(sql), params)
    return [_row(row) for row in r.fetchall()]


@router.get("/{id_activo}")
async def obtener_activo(
    id_activo: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    r = await db.execute(text("""
        SELECT a.id_activo, a.codigo_unico, a.id_tipo_activo, t.nombre AS tipo,
               t.requiere_ciudadano,
               a.descripcion, a.direccion, a.id_localidad, l.nombre AS localidad,
               a.latitud, a.longitud, a.metros_cuadrados
        FROM activos a
        JOIN tipos_activo t ON t.id_tipo_activo = a.id_tipo_activo
        LEFT JOIN localidades l ON l.id_localidad = a.id_localidad
        WHERE a.id_activo = :id AND a.activo = TRUE
    """), {"id": id_activo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    return _row(row)
