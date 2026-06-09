"""
Endpoint de mantenimiento de integridad de cuentas (mig 77, Fase 2) — cron diario.

Corre el motor de integridad (services/integridad_cuentas.py):
  suspender_usuarios_sin_vinculo -> baja lógica + marca a los usuarios activos sin
  agente ni ciudadano asociado que superaron el período de gracia (24h). Admin
  (nivel 1) exento.

Auth: header X-Dispatcher-Token (NO JWT — es máquina), validado con compare_digest
contra settings.DISPATCHER_TOKEN. Mismo token/patrón que el dispatcher de Encuestas
(§42) y el de mantenimiento de Trámites (§35). Router SEPARADO sin guard JWT global.

Típicamente 1 vez al día por GitHub Actions (.github/workflows/
integridad-cuentas.yml).
"""
from __future__ import annotations

import logging
import secrets as stdlib_secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services import integridad_cuentas as svc_integridad
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger("zaris.usuarios.mantenimiento")

router = APIRouter(prefix="/api/v1/usuarios", tags=["usuarios-mantenimiento"])


@router.post(
    "/mantenimiento/integridad-cuentas",
    summary="Suspende usuarios sin agente ni ciudadano asociado",
    description="Endpoint llamado por cron. Auth via header X-Dispatcher-Token (no JWT — es máquina).",
)
async def ejecutar_integridad_cuentas(
    request: Request,
    dry_run: bool = Query(
        False,
        description="Si True, solo reporta los usuarios que se suspenderían, sin mutar.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Suspende (activo=FALSE + suspendido_motivo='sin_vinculo' + fecha_suspension) los
    usuarios activos, nivel>1, sin agente ni ciudadano asociado, creados hace más de
    24h. Admin (nivel 1) exento.

    dry_run=True devuelve el diagnóstico sin tocar nada.
    """
    expected = settings.DISPATCHER_TOKEN
    if not expected:
        raise HTTPException(503, "Dispatcher no configurado")

    token = request.headers.get("X-Dispatcher-Token", "")
    if not stdlib_secrets.compare_digest(token, expected):
        logger.warning("Integridad cuentas: acceso no autorizado desde IP %s", get_real_ip(request))
        raise HTTPException(401, "No autorizado")

    try:
        if dry_run:
            candidatos = await svc_integridad.listar_usuarios_sin_vinculo(db)
            a_suspender = [c for c in candidatos if c.get("supera_gracia")]
            return {
                "dry_run": True,
                "sin_vinculo_total": len(candidatos),
                "a_suspender": len(a_suspender),
                "detalle": a_suspender,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        resultado = await svc_integridad.suspender_usuarios_sin_vinculo(db)
        logger.info(
            "Integridad cuentas OK: suspendidos=%s", resultado.get("suspendidos", 0)
        )
        return {
            "dry_run": False,
            **resultado,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Integridad cuentas: error inesperado")
        raise HTTPException(500, "Error procesando integridad de cuentas")
