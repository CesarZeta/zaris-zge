"""
ZARIS API — Database engine + async session factory.

Segunda barrera (IT-01 F6, PLAN_MULTI_MUNICIPIO_F6_DISENO.md §4.1-4.3): con DB_BARRERA=true el motor
de las requests entra como APP_DB_USER, sujeto a las políticas de la migración 138, que comparan
`id_municipio` con la variable `app.id_municipio`. El municipio de cada sesión vive en
`session.info["id_municipio"]` y un listener lo aplica al empezar CADA transacción (sobrevive a los
commits intermedios de un guardado). Sin municipio fijado, una tabla de municipio no devuelve filas.

- `fijar_municipio(db, id)`: lo llaman las entradas (auth, municipio_actual, origen, tokens, crons).
- `sesion_municipio(id)`: sesiones fuera de una request (avisos, mails, procesos).
- La conexión SIN barrera solo existe en `app/core/sistema.py` (lista cerrada de excepciones).
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.core.config import settings

engine = create_async_engine(
    settings.ASYNC_DATABASE_URI_APP,
    echo=False,
    future=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

_SET_MUNICIPIO = text("SELECT set_config('app.id_municipio', :m, true)")


@event.listens_for(Session, "after_begin")
def _aplicar_municipio(session: Session, transaction, connection) -> None:
    """Cada transacción nueva de una sesión con municipio arranca con la variable puesta."""
    id_municipio = session.info.get("id_municipio")
    if id_municipio is not None:
        connection.execute(_SET_MUNICIPIO, {"m": str(id_municipio)})


async def fijar_municipio(db: AsyncSession, id_municipio: int) -> None:
    """El municipio de la sesión: rige desde ya (transacción en curso) y en las siguientes."""
    id_municipio = int(id_municipio)
    db.info["id_municipio"] = id_municipio
    if db.in_transaction():
        await db.execute(_SET_MUNICIPIO, {"m": str(id_municipio)})


@asynccontextmanager
async def sesion_municipio(id_municipio: int) -> AsyncIterator[AsyncSession]:
    """Sesión fuera de una request con el municipio ya fijado."""
    async with AsyncSessionLocal() as db:
        db.info["id_municipio"] = int(id_municipio)
        yield db


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency que provee una sesión async de BD."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
