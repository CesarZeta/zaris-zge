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
from app.core.database import AsyncSessionLocal
from app.services.email import enviar_mail

logger = logging.getLogger("zaris.notificaciones")

EventoTramite = Literal["creacion", "pase", "transicion"]


async def _datos_tramite(db: AsyncSession, id_tramite: int) -> dict | None:
    """SELECT bulk de los datos del tramite que comparten todos los notificadores."""
    row = (await db.execute(
        text("""
            SELECT t.id_tramite, t.numero_expediente, t.asunto, t.id_municipio,
                   t.destinatario_actual_tipo,
                   COALESCE(t.id_subarea_actual, t.id_equipo_actual) AS destinatario_actual_id,
                   t.iniciador_tipo, t.id_subarea_iniciadora, t.id_agente_tomado_por,
                   tt.nombre AS tipo_nombre
              FROM tramite t
              JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
              JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite
             WHERE t.id_tramite = :tid AND t.activo = TRUE
        """),
        {"tid": id_tramite},
    )).fetchone()
    return dict(row._mapping) if row else None


async def _usuarios_por_subarea(db: AsyncSession, id_subarea: int) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT DISTINCT u.id_usuario, u.nombre, u.email
          FROM agentes a
          JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
         WHERE a.id_subarea = :did AND a.activo = TRUE
           AND u.email IS NOT NULL AND u.email <> ''
    """), {"did": id_subarea})).fetchall()
    return [dict(r._mapping) for r in rows]


async def _usuarios_por_equipo(db: AsyncSession, id_equipo: int) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT DISTINCT u.id_usuario, u.nombre, u.email
          FROM equipo_agentes ea
          JOIN agentes a ON a.id_agente = ea.id_agente AND a.activo = TRUE
          JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
         WHERE ea.id_equipo = :did AND ea.activo = TRUE
           AND u.email IS NOT NULL AND u.email <> ''
    """), {"did": id_equipo})).fetchall()
    return [dict(r._mapping) for r in rows]


async def _usuarios_por_agente(db: AsyncSession, id_agente: int) -> list[dict]:
    rows = (await db.execute(text("""
        SELECT u.id_usuario, u.nombre, u.email
          FROM agentes a
          JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
         WHERE a.id_agente = :aid AND a.activo = TRUE
           AND u.email IS NOT NULL AND u.email <> ''
    """), {"aid": id_agente})).fetchall()
    return [dict(r._mapping) for r in rows]


async def _emitir_a_usuarios(
    db: AsyncSession,
    usuarios: list[dict],
    *,
    tramite: dict,
    tipo_notif: str,
    titulo: str,
    mensaje: str,
    url_destino: str,
    background_tasks: Optional[BackgroundTasks],
    excluir_usuario: Optional[int] = None,
) -> int:
    """
    Inserta una fila en `notificacion` por cada usuario (excepto `excluir_usuario`)
    y encola el envio de email. Commitea al final. Devuelve la cantidad creada.

    Para usar despues de armar la lista de destinatarios concreta. Asume que el
    caller ya hizo el SELECT del tramite y armo el contenido del mensaje.
    """
    if not usuarios:
        return 0

    url_abs = _url_absoluta_tramite(tramite["numero_expediente"])
    html_body, text_body = _mail_body(titulo, mensaje, tramite["numero_expediente"], url_abs)

    creadas = 0
    envios_pendientes: list[tuple[int, str]] = []
    for u in usuarios:
        if excluir_usuario is not None and u["id_usuario"] == excluir_usuario:
            continue
        row_n = (await db.execute(
            text("""
                INSERT INTO notificacion (
                    id_usuario, tipo, titulo, mensaje, url_destino,
                    recurso_tipo, recurso_id, id_municipio
                ) VALUES (
                    :uid, :tipo, :tit, :msg, :url,
                    'tramite', :rid, :mun
                )
                RETURNING id_notificacion
            """),
            {
                "uid": u["id_usuario"],
                "tipo": tipo_notif,
                "tit": titulo,
                "msg": mensaje,
                "url": url_destino,
                "rid": tramite["id_tramite"],
                "mun": tramite.get("id_municipio"),
            },
        )).fetchone()
        creadas += 1
        envios_pendientes.append((row_n.id_notificacion, u["email"]))

    await db.commit()

    for id_notif, to in envios_pendientes:
        if background_tasks is not None:
            background_tasks.add_task(
                _enviar_mail_y_marcar, id_notif, to, titulo, html_body, text_body,
            )
        else:
            await _enviar_mail_y_marcar(id_notif, to, titulo, html_body, text_body)
    return creadas


async def _enviar_mail_y_marcar(
    id_notificacion: int,
    to: str,
    subject: str,
    body_html: str,
    body_text: str,
) -> None:
    """Envia el mail y marca la notificacion como enviada_mail=TRUE si tuvo exito.

    Pensado para correr como background task de FastAPI (que ejecuta async tasks
    en el event loop). Abre su propia sesion SQL porque la sesion del request
    original ya esta cerrada cuando esto corre.

    Fail-safe: cualquier error se logea pero no levanta — el mail puede haberse
    enviado y solo fallar el UPDATE; preferimos perder el flag a romper el flow.
    """
    try:
        ok = enviar_mail(to, subject, body_html, body_text)
        if not ok:
            return
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE notificacion
                       SET enviada_mail = TRUE,
                           enviada_mail_en = NOW(),
                           fecha_modificacion = NOW()
                     WHERE id_notificacion = :nid
                       AND activo = TRUE
                       AND enviada_mail = FALSE
                    """
                ),
                {"nid": id_notificacion},
            )
            await session.commit()
    except Exception as e:
        logger.error(
            "enviar_mail_y_marcar fallo (notif=%s, to=%s): %s",
            id_notificacion, to, e, exc_info=True,
        )


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

    Fail-safe: cualquier error se logea pero NO levanta.
    """
    try:
        tramite = await _datos_tramite(db, id_tramite)
        if not tramite:
            logger.warning("notificar_tramite: tramite %s no encontrado", id_tramite)
            return 0

        dest_tipo = tramite.get("destinatario_actual_tipo")
        dest_id = tramite.get("destinatario_actual_id")
        if not dest_tipo or not dest_id:
            logger.info(
                "notificar_tramite %s: sin destinatario actual, no se notifica",
                tramite["numero_expediente"],
            )
            return 0

        usuarios = await _resolver_destinatarios_usuarios(db, dest_tipo, dest_id)
        if not usuarios:
            logger.info(
                "notificar_tramite %s: destinatario %s/%s sin usuarios activos con email",
                tramite["numero_expediente"], dest_tipo, dest_id,
            )
            return 0

        titulo, mensaje = _titulo_y_mensaje(evento, tramite)
        creadas = await _emitir_a_usuarios(
            db, usuarios,
            tramite=tramite,
            tipo_notif=f"tramite_bandeja_{evento}",
            titulo=titulo,
            mensaje=mensaje,
            url_destino=_url_destino_tramite(tramite["numero_expediente"]),
            background_tasks=background_tasks,
        )
        logger.info(
            "notificar_tramite %s [%s]: %d notificaciones a %s/%s",
            tramite["numero_expediente"], evento, creadas, dest_tipo, dest_id,
        )
        return creadas
    except Exception as e:
        logger.error(
            "notificar_tramite_a_bandeja FALLO para tramite %s: %s",
            id_tramite, e, exc_info=True,
        )
        return 0


async def notificar_firma_pendiente(
    db: AsyncSession,
    id_tramite: int,
    id_tramite_firma: int,
    background_tasks: Optional[BackgroundTasks] = None,
) -> int:
    """
    Notifica al firmante asignado de una solicitud de firma pendiente.

    El firmante es polimorfico (agente / subarea / equipo). Se le envia notif
    a los usuarios correspondientes. Llamar despues de INSERT en `tramite_firma`
    o de `crear_firmas_pendientes()`.

    Fail-safe: cualquier error se logea pero NO levanta.
    """
    try:
        firma = (await db.execute(text("""
            SELECT id_tramite_firma, rol_intervencion,
                   id_agente_asignado, id_subarea_asignada, id_equipo_asignado
              FROM tramite_firma
             WHERE id_tramite_firma = :fid AND activo = TRUE AND estado = 'pendiente'
        """), {"fid": id_tramite_firma})).fetchone()
        if not firma:
            logger.info("notificar_firma_pendiente: firma %s no encontrada/no pendiente", id_tramite_firma)
            return 0

        tramite = await _datos_tramite(db, id_tramite)
        if not tramite:
            return 0

        if firma.id_agente_asignado:
            usuarios = await _usuarios_por_agente(db, firma.id_agente_asignado)
            scope = f"agente/{firma.id_agente_asignado}"
        elif firma.id_subarea_asignada:
            usuarios = await _usuarios_por_subarea(db, firma.id_subarea_asignada)
            scope = f"subarea/{firma.id_subarea_asignada}"
        elif firma.id_equipo_asignado:
            usuarios = await _usuarios_por_equipo(db, firma.id_equipo_asignado)
            scope = f"equipo/{firma.id_equipo_asignado}"
        else:
            logger.warning(
                "notificar_firma_pendiente %s: firma sin asignado polimorfico",
                id_tramite_firma,
            )
            return 0

        if not usuarios:
            logger.info(
                "notificar_firma_pendiente %s: %s sin usuarios con email",
                tramite["numero_expediente"], scope,
            )
            return 0

        rol = firma.rol_intervencion or "firma"
        numero = tramite["numero_expediente"]
        titulo = f"Te solicitan {rol}: {numero}"
        mensaje = (
            f"Se solicito tu {rol} para el tramite {numero} "
            f"({tramite.get('tipo_nombre') or 'tramite'})."
        )

        creadas = await _emitir_a_usuarios(
            db, usuarios,
            tramite=tramite,
            tipo_notif=f"tramite_firma_pendiente",
            titulo=titulo,
            mensaje=mensaje,
            url_destino=_url_destino_tramite(numero),
            background_tasks=background_tasks,
        )
        logger.info(
            "notificar_firma_pendiente %s [firma=%s, rol=%s]: %d notif a %s",
            numero, id_tramite_firma, rol, creadas, scope,
        )
        return creadas
    except Exception as e:
        logger.error(
            "notificar_firma_pendiente FALLO (tramite=%s, firma=%s): %s",
            id_tramite, id_tramite_firma, e, exc_info=True,
        )
        return 0


async def notificar_comentario_a_tomador(
    db: AsyncSession,
    id_tramite: int,
    id_usuario_que_comento: int,
    comentario: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> int:
    """
    Si el tramite esta tomado por un agente, notifica al usuario de ese agente
    cuando alguien que NO sea el (otro agente, supervisor) comenta.

    No notifica si:
    - el tramite no esta tomado.
    - el agente tomador no esta vinculado a un usuario activo con email.
    - el que comento es el mismo usuario que tomo el tramite.

    Fail-safe: cualquier error se logea pero NO levanta.
    """
    try:
        tramite = await _datos_tramite(db, id_tramite)
        if not tramite:
            return 0
        id_agente_tomador = tramite.get("id_agente_tomado_por")
        if not id_agente_tomador:
            return 0
        usuarios = await _usuarios_por_agente(db, id_agente_tomador)
        if not usuarios:
            return 0

        numero = tramite["numero_expediente"]
        snippet = (comentario or "").strip()
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."
        titulo = f"Nuevo comentario en {numero}"
        mensaje = (
            f"Hay un comentario nuevo en el tramite que tomaste ({numero}). "
            f"\"{snippet}\""
        )

        creadas = await _emitir_a_usuarios(
            db, usuarios,
            tramite=tramite,
            tipo_notif="tramite_comentario",
            titulo=titulo,
            mensaje=mensaje,
            url_destino=_url_destino_tramite(numero),
            background_tasks=background_tasks,
            excluir_usuario=id_usuario_que_comento,
        )
        logger.info(
            "notificar_comentario_a_tomador %s: %d notif (agente=%s, autor=%s)",
            numero, creadas, id_agente_tomador, id_usuario_que_comento,
        )
        return creadas
    except Exception as e:
        logger.error(
            "notificar_comentario_a_tomador FALLO (tramite=%s): %s",
            id_tramite, e, exc_info=True,
        )
        return 0


async def notificar_estado_final_a_iniciador(
    db: AsyncSession,
    id_tramite: int,
    estado_etiqueta: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> int:
    """
    Cuando un tramite llega a un estado final (es_final=TRUE), notifica al
    iniciador. Solo aplica para iniciador_tipo='area_interna' — los iniciadores
    ciudadano/empresa no tienen cuenta en el sistema.

    Fail-safe: cualquier error se logea pero NO levanta.
    """
    try:
        tramite = await _datos_tramite(db, id_tramite)
        if not tramite:
            return 0
        if tramite.get("iniciador_tipo") != "area_interna":
            return 0
        id_subarea_ini = tramite.get("id_subarea_iniciadora")
        if not id_subarea_ini:
            return 0
        usuarios = await _usuarios_por_subarea(db, id_subarea_ini)
        if not usuarios:
            return 0

        numero = tramite["numero_expediente"]
        titulo = f"Tramite {numero} cerrado: {estado_etiqueta}"
        mensaje = (
            f"El tramite {numero} que iniciaste llego al estado final "
            f"'{estado_etiqueta}'."
        )

        creadas = await _emitir_a_usuarios(
            db, usuarios,
            tramite=tramite,
            tipo_notif="tramite_estado_final",
            titulo=titulo,
            mensaje=mensaje,
            url_destino=_url_destino_tramite(numero),
            background_tasks=background_tasks,
        )
        logger.info(
            "notificar_estado_final %s [%s]: %d notif a subarea/%s",
            numero, estado_etiqueta, creadas, id_subarea_ini,
        )
        return creadas
    except Exception as e:
        logger.error(
            "notificar_estado_final_a_iniciador FALLO (tramite=%s): %s",
            id_tramite, e, exc_info=True,
        )
        return 0
