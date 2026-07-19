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
from app.core.database import get_db
from app.core import storage
from app.core.auth import (
    verify_password,
    hash_password,
    create_access_token,
    get_current_user,
    modulos_permitidos,
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
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


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


async def _perfil_agente_del_usuario(db: AsyncSession, id_usuario: int) -> dict:
    """Cargo y subárea del agente vinculado al usuario (regla 1:1 §39). Valores
    None si el usuario no tiene agente (externo) o el agente no los tiene.
    La subárea la usan los módulos React para scopear pickers del supervisor
    (Fase 3 roles); la imposición dura vive en el backend de cada módulo."""
    result = await db.execute(
        text("""SELECT c.nombre AS cargo_nombre,
                       a.id_subarea, s.nombre AS subarea_nombre
                FROM agentes a
                LEFT JOIN cargos c ON c.id_cargo = a.id_cargo
                LEFT JOIN subarea s ON s.id_subarea = a.id_subarea
                WHERE a.id_usuario = :id AND a.activo = TRUE
                LIMIT 1"""),
        {"id": id_usuario},
    )
    row = result.fetchone()
    if not row:
        return {"cargo_nombre": None, "id_subarea": None, "subarea_nombre": None}
    return {"cargo_nombre": row.cargo_nombre, "id_subarea": row.id_subarea,
            "subarea_nombre": row.subarea_nombre}


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Anti brute-force online: limitar intentos por IP y por cuenta ANTES de
    # tocar la DB o verificar bcrypt. Claves prefijadas por flujo (§5) para no
    # compartir bucket con otros endpoints. In-memory single-replica (limitación
    # conocida de rate_limit.py): mitiga el ataque online, no reemplaza un lockout
    # persistente en DB (pendiente, requiere migración de columnas en usuarios).
    from app.utils.request_helpers import get_real_ip
    from app.middleware.rate_limit import check_rate_limit
    _ip = get_real_ip(request)
    _mail = (body.email or "").strip().lower()
    check_rate_limit(f"loginint-ip:{_ip}", max_requests=10, window_seconds=60)
    if _mail:
        check_rate_limit(f"loginint-mail:{_mail}", max_requests=5, window_seconds=60)

    result = await db.execute(
        text("""
            SELECT id_usuario, nombre, email, nivel_acceso, password_hash, activo,
                   debe_cambiar_password, foto_url
            FROM usuarios
            WHERE email = :email
        """),
        {"email": body.email},
    )
    user = result.fetchone()

    if not user or not user.activo or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales no coinciden. Probá de nuevo.",
        )

    # Auditoría de login: actualizar el último login (denormalizado para la UI)
    # e insertar la fila append-only en usuario_login_log. Best-effort: un fallo
    # acá no debe impedir el login.
    try:
        from app.utils.request_helpers import get_real_ip
        ip = get_real_ip(request)
        ua = (request.headers.get("user-agent") or "")[:1000]
        await db.execute(
            text("UPDATE usuarios SET fecha_ultimo_login = NOW() WHERE id_usuario = :id"),
            {"id": user.id_usuario},
        )
        await db.execute(
            text("""INSERT INTO usuario_login_log (id_usuario, ip, user_agent)
                    VALUES (:id, :ip, :ua)"""),
            {"id": user.id_usuario, "ip": ip[:64], "ua": ua},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("No se pudo registrar auditoría de login id=%s: %s", user.id_usuario, exc)

    # Politica de renovacion de credenciales (mig 96): si la clave supera la
    # vigencia configurada (password_renovacion_dias, 0 = desactivado), se
    # fuerza el cambio reutilizando el gate existente de debe_cambiar_password.
    debe_cambiar = bool(user.debe_cambiar_password)
    if not debe_cambiar:
        try:
            _vig = await db.scalar(text(
                "SELECT valor FROM configuracion_general "
                "WHERE clave = 'password_renovacion_dias' AND activo = TRUE LIMIT 1"
            ))
            _dias = int(str(_vig).strip()) if _vig is not None else 0
        except (TypeError, ValueError):
            _dias = 0
        if _dias > 0:
            vencida = await db.scalar(text("""
                SELECT 1 FROM usuarios
                WHERE id_usuario = :id
                  AND password_actualizada_en IS NOT NULL
                  AND password_actualizada_en < NOW() - make_interval(days => CAST(:d AS integer))
            """), {"id": user.id_usuario, "d": _dias})
            if vencida:
                await db.execute(text(
                    "UPDATE usuarios SET debe_cambiar_password = TRUE WHERE id_usuario = :id"
                ), {"id": user.id_usuario})
                await db.commit()
                debe_cambiar = True
                logger.info("RENOVACION PASSWORD forzada por vigencia | id=%s | dias=%s",
                            user.id_usuario, _dias)

    token = create_access_token({"sub": str(user.id_usuario)})
    modulos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso)
    perfil = await _perfil_agente_del_usuario(db, user.id_usuario)
    user_data = {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "email": user.email,
        "nivel_acceso": user.nivel_acceso,
        "modulos_permitidos": modulos,
        # Cargo del agente vinculado (None si externo/sin cargo) — lo muestra
        # el topbar del shell debajo de "Nombre · Rol".
        "cargo_nombre": perfil["cargo_nombre"],
        # Subárea del agente vinculado — los módulos React la usan para scopear
        # pickers cuando el usuario es supervisor (nivel 2, Fase 3 roles).
        "id_subarea": perfil["id_subarea"],
        "subarea_nombre": perfil["subarea_nombre"],
        "foto_url": user.foto_url,
        # Si TRUE, el frontend debe forzar el cambio de contraseña antes de
        # dejar usar el sistema (clave temporal en primer ingreso, o clave
        # vencida por la politica de renovacion mig 96).
        "debe_cambiar_password": debe_cambiar,
    }
    return LoginResponse(access_token=token, user=user_data)


@router.get("/me")
async def me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    modulos = await modulos_permitidos(
        db, current_user["id_usuario"], current_user["nivel_acceso"]
    )
    perfil = await _perfil_agente_del_usuario(db, current_user["id_usuario"])
    return {**current_user, "modulos_permitidos": modulos, **perfil}


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


async def _branding_municipio(db: AsyncSession) -> tuple[str, str | None]:
    """(municipio_nombre, municipio_logo_url) desde configuracion_general."""
    res = await db.execute(
        text("SELECT clave, valor FROM configuracion_general "
             "WHERE clave IN ('municipio_nombre','municipio_logo_url')")
    )
    cfg = {r.clave: r.valor for r in res.fetchall()}
    return (cfg.get("municipio_nombre") or "Tu municipio", cfg.get("municipio_logo_url") or None)


def _login_url() -> str:
    """URL del login del shell vanilla (CTA de los mails internos)."""
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/frontend/login.html"


@router.post("/recuperar-password", response_model=GenericoOkResponse)
async def recuperar_password(
    body: RecuperarPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Olvidé mi contraseña (interno): manda link de reseteo al correo del usuario.
    Anti-enumeración + cooldown silencioso de 5 minutos."""
    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        # No revelamos validación: respondemos OK igual.
        return GenericoOkResponse()

    res = await db.execute(
        text("""SELECT id_usuario, nombre, email, fecha_ultimo_email_recovery
                FROM usuarios
                WHERE LOWER(email) = :email AND activo = TRUE
                LIMIT 1"""),
        {"email": email},
    )
    row = res.fetchone()
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

    municipio_nombre, municipio_logo_url = await _branding_municipio(db)
    background_tasks.add_task(
        enviar_mail_recovery_usuario_interno,
        row.email, row.nombre, token, _login_url(),
        municipio_nombre, municipio_logo_url,
    )
    return GenericoOkResponse()


@router.post("/recuperar-usuario", response_model=GenericoOkResponse)
async def recuperar_usuario(
    body: RecuperarUsuarioRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Olvidé mi usuario (interno): el empleado ingresa su DNI. Se resuelve el agente
    vinculado (regla 1:1 §39) → su usuario → su email, y se manda un recordatorio a
    esa casilla. Anti-enumeración: siempre 200 OK; el email nunca se muestra en pantalla."""
    dni = _solo_digitos(body.documento)
    if not (7 <= len(dni) <= 8):
        return GenericoOkResponse()  # documento inválido → no filtramos nada

    # agentes.dni → su usuario vinculado activo → email del usuario (fallback al del agente)
    res = await db.execute(
        text("""SELECT u.id_usuario, u.nombre,
                       COALESCE(NULLIF(u.email, ''), a.email) AS email_destino
                FROM agentes a
                JOIN usuarios u ON u.id_usuario = a.id_usuario
                WHERE a.dni = :dni AND a.activo = TRUE AND u.activo = TRUE
                LIMIT 1"""),
        {"dni": dni},
    )
    row = res.fetchone()
    if not row or not row.email_destino:
        return GenericoOkResponse()  # anti-enumeración / sin email donde mandar

    municipio_nombre, municipio_logo_url = await _branding_municipio(db)
    background_tasks.add_task(
        enviar_mail_recordatorio_usuario_interno,
        row.email_destino, row.nombre, _login_url(),
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
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(422, "foto_url debe ser una URL http(s) o vacía.")
    await db.execute(
        text("UPDATE usuarios SET foto_url = :u WHERE id_usuario = :id"),
        {"u": url or None, "id": current_user["id_usuario"]},
    )
    await db.commit()
    return {"ok": True, "foto_url": url or None}
