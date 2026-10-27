"""
Valores por defecto de cada municipio para catálogos globales (guía de arranque, R9 y R10).

`nacionalidades` y `tipo_representacion` son globales: el default sale de la configuración del
municipio (`id_nacionalidad_defecto`, `id_tipo_representacion_defecto`). Sin clave válida se resuelve
por nombre (la nacionalidad del país del municipio; «Representante Legal»), y si tampoco hay, 422.
"""
import re

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_municipio import leer_config


async def _desde_clave(db: AsyncSession, clave: str, tabla: str, id_municipio: int) -> int | None:
    valor = (await leer_config(db, clave, id_municipio) or "").strip()
    if re.fullmatch(r"[0-9]{1,9}", valor) and await db.scalar(
            text(f"SELECT 1 FROM {tabla} WHERE id = :i"), {"i": int(valor)}):
        return int(valor)
    return None


async def nacionalidad_por_pais(db: AsyncSession, id_municipio: int) -> int | None:
    return await db.scalar(text("""
        SELECT n.id FROM nacionalidades n
          JOIN municipios m ON m.id_municipio = :m JOIN paises p ON p.codigo_pais = m.codigo_pais
         WHERE n.pais ILIKE p.nombre ORDER BY n.id LIMIT 1"""), {"m": id_municipio})


async def representacion_por_nombre(db: AsyncSession) -> int | None:
    return await db.scalar(text(
        "SELECT id FROM tipo_representacion WHERE tipo = 'Representante Legal' ORDER BY id LIMIT 1"))


async def id_nacionalidad_defecto(db: AsyncSession, id_municipio: int) -> int:
    v = await _desde_clave(db, "id_nacionalidad_defecto", "nacionalidades", id_municipio) \
        or await nacionalidad_por_pais(db, id_municipio)
    if v is None:
        raise HTTPException(422, "El municipio no tiene nacionalidad por defecto: cargala en Configuración → Sistema.")
    return v


async def id_tipo_representacion_defecto(db: AsyncSession, id_municipio: int) -> int:
    v = await _desde_clave(db, "id_tipo_representacion_defecto", "tipo_representacion", id_municipio) \
        or await representacion_por_nombre(db)
    if v is None:
        raise HTTPException(422, "El municipio no tiene tipo de representación por defecto.")
    return v
