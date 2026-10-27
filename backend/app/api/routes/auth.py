"""
ZARIS API — Endpoints de autenticación.
POST /api/v1/auth/login  → JWT
GET  /api/v1/auth/me     → usuario actual
"""
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.config_municipio import leer_configs
from app.core.database import get_db
from typing import Optional

from app.core.municipio import resolver_municipio_de_origen
from app.core.urls import url_login_backoffice
from app.core import storage
from app.core.auth import (
    verify_password,
    hash_password,
    get_current_user,
    modulos_permitidos,
    requiere_segundo_factor,
)
from app.api.routes.segundo_factor import SegundoFactorRequerido, no_configurado, respuesta_login
from app.services import segundo_factor as sf
from app.services.login_interno import (
    USUARIO_LOGIN_SELECT as _USUARIO_LOGIN_SELECT,
    LoginResponse,
    completar_login,
    perfil_agente_del_usuario,
)
from app.services.email import (
    enviar_mail_recovery_usuario_interno,
    enviar_mail_recordatorio_usuario_interno,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
logger = logging.getLogger("zaris.auth")

# Recuperación de credenciales del usuario interno (espejo del vecino, §38).
HORAS_RECOVERY_INTERNO = 24
COOLDOWN_RECOVERY_MINUTOS = 5


class LoginRequest(BaseModel):
    """Login del usuario interno. `identificador` = email O número de documento (mig 110,
    pedido de César 2026-10-12). `email` se mantiene como alias por compat con clientes
    viejos; vale cualquiera de los dos."""
    identificador: str | None = None
    email: str | None = None
    password: str


class CambiarPasswordRequest(BaseModel):
    password_nueva: str
    password_actual: str | None = None  # obligatoria salvo cambio forzado (clave temporal)


class RecuperarPasswordRequest(BaseModel):
    """Olvidé mi contraseña: ingresa el correo con el que entra al sistema."""
    email: str


class RecuperarUsuarioRequest(BaseModel):
    """Olvidé mi usuario: ingresa su número de documento (DNI). El sistema resuelve
    el agente vinculado y le manda un mail recordándole con qué correo entra."""
    documento: str


class ResetearPasswordInternoRequest(BaseModel):
    """Aplica la nueva contraseña usando el token de recovery recibido por mail."""
    token: str
    password_nueva: str


class GenericoOkResponse(BaseModel):
    ok: bool = True


class FotoUploadRequest(BaseModel):
    mime_type: str
    tamano_bytes: int = Field(ge=1)


class FotoUpdateRequest(BaseModel):
    # URL pública del avatar ya subido al bucket. Vacía = quitar la foto.
    foto_url: str = Field(max_length=500)


# Foto de perfil: mismo bucket público que el logo del municipio (config-assets,
# 2MB, ver §26). Solo formatos de foto (sin svg/webp: pedido del usuario PNG/JPG).
FOTO_BUCKET = "config-assets"
FOTO_MIME_OK = {"image/png": "png", "image/jpeg": "jpg"}
FOTO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


async def _buscar_usuario_login(db: AsyncSession, ident: str, id_municipio: int):
    """Resuelve el usuario interno a partir del identificador del login, DENTRO del municipio
    de la dirección desde la que se entra (IT-01: una cuenta por municipio; el mismo email o DNI
    puede existir en dos municipios).

    - Con '@' → por email exacto (comportamiento histórico, memoria
      reference_login_email_prod_no_es_patron_doc).
    - Solo dígitos (7-8) → por número de documento: primero la persona de la BUC
      vinculada (`usuarios.id_ciudadano`, mig 110) y, si no hay, el agente 1:1
      (`agentes.dni`, el mismo camino que «Olvidé mi usuario»). Más de una
      coincidencia = no encontrado (no elegimos a ciegas entre dos cuentas).
    Devuelve la fila o None; el caller responde el mismo 401 genérico en todos los casos.
    """
    if not ident:
        return None
    if "@" in ident:
        res = await db.execute(text(_USUARIO_LOGIN_SELECT + " WHERE email = :email AND id_municipio = :mun"),
                               {"email": ident, "mun": id_municipio})
        return res.fetchone()

    dni = _solo_digitos(ident)
    if not (7 <= len(dni) <= 8):
        return None
    por_ciudadano = (await db.execute(text(_USUARIO_LOGIN_SELECT + """
         WHERE activo = TRUE AND id_municipio = :mun
           AND id_ciudadano IN (SELECT c.id_ciudadano FROM ciudadanos c
                                 WHERE c.doc_nro = :dni AND c.activo = TRUE AND c.id_municipio = :mun)
         LIMIT 2"""), {"dni": dni, "mun": id_municipio})).fetchall()
    if len(por_ciudadano) == 1:
        return por_ciudadano[0]
    if len(por_ciudadano) > 1:
        logger.warning("login por DNI ambiguo (ciudadanos): dni=%s", dni)
        return None
    por_agente = (await db.execute(text(_USUARIO_LOGIN_SELECT + """
         WHERE activo = TRUE AND id_municipio = :mun
           AND id_usuario IN (SELECT a.id_usuario FROM agentes a
                               WHERE a.dni = :dni AND a.activo = TRUE AND a.id_usuario IS NOT NULL
                                 AND a.id_municipio = :mun)
         LIMIT 2"""), {"dni": dni, "mun": id_municipio})).fetchall()
    if len(por_agente) == 1:
        return por_agente[0]
    if len(por_agente) > 1:
        logger.warning("login por DNI ambiguo (agentes): dni=%s", dni)
    return None


async def _buscar_super_admin(db: AsyncSession, email: str):
    """Cuenta de super administrador (nivel 0, sin municipio) con ese email. El login y la
    recuperación la buscan cuando no hay cuenta del municipio de origen: el super administrador
    entra desde cualquier dirección (spec §3). Solo por email; no tiene ficha en ninguna BUC."""
    res = await db.execute(text(_USUARIO_LOGIN_SELECT + """
         WHERE lower(email) = lower(:email) AND id_municipio IS NULL AND nivel_acceso = 0"""),
        {"email": email})
    return res.fetchone()


@router.post("/login", response_model=LoginResponse | SegundoFactorRequerido,
             responses={503: {"description": "Segundo factor sin configurar en el servidor"}})
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Anti brute-force online: limitar intentos por IP y por cuenta ANTES de
    # tocar la DB o verificar bcrypt. Claves prefijadas por flujo (§5) para no
    # compartir bucket con otros endpoints. In-memory single-replica (limitación
    # conocida de rate_limit.py): mitiga el ataque online, no reemplaza un lockout
    # persistente en DB (pendiente, requiere migración de columnas en usuarios).
    from app.utils.request_helpers import get_real_ip
    from app.middleware.rate_limit import check_rate_limit
    _ip = get_real_ip(request)
    ident = (body.identificador or body.email or "").strip()
    _clave_rl = ident.lower()
    check_rate_limit(f"loginint-ip:{_ip}", max_requests=10, window_seconds=60)
    id_municipio = await resolver_municipio_de_origen(request, db)
    if _clave_rl:
        # Por municipio: el mismo email puede ser de cuentas de dos municipios.
        check_rate_limit(f"loginint-mail:{id_municipio}:{_clave_rl}", max_requests=5, window_seconds=60)
    user = await _buscar_usuario_login(db, ident, id_municipio)
    if user is None and "@" in ident:
        user = await _buscar_super_admin(db, ident)

    if not user or not user.activo or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales no coinciden. Probá de nuevo.",
        )
    # Segundo factor (IT-01 F3b): a una cuenta de nivel 0/1 la clave no le entrega el token, sino
    # un desafío para el código de la app (o para vincularla). Auditoría, renovación de clave y
    # token van recién después del código, en /auth/segundo-factor/*.
    if requiere_segundo_factor(user.nivel_acceso):
        try:
            return await respuesta_login(db, user)
        except sf.SegundoFactorNoConfigurado:
            raise no_configurado()
    return LoginResponse(**await completar_login(db, request, user, segundo_factor=False))


@router.get("/me", responses={401: {"description": "Sesión sin municipio: volver a ingresar"}})
async def me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    modulos = await modulos_permitidos(
        db, current_user["id_usuario"], current_user["nivel_real"], current_user.get("id_municipio")
    )
    perfil = await perfil_agente_del_usuario(db, current_user["id_usuario"])
    # Al frontend va el nivel real (0 para el super administrador), no el efectivo.
    salida = {k: v for k, v in current_user.items() if k != "nivel_real"}
    return {**salida, "nivel_acceso": current_user["nivel_real"], "modulos_permitidos": modulos, **perfil}


@router.post("/cambiar-password")
async def cambiar_password(
    body: CambiarPasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cambio self-service de la propia contraseña del usuario autenticado.

    - Cambio FORZADO (clave temporal, debe_cambiar_password=TRUE): no exige la
      contraseña actual porque el usuario ya la validó al loguear con la temporal.
    - Cambio VOLUNTARIO (debe_cambiar_password=FALSE): exige `password_actual` y
      la verifica antes de aplicar el cambio.

    Limpia la marca `debe_cambiar_password` al guardar.
    """
    nueva = (body.password_nueva or "")
    if len(nueva) < 8:
        raise HTTPException(status_code=422, detail="La contraseña nueva debe tener al menos 8 caracteres.")
    if len(nueva) > 100:
        raise HTTPException(status_code=422, detail="La contraseña nueva es demasiado larga.")

    result = await db.execute(
        text("""SELECT password_hash, debe_cambiar_password
                FROM usuarios WHERE id_usuario = :id"""),
        {"id": current_user["id_usuario"]},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    forzado = bool(row.debe_cambiar_password)
    if not forzado:
        # Cambio voluntario: exigir y verificar la contraseña actual.
        if not body.password_actual:
            raise HTTPException(status_code=422, detail="Debés ingresar tu contraseña actual.")
        if not verify_password(body.password_actual, row.password_hash):
            raise HTTPException(status_code=401, detail="La contraseña actual no coincide.")

    # Evitar que la "nueva" sea idéntica a la temporal/actual.
    if verify_password(nueva, row.password_hash):
        raise HTTPException(status_code=422, detail="La contraseña nueva debe ser distinta de la actual.")

    nuevo_hash = hash_password(nueva)
    await db.execute(
        text("""UPDATE usuarios
                   SET password_hash = :h, debe_cambiar_password = FALSE,
                       password_actualizada_en = NOW()
                 WHERE id_usuario = :id"""),
        {"h": nuevo_hash, "id": current_user["id_usuario"]},
    )
    await db.commit()
    logger.info("CAMBIO PASSWORD self-service | id=%s | forzado=%s",
                current_user["id_usuario"], forzado)
    return {"ok": True, "debe_cambiar_password": False}


# ─── Recuperación de credenciales del usuario interno ─────────────────────────
# Espejo del flujo del vecino (publico_auth.py) para el login del shell vanilla.
# Anti-enumeración: los endpoints de "pedir" siempre responden 200 OK aunque el
# email/documento no exista, para no filtrar qué cuentas hay.

def _solo_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


async def _branding_municipio(db: AsyncSession, id_municipio: int) -> tuple[str, str | None]:
    """(municipio_nombre, municipio_logo_url) del municipio, desde configuracion_general."""
    cfg = await leer_configs(db, ["municipio_nombre", "municipio_logo_url"], id_municipio)
    return (cfg.get("municipio_nombre") or "Tu municipio", cfg.get("municipio_logo_url") or None)


async def _login_url(db: AsyncSession, id_municipio: Optional[int]) -> str:
    """URL del login del shell del municipio (CTA de los mails internos). El super administrador
    (sin municipio) recibe la de las direcciones sin prefijo."""
    return await url_login_backoffice(db, id_municipio)


@router.post("/recuperar-password", response_model=GenericoOkResponse,
             responses={200: {"description": "Siempre OK (anti-enumeración). El mail del super administrador sale como ZARIS"}})
async def recuperar_password(
    body: RecuperarPasswordRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Olvidé mi contraseña (interno): manda link de reseteo al correo del usuario.
    Anti-enumeración + cooldown silencioso de 5 minutos."""
    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        # No revelamos validación: respondemos OK igual.
        return GenericoOkResponse()

    id_municipio = await resolver_municipio_de_origen(request, db)
    res = await db.execute(
        text("""SELECT id_usuario, nombre, email, fecha_ultimo_email_recovery
                FROM usuarios
                WHERE LOWER(email) = :email AND activo = TRUE AND id_municipio = :mun
                LIMIT 1"""),
        {"email": email, "mun": id_municipio},
    )
    row = res.fetchone()
    es_super = False
    if not row:
        # Super administrador: entra desde cualquier dirección, también para recuperar la clave.
        es_super = True
        row = (await db.execute(
            text("""SELECT id_usuario, nombre, email, fecha_ultimo_email_recovery
                    FROM usuarios
                    WHERE LOWER(email) = :email AND activo = TRUE
                      AND id_municipio IS NULL AND nivel_acceso = 0
                    LIMIT 1"""),
            {"email": email},
        )).fetchone()
    if not row:
        return GenericoOkResponse()  # anti-enumeración

    # Cooldown 5 min
    if row.fecha_ultimo_email_recovery is not None:
        delta = datetime.now(timezone.utc) - row.fecha_ultimo_email_recovery
        if delta < timedelta(minutes=COOLDOWN_RECOVERY_MINUTOS):
            return GenericoOkResponse()

    res = await db.execute(
        text(f"""UPDATE usuarios
                    SET token_recovery = gen_random_uuid(),
                        token_recovery_expira = NOW() + INTERVAL '{HORAS_RECOVERY_INTERNO} hours',
                        fecha_ultimo_email_recovery = NOW()
                  WHERE id_usuario = :id
                  RETURNING token_recovery"""),
        {"id": row.id_usuario},
    )
    token = str(res.fetchone().token_recovery)
    await db.commit()

    # El super administrador no es de ningún municipio: su mail sale como ZARIS, no con la
    # identidad del municipio de la dirección desde la que lo pidió.
    if es_super:
        municipio_nombre, municipio_logo_url = "ZARIS", None
    else:
        municipio_nombre, municipio_logo_url = await _branding_municipio(db, id_municipio)
    background_tasks.add_task(
        enviar_mail_recovery_usuario_interno,
        row.email, row.nombre, token, await _login_url(db, None if es_super else id_municipio),
        municipio_nombre, municipio_logo_url, es_super,
    )
    return GenericoOkResponse()


@router.post("/recuperar-usuario", response_model=GenericoOkResponse)
async def recuperar_usuario(
    body: RecuperarUsuarioRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Olvidé mi usuario (interno): el empleado ingresa su DNI. Se resuelve el agente
    vinculado (regla 1:1 §39) → su usuario → su email, y se manda un recordatorio a
    esa casilla. Anti-enumeración: siempre 200 OK; el email nunca se muestra en pantalla."""
    dni = _solo_digitos(body.documento)
    if not (7 <= len(dni) <= 8):
        return GenericoOkResponse()  # documento inválido → no filtramos nada
    id_municipio = await resolver_municipio_de_origen(request, db)

    # agentes.dni → su usuario vinculado activo → email del usuario (fallback al del agente)
    res = await db.execute(
        text("""SELECT u.id_usuario, u.nombre,
                       COALESCE(NULLIF(u.email, ''), a.email) AS email_destino
                FROM agentes a
                JOIN usuarios u ON u.id_usuario = a.id_usuario
                WHERE a.dni = :dni AND a.activo = TRUE AND u.activo = TRUE AND a.id_municipio = :mun
                LIMIT 1"""),
        {"dni": dni, "mun": id_municipio},
    )
    row = res.fetchone()
    if not row or not row.email_destino:
        return GenericoOkResponse()  # anti-enumeración / sin email donde mandar

    municipio_nombre, municipio_logo_url = await _branding_municipio(db, id_municipio)
    background_tasks.add_task(
        enviar_mail_recordatorio_usuario_interno,
        row.email_destino, row.nombre, await _login_url(db, id_municipio),
        municipio_nombre, municipio_logo_url,
    )
    return GenericoOkResponse()


@router.post("/resetear-password")
async def resetear_password_interno(
    body: ResetearPasswordInternoRequest,
    db: AsyncSession = Depends(get_db),
):
    """Aplica la nueva contraseña usando el token de recovery (válido 24h).
    Limpia la marca debe_cambiar_password y el token. NO devuelve sesión: el
    usuario vuelve al login y entra con la clave nueva."""
    nueva = body.password_nueva or ""
    if len(nueva) < 8:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres.")
    if len(nueva) > 100:
        raise HTTPException(status_code=422, detail="La contraseña es demasiado larga.")

    res = await db.execute(
        text("""SELECT id_usuario, password_hash
                FROM usuarios
                WHERE token_recovery = CAST(:token AS uuid)
                  AND token_recovery_expira > NOW()
                  AND activo = TRUE
                LIMIT 1"""),
        {"token": body.token},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="El enlace es inválido o expiró. Pedí uno nuevo.")

    if verify_password(nueva, row.password_hash):
        raise HTTPException(status_code=422, detail="La contraseña nueva debe ser distinta de la actual.")

    nuevo_hash = hash_password(nueva)
    await db.execute(
        text("""UPDATE usuarios
                   SET password_hash = :h,
                       debe_cambiar_password = FALSE,
                       password_actualizada_en = NOW(),
                       token_recovery = NULL,
                       token_recovery_expira = NULL,
                       fecha_modif = NOW()
                 WHERE id_usuario = :id"""),
        {"h": nuevo_hash, "id": row.id_usuario},
    )
    await db.commit()
    logger.info("RESET PASSWORD por recovery | id=%s", row.id_usuario)
    return {"ok": True}


@router.post("/me/foto-upload-url")
async def crear_upload_url_foto(
    body: FotoUploadRequest,
    current_user: dict = Depends(get_current_user),
):
    """URL firmada para que el usuario suba SU foto de perfil directo a Storage
    (mismo flujo que el logo del municipio, §26). El backend no recibe el binario."""
    if body.mime_type not in FOTO_MIME_OK:
        raise HTTPException(422, "Formato no permitido. Subí una imagen PNG o JPG.")
    if body.tamano_bytes > FOTO_MAX_BYTES:
        raise HTTPException(422, "La imagen excede el máximo de 2 MB.")
    ext = FOTO_MIME_OK[body.mime_type]
    path = f"usuarios/{current_user['id_usuario']}/avatar-{uuid.uuid4()}.{ext}"
    signed = await storage.crear_signed_upload_url(path, bucket=FOTO_BUCKET)
    return {
        "upload_url": signed["upload_url"],
        "public_url": storage.url_publica(path, FOTO_BUCKET),
        "path": path,
        "bucket": FOTO_BUCKET,
    }


@router.put("/me/foto")
async def actualizar_foto(
    body: FotoUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persiste la URL del avatar subido (o la limpia si viene vacía).
    Solo afecta al propio usuario del token."""
    url = (body.foto_url or "").strip()
    # Solo su propio avatar, subido con /me/foto-upload-url: el vaciado borra después ese archivo y
    # una URL ajena le haría borrar otro (revisión de F4+F5).
    prefijo = storage.url_publica("", FOTO_BUCKET)
    ruta = url[len(prefijo):] if url.startswith(prefijo) else ""
    if url and not (storage.ruta_valida(ruta) and re.fullmatch(
            rf"usuarios/{current_user['id_usuario']}/avatar-[0-9a-f-]+\.(png|jpe?g)", ruta)):
        raise HTTPException(422, "La foto tiene que ser la que subiste desde tu perfil.")
    await db.execute(
        text("UPDATE usuarios SET foto_url = :u WHERE id_usuario = :id"),
        {"u": url or None, "id": current_user["id_usuario"]},
    )
    await db.commit()
    return {"ok": True, "foto_url": url or None}
