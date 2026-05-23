# -*- coding: utf-8 -*-
"""
ZARIS - Logica de negocio del modulo Encuestas (CSAT). Migracion 57.

Encuestas de satisfaccion disparadas al cierre de reclamos (estado 'Resuelto').
Sin endpoints todavia: este modulo concentra la logica que los endpoints (fase 2C+)
y un job dispatcher (cron externo) van a consumir.

Reutiliza el sender de email centralizado: app.services.email.enviar_mail (bool).
NO existe `email_service.enviar_email` — la auditoria 2A confirmo que el servicio real
es `enviar_mail(to, subject, body_html, body_text=None, from_override=None) -> bool`.

Reglas de logging: nunca loguear email completo del ciudadano, texto libre de respuestas
ni token completo. Tokens se truncan a 8 chars con `_tok()`.

Notas sobre el schema (verificado contra zaris_dev / prod 2026-05-22):
  - El estado cerrado que dispara encuesta es 'Resuelto' (NO 'Cancelado': un reclamo
    cancelado no tiene una atencion que valorar).
  - reclamos.id_subarea puede ser NULL en reclamos legacy (§27). La subarea real se
    deriva via id_tipo_reclamo -> tipo_reclamo.id_subarea, con fallback a r.id_subarea.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.email import enviar_mail

logger = logging.getLogger("zaris.encuestas")

# ── Constantes de negocio ────────────────────────────────────────────────────
ESTADO_CERRADO_RECLAMO = "Resuelto"
DIAS_EXPIRACION_ENVIO = 15           # vigencia del link de la encuesta
DIAS_ANTIFATIGA = 30                 # no encuestar 2 veces al mismo ciudadano/subarea
HORAS_DELAY_ENVIO = 24               # esperar tras el cierre antes de mandar
MAX_INTENTOS_ENVIO = 3
LARGO_DESCRIPCION_CORTA = 80

# Motivos de no-creacion (segundo elemento del tuple de crear_envio_para_reclamo).
# Los endpoints los mapean a mensajes 422.
MOTIVO_OK = "ok"
MOTIVO_DESACTIVADAS = "Encuestas deshabilitadas"
MOTIVO_NO_RESUELTO = "Reclamo no existe o no está en estado Resuelto"
MOTIVO_YA_EXISTE = "Ya existe envío para este reclamo"
MOTIVO_SIN_EMAIL = "Ciudadano sin email válido"
MOTIVO_ANTIFATIGA = "Anti-fatiga: ya recibió encuesta del área en últimos 30 días"
MOTIVO_SIN_PLANTILLA = "No hay plantilla de encuesta activa para reclamos"
MOTIVO_ERROR = "Error interno al crear el envío"


def _tok(token) -> str:
    """Trunca un token para loguear sin exponerlo entero."""
    s = str(token)
    return (s[:8] + "...") if len(s) > 8 else s


def _now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# Toggle global
# =============================================================================

async def encuestas_estan_activas(db: AsyncSession) -> bool:
    """Lee configuracion_general.encuestas_activas. False si no existe o != 'true'."""
    try:
        row = (await db.execute(text("""
            SELECT valor FROM configuracion_general
             WHERE clave = 'encuestas_activas' AND activo = TRUE
             LIMIT 1
        """))).fetchone()
        return bool(row) and str(row[0]).strip().lower() == "true"
    except Exception as e:
        logger.error("encuestas_estan_activas fallo: %s", e)
        return False


# =============================================================================
# Crear envio
# =============================================================================

async def crear_envio_para_reclamo(db: AsyncSession, id_reclamo: int):
    """
    Crea un encuesta_envio en estado 'pendiente' para un reclamo cerrado.

    Devuelve tuple (fila_mapping | None, motivo). El motivo es una de las constantes
    MOTIVO_* (string legible) que los endpoints mapean a mensajes 422. En exito,
    motivo == MOTIVO_OK.

    Idempotente: si ya hay un envio para el reclamo, devuelve (None, MOTIVO_YA_EXISTE).
    """
    try:
        # 1. Toggle
        if not await encuestas_estan_activas(db):
            logger.info("crear_envio: encuestas desactivadas, skip reclamo=%s", id_reclamo)
            return None, MOTIVO_DESACTIVADAS

        # 2. Reclamo existe + cerrado. Subarea derivada via tipo_reclamo (§27).
        rec = (await db.execute(text("""
            SELECT r.id_reclamo, r.nro_reclamo, r.estado, r.id_ciudadano,
                   r.id_municipio,
                   COALESCE(tr.id_subarea, r.id_subarea) AS id_subarea,
                   c.email AS email_ciudadano
              FROM reclamos r
              JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
              LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
             WHERE r.id_reclamo = :id
             LIMIT 1
        """), {"id": id_reclamo})).fetchone()

        if rec is None:
            logger.info("crear_envio: reclamo=%s no existe", id_reclamo)
            return None, MOTIVO_NO_RESUELTO
        rec = rec._mapping
        if rec["estado"] != ESTADO_CERRADO_RECLAMO:
            logger.info("crear_envio: reclamo=%s no esta cerrado (estado=%s)",
                        id_reclamo, rec["estado"])
            return None, MOTIVO_NO_RESUELTO

        # 3. Idempotencia: no duplicar envio por reclamo (activo)
        ya = (await db.execute(text("""
            SELECT 1 FROM encuesta_envio
             WHERE id_reclamo = :id AND activo = TRUE LIMIT 1
        """), {"id": id_reclamo})).fetchone()
        if ya:
            logger.info("crear_envio: reclamo=%s ya tiene envio, skip", id_reclamo)
            return None, MOTIVO_YA_EXISTE

        # 4. Email valido
        email = (rec["email_ciudadano"] or "").strip()
        if not email or "@" not in email:
            logger.info("crear_envio: ciudadano del reclamo=%s sin email valido", id_reclamo)
            return None, MOTIVO_SIN_EMAIL

        # 5. Anti-fatiga: mismo ciudadano + misma subarea en los ultimos 30 dias
        id_subarea = rec["id_subarea"]
        if id_subarea is not None:
            reciente = (await db.execute(text("""
                SELECT 1
                  FROM encuesta_envio ee
                 WHERE ee.id_ciudadano = :cid
                   AND ee.id_subarea = :sub
                   AND ee.activo = TRUE
                   AND ee.fecha_alta > NOW() - make_interval(days => :dias)
                 LIMIT 1
            """), {"cid": rec["id_ciudadano"], "sub": id_subarea,
                   "dias": DIAS_ANTIFATIGA})).fetchone()
            if reciente:
                logger.info("crear_envio: anti-fatiga, ciudadano=%s ya encuestado en subarea=%s (<%sd)",
                            rec["id_ciudadano"], id_subarea, DIAS_ANTIFATIGA)
                return None, MOTIVO_ANTIFATIGA

        # plantilla activa tipo='reclamos'
        plantilla = (await db.execute(text("""
            SELECT id_encuesta_plantilla FROM encuesta_plantilla
             WHERE tipo = 'reclamos' AND activo = TRUE
             ORDER BY id_encuesta_plantilla LIMIT 1
        """))).fetchone()
        if plantilla is None:
            logger.warning("crear_envio: no hay plantilla activa tipo='reclamos'")
            return None, MOTIVO_SIN_PLANTILLA

        token = uuid.uuid4()
        fecha_exp = _now() + timedelta(days=DIAS_EXPIRACION_ENVIO)

        nuevo = (await db.execute(text("""
            INSERT INTO encuesta_envio (
                id_plantilla, id_ciudadano, id_reclamo, token_unico,
                email_destino_snapshot, fecha_expiracion, estado,
                id_municipio, id_subarea
            ) VALUES (
                :pid, :cid, :rid, :token,
                :email, :fexp, 'pendiente',
                :mun, :sub
            )
            RETURNING id_encuesta_envio, token_unico, estado, id_reclamo
        """), {
            "pid": plantilla[0], "cid": rec["id_ciudadano"], "rid": id_reclamo,
            "token": str(token), "email": email, "fexp": fecha_exp,
            "mun": rec["id_municipio"], "sub": id_subarea,
        })).fetchone()
        await db.commit()

        logger.info("crear_envio: OK reclamo=%s envio=%s token=%s",
                    id_reclamo, nuevo[0], _tok(nuevo[1]))
        return nuevo._mapping, MOTIVO_OK
    except Exception as e:
        await db.rollback()
        logger.error("crear_envio_para_reclamo fallo (reclamo=%s): %s", id_reclamo, e)
        return None, MOTIVO_ERROR


# =============================================================================
# Branding del municipio (header del email)
# =============================================================================

async def _branding(db: AsyncSession) -> dict:
    rows = (await db.execute(text("""
        SELECT clave, valor FROM configuracion_general
         WHERE clave IN ('municipio_nombre', 'municipio_logo_url')
    """))).fetchall()
    cfg = {r[0]: (r[1] or "").strip() for r in rows}
    return {
        "nombre": cfg.get("municipio_nombre") or "Municipio",
        "logo_url": cfg.get("municipio_logo_url") or "",
    }


def _absolutizar_url(u: str) -> str:
    """Devuelve una URL absoluta para usar en un email. Si `u` ya es absoluta
    (http/https) la devuelve tal cual; si es relativa la prefija con
    FRONTEND_BASE_URL. Vacío → vacío (el template oculta el <img>)."""
    u = (u or "").strip()
    if not u:
        return ""
    if u.startswith("http://") or u.startswith("https://"):
        return u
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}/{u.lstrip('/')}"


def _fmt_fecha(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.strftime("%d/%m/%Y")


def _render_email_encuesta(
    *, nombre_ciudadano: str, nro_reclamo: str, descripcion: str,
    fecha_cierre: Optional[datetime], fecha_expiracion: Optional[datetime],
    url: str, municipio_nombre: str, municipio_logo_url: str,
) -> tuple[str, str, str]:
    """Devuelve (asunto, html, texto_plano)."""
    asunto = f"Tu opinión sobre el reclamo #{nro_reclamo} nos importa"

    desc = (descripcion or "").strip()
    if len(desc) > LARGO_DESCRIPCION_CORTA:
        desc = desc[:LARGO_DESCRIPCION_CORTA].rstrip() + "…"
    desc_esc = _esc(desc)
    nombre_esc = _esc(nombre_ciudadano or "")
    muni_esc = _esc(municipio_nombre)
    f_cierre = _fmt_fecha(fecha_cierre)
    f_exp = _fmt_fecha(fecha_expiracion)

    logo_html = (
        f'<img src="{_esc(municipio_logo_url)}" alt="{muni_esc}" '
        f'style="max-height:48px;margin-bottom:8px;">'
        if municipio_logo_url else ""
    )

    html = f"""\
<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"></head>
<body style="margin:0;background:#f2f1ed;font-family:Arial,Helvetica,sans-serif;color:#26251e;">
  <div style="max-width:560px;margin:0 auto;padding:24px;">
    <div style="text-align:center;padding-bottom:16px;border-bottom:1px solid rgba(38,37,30,.1);">
      {logo_html}
      <div style="font-size:14px;font-weight:bold;letter-spacing:.04em;text-transform:uppercase;color:#26251e;">{muni_esc}</div>
    </div>
    <div style="background:#f7f7f4;border-radius:12px;padding:24px;margin-top:16px;">
      <p style="font-size:16px;margin:0 0 12px;">Hola {nombre_esc},</p>
      <p style="font-size:15px;line-height:1.5;margin:0 0 12px;">
        Tu reclamo &ldquo;{desc_esc}&rdquo; fue cerrado el {f_cierre}.
        Nos gustaría saber qué te pareció la atención que recibiste.
        La encuesta toma menos de 1 minuto.
      </p>
      <div style="text-align:center;margin:24px 0;">
        <a href="{_esc(url)}" style="display:inline-block;background:#f54e00;color:#fff;
           text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:bold;
           font-size:15px;letter-spacing:.03em;">RESPONDER ENCUESTA</a>
      </div>
      <p style="font-size:13px;color:rgba(38,37,30,.55);margin:0;">
        Este link expira el {f_exp}. Gracias por ayudarnos a mejorar.
      </p>
    </div>
    <p style="text-align:center;font-size:13px;color:rgba(38,37,30,.55);margin-top:16px;">{muni_esc}</p>
  </div>
</body></html>"""

    texto = (
        f"Hola {nombre_ciudadano or ''},\n\n"
        f"Tu reclamo \"{desc}\" fue cerrado el {f_cierre}.\n"
        f"Nos gustaría saber qué te pareció la atención que recibiste. "
        f"La encuesta toma menos de 1 minuto.\n\n"
        f"Responder encuesta:\n{url}\n\n"
        f"Este link expira el {f_exp}. Gracias por ayudarnos a mejorar.\n\n"
        f"{municipio_nombre}\n"
    )
    return asunto, html, texto


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# =============================================================================
# Enviar email de la encuesta
# =============================================================================

async def enviar_email_encuesta(db: AsyncSession, id_encuesta_envio: int) -> bool:
    """Toma un envio 'pendiente', arma y manda el email. Actualiza estado/intentos."""
    try:
        env = (await db.execute(text("""
            SELECT ee.id_encuesta_envio, ee.token_unico, ee.estado,
                   ee.email_destino_snapshot, ee.fecha_expiracion, ee.intentos_envio,
                   r.nro_reclamo, r.descripcion, r.fecha_cierre,
                   c.nombre AS nombre_ciudadano
              FROM encuesta_envio ee
              JOIN reclamos r   ON r.id_reclamo = ee.id_reclamo
              JOIN ciudadanos c ON c.id_ciudadano = ee.id_ciudadano
             WHERE ee.id_encuesta_envio = :id AND ee.activo = TRUE
             LIMIT 1
        """), {"id": id_encuesta_envio})).fetchone()

        if env is None:
            logger.info("enviar_email: envio=%s no existe", id_encuesta_envio)
            return False
        env = env._mapping
        if env["estado"] != "pendiente":
            logger.info("enviar_email: envio=%s no esta pendiente (estado=%s), skip",
                        id_encuesta_envio, env["estado"])
            return False

        url = f"{settings.FRONTEND_BASE_URL}/frontend/encuesta.html?token={env['token_unico']}"
        brand = await _branding(db)
        # El logo del municipio puede estar guardado como ruta relativa
        # (ej. '/design-system/assets/...'). En un cliente de email NO hay origen,
        # así que hay que entregar una URL absoluta o el <img> queda roto.
        logo_url = _absolutizar_url(brand["logo_url"])
        asunto, html, texto = _render_email_encuesta(
            nombre_ciudadano=env["nombre_ciudadano"],
            nro_reclamo=env["nro_reclamo"] or str(id_encuesta_envio),
            descripcion=env["descripcion"],
            fecha_cierre=env["fecha_cierre"],
            fecha_expiracion=env["fecha_expiracion"],
            url=url,
            municipio_nombre=brand["nombre"],
            municipio_logo_url=logo_url,
        )

        ok = enviar_mail(env["email_destino_snapshot"], asunto, html, texto,
                         from_override=_from_municipio(brand["nombre"]))

        if ok:
            await db.execute(text("""
                UPDATE encuesta_envio
                   SET estado = 'enviada', fecha_envio = NOW(),
                       intentos_envio = intentos_envio + 1, fecha_modificacion = NOW()
                 WHERE id_encuesta_envio = :id
            """), {"id": id_encuesta_envio})
            await db.commit()
            logger.info("enviar_email: OK envio=%s token=%s",
                        id_encuesta_envio, _tok(env["token_unico"]))
            return True

        # fallo
        intentos = (env["intentos_envio"] or 0) + 1
        nuevo_estado = "error_envio" if intentos >= MAX_INTENTOS_ENVIO else "pendiente"
        await db.execute(text("""
            UPDATE encuesta_envio
               SET intentos_envio = :int, estado = :est,
                   ultimo_error_envio = :err, fecha_modificacion = NOW()
             WHERE id_encuesta_envio = :id
        """), {"int": intentos, "est": nuevo_estado,
               "err": "enviar_mail devolvio False"[:500], "id": id_encuesta_envio})
        await db.commit()
        logger.warning("enviar_email: fallo envio=%s intentos=%s estado=%s",
                       id_encuesta_envio, intentos, nuevo_estado)
        return False
    except Exception as e:
        await db.rollback()
        logger.error("enviar_email_encuesta fallo (envio=%s): %s", id_encuesta_envio, e)
        try:
            await db.execute(text("""
                UPDATE encuesta_envio
                   SET intentos_envio = intentos_envio + 1,
                       ultimo_error_envio = :err,
                       estado = CASE WHEN intentos_envio + 1 >= :max THEN 'error_envio' ELSE estado END,
                       fecha_modificacion = NOW()
                 WHERE id_encuesta_envio = :id AND estado = 'pendiente'
            """), {"err": str(e)[:500], "max": MAX_INTENTOS_ENVIO, "id": id_encuesta_envio})
            await db.commit()
        except Exception:
            await db.rollback()
        return False


def _from_municipio(nombre: str) -> Optional[str]:
    """Display name del municipio sobre el address SMTP_FROM (§38). None si no hay FROM."""
    base = settings.SMTP_FROM
    if not base:
        return None
    # extraer el address de SMTP_FROM ("ZARIS <noreply@x>" o "noreply@x")
    addr = base.split("<")[-1].rstrip(">").strip() if "<" in base else base.strip()
    return f"{nombre} <{addr}>"


# =============================================================================
# Registrar apertura del link
# =============================================================================

async def registrar_apertura(db: AsyncSession, token: str):
    """Marca el envio como 'abierta' la primera vez que se abre el link. Devuelve el envio o None."""
    try:
        env = (await db.execute(text("""
            SELECT id_encuesta_envio, estado, fecha_apertura, fecha_expiracion
              FROM encuesta_envio
             WHERE token_unico = CAST(:t AS uuid) AND activo = TRUE
             LIMIT 1
        """), {"t": token})).fetchone()
        if env is None:
            logger.info("registrar_apertura: token=%s invalido", _tok(token))
            return None
        env = env._mapping

        if env["estado"] in ("completada", "expirada", "error_envio"):
            logger.info("registrar_apertura: token=%s estado=%s, no apto",
                        _tok(token), env["estado"])
            return None
        if env["fecha_expiracion"] and env["fecha_expiracion"] < _now():
            logger.info("registrar_apertura: token=%s expirado", _tok(token))
            return None

        if env["fecha_apertura"] is None:
            await db.execute(text("""
                UPDATE encuesta_envio
                   SET fecha_apertura = NOW(), estado = 'abierta', fecha_modificacion = NOW()
                 WHERE id_encuesta_envio = :id AND fecha_apertura IS NULL
            """), {"id": env["id_encuesta_envio"]})
            await db.commit()

        return (await db.execute(text("""
            SELECT * FROM encuesta_envio WHERE id_encuesta_envio = :id
        """), {"id": env["id_encuesta_envio"]})).fetchone()._mapping
    except Exception as e:
        await db.rollback()
        logger.error("registrar_apertura fallo (token=%s): %s", _tok(token), e)
        return None


# =============================================================================
# Registrar respuesta del formulario publico
# =============================================================================

def _rama_desde_clasificacion(clasificacion: int) -> str:
    if clasificacion <= 2:
        return "insatisfechos"
    if clasificacion == 3:
        return "neutrales"
    return "satisfechos"


async def registrar_respuesta(
    db: AsyncSession,
    token: str,
    clasificacion_inicial: int,
    respuestas: list[dict],
    tiempo_completado_seg: Optional[int],
    ip_origen: Optional[str],
) -> dict:
    """
    Procesa una respuesta del formulario publico. Calcula rama_seguida SERVER-SIDE.
    respuestas: [{id_pregunta, valor_numerico?, valor_texto?, id_opcion_seleccionada?}]
    Devuelve {"ok": bool, "mensaje"|"error": str}.
    """
    try:
        # 1. Validar clasificacion
        if not isinstance(clasificacion_inicial, int) or not (1 <= clasificacion_inicial <= 5):
            return {"ok": False, "error": "clasificacion_inicial debe estar entre 1 y 5"}

        # 2. Token apto
        env = (await db.execute(text("""
            SELECT ee.id_encuesta_envio, ee.id_plantilla, ee.estado, ee.fecha_expiracion,
                   ee.id_reclamo, ee.id_ciudadano, ee.id_municipio, ee.id_subarea,
                   r.nro_reclamo,
                   COALESCE(tr.id_subarea, r.id_subarea) AS subarea_reclamo
              FROM encuesta_envio ee
              JOIN reclamos r ON r.id_reclamo = ee.id_reclamo
              LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
             WHERE ee.token_unico = CAST(:t AS uuid) AND ee.activo = TRUE
             LIMIT 1
        """), {"t": token})).fetchone()
        if env is None:
            return {"ok": False, "error": "Token inválido"}
        env = env._mapping
        if env["estado"] not in ("enviada", "abierta"):
            return {"ok": False, "error": f"La encuesta no está disponible (estado: {env['estado']})"}
        if env["fecha_expiracion"] and env["fecha_expiracion"] < _now():
            return {"ok": False, "error": "El link de la encuesta expiró"}

        rama = _rama_desde_clasificacion(clasificacion_inicial)

        # 3. Cargar preguntas de la plantilla (validacion de pertenencia + obligatorias)
        preguntas = (await db.execute(text("""
            SELECT id_encuesta_pregunta, tipo, rama, obligatoria
              FROM encuesta_pregunta
             WHERE id_plantilla = :pid AND activo = TRUE
        """), {"pid": env["id_plantilla"]})).fetchall()
        preguntas = {p[0]: {"tipo": p[1], "rama": p[2], "obligatoria": p[3]} for p in preguntas}

        ids_respondidas = set()
        for r in respuestas:
            qid = r.get("id_pregunta")
            if qid not in preguntas:
                return {"ok": False, "error": f"Pregunta {qid} no pertenece a esta encuesta"}
            ids_respondidas.add(qid)

        # obligatorias de la rama (o 'todos') deben estar todas
        faltantes = [
            qid for qid, p in preguntas.items()
            if p["obligatoria"] and p["rama"] in ("todos", rama) and qid not in ids_respondidas
        ]
        if faltantes:
            return {"ok": False, "error": f"Faltan respuestas obligatorias: {faltantes}"}

        # solicita_contacto: SI en la pregunta si_no de la rama insatisfechos (P7)
        solicita_contacto = False
        if rama == "insatisfechos":
            for r in respuestas:
                p = preguntas.get(r.get("id_pregunta"))
                if p and p["tipo"] == "si_no" and p["rama"] == "insatisfechos":
                    if (r.get("valor_numerico") in (1, "1")) or (str(r.get("valor_texto", "")).lower() in ("si", "sí", "true")):
                        solicita_contacto = True

        # 4. Inserts en transaccion
        resp = (await db.execute(text("""
            INSERT INTO encuesta_respuesta (
                id_envio, clasificacion_inicial, rama_seguida,
                tiempo_completado_seg, solicita_contacto, ip_origen,
                id_municipio, id_subarea
            ) VALUES (
                :env, :clf, :rama, :tiempo, :sc, :ip, :mun, :sub
            )
            RETURNING id_encuesta_respuesta
        """), {
            "env": env["id_encuesta_envio"], "clf": clasificacion_inicial, "rama": rama,
            "tiempo": tiempo_completado_seg, "sc": solicita_contacto, "ip": ip_origen,
            "mun": env["id_municipio"], "sub": env["id_subarea"],
        })).fetchone()
        id_respuesta = resp[0]

        for r in respuestas:
            await db.execute(text("""
                INSERT INTO encuesta_respuesta_detalle (
                    id_respuesta, id_pregunta, valor_numerico, valor_texto,
                    id_opcion_seleccionada, id_municipio, id_subarea
                ) VALUES (
                    :rid, :qid, :vn, :vt, :op, :mun, :sub
                )
            """), {
                "rid": id_respuesta, "qid": r["id_pregunta"],
                "vn": r.get("valor_numerico"), "vt": r.get("valor_texto"),
                "op": r.get("id_opcion_seleccionada"),
                "mun": env["id_municipio"], "sub": env["id_subarea"],
            })

        await db.execute(text("""
            UPDATE encuesta_envio
               SET estado = 'completada', fecha_completada = NOW(), fecha_modificacion = NOW()
             WHERE id_encuesta_envio = :id
        """), {"id": env["id_encuesta_envio"]})
        await db.commit()

        logger.info("registrar_respuesta: OK envio=%s rama=%s contacto=%s",
                    env["id_encuesta_envio"], rama, solicita_contacto)

        # 5. Notificar al area si solicita contacto (best-effort, no rompe la respuesta)
        if solicita_contacto:
            await _notificar_solicitud_contacto(
                db, id_subarea=env["subarea_reclamo"], nro_reclamo=env["nro_reclamo"],
                id_reclamo=env["id_reclamo"],
            )

        return {"ok": True, "mensaje": "¡Gracias por tu respuesta!"}
    except Exception as e:
        await db.rollback()
        logger.error("registrar_respuesta fallo (token=%s): %s", _tok(token), e)
        return {"ok": False, "error": "No se pudo registrar la respuesta"}


async def _notificar_solicitud_contacto(db, *, id_subarea, nro_reclamo, id_reclamo):
    """Manda un email a los usuarios del area responsable cuando un vecino pide contacto."""
    try:
        if id_subarea is None:
            logger.info("solicita_contacto: reclamo=%s sin subarea, no se notifica", id_reclamo)
            return
        usuarios = (await db.execute(text("""
            SELECT DISTINCT u.email
              FROM agentes a
              JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
             WHERE a.id_subarea = :sub AND a.activo = TRUE
               AND u.email IS NOT NULL AND u.email <> ''
        """), {"sub": id_subarea})).fetchall()
        if not usuarios:
            logger.info("solicita_contacto: subarea=%s sin usuarios con email", id_subarea)
            return
        asunto = f"[ZARIS] Vecino solicita contacto - Reclamo #{nro_reclamo or id_reclamo}"
        html = (
            f"<p>Un vecino respondió la encuesta de satisfacción del reclamo "
            f"<strong>#{_esc(str(nro_reclamo or id_reclamo))}</strong> y "
            f"<strong>solicitó ser contactado</strong>.</p>"
            f"<p>Revisá el reclamo en ZARIS y comunicate con el vecino.</p>"
        )
        texto = (f"Un vecino solicitó contacto tras la encuesta del reclamo "
                 f"#{nro_reclamo or id_reclamo}. Revisalo en ZARIS.")
        for u in usuarios:
            enviar_mail(u[0], asunto, html, texto)
    except Exception as e:
        logger.error("_notificar_solicitud_contacto fallo (reclamo=%s): %s", id_reclamo, e)


# =============================================================================
# Jobs (dispatcher externo)
# =============================================================================

async def expirar_envios_vencidos(db: AsyncSession) -> int:
    """Marca 'expirada' los envios vencidos en estado 'enviada'/'abierta'. Devuelve cantidad."""
    try:
        res = await db.execute(text("""
            UPDATE encuesta_envio
               SET estado = 'expirada', fecha_modificacion = NOW()
             WHERE activo = TRUE
               AND estado IN ('enviada', 'abierta')
               AND fecha_expiracion < NOW()
        """))
        await db.commit()
        n = res.rowcount or 0
        logger.info("expirar_envios_vencidos: %s envios marcados expirados", n)
        return n
    except Exception as e:
        await db.rollback()
        logger.error("expirar_envios_vencidos fallo: %s", e)
        return 0


async def procesar_envios_pendientes(db: AsyncSession, limite: int = 50) -> dict:
    """
    Procesa envios 'pendiente' con fecha_alta < NOW() - 24h (delay para dar tiempo a
    verificar que la solucion persista). Llama a enviar_email_encuesta() por cada uno.
    """
    resultado = {"procesados": 0, "exitosos": 0, "fallidos": 0}
    try:
        rows = (await db.execute(text("""
            SELECT id_encuesta_envio FROM encuesta_envio
             WHERE activo = TRUE AND estado = 'pendiente'
               AND fecha_alta < NOW() - make_interval(hours => :horas)
             ORDER BY fecha_alta
             LIMIT :lim
        """), {"horas": HORAS_DELAY_ENVIO, "lim": limite})).fetchall()

        for row in rows:
            resultado["procesados"] += 1
            ok = await enviar_email_encuesta(db, row[0])
            if ok:
                resultado["exitosos"] += 1
            else:
                resultado["fallidos"] += 1

        logger.info("procesar_envios_pendientes: %s", resultado)
        return resultado
    except Exception as e:
        logger.error("procesar_envios_pendientes fallo: %s", e)
        return resultado
