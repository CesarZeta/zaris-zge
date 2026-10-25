"""
ZARIS API — Registro del super administrador visto por el municipio (IT-01 F3, Tarea 5).

GET /api/v1/auditoria/accesos-super → lo que hizo el super administrador en el municipio de la
request (spec §4: el administrador de cada municipio ve el registro de todo lo que hizo el super
administrador en su municipio). Solo lectura, nivel administrador. Las acciones globales
(id_municipio NULL) no las ve ningún municipio.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.database import get_db
from app.core.municipio import municipio_actual
from app.services.accesos_super import ACCIONES
from app.utils.orden import clausula_orden, descripcion_orden

router = APIRouter(prefix="/api/v1/auditoria", tags=["Auditoría"])

_ORDEN = {"fecha": "a.fecha_hora", "accion": "a.accion", "usuario": "u.nombre"}


class AccesoSuperOut(BaseModel):
    id_super_admin_acceso: int
    fecha_hora: str
    id_municipio: int
    usuario: Optional[str] = None
    accion: str
    metodo: Optional[str] = None
    ruta: Optional[str] = None
    detalle: Optional[str] = None


@router.get("/accesos-super", response_model=list[AccesoSuperOut])
async def listar_accesos_super(
    response: Response,
    desde: Optional[date] = Query(None, description="Fecha local del municipio, inclusive"),
    hasta: Optional[date] = Query(None, description="Fecha local del municipio, inclusive"),
    accion: Optional[str] = Query(None, max_length=30),
    orden: Optional[str] = Query(None, description=descripcion_orden(_ORDEN, "fecha, la más nueva primero")),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0, le=1_000_000),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    if accion is not None and accion not in ACCIONES:
        raise HTTPException(422, f"accion inválida: {accion}")
    conds = ["a.id_municipio = :mun"]
    params: dict = {"mun": id_municipio, "lim": limit, "off": offset}
    if desde is not None:
        conds.append("(a.fecha_hora AT TIME ZONE m.zona_horaria)::date >= :desde")
        params["desde"] = desde
    if hasta is not None:
        conds.append("(a.fecha_hora AT TIME ZONE m.zona_horaria)::date <= :hasta")
        params["hasta"] = hasta
    if accion is not None:
        conds.append("a.accion = :accion")
        params["accion"] = accion
    where = " AND ".join(conds)
    desde_sql = """FROM super_admin_acceso a
                   JOIN municipios m ON m.id_municipio = a.id_municipio
                   LEFT JOIN usuarios u ON u.id_usuario = a.id_usuario"""
    orden_sql = clausula_orden(orden, dir, _ORDEN, desempate="a.id_super_admin_acceso",
                               por_defecto="a.fecha_hora DESC, a.id_super_admin_acceso DESC")
    total = await db.scalar(text(f"SELECT count(*) {desde_sql} WHERE {where}"), params)
    rows = await db.execute(text(f"""
        SELECT a.id_super_admin_acceso, to_char(a.fecha_hora AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS fecha_hora,
               a.id_municipio, u.nombre AS usuario, a.accion, a.metodo, a.ruta, a.detalle
          {desde_sql}
         WHERE {where}
         ORDER BY {orden_sql}
         LIMIT :lim OFFSET :off"""), params)
    response.headers["X-Total-Count"] = str(int(total or 0))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [dict(r._mapping) for r in rows.fetchall()]
