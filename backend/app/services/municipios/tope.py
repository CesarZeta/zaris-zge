"""
Tope de cuentas internas activas por municipio (IT-01 F4+F5, Tarea 14).

Cuentan los usuarios activos de nivel 1 a 5 del municipio; el super administrador (sin municipio)
y los vecinos (otra tabla) no. Bajar el tope por debajo de las activas no desactiva a nadie: solo
impide crear o reactivar hasta que haya lugar.
"""
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TOPE_ALCANZADO = ("El municipio llegó al tope de {maximo} cuentas activas. Pedí al soporte de ZARIS que lo "
                  "amplíe o desactivá una cuenta.")
# Desde qué proporción del tope la pantalla de Usuarios avisa.
UMBRAL_AVISO = 0.9

_ACTIVAS = ("SELECT count(*) FROM usuarios WHERE id_municipio = :m AND activo "
            "AND nivel_acceso BETWEEN 1 AND 5")


async def exigir_cupo(db: AsyncSession, id_municipio: int) -> None:
    """409 si el municipio ya tiene tantas cuentas activas como su tope. Toma la fila del municipio
    con FOR UPDATE hasta el commit del caller: dos altas simultáneas se serializan."""
    maximo = await db.scalar(text(
        "SELECT max_usuarios_activos FROM municipios WHERE id_municipio = :m FOR UPDATE"), {"m": id_municipio})
    if maximo is None:
        return
    if await db.scalar(text(_ACTIVAS), {"m": id_municipio}) >= maximo:
        raise HTTPException(status_code=409, detail=TOPE_ALCANZADO.format(maximo=maximo))


async def cupo(db: AsyncSession, id_municipio: int) -> dict:
    maximo = await db.scalar(text("SELECT max_usuarios_activos FROM municipios WHERE id_municipio = :m"),
                             {"m": id_municipio})
    activas = await db.scalar(text(_ACTIVAS), {"m": id_municipio})
    return {"activas": activas, "maximo": maximo,
            "aviso": maximo is not None and activas >= UMBRAL_AVISO * maximo}
