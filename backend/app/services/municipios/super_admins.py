"""
Alta y baja de super administradores (IT-01 F4+F5, Tarea 15, spec §4.6).

Cuenta de nivel 0 sin municipio. El alta no fija clave: manda una invitación (el mail sale como
ZARIS) y la cuenta entra con segundo factor (F3b). Nadie se da de baja a sí mismo y siempre queda un
super activo. Las dos operaciones van en la transacción del llamador.
"""
import secrets

import bcrypt
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.municipios.invitacion import crear_invitacion

EMAIL_EN_USO = "Ese email ya es de otra cuenta."
BAJA_PROPIA = "No podés darte de baja a vos mismo: pedíselo a otro super administrador."
ULTIMO_SUPER = "No se puede dar de baja al último super administrador activo."


async def listar_supers(db: AsyncSession) -> list[dict]:
    rows = await db.execute(text("""
        SELECT u.id_usuario, u.nombre, u.email, u.activo,
               EXISTS (SELECT 1 FROM usuario_invitacion i WHERE i.id_usuario = u.id_usuario AND i.activo
                          AND i.usada_en IS NULL AND i.vence_en > NOW()) AS invitacion_pendiente
          FROM usuarios u
         WHERE u.nivel_acceso = 0 AND u.id_municipio IS NULL
         ORDER BY u.activo DESC, u.nombre"""))
    return [dict(r._mapping) for r in rows]


async def crear_super(db: AsyncSession, *, nombre: str, apellido: str, email: str, id_actor: int,
                      background_tasks: BackgroundTasks) -> int:
    """Crea la cuenta y su invitación. 409 si el email ya es de cualquier cuenta: un email repetido con
    una cuenta de un municipio haría que el login lo resuelva a esa y no al super."""
    email = email.strip().lower()
    if await db.scalar(text("SELECT 1 FROM usuarios WHERE lower(email) = :e OR lower(username) = :e LIMIT 1"),
                       {"e": email}):
        raise HTTPException(status_code=409, detail=EMAIL_EN_USO)
    # La clave queda inutilizable hasta que la invitación la reemplace.
    hash_inutil = bcrypt.hashpw(secrets.token_hex(32).encode(), bcrypt.gensalt()).decode()
    id_usuario = await db.scalar(text("""
        INSERT INTO usuarios (nombre, nivel_acceso, username, email, password_hash, id_municipio, activo,
                              buc_acceso, debe_cambiar_password)
        VALUES (:n, 0, :e, :e, :h, NULL, TRUE, FALSE, FALSE)
        RETURNING id_usuario"""), {"n": f"{nombre.strip()} {apellido.strip()}", "e": email, "h": hash_inutil})
    await crear_invitacion(db, id_usuario=id_usuario, id_municipio=None, id_actor=id_actor,
                           background_tasks=background_tasks)
    return id_usuario


async def dar_de_baja_super(db: AsyncSession, *, id_usuario: int, id_actor: int) -> None:
    """Desactiva la cuenta, corta sus sesiones y anula sus invitaciones. Toma las filas de los supers
    con FOR UPDATE: dos bajas cruzadas a la vez no dejan el sistema sin super."""
    filas = (await db.execute(text("""
        SELECT id_usuario, activo FROM usuarios WHERE nivel_acceso = 0 AND id_municipio IS NULL
         ORDER BY id_usuario FOR UPDATE"""))).all()
    objetivo = next((f for f in filas if f.id_usuario == id_usuario), None)
    if objetivo is None:
        raise HTTPException(status_code=404, detail="Super administrador no encontrado")
    if id_usuario == id_actor:
        raise HTTPException(status_code=409, detail=BAJA_PROPIA)
    if not any(f.activo for f in filas if f.id_usuario != id_usuario):
        raise HTTPException(status_code=409, detail=ULTIMO_SUPER)
    await db.execute(text("""
        UPDATE usuarios SET activo = FALSE, sesiones_validas_desde = NOW() WHERE id_usuario = :u"""),
        {"u": id_usuario})
    await db.execute(text("UPDATE usuario_invitacion SET activo = FALSE WHERE id_usuario = :u AND activo"),
                     {"u": id_usuario})
