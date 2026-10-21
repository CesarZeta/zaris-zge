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
from app.services.avisos import registrar_aviso_ciudadano

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
    """Push al ciudadano del reclamo con su estado actual. No-op sin suscripcion.

    Auditoria posterior al cierre (mig 112): es interna. No se avisa por los
    estados 'En auditoria'/'Auditado' (el vecino sigue viendo 'Resuelto'). El
    retrabajo de una auditoria observada SI avisa como cualquier reclamo: desde
    F4 (2026-10-20) el vecino lo ve en la app."""
    try:
        async with AsyncSessionLocal() as db:
            r = (await db.execute(text("""
                SELECT nro_reclamo, estado, id_ciudadano, resolucion
                FROM reclamos WHERE id_reclamo = :id
            """), {"id": id_reclamo})).mappings().first()
        if not r or not r["id_ciudadano"]:
            return
        if r["estado"] in ("En auditoría", "Auditado"):
            return
        id_c = int(r["id_ciudadano"])
        titulo = f"Tu reclamo {r['nro_reclamo'] or ''}".strip()
        cuerpo = f"Cambio de estado: {r['estado']}."
        resolucion = (r["resolucion"] or "").strip()
        if r["estado"] == "Resuelto" and resolucion:
            # La resolución que escribió quien lo cerró (mig 117, César 2026-10-21).
            cuerpo = f"Resuelto: {resolucion}"
        url = f"/reclamos/{id_reclamo}"
        # Bandeja persistente (mig 99) ANTES del push: queda aunque no haya
        # suscripcion. Mismo texto/URL que la notificacion.
        await registrar_aviso_ciudadano(
            id_c, "reclamo_estado", titulo, cuerpo[:1000], url,
            recurso_tipo="reclamo", recurso_id=id_reclamo,
        )
        corto = cuerpo if len(cuerpo) <= 180 else cuerpo[:177] + "…"
        await enviar_push_ciudadano(id_c, titulo=titulo, cuerpo=corto, url=url)
    except Exception as e:  # noqa: BLE001
        logger.warning("notificar_estado_reclamo(%s) fallo: %s", id_reclamo, e)


async def notificar_retrabajo_auditoria(id_retrabajo: int) -> None:
    """Aviso al vecino de que una auditoria de su reclamo resulto observada y se
    abrio un reclamo nuevo para rehacer el trabajo (PLAN_AUDITORIA_RECLAMOS.md F4).

    Mail (texto generico, sin la observacion del auditor) + bandeja + push. El mail
    sale solo si el vecino tiene email y el portal esta configurado (fail-closed,
    core/urls). Best-effort: cada canal falla por su cuenta sin cortar los demas."""
    from app.core.urls import url_portal_vecino
    from app.services.cuenta_vecino import _municipio_branding
    from app.services.email import enviar_mail_retrabajo_auditoria_ciudadano

    try:
        async with AsyncSessionLocal() as db:
            r = (await db.execute(text("""
                SELECT rt.nro_reclamo, rt.id_ciudadano, ro.nro_reclamo AS nro_origen,
                       c.nombre, c.apellido, c.email
                FROM reclamos rt
                JOIN reclamos ro ON ro.id_reclamo = rt.id_reclamo_origen_auditoria
                JOIN ciudadanos c ON c.id_ciudadano = rt.id_ciudadano
                WHERE rt.id_reclamo = :id
            """), {"id": id_retrabajo})).mappings().first()
            if not r:
                return
            municipio_nombre, municipio_logo_url = await _municipio_branding(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("notificar_retrabajo_auditoria(%s) fallo al leer: %s", id_retrabajo, e)
        return

    id_c = int(r["id_ciudadano"])
    nro_rt = r["nro_reclamo"] or f"REC-{id_retrabajo}"
    nro_or = r["nro_origen"] or "anterior"

    email = (r["email"] or "").strip()
    portal = url_portal_vecino()
    if email and "@" in email and portal:
        try:
            await enviar_mail_retrabajo_auditoria_ciudadano(
                to=email, nombre=r["nombre"] or "", apellido=r["apellido"] or "",
                nro_reclamo_origen=nro_or, nro_reclamo_retrabajo=nro_rt,
                municipio_nombre=municipio_nombre, portal_url=portal,
                municipio_logo_url=municipio_logo_url,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("mail de retrabajo %s fallo: %s", id_retrabajo, e)

    titulo = f"Tu reclamo {nro_or}"
    cuerpo = f"Vamos a volver a hacer el trabajo: abrimos el reclamo {nro_rt}."
    url = f"/reclamos/{id_retrabajo}"
    try:
        await registrar_aviso_ciudadano(
            id_c, "reclamo_estado", titulo, cuerpo, url,
            recurso_tipo="reclamo", recurso_id=id_retrabajo,
        )
        await enviar_push_ciudadano(id_c, titulo=titulo, cuerpo=cuerpo, url=url)
    except Exception as e:  # noqa: BLE001
        logger.warning("aviso/push de retrabajo %s fallo: %s", id_retrabajo, e)


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
        id_c = int(r["id_ciudadano_buc"])
        titulo = f"Tu reporte {r['numero_operativo'] or ''}".strip()
        cuerpo = f"Estado: {r['estado_nombre'] or 'actualizado'}."
        url = "/emergencias"
        # Bandeja persistente (mig 99) ANTES del push — ver notificar_estado_reclamo.
        await registrar_aviso_ciudadano(
            id_c, "emergencia_estado", titulo, cuerpo, url,
            recurso_tipo="emergencia", recurso_id=id_evento,
        )
        await enviar_push_ciudadano(id_c, titulo=titulo, cuerpo=cuerpo, url=url)
    except Exception as e:  # noqa: BLE001
        logger.warning("notificar_estado_emergencia(%s) fallo: %s", id_evento, e)


# ─── Push a USUARIOS INTERNOS (App de agentes `zaris-agentes`, mig 108) ─────
# Mismo mecanismo que el del ciudadano pero sobre `usuario_push_subscription`.
# Sin toggle de canal: la suscripcion activa ES el toggle (unsubscribe la apaga).

async def enviar_push_usuario(
    id_usuario: int,
    titulo: str,
    cuerpo: str,
    url: str = "/inicio",
) -> int:
    """Notifica a TODAS las suscripciones activas del usuario interno. Best-effort:
    loguea y devuelve cuantas se enviaron; jamas levanta excepcion. Sesion propia
    (se llama post-commit)."""
    try:
        cfg = await vapid_config()
        if not cfg["private"]:
            logger.debug("push deshabilitado (sin claves VAPID) — usuario %s", id_usuario)
            return 0

        async with AsyncSessionLocal() as db:
            subs = (await db.execute(text("""
                SELECT id_usuario_push_subscription, endpoint, p256dh, auth_secret
                FROM usuario_push_subscription
                WHERE id_usuario = :u AND activo = TRUE
            """), {"u": id_usuario})).mappings().all()
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
                vencidas.append(int(s["id_usuario_push_subscription"]))
            else:
                logger.warning("push a usuario %s fallo (status=%s)", id_usuario, status)

        if vencidas:
            async with AsyncSessionLocal() as db:
                await db.execute(text("""
                    UPDATE usuario_push_subscription
                       SET activo = FALSE, fecha_modificacion = NOW()
                     WHERE id_usuario_push_subscription = ANY(:ids)
                """), {"ids": vencidas})
                await db.commit()
            logger.info("push: %s suscripciones vencidas dadas de baja (usuario %s)",
                        len(vencidas), id_usuario)

        return enviadas
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.warning("enviar_push_usuario(%s) fallo: %s", id_usuario, e)
        return 0


async def notificar_ot_asignada(id_ot: int) -> None:
    """Aviso de OT OPERATIVA asignada (alta, reasignacion, delegacion): fila en la
    campana (`notificacion`, sin mail) + push a la app de agentes. Destinatarios:
    el agente asignado o, si la OT es de un equipo sin agente, TODOS sus
    integrantes activos con usuario — el destinatario final siempre es una
    persona (César 2026-10-20; antes una OT de cuadrilla no avisaba a nadie).
    OT de auditoria o sin destinatarios: no-op. Llamar POST-COMMIT, best-effort."""
    try:
        async with AsyncSessionLocal() as db:
            r = (await db.execute(text("""
                SELECT ot.nro_ot, ot.es_auditoria, ot.id_agente, ot.id_equipo,
                       ot.id_municipio, eq.nombre AS equipo_nombre,
                       tr.nombre AS tipo_nombre, r.direccion, r.prioridad
                FROM ordenes_trabajo ot
                JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
                LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
                LEFT JOIN equipos eq ON eq.id_equipo = ot.id_equipo
                WHERE ot.id_ot = :id AND ot.activo = TRUE
            """), {"id": id_ot})).mappings().first()
            if not r or r["es_auditoria"]:
                return
            usuarios = [int(x.id_usuario) for x in (await db.execute(text("""
                SELECT DISTINCT a.id_usuario
                FROM agentes a
                JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
                WHERE a.activo = TRUE
                  AND (a.id_agente = :ag
                       OR (CAST(:ag AS integer) IS NULL AND a.id_agente IN (
                             SELECT ea.id_agente FROM equipo_agentes ea
                              WHERE ea.id_equipo = :eq AND ea.activo = TRUE)))
            """), {"ag": r["id_agente"], "eq": r["id_equipo"]})).fetchall()]
            if not usuarios:
                logger.warning("notificar_ot_asignada(%s): sin destinatarios", id_ot)
                return
            titulo = f"Nueva orden de trabajo {r['nro_ot'] or ''}".strip()
            partes = [p for p in (r["tipo_nombre"], r["direccion"]) if p]
            cuerpo = " · ".join(partes) or "Te asignaron una orden de trabajo."
            if r["id_agente"] is None and r["equipo_nombre"]:
                cuerpo = f"Para tu cuadrilla {r['equipo_nombre']}. {cuerpo}"
            if r["prioridad"] == "Alta":
                cuerpo = f"Prioridad alta. {cuerpo}"
            # Campana del backoffice y de la app de agentes (la app navega por
            # recurso_tipo/recurso_id; el shell por url_destino).
            for uid in usuarios:
                await db.execute(text("""
                    INSERT INTO notificacion (id_usuario, tipo, titulo, mensaje, url_destino,
                                              recurso_tipo, recurso_id, id_municipio)
                    VALUES (:uid, 'ot_asignada', :tit, :msg, '#/ot/agente', 'ot', :rid, :mun)
                """), {"uid": uid, "tit": titulo, "msg": cuerpo, "rid": id_ot,
                       "mun": r["id_municipio"]})
            await db.commit()
        for uid in usuarios:
            await enviar_push_usuario(uid, titulo=titulo, cuerpo=cuerpo, url=f"/ot/{id_ot}")
    except Exception as e:  # noqa: BLE001
        logger.warning("notificar_ot_asignada(%s) fallo: %s", id_ot, e)
