"""
ZARIS API — Endpoints de autenticación.
POST /api/v1/auth/login  → JWT
GET  /api/v1/auth/me     → usuario actual
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core import storage
from app.core.auth import (
    verify_password,
    hash_password,
    create_access_token,
    get_current_user,
    modulos_permitidos,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
logger = logging.getLogger("zaris.auth")


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


async def _cargo_del_usuario(db: AsyncSession, id_usuario: int) -> str | None:
    """Cargo del agente vinculado al usuario (regla 1:1 §39). NULL si el usuario
    no tiene agente (externo) o el agente no tiene cargo asignado."""
    result = await db.execute(
        text("""SELECT c.nombre
                FROM agentes a
                JOIN cargos c ON c.id_cargo = a.id_cargo
                WHERE a.id_usuario = :id AND a.activo = TRUE
                LIMIT 1"""),
        {"id": id_usuario},
    )
    return result.scalar()


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
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

    token = create_access_token({"sub": str(user.id_usuario)})
    modulos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso)
    cargo = await _cargo_del_usuario(db, user.id_usuario)
    user_data = {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "email": user.email,
        "nivel_acceso": user.nivel_acceso,
        "modulos_permitidos": modulos,
        # Cargo del agente vinculado (None si externo/sin cargo) — lo muestra
        # el topbar del shell debajo de "Nombre · Rol".
        "cargo_nombre": cargo,
        "foto_url": user.foto_url,
        # Si TRUE, el frontend debe forzar el cambio de contraseña antes de
        # dejar usar el sistema (Fase 3, clave temporal en primer ingreso).
        "debe_cambiar_password": bool(user.debe_cambiar_password),
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
    cargo = await _cargo_del_usuario(db, current_user["id_usuario"])
    return {**current_user, "modulos_permitidos": modulos, "cargo_nombre": cargo}


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
                   SET password_hash = :h, debe_cambiar_password = FALSE
                 WHERE id_usuario = :id"""),
        {"h": nuevo_hash, "id": current_user["id_usuario"]},
    )
    await db.commit()
    logger.info("CAMBIO PASSWORD self-service | id=%s | forzado=%s",
                current_user["id_usuario"], forzado)
    return {"ok": True, "debe_cambiar_password": False}


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
