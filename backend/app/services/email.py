"""
ZARIS - Sender de email via API HTTP de Resend (https://resend.com).

Migrado desde SMTP Zoho (smtplib) porque Railway bloquea el egress SMTP saliente
(puertos 587/465 dan timeout consistente). Resend usa HTTPS (puerto 443), que Railway
no bloquea. Un solo endpoint: POST https://api.resend.com/emails.

Diseno (decidido con Cesar):
  - httpx.AsyncClient directo (el backend es async, evitamos la lib oficial `resend`).
  - Remitente por defecto: no-reply@zaris.com.ar (dominio RAIZ verificado en Resend; el
    subdominio send.* da 403 — ver memoria reference_railway_bloquea_egress_smtp).
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
    municipio, ej. "MUNICIPALIDAD DE SAN ANDRES <no-reply@zaris.com.ar>").
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
    no-reply@zaris.com.ar). Si no se pasa, usa settings.RESEND_FROM.

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
    raw = settings.RESEND_FROM or "no-reply@zaris.com.ar"
    if "<" in raw and ">" in raw:
        return raw.split("<", 1)[1].split(">", 1)[0].strip()
    return raw.strip()


_CTA_COLOR_DEFAULT = "#f54e00"
_CTA_COLOR_TTL_SEG = 300.0
_cta_color_cache: dict = {"ts": 0.0, "color": _CTA_COLOR_DEFAULT}


async def _color_cta_municipio() -> str:
    """Color del boton CTA de los mails al vecino: `municipio_color_primary`
    de configuracion_general (branding del piloto, etapa F del plan App
    Vecinos), con fallback neutro al naranja default si la clave falta, esta
    vacia o no es un hex valido. Cache TTL 5 min, sesion propia (los mails
    corren en BackgroundTasks sin sesion de request)."""
    import re
    import time as _time

    now = _time.monotonic()
    if now - _cta_color_cache["ts"] < _CTA_COLOR_TTL_SEG:
        return _cta_color_cache["color"]
    color = _CTA_COLOR_DEFAULT
    try:
        from sqlalchemy import text as _text

        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            valor = await db.scalar(_text(
                "SELECT valor FROM configuracion_general WHERE clave = 'municipio_color_primary'"
            ))
        if valor and re.fullmatch(r"#[0-9a-fA-F]{6}", valor.strip()):
            color = valor.strip()
    except Exception as e:  # noqa: BLE001 — el mail nunca se cae por branding
        logger.warning("color CTA: no pude leer municipio_color_primary (%s)", e)
    _cta_color_cache.update(ts=now, color=color)
    return color


def _build_template_app_vecinos(
    titulo: str,
    saludo: str,
    parrafo_principal: str,
    cta_texto: str,
    cta_url: str,
    parrafo_extra: str,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
    cta_color: str = _CTA_COLOR_DEFAULT,
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
        <a href="{cta_url}" style="display:inline-block;padding:14px 28px;background:{cta_color};color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;border-radius:6px;">
          {cta_texto}
        </a>
      </div>
      <p style="margin:24px 0 8px 0;font-size:13px;line-height:1.5;color:rgba(38,37,30,.6);">
        {parrafo_extra}
      </p>
      <p style="margin:0;font-size:12px;line-height:1.5;color:rgba(38,37,30,.5);word-break:break-all;">
        Si el boton no funciona, copia y pega este enlace en tu navegador:<br>
        <span style="color:{cta_color};">{cta_url}</span>
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
        cta_color=await _color_cta_municipio(),
    )

    # Display name del municipio + address del subdominio Resend (decision sesion 2026-05-19).
    from_header = formatear_remitente(municipio_nombre, _from_address_base())

    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)


# ────────────────────────────────────────────────────────────────────────────
# Templates de ALTA PÚBLICA de vecinos (autoregistro desde URL pública)
# ────────────────────────────────────────────────────────────────────────────

async def enviar_mail_verificacion_alta_ciudadano(
    to: str,
    nombre: str,
    apellido: str,
    cta_url: str,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
) -> bool:
    """
    Mail de verificación del alta pública de un ciudadano (autoregistro).
    El link `cta_url` (ya armado por el caller, con el slug del municipio) verifica el
    email: al clickearlo el ciudadano queda email_chk=TRUE, estado_validacion='verificado'
    y su cuenta activada.
    """
    saludo_nombre = (nombre or "").strip() or apellido or "vecino"
    subject = f"Verificá tu alta en {municipio_nombre}"

    html, text = _build_template_app_vecinos(
        titulo="Verificá tu alta",
        saludo=f"Hola {saludo_nombre},",
        parrafo_principal=(
            f"Recibimos tu solicitud de alta como vecino de {municipio_nombre}. "
            f"Para confirmar que este correo es tuyo y activar tu cuenta, hacé clic en el siguiente botón."
        ),
        cta_texto="Verificar mi alta",
        cta_url=cta_url,
        parrafo_extra="Este enlace es válido por 7 días. Si no fuiste vos, podés ignorar este mensaje.",
        municipio_nombre=municipio_nombre,
        municipio_logo_url=municipio_logo_url,
        cta_color=await _color_cta_municipio(),
    )

    from_header = formatear_remitente(municipio_nombre, _from_address_base())
    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)


async def enviar_mail_verificacion_alta_empresa(
    to: str,
    razon_social: str,
    cta_url: str,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
) -> bool:
    """
    Mail de verificación del alta pública de una empresa (autoregistro, vinculada a un
    ciudadano). El link verifica el email de la empresa: empresa.email_chk=TRUE.
    """
    nombre_mostrado = (razon_social or "").strip() or "tu empresa"
    subject = f"Verificá el alta de {nombre_mostrado} en {municipio_nombre}"

    html, text = _build_template_app_vecinos(
        titulo="Verificá el alta de tu empresa",
        saludo="Hola,",
        parrafo_principal=(
            f"Se solicitó el alta de <strong>{nombre_mostrado}</strong> en {municipio_nombre}. "
            f"Para confirmar que esta casilla de correo pertenece a la empresa, hacé clic en el botón."
        ),
        cta_texto="Verificar el alta de la empresa",
        cta_url=cta_url,
        parrafo_extra="Este enlace es válido por 7 días. Si no esperabas este correo, podés ignorarlo.",
        municipio_nombre=municipio_nombre,
        municipio_logo_url=municipio_logo_url,
        cta_color=await _color_cta_municipio(),
    )

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
        cta_color=await _color_cta_municipio(),
    )

    from_header = formatear_remitente(municipio_nombre, _from_address_base())

    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)


# ────────────────────────────────────────────────────────────────────────────
# Template de credenciales de USUARIO INTERNO (backoffice ZARIS)
# Se usa al dar de alta un empleado municipal: se le manda usuario + clave
# temporal generada por el sistema. En su primer ingreso el sistema lo fuerza a
# cambiarla (Fase 3, debe_cambiar_password). NO reusa el template de App Vecinos:
# acá no hay link de activación, las credenciales van en el cuerpo y el CTA va al
# login del backoffice.
# ────────────────────────────────────────────────────────────────────────────

async def enviar_mail_credenciales_usuario_interno(
    to: str,
    username: str,
    password_temporal: str,
    login_url: str,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
) -> bool:
    """
    Mail al empleado municipal recién dado de alta con su clave temporal.
    Deberá cambiarla en su primer ingreso. Modo MOCK si Resend no está configurado.
    """
    subject = f"Tu acceso a ZARIS — {municipio_nombre}"

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
        {municipio_nombre} · GESTION ESTADO
      </div>
    </td></tr>
    <tr><td style="padding:32px;">
      <h1 style="margin:0 0 16px 0;font-size:22px;font-weight:600;color:#26251e;line-height:1.3;">
        Se creó tu cuenta en ZARIS
      </h1>
      <p style="margin:0 0 16px 0;font-size:15px;line-height:1.55;color:#26251e;">
        Hola,
      </p>
      <p style="margin:0 0 20px 0;font-size:15px;line-height:1.55;color:rgba(38,37,30,.85);">
        Un administrador te dio de alta en el sistema de gestión municipal.
        Estas son tus credenciales de acceso. Por seguridad, el sistema te pedirá
        elegir una contraseña nueva la primera vez que ingreses.
      </p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px 0;background:#f7f7f4;border:1px solid rgba(38,37,30,.1);border-radius:6px;">
        <tr><td style="padding:18px 20px;">
          <div style="font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:rgba(38,37,30,.55);margin-bottom:4px;">Usuario (email)</div>
          <div style="font-size:16px;font-weight:600;color:#26251e;margin-bottom:14px;word-break:break-all;">{to}</div>
          <div style="font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:rgba(38,37,30,.55);margin-bottom:4px;">Contraseña temporal</div>
          <div style="font-size:18px;font-weight:700;color:#f54e00;font-family:'Courier New',monospace;letter-spacing:.02em;">{password_temporal}</div>
        </td></tr>
      </table>
      <div style="margin:24px 0;text-align:center;">
        <a href="{login_url}" style="display:inline-block;padding:14px 28px;background:#f54e00;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;border-radius:6px;">
          Ingresar a ZARIS
        </a>
      </div>
      <p style="margin:24px 0 0 0;font-size:13px;line-height:1.5;color:rgba(38,37,30,.6);">
        Esta contraseña es temporal y de un solo uso para tu primer ingreso.
        Si no esperabas este correo, contactá al administrador del sistema.
      </p>
    </td></tr>
    <tr><td style="padding:16px 32px;text-align:center;border-top:1px solid rgba(38,37,30,.08);font-size:11px;color:rgba(38,37,30,.5);">
      Este mensaje fue enviado por {municipio_nombre}.
    </td></tr>
  </table>
</body>
</html>"""

    text = f"""\
{municipio_nombre} · GESTION ESTADO

Se creó tu cuenta en ZARIS

Un administrador te dio de alta en el sistema de gestión municipal.
Estas son tus credenciales de acceso:

  Usuario (email):       {to}
  Contraseña temporal:   {password_temporal}

Ingresá en: {login_url}

Por seguridad, el sistema te pedirá elegir una contraseña nueva la primera
vez que ingreses. Esta contraseña es temporal.

Si no esperabas este correo, contactá al administrador del sistema.
"""

    from_header = formatear_remitente(municipio_nombre, _from_address_base())
    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)


# ────────────────────────────────────────────────────────────────────────────
# Templates de RECUPERACIÓN de credenciales del USUARIO INTERNO (backoffice).
# Espejo del recovery del vecino (publico_auth.py) pero para el login del shell
# (frontend/login.html). Usa el look del shell (marca ZARIS · GESTION ESTADO),
# no el de App Vecinos. El CTA va al login del backoffice.
# ────────────────────────────────────────────────────────────────────────────

def _build_template_interno(
    titulo: str,
    cuerpo_html: str,
    cta_texto: str | None,
    cta_url: str | None,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
) -> str:
    """Arma el HTML del shell interno (header con marca, CTA naranja opcional).
    `cuerpo_html` ya viene formateado (puede traer <p>, <table>, etc.)."""
    logo_html = ""
    if municipio_logo_url:
        logo_html = (
            f'<img src="{municipio_logo_url}" alt="{municipio_nombre}" '
            f'style="max-height:64px;max-width:240px;display:block;margin:0 auto 16px;">'
        )
    cta_html = ""
    if cta_texto and cta_url:
        cta_html = f"""\
      <div style="margin:24px 0;text-align:center;">
        <a href="{cta_url}" style="display:inline-block;padding:14px 28px;background:#f54e00;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;border-radius:6px;">
          {cta_texto}
        </a>
      </div>
      <p style="margin:0;font-size:12px;line-height:1.5;color:rgba(38,37,30,.5);word-break:break-all;">
        Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
        <span style="color:#f54e00;">{cta_url}</span>
      </p>"""

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:32px 16px;background:#f2f1ed;font-family:'Helvetica Neue',Arial,sans-serif;color:#26251e;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid rgba(38,37,30,.1);border-radius:8px;">
    <tr><td style="padding:32px 32px 24px 32px;text-align:center;border-bottom:1px solid rgba(38,37,30,.08);">
      {logo_html}
      <div style="font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:rgba(38,37,30,.6);">
        {municipio_nombre} · GESTION ESTADO
      </div>
    </td></tr>
    <tr><td style="padding:32px;">
      <h1 style="margin:0 0 16px 0;font-size:22px;font-weight:600;color:#26251e;line-height:1.3;">
        {titulo}
      </h1>
      {cuerpo_html}
      {cta_html}
    </td></tr>
    <tr><td style="padding:16px 32px;text-align:center;border-top:1px solid rgba(38,37,30,.08);font-size:11px;color:rgba(38,37,30,.5);">
      Este mensaje fue enviado por {municipio_nombre}.<br>
      Si no esperabas este correo, podés ignorarlo.
    </td></tr>
  </table>
</body>
</html>"""


async def enviar_mail_recovery_usuario_interno(
    to: str,
    nombre: str,
    token: str,
    login_url: str,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
) -> bool:
    """
    Mail de recuperación de contraseña para un usuario INTERNO (empleado municipal).
    Link: {login_url}?recovery={token} — válido 24 horas. El login del shell detecta
    el query param y muestra el form de "elegir nueva contraseña".
    Modo MOCK si Resend no está configurado.
    """
    cta_url = f"{login_url}?recovery={token}"
    saludo_nombre = (nombre or "").strip() or "equipo"
    subject = f"Restablecé tu contraseña — ZARIS {municipio_nombre}"

    cuerpo = f"""\
      <p style="margin:0 0 16px 0;font-size:15px;line-height:1.55;color:#26251e;">
        Hola {saludo_nombre},
      </p>
      <p style="margin:0 0 16px 0;font-size:15px;line-height:1.55;color:rgba(38,37,30,.85);">
        Recibimos un pedido para restablecer la contraseña de tu cuenta en el sistema de
        gestión municipal. Hacé clic en el botón para elegir una nueva.
      </p>
      <p style="margin:0 0 8px 0;font-size:13px;line-height:1.5;color:rgba(38,37,30,.6);">
        Recordá que ingresás al sistema con tu correo: <strong>{to}</strong>
      </p>
      <p style="margin:0 0 8px 0;font-size:13px;line-height:1.5;color:rgba(38,37,30,.6);">
        Este enlace es válido por 24 horas. Si no pediste este cambio, ignorá este mensaje.
      </p>"""

    html = _build_template_interno(
        titulo="Restablecé tu contraseña",
        cuerpo_html=cuerpo,
        cta_texto="Elegir nueva contraseña",
        cta_url=cta_url,
        municipio_nombre=municipio_nombre,
        municipio_logo_url=municipio_logo_url,
    )
    text = (
        f"{municipio_nombre} · GESTION ESTADO\n\n"
        f"Restablecé tu contraseña\n\n"
        f"Hola {saludo_nombre},\n\n"
        f"Recibimos un pedido para restablecer la contraseña de tu cuenta.\n"
        f"Ingresás al sistema con tu correo: {to}\n\n"
        f"Elegí una nueva contraseña en: {cta_url}\n\n"
        f"Este enlace es válido por 24 horas. Si no pediste este cambio, ignorá este mensaje.\n"
    )

    from_header = formatear_remitente(municipio_nombre, _from_address_base())
    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)


async def enviar_mail_recordatorio_usuario_interno(
    to: str,
    nombre: str,
    login_url: str,
    municipio_nombre: str,
    municipio_logo_url: str | None = None,
) -> bool:
    """
    Mail que le recuerda al usuario INTERNO con qué correo ingresa al sistema.
    Lo dispara "Olvidé mi usuario": el empleado tipea su número de documento, el
    sistema resuelve el agente -> usuario -> email y manda este recordatorio a esa
    casilla. NO revela el email en pantalla (anti-enumeración): se entera por el mail.
    Modo MOCK si Resend no está configurado.
    """
    saludo_nombre = (nombre or "").strip() or "equipo"
    subject = f"Tu usuario de acceso — ZARIS {municipio_nombre}"

    cuerpo = f"""\
      <p style="margin:0 0 16px 0;font-size:15px;line-height:1.55;color:#26251e;">
        Hola {saludo_nombre},
      </p>
      <p style="margin:0 0 20px 0;font-size:15px;line-height:1.55;color:rgba(38,37,30,.85);">
        Pediste recuperar tu usuario de acceso al sistema de gestión municipal.
        Ingresás con este correo electrónico:
      </p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 20px 0;background:#f7f7f4;border:1px solid rgba(38,37,30,.1);border-radius:6px;">
        <tr><td style="padding:18px 20px;">
          <div style="font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:rgba(38,37,30,.55);margin-bottom:4px;">Usuario (email)</div>
          <div style="font-size:16px;font-weight:600;color:#26251e;word-break:break-all;">{to}</div>
        </td></tr>
      </table>
      <p style="margin:0;font-size:13px;line-height:1.5;color:rgba(38,37,30,.6);">
        Si olvidaste también tu contraseña, desde el login podés pedir restablecerla.
      </p>"""

    html = _build_template_interno(
        titulo="Tu usuario de acceso",
        cuerpo_html=cuerpo,
        cta_texto="Ir al login",
        cta_url=login_url,
        municipio_nombre=municipio_nombre,
        municipio_logo_url=municipio_logo_url,
    )
    text = (
        f"{municipio_nombre} · GESTION ESTADO\n\n"
        f"Tu usuario de acceso\n\n"
        f"Hola {saludo_nombre},\n\n"
        f"Pediste recuperar tu usuario de acceso. Ingresás con este correo: {to}\n\n"
        f"Ir al login: {login_url}\n\n"
        f"Si olvidaste también tu contraseña, desde el login podés pedir restablecerla.\n"
    )

    from_header = formatear_remitente(municipio_nombre, _from_address_base())
    return await enviar_mail(to=to, subject=subject, body_html=html, body_text=text, from_override=from_header)
