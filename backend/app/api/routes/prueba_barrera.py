"""
ZARIS API — Endpoint de prueba de la segunda barrera, SOLO LOCAL (IT-01 F6.2, Task 4).

Consulta reclamos SIN filtro de municipio, a propósito: con DB_BARRERA=true la base igual devuelve
solo el municipio de la request; con false se ven todos (el filtro que falta se nota). main.py lo
registra únicamente si `_es_entorno_local()`. Lo usa `smoke_barrera.py`.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.municipio import municipio_actual

router = APIRouter(prefix="/api/v1/_prueba", tags=["prueba (solo local)"])


@router.get("/reclamos-sin-filtro")
async def reclamos_sin_filtro(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
    _mun: int = Depends(municipio_actual),
):
    filas = await db.execute(text(
        "SELECT id_municipio, count(*) AS cantidad FROM reclamos GROUP BY id_municipio ORDER BY id_municipio"))
    return [dict(f._mapping) for f in filas]
