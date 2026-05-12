"""
ZARIS API — Autenticación JWT + hashing de contraseñas.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 1440  # 24 h


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise unauthorized
    except JWTError:
        raise unauthorized

    result = await db.execute(
        text("SELECT id_usuario, nombre, email, nivel_acceso, activo FROM usuarios WHERE id_usuario = :id"),
        {"id": int(user_id)},
    )
    user = result.fetchone()
    if not user or not user.activo:
        raise unauthorized
    return dict(user._mapping)


async def modulos_permitidos(db: AsyncSession, id_usuario: int, nivel: int) -> list[str]:
    """Resuelve la lista de modulo_codigo que un usuario puede ver, aplicando
    el modelo hibrido de CLAUDE.md §30: default por min_nivel_acceso + override
    explicito por usuario_modulos (permitido TRUE otorga, FALSE bloquea).
    """
    defaults = await db.execute(
        text("""
            SELECT modulo_codigo FROM modulos
            WHERE activo = TRUE AND min_nivel_acceso >= :nivel
        """),
        {"nivel": nivel},
    )
    permitidos = {r.modulo_codigo for r in defaults.fetchall()}

    overrides = await db.execute(
        text("""
            SELECT modulo_codigo, permitido FROM usuario_modulos
            WHERE id_usuario = :uid AND activo = TRUE
        """),
        {"uid": id_usuario},
    )
    for r in overrides.fetchall():
        if r.permitido:
            permitidos.add(r.modulo_codigo)
        else:
            permitidos.discard(r.modulo_codigo)
    return sorted(permitidos)


def require_modulo(modulo: str):
    """Dependencia FastAPI que valida que el usuario tenga acceso al modulo
    indicado. Uso: `current = Depends(require_modulo("reclamos"))`. Devuelve
    el `current_user` igual que `get_current_user` para que el endpoint lo use.
    """
    async def _guard(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        modulos = await modulos_permitidos(
            db, current_user["id_usuario"], current_user["nivel_acceso"]
        )
        if modulo not in modulos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sin acceso al modulo '{modulo}'",
            )
        return current_user
    return _guard
