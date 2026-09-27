"""
ZARIS API - Web Push de USUARIOS INTERNOS (App de agentes `zaris-agentes`).

Espejo de publico_push.py sobre `usuario_push_subscription` (mig 108), con el
guard de agentes (get_current_user, cualquier nivel). El navegador del agente
se suscribe desde la app (Cuenta → Notificaciones); el backend le manda push
cuando le asignan una OT (services/push.py::notificar_ot_asignada).

GET  /api/v1/auth/push/public-key    clave VAPID (503 si el push no esta configurado)
POST /api/v1/auth/push/subscribe     registra (o reactiva) la suscripcion del navegador
POST /api/v1/auth/push/unsubscribe   da de baja una suscripcion (o todas las del usuario)

Claves VAPID: las mismas que la App Vecinos (env vars o configuracion_general).
No hay "canal preferido": la suscripcion activa ES el toggle.
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.services.push import vapid_config
from app.utils.request_helpers import get_real_ip

router = APIRouter(prefix="/api/v1/auth/push", tags=["Auth · Push (agentes)"])
logger = logging.getLogger("zaris.usuario_push")


class SubscribeIn(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=1000)
    p256dh: str = Field(..., min_length=10, max_length=300)
    auth: str = Field(..., min_length=5, max_length=100)


class UnsubscribeIn(BaseModel):
    endpoint: Optional[str] = Field(None, max_length=1000)
    """Sin endpoint => da de baja TODAS las suscripciones del usuario."""


@router.get("/public-key")
async def public_key(current_user: dict = Depends(get_current_user)) -> Any:
    """Clave publica VAPID. 503 si el push no esta configurado en este deploy."""
    cfg = await vapid_config()
    if not cfg["public"]:
        raise HTTPException(503, "Las notificaciones push no están configuradas en este servidor.")
    return {"public_key": cfg["public"]}


@router.post("/subscribe", status_code=201)
async def subscribe(
    payload: SubscribeIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Any:
    """Registra (o reactiva) la suscripcion del navegador del usuario logueado."""
    check_rate_limit(f"pushusr:{get_real_ip(request)}", max_requests=10, window_seconds=60)
    id_usuario = int(current_user["id_usuario"])
    ua = (request.headers.get("user-agent") or "")[:300]

    # UNIQUE (id_usuario, endpoint) — mig 108. Re-suscribirse reactiva y
    # refresca las claves (el navegador puede rotarlas).
    await db.execute(text("""
        INSERT INTO usuario_push_subscription
            (id_usuario, endpoint, p256dh, auth_secret, user_agent, id_municipio,
             id_usuario_alta, id_usuario_modificacion)
        VALUES (:u, :e, :p, :a, :ua, 1, :u, :u)
        ON CONFLICT (id_usuario, endpoint)
        DO UPDATE SET p256dh = :p, auth_secret = :a, user_agent = :ua,
                      activo = TRUE, fecha_modificacion = NOW(),
                      id_usuario_modificacion = :u
    """), {"u": id_usuario, "e": payload.endpoint, "p": payload.p256dh,
           "a": payload.auth, "ua": ua})
    await db.commit()
    logger.info("push agente: suscripcion registrada | id_usuario=%s", id_usuario)
    return {"suscripto": True}


@router.post("/unsubscribe")
async def unsubscribe(
    payload: UnsubscribeIn,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Any:
    """Da de baja la suscripcion indicada (o todas las del usuario)."""
    id_usuario = int(current_user["id_usuario"])
    if payload.endpoint:
        await db.execute(text("""
            UPDATE usuario_push_subscription
               SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :u
             WHERE id_usuario = :u AND endpoint = :e
        """), {"u": id_usuario, "e": payload.endpoint})
    else:
        await db.execute(text("""
            UPDATE usuario_push_subscription
               SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :u
             WHERE id_usuario = :u AND activo = TRUE
        """), {"u": id_usuario})
    await db.commit()
    return {"suscripto": False}
