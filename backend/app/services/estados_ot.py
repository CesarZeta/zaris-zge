"""
Estados de OT por su nombre (catálogo global `estado_ot`; el nombre es único y hace de código).

Un estado que falta da 409 con el nombre, en lugar de insertar o actualizar una OT con estado NULL
(guía de arranque, R7).
"""
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def id_estado_ot(db: AsyncSession, nombre: str) -> int:
    valor = await db.scalar(text("SELECT id_estado_ot FROM estado_ot WHERE nombre = :n AND activo = TRUE"),
                            {"n": nombre})
    if valor is None:
        raise HTTPException(409, f"Falta el estado de OT «{nombre}» en el catálogo: pedí al soporte de ZARIS que lo cargue.")
    return valor
