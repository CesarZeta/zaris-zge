"""
ZARIS API - Suscripciones Web Push del vecino (App Vecinos, etapa E).

Bajo /api/v1/publico/push/*. Guard get_current_ciudadano (JWT scope 'publico').

  - GET  /public-key   -> clave publica VAPID (la PWA la usa en pushManager.subscribe)
  - POST /subscribe    -> UPSERT de la suscripcion del navegador + canal_push=TRUE
  - POST /unsubscribe  -> baja logica de la suscripcion + canal_push=FALSE

La preferencia vive en ciudadano_canal_preferido.canal_push (mig 53): el toggle
de la PWA es la unica UI que la toca. El envio real vive en services/push.py.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip
from app.services.push import vapid_config

router = APIRouter(prefix="/api/v1/publico/push", tags=["publico-push"])
logger = logging.getLogger("zaris.publico_push")


class SubscribeIn(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=1000)
    p256dh: str = Field(..., min_length=10, max_length=300)
    auth: str = Field(..., min_length=5, max_length=100)


class UnsubscribeIn(BaseModel):
    endpoint: Optional[str] = Field(None, max_length=1000)
    """Sin endpoint => da de baja TODAS las suscripciones del ciudadano."""


async def _set_canal_push(db: AsyncSession, id_ciudadano: int, valor: bool) -> None:
    """UPSERT de la preferencia. La fila puede no existir para vecinos viejos."""
    await db.execute(text("""
        INSERT INTO ciudadano_canal_preferido (id_ciudadano, canal_push)
        VALUES (:c, :v)
        ON CONFLICT (id_ciudadano)
        DO UPDATE SET canal_push = :v, fecha_modificacion = NOW()
    """), {"c": id_ciudadano, "v": valor})


@router.get("/public-key")
async def public_key(
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Clave publica VAPID. 503 si el push no esta configurado en este deploy."""
    cfg = await vapid_config()
    if not cfg["public"]:
        raise HTTPException(503, "Las notificaciones push no estan configuradas")
    return {"public_key": cfg["public"]}


@router.post("/subscribe", status_code=201)
async def subscribe(
    payload: SubscribeIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Registra (o reactiva) la suscripcion del navegador y habilita el canal."""
    check_rate_limit(f"pushsub:{get_real_ip(request)}", max_requests=10, window_seconds=60)
    id_ciudadano = current["id_ciudadano"]
    ua = (request.headers.get("user-agent") or "")[:300]

    # UNIQUE (id_ciudadano, endpoint) — mig 53. Re-suscribirse reactiva y
    # refresca las claves (el navegador puede rotarlas).
    await db.execute(text("""
        INSERT INTO ciudadano_push_subscription
            (id_ciudadano, endpoint, p256dh, auth_secret, user_agent, id_municipio)
        VALUES (:c, :e, :p, :a, :ua, 1)
        ON CONFLICT (id_ciudadano, endpoint)
        DO UPDATE SET p256dh = :p, auth_secret = :a, user_agent = :ua,
                      activo = TRUE, fecha_modificacion = NOW()
    """), {"c": id_ciudadano, "e": payload.endpoint, "p": payload.p256dh,
           "a": payload.auth, "ua": ua})
    await _set_canal_push(db, id_ciudadano, True)
    await db.commit()
    return {"suscripto": True}


@router.post("/unsubscribe")
async def unsubscribe(
    payload: UnsubscribeIn,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Da de baja la suscripcion (o todas) y deshabilita el canal."""
    id_ciudadano = current["id_ciudadano"]
    if payload.endpoint:
        await db.execute(text("""
            UPDATE ciudadano_push_subscription
               SET activo = FALSE, fecha_modificacion = NOW()
             WHERE id_ciudadano = :c AND endpoint = :e
        """), {"c": id_ciudadano, "e": payload.endpoint})
    else:
        await db.execute(text("""
            UPDATE ciudadano_push_subscription
               SET activo = FALSE, fecha_modificacion = NOW()
             WHERE id_ciudadano = :c AND activo = TRUE
        """), {"c": id_ciudadano})
    await _set_canal_push(db, id_ciudadano, False)
    await db.commit()
    return {"suscripto": False}
