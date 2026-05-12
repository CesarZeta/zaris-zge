"""
ZARIS API — Endpoints de autenticación.
POST /api/v1/auth/login  → JWT
GET  /api/v1/auth/me     → usuario actual
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import (
    verify_password,
    create_access_token,
    get_current_user,
    modulos_permitidos,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT id_usuario, nombre, email, nivel_acceso, password_hash, activo
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

    token = create_access_token({"sub": str(user.id_usuario)})
    modulos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso)
    user_data = {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "email": user.email,
        "nivel_acceso": user.nivel_acceso,
        "modulos_permitidos": modulos,
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
