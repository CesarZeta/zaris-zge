"""
ZARIS — Web Push a ciudadanos (App Vecinos, etapa E del plan).

Envia notificaciones push a las suscripciones activas de un ciudadano
(`ciudadano_push_subscription`, mig 53). Pensado para HOOKS post-commit
best-effort (patron encuestas §42): NUNCA levanta excepcion hacia el caller —
una falla de push no puede romper la operacion de negocio.

Claves VAPID: env vars (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_CLAIMS_EMAIL)
con fallback a `configuracion_general` (claves vapid_*, sembradas por entorno —
NO viven en el repo porque es publico). Cache TTL 5 min. Sin claves => modo
deshabilitado silencioso (log debug, no envia).

pywebpush es sincronico (requests) => se corre en thread (asyncio.to_thread).
410 Gone / 404 del push service => suscripcion vencida => soft-delete (§19).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger("zaris.push")

_VAPID_TTL_SEG = 300.0
_vapid_cache: dict = {"ts": 0.0, "public": "", "private": "", "claims_email": ""}


async def vapid_config() -> dict:
    """{public, private, claims_email} desde env vars o configuracion_general.

    Valores vacios = push deshabilitado (el caller decide; enviar_push_ciudadano
    simplemente no envia).
    """
    if settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY:
        return {
            "public": settings.VAPID_PUBLIC_KEY,
            "private": settings.VAPID_PRIVATE_KEY,
            "claims_email": settings.VAPID_CLAIMS_EMAIL or "mailto:notificaciones@zaris.com.ar",
        }
    now = time.monotonic()
    if now - _vapid_cache["ts"] < _VAPID_TTL_SEG:
        return {k: _vapid_cache[k] for k in ("public", "private", "claims_email")}
    pub = priv = email = ""
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(text(
                "SELECT clave, valor FROM configuracion_general "
                "WHERE clave IN ('vapid_public_key','vapid_private_key','vapid_claims_email')"
            ))
            vals = {row.clave: (row.valor or "").strip() for row in r.fetchall()}
        pub = vals.get("vapid_public_key", "")
        priv = vals.get("vapid_private_key", "")
        email = vals.get("vapid_claims_email", "") or "mailto:notificaciones@zaris.com.ar"
    except Exception as e:  # noqa: BLE001 — push nunca rompe nada
        logger.warning("vapid_config: no pude leer configuracion_general (%s)", e)
    _vapid_cache.update(ts=now, public=pub, private=priv, claims_email=email)
    return {"public": pub, "private": priv, "claims_email": email}


def _webpush_sync(sub_info: dict, payload: str, private_key: str, claims_email: str) -> Optional[int]:
    """Envio sincronico. Devuelve el status code del push service, o None si
    fallo antes de llegar al servicio (claves corruptas, red, etc.) — el catch
    generico evita que UNA suscripcion rota corte el envio a las demas."""
    from pywebpush import WebPushException, webpush  # import diferido: arranque sin la lib instalada no rompe

    try:
        resp = webpush(
            subscription_info=sub_info,
            data=payload,
            vapid_private_key=private_key,
            vapid_claims={"sub": claims_email},
            timeout=10,
        )
        return resp.status_code
    except WebPushException as e:
        return e.response.status_code if e.response is not None else None
    except Exception as e:  # noqa: BLE001 — suscripcion con claves invalidas, etc.
        logger.warning("webpush fallo pre-envio (%s): %s", type(e).__name__, e)
        return None


async def enviar_push_ciudadano(
    id_ciudadano: int,
    titulo: str,
    cuerpo: str,
    url: str = "/inicio",
) -> int:
    """Notifica a TODAS las suscripciones activas del ciudadano. Best-effort:
    loguea y devuelve cuantas se enviaron; jamas levanta excepcion.

    Abre sesion DB propia (se llama post-commit / en background, la sesion del
    request ya esta cerrada — patron §29 background tasks). Respeta el toggle
    `ciudadano_canal_preferido.canal_push` (sin fila => habilitado por default,
    espeja el DEFAULT TRUE de la tabla).
    """
    try:
        cfg = await vapid_config()
        if not cfg["private"]:
            logger.debug("push deshabilitado (sin claves VAPID) — ciudadano %s", id_ciudadano)
            return 0

        async with AsyncSessionLocal() as db:
            quiere = await db.scalar(text(
                "SELECT canal_push FROM ciudadano_canal_preferido WHERE id_ciudadano = :c"
            ), {"c": id_ciudadano})
            if quiere is False:
                return 0
            subs = (await db.execute(text("""
                SELECT id_ciudadano_push_subscription, endpoint, p256dh, auth_secret
                FROM ciudadano_push_subscription
                WHERE id_ciudadano = :c AND activo = TRUE
            """), {"c": id_ciudadano})).mappings().all()
        if not subs:
            return 0

        payload = json.dumps(
            {"titulo": titulo, "cuerpo": cuerpo, "url": url}, ensure_ascii=False
        )
        enviadas = 0
        vencidas: list[int] = []
        for s in subs:
            sub_info = {
                "endpoint": s["endpoint"],
                "keys": {"p256dh": s["p256dh"], "auth": s["auth_secret"]},
            }
            status = await asyncio.to_thread(
                _webpush_sync, sub_info, payload, cfg["private"], cfg["claims_email"]
            )
            if status in (200, 201):
                enviadas += 1
            elif status in (404, 410):
                vencidas.append(int(s["id_ciudadano_push_subscription"]))
            else:
                logger.warning("push a ciudadano %s fallo (status=%s)", id_ciudadano, status)

        if vencidas:
            async with AsyncSessionLocal() as db:
                await db.execute(text("""
                    UPDATE ciudadano_push_subscription
                       SET activo = FALSE, fecha_modificacion = NOW()
                     WHERE id_ciudadano_push_subscription = ANY(:ids)
                """), {"ids": vencidas})
                await db.commit()
            logger.info("push: %s suscripciones vencidas dadas de baja (ciudadano %s)",
                        len(vencidas), id_ciudadano)

        return enviadas
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.warning("enviar_push_ciudadano(%s) fallo: %s", id_ciudadano, e)
        return 0


# ─── Hooks de negocio (llamar POST-COMMIT, best-effort) ─────────────────────
# Leen el estado ACTUAL desde la DB (sesion propia) — el caller solo pasa el id,
# sin armar el mensaje. Cubren TODAS las vias de cambio de estado (memoria
# guard_subarea_cubre_todas_las_vias: un hook en una sola ruta deja mudas las
# demas).

async def notificar_estado_reclamo(id_reclamo: int) -> None:
    """Push al ciudadano del reclamo con su estado actual. No-op sin suscripcion."""
    try:
        async with AsyncSessionLocal() as db:
            r = (await db.execute(text("""
                SELECT nro_reclamo, estado, id_ciudadano
                FROM reclamos WHERE id_reclamo = :id
            """), {"id": id_reclamo})).mappings().first()
        if not r or not r["id_ciudadano"]:
            return
        await enviar_push_ciudadano(
            int(r["id_ciudadano"]),
            titulo=f"Tu reclamo {r['nro_reclamo'] or ''}".strip(),
            cuerpo=f"Cambio de estado: {r['estado']}.",
            url=f"/reclamos/{id_reclamo}",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("notificar_estado_reclamo(%s) fallo: %s", id_reclamo, e)


async def notificar_estado_emergencia(id_evento: int) -> None:
    """Push al denunciante (ciudadano BUC) de un evento de emergencias.
    Anonimos / contactos eventuales: no-op. Solo llega a quien tiene la app
    con push activo (el gating real es la suscripcion + canal_push)."""
    try:
        async with AsyncSessionLocal() as db:
            r = (await db.execute(text("""
                SELECT ev.numero_operativo, ev.id_ciudadano_buc,
                       es.nombre AS estado_nombre
                FROM emergencia_evento ev
                LEFT JOIN emergencia_estado es ON es.id_emergencia_estado = ev.id_estado
                WHERE ev.id_emergencia_evento = :id
            """), {"id": id_evento})).mappings().first()
        if not r or not r["id_ciudadano_buc"]:
            return
        await enviar_push_ciudadano(
            int(r["id_ciudadano_buc"]),
            titulo=f"Tu reporte {r['numero_operativo'] or ''}".strip(),
            cuerpo=f"Estado: {r['estado_nombre'] or 'actualizado'}.",
            url="/emergencias",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("notificar_estado_emergencia(%s) fallo: %s", id_evento, e)
