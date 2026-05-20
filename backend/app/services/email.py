"""
ZARIS - Sender de email simple via SMTP (stdlib).

Modo MOCK cuando SMTP no esta configurado: logea el mail a stdout en lugar de enviarlo.
Pensado para correr en BackgroundTasks de FastAPI (no bloquea el endpoint).
"""
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger("zaris.email")


def smtp_configurado() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS and settings.SMTP_FROM)


def enviar_mail(
    to: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    from_override: str | None = None,
) -> bool:
    """
    Envia un email sincronicamente. Si SMTP no esta configurado, logea el contenido (modo MOCK)
    y devuelve True (no rompe el flujo del caller).

    En BackgroundTasks: FastAPI corre cada task en un threadpool, asi que smtplib (sincrono)
    no bloquea el event loop.

    from_override: si se pasa, reemplaza el header "From" (util para que el display name
    sea del municipio aunque el address sea siempre noreply@zaris.com.ar).

    Returns:
        True si el envio fue exitoso (o mock). False si SMTP esta configurado pero fallo.
    """
    if not to or "@" not in to:
        logger.warning("enviar_mail: destinatario invalido %r", to)
        return False

    if not smtp_configurado():
        logger.info(
            "[email MOCK] to=%s subject=%r body=%s",
            to,
            subject,
            (body_text or _strip_html(body_html))[:200],
        )
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_override or settings.SMTP_FROM
    msg["To"] = to
    msg.set_content(body_text or _strip_html(body_html))
    msg.add_alternative(body_html, subtype="html")

    try:
        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
                smtp.send_message(msg)
        logger.info("email enviado: to=%s subject=%r", to, subject)
        return True
    except Exception as e:
        logger.error("email fallo: to=%s subject=%r error=%s", to, subject, e)
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
    """Helper para armar 'Nombre <email@dom>'."""
    return formataddr((nombre, email))


# ────────────────────────────────────────────────────────────────────────────
# Templates de App Vecinos (auth publico de ciudadanos)
# ────────────────────────────────────────────────────────────────────────────

def _zaris_from_address() -> str:
    """Address del remitente real (parte despues del '<' en SMTP_FROM, o el SMTP_USER)."""
    raw = settings.SMTP_FROM or settings.SMTP_USER or "noreply@zaris.com.ar"
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


def enviar_mail_activacion_ciudadano(
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
    Modo MOCK si SMTP no esta configurado.
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

    # Display name del municipio + address ZARIS (decision sesion 2026-05-19).
    from_addr = _zaris_from_address()
    from_header = formatear_remitente(municipio_nombre, from_addr)

    return enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)


def enviar_mail_recovery_ciudadano(
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

    from_addr = _zaris_from_address()
    from_header = formatear_remitente(municipio_nombre, from_addr)

    return enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)
