"""
ZARIS API — Reglas del super administrador que usan otros módulos (IT-01 F3).

Los identificadores de las cuentas de nivel 0 quedan reservados (spec §3): ninguna cuenta de un
municipio puede usar el email de un super administrador, porque el login busca primero en el
municipio y una cuenta así le taparía el acceso. Plan: PLAN_MULTI_MUNICIPIO_F3.md, Tarea 4.
"""
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

EMAIL_RESERVADO = "Ese email está reservado"


async def email_reservado_super_admin(db: AsyncSession, email: Optional[str]) -> bool:
    """True si el email es el de una cuenta sin municipio (super administrador)."""
    if not (email or "").strip():
        return False
    return bool(await db.scalar(text(
        "SELECT 1 FROM usuarios WHERE lower(email) = lower(:e) AND id_municipio IS NULL LIMIT 1"),
        {"e": email.strip()}))
