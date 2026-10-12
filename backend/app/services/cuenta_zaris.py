"""
Servicio: alta de un USUARIO INTERNO de ZARIS (backoffice + app de agentes).

Una sola implementación para las dos vías de alta (misma lógica, no dos copias):
  - Maestros → Usuarios (`POST /buc/usuarios`): alta "a secas", el agente 1:1 nace con
    datos mínimos (se completan después desde Agentes).
  - Ficha del ciudadano (`POST /buc/ciudadanos/{id}/cuenta-zaris`, mig 110): el usuario
    queda vinculado a la persona de la BUC (`usuarios.id_ciudadano`) y el agente 1:1 nace
    con nombre, apellido, DNI, CUIL, email y teléfono reales.

Reglas que conserva (§39): clave temporal + `debe_cambiar_password` (si el cliente no
manda password), email obligatorio y único, username único, agente 1:1 salvo externo,
mail de credenciales best-effort post-commit (BackgroundTasks).

NO commitea — el caller controla la transacción (y puede sumar otras escrituras, como
asegurar la cuenta de vecino, antes del commit).
"""
import logging
import secrets

import bcrypt
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.buc import Ciudadano, Usuario
from app.schemas.buc import UsuarioCreate

logger = logging.getLogger("zaris.cuenta_zaris")


def generar_password_temporal(largo: int = 10) -> str:
    """Clave temporal legible y segura: sin caracteres ambiguos (0/O, 1/l/I).
    Garantiza al menos una mayúscula, una minúscula y un dígito."""
    minus = "abcdefghijkmnpqrstuvwxyz"   # sin l
    mayus = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # sin I, O
    digs = "23456789"                     # sin 0, 1
    alfabeto = minus + mayus + digs
    while True:
        clave = "".join(secrets.choice(alfabeto) for _ in range(largo))
        if (any(c in minus for c in clave) and any(c in mayus for c in clave)
                and any(c in digs for c in clave)):
            return clave


async def branding_municipio(db: AsyncSession) -> dict:
    """Nombre y logo del municipio desde configuracion_general (para los mails)."""
    res = await db.execute(text("""
        SELECT clave, valor FROM configuracion_general
         WHERE clave IN ('municipio_nombre','municipio_logo_url')
    """))
    return {r.clave: (r.valor or None) for r in res.fetchall()}


async def crear_usuario_interno(
    db: AsyncSession,
    *,
    data: UsuarioCreate,
    background_tasks: BackgroundTasks,
    ciudadano: Ciudadano | None = None,
) -> Usuario:
    """
    Inserta el usuario (+ su agente 1:1 si no es externo) y encola el mail con la clave
    temporal. Devuelve el ORM `Usuario` ya flusheado (con id). 409 si username o email
    ya existen. El caller hace `commit()` (+ `refresh()` si devuelve el objeto).

    `ciudadano`: persona de la BUC a la que queda vinculado el usuario (mig 110). Con él,
    el agente nace con los datos reales de la ficha y el mail indica que puede ingresar
    con su email o su DNI.
    """
    existing = await db.execute(select(Usuario).where(Usuario.username == data.username))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe un usuario con username '{data.username}'")

    data_dict = data.model_dump()

    # Password: si el cliente la mandó (seeds/compat), se respeta sin forzar cambio.
    # Si no, el sistema genera una temporal y marca debe_cambiar_password=TRUE.
    password_explicita = data_dict.pop("password", None)
    password_temporal = None
    if password_explicita:
        clave = password_explicita
        data_dict["debe_cambiar_password"] = False
    else:
        password_temporal = generar_password_temporal()
        clave = password_temporal
        data_dict["debe_cambiar_password"] = True
    data_dict["password_hash"] = bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode()

    # `nombre` es NOT NULL en la DB pero el form de Usuarios ya no lo captura: el
    # usuario ES la identidad. Si no vino, lo igualamos al username.
    if not (data_dict.get("nombre") or "").strip():
        data_dict["nombre"] = data.username

    # Email obligatorio (validado en el schema). /auth/login busca por email y es
    # el canal por el que se entrega la clave temporal.
    email = (data_dict.get("email") or "").strip()
    data_dict["email"] = email
    dup_email = await db.execute(select(Usuario).where(Usuario.email == email))
    if dup_email.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe un usuario con email '{email}'")

    if ciudadano is not None:
        data_dict["id_ciudadano"] = ciudadano.id_ciudadano

    usuario = Usuario(**data_dict)
    db.add(usuario)
    await db.flush()  # asigna id_usuario sin cerrar la transacción

    # Regla 1:1 agente↔usuario (mig 64): un usuario INTERNO fuerza la creación de su
    # agente vinculado. Los externos NO tienen agente. Con la persona de la BUC a la
    # vista, el agente nace con datos reales; sin ella, con los mínimos (se completan
    # luego desde Maestros → Agentes).
    if not usuario.es_externo:
        if ciudadano is not None:
            await db.execute(text("""
                INSERT INTO agentes (nombre, apellido, dni, cuil, email, telefono,
                                     id_subarea, id_municipio, id_usuario, activo)
                VALUES (:nombre, :apellido, :dni, :cuil, :email, :telefono,
                        :id_subarea, :id_municipio, :id_usuario, TRUE)
            """), {
                "nombre": ciudadano.nombre,
                "apellido": ciudadano.apellido,
                "dni": ciudadano.doc_nro if ciudadano.doc_tipo == "DNI" else None,
                "cuil": ciudadano.cuil,
                "email": email,
                "telefono": ciudadano.telefono,
                "id_subarea": usuario.id_subarea,
                "id_municipio": usuario.id_municipio,
                "id_usuario": usuario.id_usuario,
            })
        else:
            await db.execute(text("""
                INSERT INTO agentes (nombre, apellido, id_subarea, id_municipio, id_usuario, activo)
                VALUES (:nombre, '', :id_subarea, :id_municipio, :id_usuario, TRUE)
            """), {
                "nombre": usuario.nombre,
                "id_subarea": usuario.id_subarea,
                "id_municipio": usuario.id_municipio,
                "id_usuario": usuario.id_usuario,
            })

    logger.info("ALTA usuario | id=%s | username=%s | externo=%s | agente_creado=%s | "
                "pass_temporal=%s | id_ciudadano=%s",
                usuario.id_usuario, usuario.username, usuario.es_externo,
                not usuario.es_externo, password_temporal is not None,
                getattr(ciudadano, "id_ciudadano", None))

    # Mail con la clave temporal (solo si el sistema la generó). Best-effort, corre
    # después del commit del caller (BackgroundTasks) — un fallo de mail no aborta el alta.
    if password_temporal:
        from app.services.email import enviar_mail_credenciales_usuario_interno
        cfg = await branding_municipio(db)
        login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/frontend/login.html"
        app_agentes_url = (settings.APP_AGENTES_FRONTEND_URL or "").strip() or None
        background_tasks.add_task(
            enviar_mail_credenciales_usuario_interno,
            to=email,
            username=usuario.username,
            password_temporal=password_temporal,
            login_url=login_url,
            municipio_nombre=cfg.get("municipio_nombre") or "Tu municipio",
            municipio_logo_url=cfg.get("municipio_logo_url"),
            app_agentes_url=app_agentes_url,
            dni=(ciudadano.doc_nro if ciudadano is not None and ciudadano.doc_tipo == "DNI" else None),
        )

    return usuario
