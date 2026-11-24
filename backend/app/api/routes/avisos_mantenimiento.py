"""
ZARIS API — Recordatorio de turnos y entradas (cron, PLAN_AVISOS_TURNOS_ENTRADAS.md).

Auth: header X-Dispatcher-Token (no JWT), como los demás procesos de máquina. Idempotente: cada turno y
cada entrada se recuerda una sola vez (`recordado_en`, mig 144).
"""
from __future__ import annotations

import logging
import secrets as stdlib_secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.municipio import por_cada_municipio, resumen_municipios
from app.services.avisos_turnos import enviar_recordatorios
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger("zaris.avisos.mantenimiento")

router = APIRouter(prefix="/api/v1/avisos", tags=["avisos-mantenimiento"])


@router.post(
    "/mantenimiento/recordatorios",
    summary="Recuerda a los vecinos sus turnos y entradas de mañana",
    description="Endpoint llamado por cron. Auth via header X-Dispatcher-Token (no JWT — es máquina).",
)
async def ejecutar_recordatorios(request: Request, db: AsyncSession = Depends(get_db)):
    expected = settings.DISPATCHER_TOKEN
    if not expected:
        raise HTTPException(503, "Dispatcher no configurado")
    if not stdlib_secrets.compare_digest(request.headers.get("X-Dispatcher-Token", ""), expected):
        logger.warning("Recordatorios: acceso no autorizado desde IP %s", get_real_ip(request))
        raise HTTPException(401, "No autorizado")

    async def _uno(id_m: int) -> dict:
        return await enviar_recordatorios(db, id_m)

    por_municipio = await por_cada_municipio(db, "Recordatorios de turnos y entradas", _uno)
    totales = {k: sum(r.get(k, 0) for r in por_municipio.values()) for k in ("turnos", "entradas", "fallidos")}
    logger.info("Recordatorios: %s", totales)
    return {**totales, "por_municipio": por_municipio, **await resumen_municipios(db, por_municipio)}
