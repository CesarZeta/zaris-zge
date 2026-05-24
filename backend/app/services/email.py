"""
ZARIS - Sender de email via API HTTP de Resend (https://resend.com).

Migrado desde SMTP Zoho (smtplib) porque Railway bloquea el egress SMTP saliente
(puertos 587/465 dan timeout consistente). Resend usa HTTPS (puerto 443), que Railway
no bloquea. Un solo endpoint: POST https://api.resend.com/emails.

Diseno (decidido con Cesar):
  - httpx.AsyncClient directo (el backend es async, evitamos la lib oficial `resend`).
  - Remitente por defecto: notificaciones@send.zaris.com.ar (subdominio verificado en Resend).
  - `enviar_mail(...) -> bool` mantiene su firma publica (no rompe los 4 modulos clientes).
    Es ASYNC: se encola en BackgroundTasks (Starlette await-ea corutinas encoladas).
  - Modo MOCK cuando RESEND_API_KEY no esta configurada: logea el mail a stdout y devuelve
    True (no rompe el flujo del caller). Util para dev sin la key y para tests.
  - Cada envio exitoso logea el `message_id` que devuelve Resend (trazabilidad en Resend > Logs).
  - `enviar_mail_raise(...) -> str` (NUEVA): levanta ResendError ante 4xx/5xx, para cuando un
    caller quiera distinguir fallo transitorio de definitivo. `enviar_mail` la envuelve y
    captura, devolviendo bool (contrato historico de los clientes).
"""
import logging

import httpx

from app.core.config import settings
from app.utils.log_helpers import mask_email

logger = logging.getLogger("zaris.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Resend a veces tarda en responder bajo carga: 10s para conectar, 30s total.
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ResendError(Exception):
    """Resend devolvio un error (4xx/5xx) o la request fallo a nivel transporte.

    `status_code` es None cuando el fallo fue de red/timeout (no hubo respuesta HTTP).
    """

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def resend_configurado() -> bool:
    """True si hay API key de Resend. Si False, el sender corre en modo MOCK."""
    return bool(settings.RESEND_API_KEY)


async def enviar_mail_raise(
    to: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    from_override: str | None = None,
) -> str:
    """
    Envia un email via Resend. Devuelve el `message_id` de Resend en caso de exito.

    Levanta ResendError si Resend responde 4xx/5xx o si la request falla a nivel red.
    NO entra en modo MOCK: esta variante siempre intenta enviar de verdad (usar cuando
    el caller quiere manejar el error explicitamente).

    from_override: reemplaza el remitente (util para que el display name sea el del
    municipio, ej. "MUNICIPALIDAD DE SAN ANDRES <notificaciones@send.zaris.com.ar>").
    Si no se pasa, usa settings.RESEND_FROM.

    Raises:
        ResendError: ante 4xx/5xx de Resend o fallo de transporte.
        ValueError: si el destinatario es invalido.
    """
    if not to or "@" not in to:
        raise ValueError(f"destinatario invalido: {mask_email(to)}")

    payload: dict = {
        "from": from_override or settings.RESEND_FROM,
        "to": [to],
        "subject": subject,
        "html": body_html,
    }
    if body_text:
        payload["text"] = body_text

    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(RESEND_ENDPOINT, json=payload, headers=headers)
    except httpx.HTTPError as e:
        # Timeout, DNS, conexion rechazada, etc. — no hubo respuesta HTTP.
        logger.error("Resend transporte fallo: to=%s subject=%r error=%s", mask_email(to), subject, e)
        raise ResendError(f"fallo de transporte hacia Resend: {e}", status_code=None) from e

    if resp.status_code >= 400:
        body = resp.text[:500]
        logger.error(
            "Resend rechazo: to=%s subject=%r status=%s body=%s",
            mask_email(to), subject, resp.status_code, body,
        )
        raise ResendError(
            f"Resend devolvio {resp.status_code}", status_code=resp.status_code, body=body
        )

    message_id = ""
    try:
        message_id = (resp.json() or {}).get("id", "")
    except Exception:
        pass  # Resend respondio 2xx pero el body no era JSON parseable; igual fue exito.

    logger.info(
        "email enviado (Resend): to=%s subject=%r message_id=%s",
        mask_email(to), subject, message_id,
    )
    return message_id


async def enviar_mail(
    to: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    from_override: str | None = None,
) -> bool:
    """
    Envia un email via Resend. Si RESEND_API_KEY no esta configurada, logea el contenido
    (modo MOCK) y devuelve True (no rompe el flujo del caller).

    Es ASYNC y se encola en BackgroundTasks de FastAPI (Starlette await-ea corutinas).

    from_override: reemplaza el remitente (display name del municipio sobre el address
    notificaciones@send.zaris.com.ar). Si no se pasa, usa settings.RESEND_FROM.

    Returns:
        True si el envio fue exitoso (o mock). False si Resend esta configurado pero fallo
        (el caller — ej. el dispatcher de encuestas — decide si reintentar o marcar fallido).
    """
    if not to or "@" not in to:
        logger.warning("enviar_mail: destinatario invalido %s", mask_email(to))
        return False

    if not resend_configurado():
        logger.info(
            "[email MOCK] to=%s subject=%r body=%s",
            mask_email(to),
            subject,
            (body_text or _strip_html(body_html))[:200],
        )
        return True

    try:
        await enviar_mail_raise(
            to=to, subject=subject, body_html=body_html,
            body_text=body_text, from_override=from_override,
        )
        return True
    except (ResendError, ValueError):
        # enviar_mail_raise ya logueo el detalle. Devolvemos bool para no romper el
        # contrato historico de los clientes (notificaciones, encuestas, App Vecinos).
        return False


def _strip_html(html: str) -> str:
    """Texto plano basico para clientes sin HTML. NO es un parser completo."""
    import re
    # quitar tags
    txt = re.sub(r"<[^>]+>", "", html)
    # entidades HTML basicas
    txt = (
        txt.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    # colapsar whitespace
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def formatear_remitente(nombre: str, email: str) -> str:
    """Helper para armar 'Nombre <email@dom>'. Resend acepta este formato en `from`."""
    nombre = (nombre or "").strip()
    if not nombre:
        return email
    return f"{nombre} <{email}>"


# ────────────────────────────────────────────────────────────────────────────
# Templates de App Vecinos (auth publico de ciudadanos)
# ────────────────────────────────────────────────────────────────────────────

def _from_address_base() -> str:
    """Address base del remitente (settings.RESEND_FROM, sin display name)."""
    raw = settings.RESEND_FROM or "notificaciones@zaris.com.ar"
    if "<" in raw and ">" in raw:
        return raw.split("<", 1)[1].split(">", 1)[0].strip()
    return raw.strip()


def _build_template_app_vecinos(
    titulo: str,
    saludo: str,
    parrafo_principal: str,
    cta_texto: str,
    cta_url: str,
    parrafo_extra: str,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
) -> tuple[str, str]:
    """Arma (html, text) con el look App Vecinos: sobrio, sin emojis, sin marca ZARIS."""
    logo_html = ""
    if municipio_logo_url:
        logo_html = (
            f'<img src="{municipio_logo_url}" alt="{municipio_nombre}" '
            f'style="max-height:64px;max-width:240px;display:block;margin:0 auto 16px;">'
        )

    html = f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:32px 16px;background:#f2f1ed;font-family:'Helvetica Neue',Arial,sans-serif;color:#26251e;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid rgba(38,37,30,.1);border-radius:8px;">
    <tr><td style="padding:32px 32px 24px 32px;text-align:center;border-bottom:1px solid rgba(38,37,30,.08);">
      {logo_html}
      <div style="font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:rgba(38,37,30,.6);">
        {municipio_nombre}
      </div>
    </td></tr>
    <tr><td style="padding:32px;">
      <h1 style="margin:0 0 16px 0;font-size:22px;font-weight:600;color:#26251e;line-height:1.3;">
        {titulo}
      </h1>
      <p style="margin:0 0 16px 0;font-size:15px;line-height:1.55;color:#26251e;">
        {saludo}
      </p>
      <p style="margin:0 0 24px 0;font-size:15px;line-height:1.55;color:rgba(38,37,30,.85);">
        {parrafo_principal}
      </p>
      <div style="margin:24px 0;text-align:center;">
        <a href="{cta_url}" style="display:inline-block;padding:14px 28px;background:#f54e00;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;border-radius:6px;">
          {cta_texto}
        </a>
      </div>
      <p style="margin:24px 0 8px 0;font-size:13px;line-height:1.5;color:rgba(38,37,30,.6);">
        {parrafo_extra}
      </p>
      <p style="margin:0;font-size:12px;line-height:1.5;color:rgba(38,37,30,.5);word-break:break-all;">
        Si el boton no funciona, copia y pega este enlace en tu navegador:<br>
        <span style="color:#f54e00;">{cta_url}</span>
      </p>
    </td></tr>
    <tr><td style="padding:16px 32px;text-align:center;border-top:1px solid rgba(38,37,30,.08);font-size:11px;color:rgba(38,37,30,.5);">
      Este mensaje fue enviado por {municipio_nombre}.<br>
      Si no esperabas este correo, podes ignorarlo.
    </td></tr>
  </table>
</body>
</html>"""

    text = f"""\
{municipio_nombre}

{titulo}

{saludo}

{parrafo_principal}

{cta_texto}: {cta_url}

{parrafo_extra}

Si el boton no funciona, copia y pega el enlace de arriba en tu navegador.

---
Este mensaje fue enviado por {municipio_nombre}.
Si no esperabas este correo, podes ignorarlo.
"""
    return html, text


async def enviar_mail_activacion_ciudadano(
    to: str,
    nombre: str,
    apellido: str,
    token: str,
    municipio_nombre: str,
    frontend_url: str,
    municipio_logo_url: str | None = None,
) -> bool:
    """
    Manda mail de activacion al ciudadano recien dado de alta.
    Link: {frontend_url}/activar?token={token} - valido 7 dias.
    Modo MOCK si Resend no esta configurado.
    """
    cta_url = f"{frontend_url.rstrip('/')}/activar?token={token}"
    saludo_nombre = (nombre or "").strip() or apellido or "vecino"
    subject = f"Activa tu cuenta en {municipio_nombre} - App Vecinos"

    html, text = _build_template_app_vecinos(
        titulo="Activa tu cuenta",
        saludo=f"Hola {saludo_nombre},",
        parrafo_principal=(
            f"{municipio_nombre} te dio de alta en App Vecinos, "
            f"el servicio para enviar reclamos y hacer seguimiento desde tu celular. "
            f"Para empezar a usarlo, definí tu contraseña haciendo clic en el siguiente boton."
        ),
        cta_texto="Activar mi cuenta",
        cta_url=cta_url,
        parrafo_extra="Este enlace es valido por 7 dias. Si expira, podes pedir un nuevo correo desde la app.",
        municipio_nombre=municipio_nombre,
        municipio_logo_url=municipio_logo_url,
    )

    # Display name del municipio + address del subdominio Resend (decision sesion 2026-05-19).
    from_header = formatear_remitente(municipio_nombre, _from_address_base())

    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)


async def enviar_mail_recovery_ciudadano(
    to: str,
    nombre: str,
    apellido: str,
    token: str,
    municipio_nombre: str,
    frontend_url: str,
    municipio_logo_url: str | None = None,
) -> bool:
    """
    Manda mail de recuperacion de password al ciudadano.
    Link: {frontend_url}/resetear-password?token={token} - valido 24 horas.
    """
    cta_url = f"{frontend_url.rstrip('/')}/resetear-password?token={token}"
    saludo_nombre = (nombre or "").strip() or apellido or "vecino"
    subject = f"Restablece tu contraseña en {municipio_nombre} - App Vecinos"

    html, text = _build_template_app_vecinos(
        titulo="Restablece tu contraseña",
        saludo=f"Hola {saludo_nombre},",
        parrafo_principal=(
            "Recibimos un pedido para restablecer la contraseña de tu cuenta en App Vecinos. "
            "Hace clic en el boton para elegir una nueva."
        ),
        cta_texto="Elegir nueva contraseña",
        cta_url=cta_url,
        parrafo_extra="Este enlace es valido por 24 horas. Si no pediste este cambio, ignora este mensaje.",
        municipio_nombre=municipio_nombre,
        municipio_logo_url=municipio_logo_url,
    )

    from_header = formatear_remitente(municipio_nombre, _from_address_base())

    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)
