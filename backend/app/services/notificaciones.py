"""
ZARIS - Servicio de notificaciones in-app + email.

Patron:
- `notificar_tramite_a_bandeja(db, id_tramite, evento)` se llama desde los handlers
  de POST /tramites, /pase, /transicionar (cuando cambia el destinatario).
- Resuelve destinatarios (usuarios del subarea/equipo destinatario), inserta una fila
  por usuario en `notificacion` y dispara mail async.

Idempotencia: NO chequea duplicados. Cada evento inserta filas nuevas. Si el caller
llama dos veces, hay dos notifs (esperable, son eventos distintos).

Mail: el envio queda en background_tasks (FastAPI) cuando se le pasa, sino se logea
sincronamente (modo MOCK). No bloquea el endpoint.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.email import enviar_mail

logger = logging.getLogger("zaris.notificaciones")

EventoTramite = Literal["creacion", "pase", "transicion"]


async def _resolver_destinatarios_usuarios(
    db: AsyncSession,
    destinatario_tipo: str,
    destinatario_id: int,
) -> list[dict]:
    """
    Devuelve la lista de usuarios (id_usuario, nombre, email) a notificar segun el destinatario.

    - 'subarea': todos los agentes activos de esa subarea que esten vinculados a un usuario activo.
    - 'equipo': todos los agentes activos del equipo (via equipo_agentes) vinculados a usuario activo.

    Si no hay match (subarea sin agentes, equipo sin miembros, agentes sin usuario), devuelve [].
    Fail-open en caso de error de query: log + lista vacia.
    """
    try:
        if destinatario_tipo == "subarea":
            sql = """
                SELECT DISTINCT u.id_usuario, u.nombre, u.email
                FROM agentes a
                JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
                WHERE a.id_subarea = :did
                  AND a.activo = TRUE
                  AND u.email IS NOT NULL AND u.email <> ''
            """
        elif destinatario_tipo == "equipo":
            sql = """
                SELECT DISTINCT u.id_usuario, u.nombre, u.email
                FROM equipo_agentes ea
                JOIN agentes a ON a.id_agente = ea.id_agente AND a.activo = TRUE
                JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
                WHERE ea.id_equipo = :did
                  AND ea.activo = TRUE
                  AND u.email IS NOT NULL AND u.email <> ''
            """
        else:
            logger.warning("destinatario_tipo desconocido: %s", destinatario_tipo)
            return []

        rows = (await db.execute(text(sql), {"did": destinatario_id})).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception as e:
        logger.error("error resolviendo destinatarios %s/%s: %s", destinatario_tipo, destinatario_id, e)
        return []


def _url_destino_tramite(numero_expediente: str) -> str:
    """URL relativa para in-app + URL absoluta para mail."""
    return f"#/tramites/{numero_expediente}"


def _url_absoluta_tramite(numero_expediente: str) -> str:
    base = settings.APP_BASE_URL.rstrip("/")
    return f"{base}/#/tramites/{numero_expediente}"


def _titulo_y_mensaje(evento: EventoTramite, tramite: dict) -> tuple[str, str]:
    numero = tramite["numero_expediente"]
    asunto = tramite.get("asunto") or "(sin asunto)"
    tipo_nombre = tramite.get("tipo_nombre") or "Tramite"

    if evento == "creacion":
        titulo = f"Nuevo tramite en tu bandeja: {numero}"
        mensaje = f"Se creo el tramite {numero} ({tipo_nombre}): {asunto}."
    elif evento == "pase":
        titulo = f"Tramite recibido por pase: {numero}"
        mensaje = f"El tramite {numero} ({tipo_nombre}) llego a tu bandeja por pase: {asunto}."
    elif evento == "transicion":
        titulo = f"Tramite recibido por transicion: {numero}"
        mensaje = f"El tramite {numero} ({tipo_nombre}) llego a tu bandeja por cambio de estado: {asunto}."
    else:
        titulo = f"Tramite {numero}"
        mensaje = asunto
    return titulo, mensaje


def _mail_body(titulo: str, mensaje: str, numero: str, url_abs: str) -> tuple[str, str]:
    """Devuelve (html, text)."""
    html = f"""\
<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;color:#26251e;line-height:1.5;max-width:560px;margin:auto;padding:24px">
  <h2 style="color:#26251e;font-size:18px;margin:0 0 12px">{titulo}</h2>
  <p style="margin:0 0 16px">{mensaje}</p>
  <p style="margin:0 0 24px">
    <a href="{url_abs}"
       style="background:#f54e00;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;display:inline-block;font-weight:500">
       Abrir tramite {numero}
    </a>
  </p>
  <p style="margin:24px 0 0;font-size:12px;color:#999">
    Recibis este mail porque sos miembro activo del destinatario de este tramite en ZARIS.
  </p>
</body></html>"""
    text_body = f"{titulo}\n\n{mensaje}\n\nAbrir: {url_abs}\n"
    return html, text_body


async def notificar_tramite_a_bandeja(
    db: AsyncSession,
    id_tramite: int,
    evento: EventoTramite,
    background_tasks: Optional[BackgroundTasks] = None,
) -> int:
    """
    Notifica al destinatario actual del tramite que tiene algo nuevo en su bandeja.

    Hace:
    1. SELECT del tramite (numero, asunto, tipo, destinatario actual, id_municipio)
    2. Resuelve usuarios destinatarios
    3. INSERT en notificacion (una fila por usuario)
    4. Dispara mail async via background_tasks (si se paso); sino sincronicamente.

    Returns: cantidad de notificaciones creadas.

    Fail-safe: cualquier error se logea pero NO levanta — no queremos romper la creacion
    del tramite por una notificacion fallida.
    """
    try:
        row = (await db.execute(
            text("""
                SELECT t.id_tramite, t.numero_expediente, t.asunto, t.id_municipio,
                       t.destinatario_actual_tipo,
                       COALESCE(t.id_subarea_actual, t.id_equipo_actual) AS destinatario_actual_id,
                       tt.nombre AS tipo_nombre
                  FROM tramite t
                  JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
                  JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite
                 WHERE t.id_tramite = :tid AND t.activo = TRUE
            """),
            {"tid": id_tramite},
        )).fetchone()
        if not row:
            logger.warning("notificar_tramite: tramite %s no encontrado", id_tramite)
            return 0

        tramite = dict(row._mapping)
        dest_tipo = tramite.get("destinatario_actual_tipo")
        dest_id = tramite.get("destinatario_actual_id")
        if not dest_tipo or not dest_id:
            logger.info("notificar_tramite %s: sin destinatario actual, no se notifica", tramite["numero_expediente"])
            return 0

        usuarios = await _resolver_destinatarios_usuarios(db, dest_tipo, dest_id)
        if not usuarios:
            logger.info(
                "notificar_tramite %s: destinatario %s/%s sin usuarios activos con email",
                tramite["numero_expediente"], dest_tipo, dest_id,
            )
            return 0

        titulo, mensaje = _titulo_y_mensaje(evento, tramite)
        url_dest = _url_destino_tramite(tramite["numero_expediente"])
        url_abs = _url_absoluta_tramite(tramite["numero_expediente"])
        html_body, text_body = _mail_body(titulo, mensaje, tramite["numero_expediente"], url_abs)

        creadas = 0
        for u in usuarios:
            await db.execute(
                text("""
                    INSERT INTO notificacion (
                        id_usuario, tipo, titulo, mensaje, url_destino,
                        recurso_tipo, recurso_id, id_municipio
                    ) VALUES (
                        :uid, :tipo, :tit, :msg, :url,
                        'tramite', :rid, :mun
                    )
                """),
                {
                    "uid": u["id_usuario"],
                    "tipo": f"tramite_bandeja_{evento}",
                    "tit": titulo,
                    "msg": mensaje,
                    "url": url_dest,
                    "rid": tramite["id_tramite"],
                    "mun": tramite.get("id_municipio"),
                },
            )
            creadas += 1

            # mail async (background) o sync (mock log)
            if background_tasks is not None:
                background_tasks.add_task(enviar_mail, u["email"], titulo, html_body, text_body)
            else:
                enviar_mail(u["email"], titulo, html_body, text_body)

        await db.commit()
        logger.info(
            "notificar_tramite %s [%s]: %d notificaciones a %s/%s",
            tramite["numero_expediente"], evento, creadas, dest_tipo, dest_id,
        )
        return creadas
    except Exception as e:
        logger.error("notificar_tramite_a_bandeja FALLO para tramite %s: %s", id_tramite, e, exc_info=True)
        return 0
