"""
ZARIS API — Rutas del módulo BUC (Base Única de Ciudadanos).
Endpoints: /api/v1/buc/
"""
import logging
import secrets
import string
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import select, or_, and_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.auth import get_current_user, require_admin
from app.models.buc import (
    Usuario, Nacionalidad, TipoRepresentacion, Actividad,
    Ciudadano, Empresa, CiudadanoEmpresa
)
import bcrypt

from app.schemas.buc import (
    UsuarioCreate, UsuarioUpdate, UsuarioOut,
    NacionalidadOut, TipoRepresentacionOut, ActividadOut,
    CiudadanoCreate, CiudadanoUpdate, CiudadanoOut, CiudadanoConNacionalidad,
    EmpresaCreate, EmpresaUpdate, EmpresaOut, EmpresaConActividad,
    CiudadanoEmpresaCreate, CiudadanoEmpresaOut
)
from app.services.cuenta_vecino import asegurar_cuenta_vecino

# Guard a nivel router: TODO endpoint del módulo BUC exige JWT válido (scope agente).
# Esto cubre los GET de búsqueda/catálogo además de las mutaciones — ningún
# consumidor es público (la App Vecinos usa el router /publico/*, no /buc/*).
# Cualquier endpoint nuevo en este router queda protegido por defecto.
router = APIRouter(
    prefix="/api/v1/buc",
    tags=["BUC"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger("zaris.buc")


# ═══════════════════════════════════════════════════════════════
# USUARIOS
# ═══════════════════════════════════════════════════════════════

# SELECT base que enriquece cada usuario con el nombre de su subárea (LEFT JOIN,
# porque los usuarios externos / sin subárea tienen id_subarea NULL).
_USUARIO_SELECT = """
    SELECT u.id_usuario, u.nombre, u.nivel_acceso, u.username, u.email, u.id_cargo,
           u.id_municipio, u.activo, u.cuil, u.buc_acceso,
           u.id_subarea, s.nombre AS subarea_nombre, u.es_externo,
           u.debe_cambiar_password,
           u.fecha_alta, u.fecha_modif, u.fecha_ultimo_login
    FROM usuarios u
    LEFT JOIN subarea s ON s.id_subarea = u.id_subarea
"""


async def _modulos_permitidos_batch(db: AsyncSession, usuarios: list[dict]) -> None:
    """Puebla in-place `modulos_permitidos` en cada dict de usuario.

    Resuelve el modelo híbrido §30 (default por min_nivel_acceso + overrides
    por usuario) para un lote, con 2 queries totales en vez de 2×N.
    """
    if not usuarios:
        return

    # 1. Defaults por nivel: para cada nivel presente, los módulos cuyo
    #    min_nivel_acceso >= nivel.
    cat = await db.execute(text(
        "SELECT modulo_codigo, min_nivel_acceso FROM modulos WHERE activo = TRUE"
    ))
    catalogo = [(r.modulo_codigo, r.min_nivel_acceso) for r in cat.fetchall()]

    # 2. Overrides de todos los usuarios del lote.
    ids = [u["id_usuario"] for u in usuarios]
    ov = await db.execute(text(
        "SELECT id_usuario, modulo_codigo, permitido FROM usuario_modulos "
        "WHERE activo = TRUE AND id_usuario = ANY(:ids)"
    ), {"ids": ids})
    overrides: dict[int, dict[str, bool]] = {}
    for r in ov.fetchall():
        overrides.setdefault(r.id_usuario, {})[r.modulo_codigo] = r.permitido

    for u in usuarios:
        nivel = u["nivel_acceso"]
        permitidos = {cod for cod, minn in catalogo if minn >= nivel}
        for cod, ok in overrides.get(u["id_usuario"], {}).items():
            if ok:
                permitidos.add(cod)
            else:
                permitidos.discard(cod)
        u["modulos_permitidos"] = sorted(permitidos)


@router.get("/usuarios/{id}/login-log")
async def historial_logins(
    id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Historial de accesos (auditoría) de un usuario, más reciente primero.

    IDOR guard: solo el Administrador (nivel 1) puede ver logs ajenos; el resto
    solo el propio (IP + user-agent son datos sensibles de trazabilidad).
    """
    if current_user.get("nivel_acceso") != 1 and current_user.get("id_usuario") != id:
        raise HTTPException(
            status_code=403,
            detail="Sin permiso para ver este historial de accesos",
        )
    r = await db.execute(text("""
        SELECT id_login_log, fecha_login, ip, user_agent
        FROM usuario_login_log
        WHERE id_usuario = :id
        ORDER BY fecha_login DESC
        LIMIT :lim
    """), {"id": id, "lim": limit})
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/usuarios/buscar", response_model=list[UsuarioOut])
async def buscar_usuario(
    q: str = Query(..., min_length=1, description="Nombre, username o CUIL"),
    tipo: str = Query("auto", description="'numero' para CUIL/username, 'texto' para nombre, 'auto' para detectar"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Buscar usuarios por nombre, username o CUIL."""
    es_numerico = tipo == "numero" or (tipo == "auto" and q.replace("-", "").isdigit())
    if es_numerico:
        cond = "(u.cuil ILIKE :q OR u.username ILIKE :q)"
    else:
        cond = "(u.nombre ILIKE :q OR u.username ILIKE :q)"
    r = await db.execute(text(
        _USUARIO_SELECT + f" WHERE {cond} ORDER BY u.nombre OFFSET :off LIMIT :lim"
    ), {"q": f"%{q}%", "off": offset, "lim": limit})
    rows = [dict(row._mapping) for row in r.fetchall()]
    await _modulos_permitidos_batch(db, rows)
    return rows


@router.get("/usuarios", response_model=list[UsuarioOut])
async def listar_usuarios(
    solo_activos: bool = Query(True, description="Filtrar solo usuarios activos"),
    db: AsyncSession = Depends(get_db)
):
    """Listar usuarios del sistema (para selector modificado_por)."""
    where = " WHERE u.activo = TRUE" if solo_activos else ""
    r = await db.execute(text(_USUARIO_SELECT + where + " ORDER BY u.nombre"))
    rows = [dict(row._mapping) for row in r.fetchall()]
    await _modulos_permitidos_batch(db, rows)
    return rows


@router.get("/usuarios/{id}", response_model=UsuarioOut)
async def obtener_usuario(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener usuario por ID."""
    r = await db.execute(text(_USUARIO_SELECT + " WHERE u.id_usuario = :id"), {"id": id})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    d = dict(row._mapping)
    await _modulos_permitidos_batch(db, [d])
    return d


@router.get("/subareas/buscar")
async def buscar_subareas(
    q: str = Query("", description="Texto libre sobre nombre de subárea o área"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Buscador predictivo de subáreas (para el form de Usuarios).
    Devuelve id, nombre de subárea y nombre del área a la que pertenece."""
    params = {"lim": limit}
    where = "WHERE s.activo = TRUE"
    if q.strip():
        where += " AND (s.nombre ILIKE :q OR a.nombre ILIKE :q)"
        params["q"] = f"%{q.strip()}%"
    r = await db.execute(text(f"""
        SELECT s.id_subarea, s.nombre, a.nombre AS area_nombre
        FROM subarea s
        LEFT JOIN area a ON a.id_area = s.id_area
        {where}
        ORDER BY s.nombre
        LIMIT :lim
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


def _generar_password_temporal(largo: int = 10) -> str:
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


async def _branding_municipio(db: AsyncSession) -> dict:
    """Nombre y logo del municipio desde configuracion_general (para los mails)."""
    res = await db.execute(text("""
        SELECT clave, valor FROM configuracion_general
         WHERE clave IN ('municipio_nombre','municipio_logo_url')
    """))
    cfg = {r.clave: (r.valor or None) for r in res.fetchall()}
    return cfg


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
async def crear_usuario(
    data: UsuarioCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Alta de usuario interno.

    El sistema genera una contraseña temporal aleatoria, la manda por email y marca
    `debe_cambiar_password=TRUE` (Fase 3): el usuario deberá elegir una nueva en su
    primer ingreso. Si el cliente igualmente manda `password` (seeds/compat), se
    respeta y NO se fuerza el cambio.
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
        password_temporal = _generar_password_temporal()
        clave = password_temporal
        data_dict["debe_cambiar_password"] = True
    data_dict["password_hash"] = bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode()

    # `nombre` es NOT NULL en la DB pero el form ya no lo captura: el usuario ES
    # la identidad. Si no vino, lo igualamos al username.
    if not (data_dict.get("nombre") or "").strip():
        data_dict["nombre"] = data.username

    # Email obligatorio (validado en el schema). /auth/login busca por email y es
    # el canal por el que se entrega la clave temporal.
    email = (data_dict.get("email") or "").strip()
    data_dict["email"] = email
    dup_email = await db.execute(select(Usuario).where(Usuario.email == email))
    if dup_email.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe un usuario con email '{email}'")

    usuario = Usuario(**data_dict)
    db.add(usuario)
    await db.flush()  # asigna id_usuario sin cerrar la transacción

    # Regla 1:1 agente↔usuario: un usuario INTERNO fuerza la creación de su
    # agente vinculado (datos mínimos, se completan luego desde Maestros →
    # Agentes). Los externos NO tienen agente. La auditoría se lleva por
    # usuario y, vía este vínculo, se puede auditar por agente.
    if not usuario.es_externo:
        await db.execute(text("""
            INSERT INTO agentes (nombre, apellido, id_subarea, id_municipio, id_usuario, activo)
            VALUES (:nombre, '', :id_subarea, :id_municipio, :id_usuario, TRUE)
        """), {
            "nombre": usuario.nombre,
            "id_subarea": usuario.id_subarea,
            "id_municipio": usuario.id_municipio,
            "id_usuario": usuario.id_usuario,
        })

    # Branding del municipio para el mail (mientras la sesión sigue abierta).
    cfg = await _branding_municipio(db) if password_temporal else {}

    await db.commit()
    await db.refresh(usuario)
    logger.info("ALTA usuario | id=%s | username=%s | externo=%s | agente_creado=%s | pass_temporal=%s",
                usuario.id_usuario, usuario.username, usuario.es_externo,
                not usuario.es_externo, password_temporal is not None)

    # Mail con la clave temporal (solo si el sistema la generó). Best-effort,
    # post-commit, en BackgroundTasks — un fallo de mail no debe abortar el alta.
    if password_temporal:
        from app.services.email import enviar_mail_credenciales_usuario_interno
        login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/frontend/login.html"
        municipio_nombre = cfg.get("municipio_nombre") or "Tu municipio"
        background_tasks.add_task(
            enviar_mail_credenciales_usuario_interno,
            to=email,
            username=usuario.username,
            password_temporal=password_temporal,
            login_url=login_url,
            municipio_nombre=municipio_nombre,
            municipio_logo_url=cfg.get("municipio_logo_url"),
        )

    return usuario


@router.put("/usuarios/{id}", response_model=UsuarioOut)
async def modificar_usuario(
    id: int,
    data: UsuarioUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Modificar datos de usuario. Si se envía 'password', se re-hashea."""
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id))
    usuario = result.scalars().first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = bcrypt.hashpw(update_data.pop("password").encode(), bcrypt.gensalt()).decode()

    campos_modificados = list(update_data.keys())
    for field, value in update_data.items():
        setattr(usuario, field, value)

    await db.commit()
    await db.refresh(usuario)
    logger.info("MODIFICACION usuario | id=%s | username=%s | campos=%s",
                usuario.id_usuario, usuario.username, campos_modificados)
    return usuario


@router.put("/usuarios/{id}/estado", response_model=UsuarioOut)
async def cambiar_estado_usuario(
    id: int,
    activo: bool = Query(..., description="true para reactivar, false para dar de baja"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Dar de alta o de baja a un usuario (soft delete).

    Guards anti-lockout (hallazgo 2026-07-16, pasó en QA local): un admin se
    desactivó a sí mismo y quedó afuera (401 en el próximo request, reactivado
    por DB). Ni auto-baja ni dejar el sistema sin administradores activos.
    """
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id))
    usuario = result.scalars().first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not activo:
        if usuario.id_usuario == admin["id_usuario"]:
            raise HTTPException(
                status_code=422,
                detail="No podés desactivar tu propio usuario (te quedarías sin acceso). Pedile a otro administrador que lo haga.",
            )
        if usuario.activo and usuario.nivel_acceso == 1:
            otros_admins = await db.scalar(
                select(func.count()).select_from(Usuario).where(
                    Usuario.nivel_acceso == 1,
                    Usuario.activo == True,  # noqa: E712
                    Usuario.id_usuario != id,
                )
            )
            if not otros_admins:
                raise HTTPException(
                    status_code=422,
                    detail="No se puede desactivar al último administrador activo del sistema.",
                )

    usuario.activo = activo
    await db.commit()
    await db.refresh(usuario)
    accion = "REACTIVACION" if activo else "BAJA"
    logger.info("%s usuario | id=%s | username=%s", accion, usuario.id_usuario, usuario.username)
    return usuario


# ═══════════════════════════════════════════════════════════════
# CATÁLOGOS
# ═══════════════════════════════════════════════════════════════

@router.get("/nacionalidades", response_model=list[NacionalidadOut])
async def listar_nacionalidades(db: AsyncSession = Depends(get_db)):
    """Listar todas las nacionalidades."""
    result = await db.execute(select(Nacionalidad).order_by(Nacionalidad.pais))
    return result.scalars().all()


@router.get("/actividades", response_model=list[ActividadOut])
async def listar_actividades(db: AsyncSession = Depends(get_db)):
    """Listar todas las actividades CLAE."""
    result = await db.execute(select(Actividad).order_by(Actividad.descripcion))
    return result.scalars().all()


@router.get("/tipo-representacion", response_model=list[TipoRepresentacionOut])
async def listar_tipo_representacion(db: AsyncSession = Depends(get_db)):
    """Listar tipos de representación ciudadano-empresa."""
    result = await db.execute(select(TipoRepresentacion).order_by(TipoRepresentacion.id))
    return result.scalars().all()


# ═══════════════════════════════════════════════════════════════
# CIUDADANOS
# ═══════════════════════════════════════════════════════════════

@router.get("/ciudadanos", response_model=list[CiudadanoOut])
async def listar_ciudadanos(
    solo_activos: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Listar ciudadanos (para vista previa y listado)."""
    stmt = select(Ciudadano).order_by(Ciudadano.id_ciudadano.desc()).offset(offset).limit(limit)
    if solo_activos:
        stmt = stmt.where(Ciudadano.activo == True)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/ciudadanos/buscar", response_model=list[CiudadanoOut])
async def buscar_ciudadano(
    response: Response,
    q: str = Query(..., min_length=1, description="DNI, CUIL, teléfono, email o nombre/apellido"),
    tipo: str = Query("auto", description="'numero' (DNI/CUIL/tel), 'texto' (nombre/apellido/email), 'auto'"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Búsqueda flexible de ciudadanos. En modo `auto`:
    - Si el query es solo dígitos (ignorando guiones/espacios/paréntesis),
      busca en `doc_nro`, `cuil` y `telefono` — todos comparados con dígitos
      normalizados (matchea "(11) 6429-5018" con "1164295018").
    - Si tiene letras, hace `AND` multi-palabra: cada palabra debe matchear
      en alguno de `apellido`, `nombre` o `email`. "calabro elisa" encuentra
      "Calabro Elisabeth Graciela" — el OR del comportamiento previo daba
      muchos falsos positivos.

    Header `X-Total-Count`: total de matches sin paginar (para mostrar
    "y N más" en el frontend).
    """
    q_clean = q.strip()
    soloDigits = q_clean.translate(str.maketrans("", "", " -()._"))
    es_numerico = tipo == "numero" or (tipo == "auto" and soloDigits.isdigit() and len(soloDigits) >= 3)

    if es_numerico:
        # Normalizamos las columnas removiendo separadores comunes
        digits_expr = lambda col: func.regexp_replace(col, r"[^0-9]", "", "g")
        cond = or_(
            digits_expr(Ciudadano.doc_nro).ilike(f"%{soloDigits}%"),
            digits_expr(Ciudadano.cuil).ilike(f"%{soloDigits}%"),
            digits_expr(Ciudadano.telefono).ilike(f"%{soloDigits}%"),
        )
    else:
        # AND multi-palabra: cada token debe matchear en algún campo de texto
        tokens = [t for t in q_clean.split() if t]
        if not tokens:
            response.headers["X-Total-Count"] = "0"
            return []
        cond = and_(*[
            or_(
                Ciudadano.apellido.ilike(f"%{tok}%"),
                Ciudadano.nombre.ilike(f"%{tok}%"),
                Ciudadano.email.ilike(f"%{tok}%"),
            )
            for tok in tokens
        ])

    base_filter = (Ciudadano.activo == True, cond)

    # Total sin paginar (para X-Total-Count)
    total_q = select(func.count()).select_from(Ciudadano).where(*base_filter)
    total = (await db.execute(total_q)).scalar_one()

    page_q = (
        select(Ciudadano)
        .where(*base_filter)
        .order_by(Ciudadano.apellido, Ciudadano.nombre)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(page_q)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return result.scalars().all()


@router.get("/ciudadanos/verificar-duplicado")
async def verificar_duplicado_ciudadano(
    campo: str = Query(..., description="Campo a verificar: email, telefono, cuil, doc_nro"),
    valor: str = Query(..., description="Valor a buscar"),
    excluir_id: Optional[int] = Query(None, description="ID a excluir (para edición)"),
    db: AsyncSession = Depends(get_db)
):
    """Verificar si ya existe un ciudadano con ese valor en el campo dado."""
    campo_map = {
        "email": Ciudadano.email,
        "telefono": Ciudadano.telefono,
        "cuil": Ciudadano.cuil,
        "doc_nro": Ciudadano.doc_nro,
    }
    if campo not in campo_map:
        raise HTTPException(status_code=400, detail=f"Campo '{campo}' no soportado")

    col = campo_map[campo]
    q = select(Ciudadano).where(col == valor, Ciudadano.activo == True)
    if excluir_id:
        q = q.where(Ciudadano.id_ciudadano != excluir_id)
    result = await db.execute(q)
    c = result.scalars().first()
    if c:
        return {"existe": True, "id": c.id_ciudadano, "nombre": f"{c.apellido}, {c.nombre}", "cuil": c.cuil}
    return {"existe": False}


@router.post("/ciudadanos", response_model=CiudadanoOut, status_code=201)
async def crear_ciudadano(
    data: CiudadanoCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Alta de ciudadano.

    Además de crear la persona en el padrón (BUC), crea automáticamente su CUENTA
    de App Vecinos (credencial sin password + token de activación) y dispara el mail
    de activación al email cargado. El vecino abre el mail, se loguea y elige su
    propia clave (§38 Camino B). El email es obligatorio (lo exige CiudadanoCreate).
    """
    existing = await db.execute(
        select(Ciudadano).where(
            Ciudadano.doc_tipo == data.doc_tipo,
            Ciudadano.doc_nro == data.doc_nro
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un ciudadano con {data.doc_tipo} {data.doc_nro}"
        )

    existing_cuil = await db.execute(
        select(Ciudadano).where(Ciudadano.cuil == data.cuil)
    )
    if existing_cuil.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe un ciudadano con CUIL {data.cuil}")

    # El email debe ser único entre cuentas de App Vecinos activas (lo exige la
    # cuenta de portal que vamos a crear). Mismo criterio que POST /publico/auth/registrar.
    email_norm = (data.email or "").lower().strip()
    dup_email = await db.execute(
        text("""
            SELECT cc.id_ciudadano FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE LOWER(c.email) = :email AND cc.activo = TRUE AND c.activo = TRUE
             LIMIT 1
        """),
        {"email": email_norm},
    )
    if dup_email.fetchone():
        raise HTTPException(
            status_code=409,
            detail="Ya existe una cuenta de App Vecinos con ese email.",
        )

    ciudadano = Ciudadano(**data.model_dump())
    db.add(ciudadano)
    await db.flush()  # obtener id_ciudadano sin cerrar la tx (la cuenta va en la misma)

    # El agente cargó la ficha completa en el form → el vecino NO pasa por el paso 2
    # (completar ficha) al loguearse: entra directo al portal. ficha_completa NO está
    # mapeada en el modelo ORM, por eso UPDATE directo (igual que estado_validacion).
    await db.execute(
        text("UPDATE ciudadanos SET ficha_completa = TRUE WHERE id_ciudadano = :id"),
        {"id": ciudadano.id_ciudadano},
    )

    # Crear la cuenta de App Vecinos + encolar mail de activación (idempotente).
    await asegurar_cuenta_vecino(
        db,
        id_ciudadano=ciudadano.id_ciudadano,
        nombre=ciudadano.nombre,
        apellido=ciudadano.apellido,
        email=email_norm,
        id_municipio=getattr(ciudadano, "id_municipio", None) or current_user.get("id_municipio") or 1,
        id_usuario_alta=current_user.get("id_usuario"),
        background_tasks=background_tasks,
    )

    await db.commit()
    await db.refresh(ciudadano)

    logger.info(
        "ALTA ciudadano + cuenta vecino | id=%s | doc=%s %s | cuil=%s | nombre=%s %s | email=%s",
        ciudadano.id_ciudadano, ciudadano.doc_tipo, ciudadano.doc_nro,
        ciudadano.cuil, ciudadano.apellido, ciudadano.nombre, email_norm
    )
    return ciudadano


@router.post("/ciudadanos/{id}/cuenta-vecino")
async def crear_cuenta_vecino_existente(
    id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Crea (o reenvía la activación de) la cuenta de App Vecinos para un ciudadano YA
    existente en la BUC. Es la vía de mostrador para vecinos pre-existentes que no
    pasaron por el alta unificada (que ya crea la cuenta automáticamente).

    Idempotente vía asegurar_cuenta_vecino: cuenta ya activada -> no toca nada
    (enviado=False); credencial sin activar -> regenera el token y reenvía el mail.
    """
    result = await db.execute(
        select(Ciudadano).where(Ciudadano.id_ciudadano == id, Ciudadano.activo == True)
    )
    ciudadano = result.scalars().first()
    if not ciudadano:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")

    email = (ciudadano.email or "").strip()
    if not email:
        raise HTTPException(
            status_code=422,
            detail="El ciudadano no tiene email cargado. Cargale el email primero (es el canal de activación).",
        )

    enviado = await asegurar_cuenta_vecino(
        db,
        id_ciudadano=ciudadano.id_ciudadano,
        nombre=ciudadano.nombre or "",
        apellido=ciudadano.apellido or "",
        email=email,
        id_municipio=getattr(ciudadano, "id_municipio", None) or current_user.get("id_municipio") or 1,
        id_usuario_alta=current_user.get("id_usuario"),
        background_tasks=background_tasks,
    )
    await db.commit()
    return {"enviado": enviado, "ya_activada": not enviado, "email": email}


@router.get("/ciudadanos/{id}", response_model=CiudadanoConNacionalidad)
async def obtener_ciudadano(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener ciudadano por ID con datos de nacionalidad."""
    result = await db.execute(
        select(Ciudadano)
        .options(selectinload(Ciudadano.nacionalidad))
        .where(Ciudadano.id_ciudadano == id, Ciudadano.activo == True)
    )
    ciudadano = result.scalars().first()
    if not ciudadano:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")
    return ciudadano


@router.put("/ciudadanos/{id}", response_model=CiudadanoOut)
async def modificar_ciudadano(
    id: int,
    data: CiudadanoUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Modificar ciudadano existente (update parcial)."""
    result = await db.execute(
        select(Ciudadano).where(Ciudadano.id_ciudadano == id, Ciudadano.activo == True)
    )
    ciudadano = result.scalars().first()
    if not ciudadano:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    campos_modificados = list(update_data.keys())
    for field, value in update_data.items():
        setattr(ciudadano, field, value)

    await db.commit()
    await db.refresh(ciudadano)

    logger.info(
        "MODIFICACION ciudadano | id=%s | cuil=%s | campos=%s | usuario=%s",
        ciudadano.id_ciudadano, ciudadano.cuil, campos_modificados, ciudadano.modificado_por
    )
    return ciudadano


@router.put("/ciudadanos/{id}/estado", response_model=CiudadanoOut)
async def cambiar_estado_ciudadano(
    id: int,
    activo: bool = Query(..., description="true para reactivar, false para dar de baja"),
    db: AsyncSession = Depends(get_db),
):
    """Dar de baja o reactivar un ciudadano (soft delete)."""
    result = await db.execute(select(Ciudadano).where(Ciudadano.id_ciudadano == id))
    ciudadano = result.scalars().first()
    if not ciudadano:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")
    ciudadano.activo = activo
    await db.commit()
    await db.refresh(ciudadano)
    accion = "REACTIVACION" if activo else "BAJA"
    logger.info("%s ciudadano | id=%s | cuil=%s", accion, ciudadano.id_ciudadano, ciudadano.cuil)
    return ciudadano


@router.get("/ciudadanos/{id}/empresas-vinculadas")
async def obtener_empresas_vinculadas(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener las empresas vinculadas a un ciudadano (via tabla ciudadano_empresa)."""
    result = await db.execute(
        select(CiudadanoEmpresa)
        .options(
            selectinload(CiudadanoEmpresa.empresa),
            selectinload(CiudadanoEmpresa.tipo_representacion)
        )
        .where(
            CiudadanoEmpresa.id_ciudadano == id,
            CiudadanoEmpresa.activo == True
        )
    )
    relaciones = result.scalars().all()
    datos = []
    for rel in relaciones:
        emp = rel.empresa
        if emp and emp.activo:
            datos.append({
                "id_relacion":            rel.id,
                "id_empresa":             emp.id_empresa,
                "cuit":                   emp.cuit,
                "nombre":                 emp.nombre,
                "telefono":               emp.telefono,
                "email":                  emp.email,
                "calle":                  emp.calle,
                "localidad":              emp.localidad,
                "provincia":              emp.provincia,
                "id_actividad":           emp.id_actividad,
                "tipo_representacion":    rel.tipo_representacion.tipo if rel.tipo_representacion else None,
                "id_tipo_representacion": rel.id_tipo_representacion,
            })
    return datos


# ═══════════════════════════════════════════════════════════════
# EMPRESAS
# ═══════════════════════════════════════════════════════════════

@router.get("/empresas", response_model=list[EmpresaOut])
async def listar_empresas(
    solo_activos: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Listar empresas (para vista previa y listado)."""
    stmt = select(Empresa).order_by(Empresa.id_empresa.desc()).offset(offset).limit(limit)
    if solo_activos:
        stmt = stmt.where(Empresa.activo == True)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/empresas/buscar", response_model=list[EmpresaOut])
async def buscar_empresa(
    q: str = Query(..., min_length=1, description="CUIT, Email o Nombre"),
    tipo: str = Query("auto", description="'numero' para CUIT, 'texto' para nombre, 'auto' para detectar"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    db: AsyncSession = Depends(get_db)
):
    """Buscar empresa por CUIT, email o nombre (contains)."""
    es_numerico = tipo == "numero" or (tipo == "auto" and q.replace("-", "").isdigit())
    if es_numerico:
        q_normalizado = q.replace("-", "")
        cond = func.replace(Empresa.cuit, "-", "").ilike(f"%{q_normalizado}%")
    else:
        cond = or_(
            Empresa.nombre.ilike(f"%{q}%"),
            Empresa.email.ilike(f"%{q}%"),
        )
    query = (
        select(Empresa)
        .where(Empresa.activo == True, cond)
        .order_by(Empresa.nombre)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/empresas/verificar-duplicado")
async def verificar_duplicado_empresa(
    campo: str = Query(..., description="Campo a verificar: email, telefono, cuit"),
    valor: str = Query(..., description="Valor a buscar"),
    excluir_id: Optional[int] = Query(None, description="ID a excluir (para edición)"),
    db: AsyncSession = Depends(get_db)
):
    """Verificar si ya existe una empresa con ese valor en el campo dado."""
    campo_map = {
        "email": Empresa.email,
        "telefono": Empresa.telefono,
        "cuit": Empresa.cuit,
    }
    if campo not in campo_map:
        raise HTTPException(status_code=400, detail=f"Campo '{campo}' no soportado")

    col = campo_map[campo]
    q = select(Empresa).where(col == valor, Empresa.activo == True)
    if excluir_id:
        q = q.where(Empresa.id_empresa != excluir_id)
    result = await db.execute(q)
    e = result.scalars().first()
    if e:
        return {"existe": True, "id": e.id_empresa, "nombre": e.nombre, "cuit": e.cuit}
    return {"existe": False}


@router.post("/empresas", response_model=EmpresaOut, status_code=201)
async def crear_empresa(
    data: EmpresaCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Alta de empresa CON su vecino representante, en una sola transacción.

    Regla de negocio (BUC §2): toda empresa DEBE nacer vinculada a un vecino (persona
    física) como representante/contacto — no existen empresas huérfanas. El vínculo
    ciudadano_empresa se crea en la misma transacción que la empresa: si algo falla,
    no queda ni empresa suelta ni vínculo colgado.
    """
    # El vecino representante DEBE existir y estar activo
    cid = await db.execute(
        select(Ciudadano).where(
            Ciudadano.id_ciudadano == data.id_ciudadano, Ciudadano.activo == True
        )
    )
    if not cid.scalars().first():
        raise HTTPException(
            status_code=422,
            detail="La empresa requiere un vecino representante/contacto válido y activo.",
        )

    existing = await db.execute(
        select(Empresa).where(Empresa.cuit == data.cuit)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe una empresa con CUIT {data.cuit}")

    # Separar los campos del vínculo (no son columnas de Empresa)
    payload = data.model_dump()
    id_ciudadano = payload.pop("id_ciudadano")
    id_tipo_representacion = payload.pop("id_tipo_representacion")

    empresa = Empresa(**payload)
    db.add(empresa)
    await db.flush()  # obtiene empresa.id_empresa sin cerrar la transacción

    vinculo = CiudadanoEmpresa(
        id_ciudadano=id_ciudadano,
        id_empresa=empresa.id_empresa,
        id_tipo_representacion=id_tipo_representacion,
    )
    db.add(vinculo)

    await db.commit()
    await db.refresh(empresa)

    logger.info(
        "ALTA empresa | id=%s | cuit=%s | nombre=%s | representante=%s | tipo_rep=%s",
        empresa.id_empresa, empresa.cuit, empresa.nombre, id_ciudadano, id_tipo_representacion
    )
    return empresa


@router.get("/empresas/{id}", response_model=EmpresaConActividad)
async def obtener_empresa(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener empresa por ID con datos de actividad."""
    result = await db.execute(
        select(Empresa)
        .options(selectinload(Empresa.actividad))
        .where(Empresa.id_empresa == id, Empresa.activo == True)
    )
    empresa = result.scalars().first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


@router.put("/empresas/{id}", response_model=EmpresaOut)
async def modificar_empresa(
    id: int,
    data: EmpresaUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Modificar empresa existente."""
    result = await db.execute(
        select(Empresa).where(Empresa.id_empresa == id, Empresa.activo == True)
    )
    empresa = result.scalars().first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    campos_modificados = list(update_data.keys())
    for field, value in update_data.items():
        setattr(empresa, field, value)

    await db.commit()
    await db.refresh(empresa)

    logger.info(
        "MODIFICACION empresa | id=%s | cuit=%s | campos=%s | usuario=%s",
        empresa.id_empresa, empresa.cuit, campos_modificados, empresa.modificado_por
    )
    return empresa


@router.put("/empresas/{id}/estado", response_model=EmpresaOut)
async def cambiar_estado_empresa(
    id: int,
    activo: bool = Query(..., description="true para reactivar, false para dar de baja"),
    db: AsyncSession = Depends(get_db),
):
    """Dar de baja o reactivar una empresa (soft delete)."""
    result = await db.execute(select(Empresa).where(Empresa.id_empresa == id))
    empresa = result.scalars().first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa.activo = activo
    await db.commit()
    await db.refresh(empresa)
    accion = "REACTIVACION" if activo else "BAJA"
    logger.info("%s empresa | id=%s | cuit=%s", accion, empresa.id_empresa, empresa.cuit)
    return empresa


# ═══════════════════════════════════════════════════════════════
# CIUDADANO-EMPRESA (relación)
# ═══════════════════════════════════════════════════════════════

@router.post("/ciudadano-empresa", response_model=CiudadanoEmpresaOut, status_code=201)
async def crear_relacion_ciudadano_empresa(
    data: CiudadanoEmpresaCreate,
    db: AsyncSession = Depends(get_db),
):
    """Crear relación ciudadano-empresa con tipo de representación."""
    cid = await db.execute(
        select(Ciudadano).where(Ciudadano.id_ciudadano == data.id_ciudadano, Ciudadano.activo == True)
    )
    if not cid.scalars().first():
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")

    emp = await db.execute(
        select(Empresa).where(Empresa.id_empresa == data.id_empresa, Empresa.activo == True)
    )
    if not emp.scalars().first():
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    existing = await db.execute(
        select(CiudadanoEmpresa).where(
            CiudadanoEmpresa.id_ciudadano == data.id_ciudadano,
            CiudadanoEmpresa.id_empresa == data.id_empresa,
            CiudadanoEmpresa.id_tipo_representacion == data.id_tipo_representacion
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="Ya existe esta relacion ciudadano-empresa con ese tipo de representacion"
        )

    relacion = CiudadanoEmpresa(**data.model_dump())
    db.add(relacion)
    await db.commit()
    await db.refresh(relacion)

    logger.info(
        "VINCULACION ciudadano-empresa | ciudadano_id=%s | empresa_id=%s | tipo_rep=%s",
        relacion.id_ciudadano, relacion.id_empresa, relacion.id_tipo_representacion
    )
    return relacion
