"""
ZARIS API — Lectura y guardado de configuracion_general por municipio (IT-01, F2).

Cada clave puede tener una fila del municipio y/o una global (`id_municipio IS NULL`): se lee la
del municipio y, si no hay, la global. Las claves VAPID son solo globales. Toda lectura de
configuracion_general pasa por acá (regla R9 de PLAN_MULTI_MUNICIPIO_F1_F2.md).

Mientras exista el índice viejo UNIQUE (clave) (hasta el lote de limpieza), una clave no puede
estar a la vez como global y como del municipio, ni en dos municipios: guardar_config solo
actualiza la fila existente del municipio.
"""
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def leer_config(db: AsyncSession, clave: str, id_municipio: Optional[int]) -> Optional[str]:
    """Valor activo de la clave para el municipio (o el global si el municipio no la tiene)."""
    return (await db.execute(text("""
        SELECT valor FROM configuracion_general
         WHERE clave = :clave AND activo = TRUE
           AND (id_municipio = :mun OR id_municipio IS NULL)
         ORDER BY id_municipio NULLS LAST
         LIMIT 1"""), {"clave": clave, "mun": id_municipio})).scalar()


async def leer_configs(db: AsyncSession, claves: list[str], id_municipio: Optional[int]) -> dict[str, str]:
    """Varias claves de una vez, con la misma precedencia que leer_config."""
    rows = (await db.execute(text("""
        SELECT DISTINCT ON (clave) clave, valor FROM configuracion_general
         WHERE clave = ANY(:claves) AND activo = TRUE
           AND (id_municipio = :mun OR id_municipio IS NULL)
         ORDER BY clave, id_municipio NULLS LAST"""), {"claves": list(claves), "mun": id_municipio})).fetchall()
    return {r.clave: r.valor for r in rows}


async def guardar_config(db: AsyncSession, clave: str, valor: str, id_municipio: int, tipo: str = "string") -> bool:
    """Guarda la clave del municipio: la actualiza o, si el municipio no la tiene (municipio nuevo o
    vaciado), la crea con `tipo` y activa (guía de arranque, R3). Devuelve True."""
    await db.execute(text("""
        INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
        VALUES (:clave, :valor, :tipo, :descripcion, TRUE, :mun)
        ON CONFLICT (id_municipio, clave) DO UPDATE SET valor = EXCLUDED.valor, fecha_modificacion = NOW()"""),
        {"clave": clave, "valor": valor, "tipo": tipo, "descripcion": clave, "mun": id_municipio})
    return True
