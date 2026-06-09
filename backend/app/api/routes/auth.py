"""
ZARIS API — Endpoints de autenticación.
POST /api/v1/auth/login  → JWT
GET  /api/v1/auth/me     → usuario actual
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT id_usuario, nombre, email, nivel_acceso, password_hash, activo,
                   debe_cambiar_password
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
    user_data = {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "email": user.email,
        "nivel_acceso": user.nivel_acceso,
        "modulos_permitidos": modulos,
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
    return {**current_user, "modulos_permitidos": modulos}


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
