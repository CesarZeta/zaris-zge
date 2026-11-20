"""
ZARIS API — Lo único que corre SIN la segunda barrera (IT-01 F6, PLAN_MULTI_MUNICIPIO_F6_DISENO.md §4.4).

Cinco excepciones, todas de autenticación o exclusivas del super administrador:
  1. Cuentas del super por identificador (login, emails reservados).
  2. La sesión del super (su cuenta sin municipio, su segundo factor, su registro de accesos).
  3. Tokens públicos: token → municipio, nada más; el resto de la request sigue con la barrera.
  4. Alta de un municipio (lee del modelo y escribe en el nuevo).
  5. Pantallas globales del super (módulo Municipios, parámetros globales, registro de accesos).

Este es el ÚNICO archivo que abre la conexión sin barrera. `tools/barrido_sistema.py` falla si
`SesionSistema` o `get_db_sistema` se importan desde un archivo que no está en su lista permitida.
Con DB_BARRERA=false reusa el motor de siempre (ninguna conexión extra contra el pooler).
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import database
from app.core.config import settings

_engine_sistema = (
    create_async_engine(settings.ASYNC_DATABASE_URI, echo=False, future=True, pool_size=2, max_overflow=3)
    if settings.DB_BARRERA else database.engine
)

SesionSistema = async_sessionmaker(_engine_sistema, class_=AsyncSession, expire_on_commit=False)


async def get_db_sistema():
    """Dependency para los handlers de las excepciones 4 y 5 (solo routers exclusivos del super)."""
    async with SesionSistema() as session:
        try:
            yield session
        finally:
            await session.close()
