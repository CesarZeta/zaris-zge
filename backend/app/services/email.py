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


def enviar_mail(to: str, subject: str, body_html: str, body_text: str | None = None) -> bool:
    """
    Envia un email sincronicamente. Si SMTP no esta configurado, logea el contenido (modo MOCK)
    y devuelve True (no rompe el flujo del caller).

    En BackgroundTasks: FastAPI corre cada task en un threadpool, asi que smtplib (sincrono)
    no bloquea el event loop.

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
    msg["From"] = settings.SMTP_FROM
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
