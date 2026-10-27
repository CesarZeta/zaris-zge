"""
Invitación a elegir la clave (IT-01 F4+F5, Tarea 11): primer administrador de un municipio y super
administradores nuevos. El token viaja solo por mail; en la base queda su sha256. Vale
INVITACION_HORAS y una sola vez; una invitación nueva desactiva las anteriores de la cuenta.
Aceptarla guarda la clave y habilita la vinculación del segundo factor (24 h, como F3b): el super que
invitó nunca conoce la clave.
"""
import hashlib
import secrets
from typing import Optional

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_municipio import leer_configs
from app.core.urls import base_app
from app.services.municipios.constantes import INVITACION_HORAS

INVITACION_INVALIDA = "El enlace venció o ya se usó. Pedí al soporte de ZARIS que te reenvíe la invitación."


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def crear_invitacion(db: AsyncSession, *, id_usuario: int, id_municipio: Optional[int], id_actor: int,
                           background_tasks: BackgroundTasks) -> str:
    """Crea la invitación (desactiva las anteriores), encola el mail y devuelve el link. NO commitea:
    va en la transacción del llamador (si el alta falla, no queda invitación)."""
    base = await base_app(db, id_municipio, "zge")
    if not base:
        raise HTTPException(422, "El municipio no tiene dirección: falta el subdominio")
    usuario = (await db.execute(text("SELECT nombre, email FROM usuarios WHERE id_usuario = :u"),
                                {"u": id_usuario})).first()
    if usuario is None or not (usuario.email or "").strip():
        raise HTTPException(422, "La cuenta no tiene email")
    token = secrets.token_urlsafe(32)
    await db.execute(text("UPDATE usuario_invitacion SET activo = FALSE WHERE id_usuario = :u AND activo"),
                     {"u": id_usuario})
    await db.execute(text("""
        INSERT INTO usuario_invitacion (id_usuario, id_municipio, token_hash, vence_en, id_usuario_alta)
        VALUES (:u, :m, :h, NOW() + make_interval(hours => :horas), :a)"""),
        {"u": id_usuario, "m": id_municipio, "h": hash_token(token), "horas": INVITACION_HORAS, "a": id_actor})
    link = f"{base}/frontend/invitacion.html?t={token}"
    if id_municipio is None:
        nombre_mun, logo = "ZARIS", None
    else:
        cfg = await leer_configs(db, ["municipio_nombre", "municipio_logo_url"], id_municipio)
        nombre_mun = cfg.get("municipio_nombre") or await db.scalar(
            text("SELECT nombre FROM municipios WHERE id_municipio = :m"), {"m": id_municipio}) or "Tu municipio"
        logo = cfg.get("municipio_logo_url") or None
    from app.services.email import enviar_mail_invitacion_usuario_interno
    background_tasks.add_task(
        enviar_mail_invitacion_usuario_interno, usuario.email, usuario.nombre, link, INVITACION_HORAS,
        nombre_mun, logo, id_municipio is None)
    return link


async def tomar_invitacion(db: AsyncSession, token: str):
    """La invitación vigente del token, bloqueada para esta transacción (dos aceptaciones a la vez:
    pasa una). 401 con el texto fijo si no existe, venció o ya se usó."""
    fila = (await db.execute(text("""
        SELECT i.id_invitacion, i.id_usuario, i.id_municipio, i.id_usuario_alta
          FROM usuario_invitacion i
         WHERE i.token_hash = :h AND i.activo AND i.usada_en IS NULL AND i.vence_en > NOW()
         FOR UPDATE"""), {"h": hash_token(token or "")})).first()
    if fila is None:
        raise HTTPException(401, INVITACION_INVALIDA)
    return fila
