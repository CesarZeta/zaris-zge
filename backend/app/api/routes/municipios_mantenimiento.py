"""
ZARIS API — Mantenimiento de municipios (IT-01 F4+F5, Tarea 16).

POST /api/v1/municipios/mantenimiento/purgar-exportaciones → borra el archivo de las exportaciones
    vencidas (EXPORTACION_RETENCION_DIAS) y las marca. Lo llama el workflow diario
    `.github/workflows/municipios-mantenimiento.yml`.

Auth: header X-Dispatcher-Token (máquina, sin JWT), como el mantenimiento de Trámites.
"""
import logging
import secrets as stdlib_secrets

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.services.municipios.exportacion import purgar_vencidas
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger("zaris.municipios")

router = APIRouter(prefix="/api/v1/municipios/mantenimiento", tags=["municipios-mantenimiento"])


@router.post("/purgar-exportaciones", responses={401: {"description": "Token inválido"},
                                                 503: {"description": "Dispatcher no configurado"}})
async def purgar_exportaciones(request: Request):
    esperado = settings.DISPATCHER_TOKEN
    if not esperado:
        raise HTTPException(503, "Dispatcher no configurado")
    if not stdlib_secrets.compare_digest(request.headers.get("X-Dispatcher-Token", ""), esperado):
        logger.warning("Purga de exportaciones: acceso no autorizado desde IP %s", get_real_ip(request))
        raise HTTPException(401, "No autorizado")
    purgadas = await purgar_vencidas()
    logger.info("Purga de exportaciones: %s vencidas borradas", purgadas)
    return {"purgadas": purgadas}
