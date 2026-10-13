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
from app.schemas.buc import CuentaZarisIn, UsuarioCreate
from app.services.cuenta_vecino import asegurar_cuenta_vecino

logger = logging.getLogger("zaris.cuenta_zaris")

MSG_SOLO_ADMIN_FUNCIONARIO = (
    "Solo un administrador puede marcar a un ciudadano como funcionario del municipio "
    "(la marca crea su cuenta ZARIS)."
)
MSG_FALTAN_DATOS_ZARIS = (
    "Para crear la cuenta ZARIS del funcionario completá nivel de acceso, subárea y nombre de usuario."
)


def exigir_admin_funcionario(current_user: dict) -> None:
    """403 si quien opera no es Administrador (nivel 1): marcar el tilde de funcionario
    equivale a crear la cuenta ZARIS, y eso es exclusivo del admin (plan, decisión 2)."""
    if current_user.get("nivel_acceso") != 1:
        raise HTTPException(status_code=403, detail=MSG_SOLO_ADMIN_FUNCIONARIO)


async def crear_cuenta_zaris_desde_ficha(
    db: AsyncSession,
    *,
    ciudadano: Ciudadano,
    data: CuentaZarisIn,
    admin: dict,
    background_tasks: BackgroundTasks,
) -> tuple[Usuario, bool]:
    """
    Cuenta ZARIS (backoffice + app de agentes) de un ciudadano marcado como FUNCIONARIO
    (mig 110). Un paso, dos credenciales: el usuario interno (clave temporal por mail +
    cambio forzado, agente 1:1 con los datos reales de la ficha, vinculado por
    `usuarios.id_ciudadano`) y, si la persona todavía no tenía NINGUNA, la cuenta de
    vecino (activación por link). La clave de vecino NO sirve para entrar a ZARIS.

    La llaman el alta y la edición de la ficha (`POST`/`PUT /buc/ciudadanos`, cuando
    viene `cuenta_zaris` con el tilde puesto) y `POST /buc/ciudadanos/{id}/cuenta-zaris`.
    `admin` es quien opera: el caller YA verificó que es nivel 1.

    422 sin tilde o sin email · 409 si ya tiene usuario vinculado (o username/email
    repetidos, vía crear_usuario_interno). Devuelve (usuario, cuenta_vecino_creada).
    NO commitea.
    """
    if not ciudadano.es_funcionario:
        raise HTTPException(
            status_code=422,
            detail="El ciudadano no está marcado como funcionario del municipio. Tildalo en la ficha y guardá.",
        )
    email = (ciudadano.email or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=422,
            detail="El ciudadano no tiene email cargado. Cargale el email primero (ahí se envían las credenciales).",
        )
    existente = (await db.execute(
        text("SELECT id_usuario, username FROM usuarios WHERE id_ciudadano = :id LIMIT 1"),
        {"id": ciudadano.id_ciudadano},
    )).fetchone()
    if existente:
        raise HTTPException(
            status_code=409,
            detail=f"Este ciudadano ya tiene cuenta ZARIS (usuario '{existente.username}').",
        )

    id_municipio = getattr(ciudadano, "id_municipio", None) or admin.get("id_municipio") or 1
    payload = UsuarioCreate(
        nombre=f"{ciudadano.apellido}, {ciudadano.nombre}",
        nivel_acceso=data.nivel_acceso,
        username=data.username,
        email=email,
        cuil=(ciudadano.cuil or None),
        id_municipio=id_municipio,
        id_subarea=data.id_subarea,
        es_externo=False,
    )
    usuario = await crear_usuario_interno(
        db, data=payload, background_tasks=background_tasks, ciudadano=ciudadano,
    )

    # El funcionario es vecino también: si la persona no tenía NINGUNA cuenta de App
    # Vecinos (altas anteriores a la unificación de junio), se la creamos en el mismo
    # guardado. Si ya existe (activa o pendiente) no se toca: asegurar_cuenta_vecino
    # reenviaría la activación y el funcionario recibiría dos mails por un guardado.
    tiene_cred = await db.scalar(
        text("SELECT 1 FROM ciudadano_credencial WHERE id_ciudadano = :id AND activo = TRUE LIMIT 1"),
        {"id": ciudadano.id_ciudadano},
    )
    cuenta_vecino_creada = False
    if not tiene_cred:
        cuenta_vecino_creada = await asegurar_cuenta_vecino(
            db,
            id_ciudadano=ciudadano.id_ciudadano,
            nombre=ciudadano.nombre or "",
            apellido=ciudadano.apellido or "",
            email=email,
            id_municipio=id_municipio,
            id_usuario_alta=admin.get("id_usuario"),
            background_tasks=background_tasks,
        )

    logger.info("CUENTA ZARIS desde ficha | id_ciudadano=%s | id_usuario=%s | username=%s | nivel=%s | por=%s",
                ciudadano.id_ciudadano, usuario.id_usuario, usuario.username, usuario.nivel_acceso,
                admin.get("id_usuario"))
    return usuario, cuenta_vecino_creada


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
