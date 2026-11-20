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
import uuid
from typing import Optional

from sqlalchemy import text
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


# ── Excepciones 1 y 2: cuentas del super (sin municipio) ─────────────────────────────────────

async def cuenta_de_sesion_super(id_usuario: int):
    """La cuenta detrás de un token de super (`sa`), con las columnas que valida get_current_user."""
    from app.core.auth import COLUMNAS_SESION
    async with SesionSistema() as db:
        return (await db.execute(text(COLUMNAS_SESION + " WHERE id_usuario = :id"), {"id": id_usuario})).fetchone()


async def es_email_de_super(email: Optional[str]) -> bool:
    """True si el email es el de una cuenta sin municipio (emails reservados, CLAUDE.md §1)."""
    if not (email or "").strip():
        return False
    async with SesionSistema() as db:
        return bool(await db.scalar(text(
            "SELECT 1 FROM usuarios WHERE lower(email) = lower(:e) AND id_municipio IS NULL LIMIT 1"),
            {"e": email.strip()}))


# ── Excepción 3: tokens públicos → municipio ─────────────────────────────────────────────────

# tipo → (tabla, columna del token, la columna es uuid). Lista cerrada: un tipo nuevo se suma acá.
_TOKENS: dict[str, tuple[str, str, bool]] = {
    "encuesta": ("encuesta_envio", "token_unico", True),
    "turno": ("turnos", "token_turno", True),
    "pantalla": ("espacios_agenda", "token_pantalla", True),
    "evento": ("eventos", "token_publico", True),
    "reserva": ("evento_reservas", "token_reserva", True),
    "activacion_vecino": ("ciudadano_credencial", "token_activacion", True),
    "recuperacion_vecino": ("ciudadano_credencial", "token_recovery", True),
    "verificacion_empresa": ("empresa_credencial", "token_verificacion", True),
    "recuperacion_interna": ("usuarios", "token_recovery", True),
    "invitacion": ("usuario_invitacion", "token_hash", False),
}


async def municipio_de_token(tipo: str, token: str) -> Optional[dict]:
    """{"id_municipio": …} de la fila del token, o None si no existe. Solo eso: el resto de la request
    sigue con la barrera de ese municipio. `id_municipio` puede ser None (recuperación o invitación
    de una cuenta del super): ese caso lo sigue la conexión de sistema."""
    if tipo not in _TOKENS:
        raise ValueError(f"tipo de token desconocido: {tipo}")
    tabla, columna, es_uuid = _TOKENS[tipo]
    if es_uuid:
        try:
            token = str(uuid.UUID(str(token)))
        except (ValueError, AttributeError, TypeError):
            return None
    valor = "CAST(:t AS uuid)" if es_uuid else ":t"
    async with SesionSistema() as db:
        fila = (await db.execute(text(f"SELECT id_municipio FROM {tabla} WHERE {columna} = {valor} LIMIT 1"),
                                 {"t": token})).first()
    return None if fila is None else {"id_municipio": fila.id_municipio}


async def fijar_por_token(db: AsyncSession, token: str, *tipos: str) -> bool:
    """Fija en `db` el municipio de la fila del token (el primero de `tipos` que lo tenga) y devuelve
    True. Si no aparece, no fija nada: la ruta sigue y su propia consulta responde «no encontrado».
    Para `invitacion` se pasa el hash del token (la tabla guarda el hash)."""
    for tipo in tipos:
        duenio = await municipio_de_token(tipo, token)
        if duenio is not None and duenio["id_municipio"] is not None:
            await database.fijar_municipio(db, duenio["id_municipio"])
            return True
    return False
