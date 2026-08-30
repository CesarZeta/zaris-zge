"""
Endpoint de mantenimiento de Tramites (mig 75, Fase 5) — disparado por cron.

Corre los dos motores de la politica de retencion (ver services/tramites/
retencion.py):
  1. archivar_inactivos  -> archiva tramites sin movimiento hace N dias.
  2. purgar_binarios      -> depura el archivo fisico de documentos vencidos
                             (dry-run salvo configuracion_general.
                             tramite_purga_binarios_real = 'true').

Auth: header X-Dispatcher-Token (NO JWT — es maquina), validado con
compare_digest contra settings.DISPATCHER_TOKEN. Mismo token/patron que el
dispatcher de Encuestas (S42). Router SEPARADO sin guard JWT global.

Tipicamente 1 vez al dia por GitHub Actions (.github/workflows/
tramites-mantenimiento.yml).
"""
from __future__ import annotations

import logging
import secrets as stdlib_secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.tramites import retencion as svc_ret
from app.services.tramites import ciclo_vida as svc_ciclo
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger("zaris.tramites.mantenimiento")

router = APIRouter(prefix="/api/v1/tramites", tags=["tramites-mantenimiento"])


@router.post(
    "/mantenimiento/ejecutar",
    summary="Archiva tramites inactivos y depura binarios vencidos",
    description="Endpoint llamado por cron. Auth via header X-Dispatcher-Token (no JWT — es maquina).",
)
async def ejecutar_mantenimiento(
    request: Request,
    forzar_purga_real: bool = Query(
        False,
        description="Si True, fuerza la purga REAL ignorando el switch dry-run. "
                    "Usar solo para una corrida controlada; el cron NO lo manda.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    1. Archiva tramites sin movimiento hace >= tramite_inactividad_dias dias
       (los marca resultado='rechazado', motivo 'inactividad').
    2. Depura el binario fisico de documentos cuyo plazo de retencion vencio
       (dry-run por default; real si configuracion_general.
       tramite_purga_binarios_real='true' o si forzar_purga_real=True).

    El registro de cada documento (metadatos + hash) NUNCA se borra.
    """
    expected = settings.DISPATCHER_TOKEN
    if not expected:
        raise HTTPException(503, "Dispatcher no configurado")

    token = request.headers.get("X-Dispatcher-Token", "")
    if not stdlib_secrets.compare_digest(token, expected):
        logger.warning("Mantenimiento tramites: acceso no autorizado desde IP %s", get_real_ip(request))
        raise HTTPException(401, "No autorizado")

    try:
        archivado = await svc_ret.archivar_inactivos(db)
        # forzar_purga_real=True -> dry_run=False; sino lo decide el switch de config.
        dry_run = None if not forzar_purga_real else False
        purga = await svc_ret.purgar_binarios(db, dry_run=dry_run)
        # mig 101: timer de desistimiento de tramites a la espera del vecino
        # (avisos escalonados + desistido automatico). Best-effort: un fallo
        # aca no debe tumbar el archivado/purga ya hechos.
        try:
            desistimiento = await svc_ciclo.procesar_desistimientos(db)
        except Exception:
            logger.exception("Mantenimiento tramites: desistimiento fallo")
            await db.rollback()
            desistimiento = {"error": True, "avisos": 0, "desistidos": 0}
        logger.info(
            "Mantenimiento tramites OK: archivados=%s purga_dry_run=%s purgados=%s errores=%s "
            "avisos_desist=%s desistidos=%s",
            archivado.get("archivados", 0),
            purga.get("dry_run"),
            purga.get("purgados", 0),
            purga.get("errores", 0),
            desistimiento.get("avisos", 0),
            desistimiento.get("desistidos", 0),
        )
        return {
            "archivado": archivado,
            "purga": purga,
            "desistimiento": desistimiento,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Mantenimiento tramites: error inesperado")
        raise HTTPException(500, "Error procesando mantenimiento")
