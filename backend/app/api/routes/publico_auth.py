"""
ZARIS API - Endpoints publicos de auth para ciudadanos (App Vecinos).

Todos bajo /api/v1/publico/auth/*. Modelo:
- Scope JWT 'publico' (vigencia 30 dias por default).
- Login con DNI + password.
- Alta la hace un agente (con scope='agente', nivel<=3).
- Activacion por email con token UUID (7 dias).
- Recovery por email con token UUID (24 horas).
- Lockout: 5 intentos fallidos -> 15 minutos.
- Anti-enumeracion: /reenviar-activacion y /recuperar-password siempre 200 OK.
"""
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    hash_password,
    verify_password,
    get_current_user,
    get_current_ciudadano,
    crear_token_ciudadano,
)
from app.core.config import settings
from app.core.database import get_db
from app.services.email import (
    enviar_mail_activacion_ciudadano,
    enviar_mail_recovery_ciudadano,
)
from app.schemas.publico_auth import (
    RegistroCiudadanoIn,
    RegistroCiudadanoOut,
    ActivarIn,
    ActivarOut,
    ReenviarActivacionIn,
    LoginCiudadanoIn,
    LoginCiudadanoOut,
    RecuperarPasswordIn,
    ResetearPasswordIn,
    ResetearPasswordOut,
    CiudadanoBasicoOut,
    GenericoOkOut,
)
from app.schemas.publico_alta import CompletarFichaIn, CompletarFichaOut

router = APIRouter(prefix="/api/v1/publico/auth", tags=["publico-auth"])

LOCKOUT_INTENTOS = 5
LOCKOUT_MINUTOS = 15
COOLDOWN_REENVIO_MINUTOS = 5
DIAS_ACTIVACION = 7
HORAS_RECOVERY = 24


# ─── helpers ────────────────────────────────────────────────────────────────

def _solo_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _validar_dni(dni: str) -> str:
    """Devuelve DNI digits-only. Levanta 400 si no es 7-8 chars."""
    limpio = _solo_digitos(dni)
    if not (7 <= len(limpio) <= 8):
        raise HTTPException(status_code=400, detail="DNI invalido: debe tener 7 u 8 digitos")
    return limpio


def _construir_cuil_placeholder(dni: str) -> str:
    """
    Cuando un agente da de alta un ciudadano por la PWA, no le pedimos CUIL real
    (lo completa el ciudadano despues si hace falta). Pero ciudadanos.cuil es NOT NULL
    UNIQUE. Generamos uno digit-only basado en el DNI con prefijo '20' (masculino default).
    El ciudadano puede actualizarlo desde la PWA mas adelante.
    """
    return f"20{dni.zfill(8)}9"


def _ciudadano_a_basico(row) -> CiudadanoBasicoOut:
    return CiudadanoBasicoOut(
        id_ciudadano=row.id_ciudadano,
        dni=row.doc_nro,
        nombre=row.nombre,
        apellido=row.apellido,
        email=row.email,
        estado_validacion=row.estado_validacion,
        ficha_completa=bool(getattr(row, "ficha_completa", False)),
    )


async def _municipio_branding(db: AsyncSession) -> tuple[str, str | None]:
    """Devuelve (municipio_nombre, municipio_logo_url) leyendo configuracion_general."""
    res = await db.execute(
        text("SELECT clave, valor FROM configuracion_general WHERE clave IN ('municipio_nombre','municipio_logo_url')")
    )
    cfg = {r.clave: r.valor for r in res.fetchall()}
    return (
        cfg.get("municipio_nombre") or "Tu municipio",
        cfg.get("municipio_logo_url") or None,
    )


# ─── endpoints ──────────────────────────────────────────────────────────────

@router.post("/registrar", response_model=RegistroCiudadanoOut, status_code=201)
async def registrar_ciudadano(
    data: RegistroCiudadanoIn,
    background_tasks: BackgroundTasks,
    current_agente: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Un agente municipal (nivel<=3) da de alta un ciudadano + su credencial.
    Manda mail de activacion. Para activarse, el ciudadano clickea el link y elige su password.
    """
    if current_agente["nivel_acceso"] > 3:
        raise HTTPException(
            status_code=403,
            detail="Se requiere nivel de acceso Operador o superior",
        )

    dni = _validar_dni(data.dni)
    email = data.email.lower().strip()

    # DNI no debe estar en ciudadanos activos
    res = await db.execute(
        text("SELECT id_ciudadano FROM ciudadanos WHERE doc_nro = :dni AND activo = TRUE LIMIT 1"),
        {"dni": dni},
    )
    if res.fetchone():
        raise HTTPException(
            status_code=409,
            detail="Ya existe un ciudadano con ese DNI. Buscarlo y vincular cuenta en vez de crear nuevo.",
        )

    # Email no debe estar usado por credencial activa de OTRO ciudadano
    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE LOWER(c.email) = :email AND cc.activo = TRUE AND c.activo = TRUE
             LIMIT 1
        """),
        {"email": email},
    )
    if res.fetchone():
        raise HTTPException(
            status_code=409,
            detail="Ya hay una cuenta de App Vecinos con ese email.",
        )

    # Insert ciudadano con defaults pragmaticos (decision sesion 2026-05-19, §32 quirk extendido).
    # El ciudadano puede actualizar fecha_nac, sexo, cuil real desde la PWA mas adelante.
    id_municipio = current_agente.get("id_municipio") or 1
    cuil_placeholder = _construir_cuil_placeholder(dni)

    insert_ciudadano = await db.execute(
        text("""
            INSERT INTO ciudadanos
                (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                 id_nacionalidad, ren_chk, telefono, email, email_chk, emp_chk,
                 activo, estado_validacion, ficha_completa, id_municipio,
                 id_usuario_alta, fecha_alta, fecha_modificacion)
            VALUES
                ('DNI', :dni, :cuil, :nombre, :apellido, 'OTROS', DATE '1900-01-01',
                 1, FALSE, :telefono, :email, FALSE, FALSE,
                 TRUE, 'verificado', FALSE, :id_municipio,
                 :id_usuario_alta, NOW(), NOW())
            RETURNING id_ciudadano
        """),
        {
            "dni": dni,
            "cuil": cuil_placeholder,
            "nombre": data.nombre.strip(),
            "apellido": data.apellido.strip(),
            "telefono": (data.telefono or "0").strip() or "0",
            "email": email,
            "id_municipio": id_municipio,
            "id_usuario_alta": current_agente["id_usuario"],
        },
    )
    id_ciudadano = insert_ciudadano.fetchone().id_ciudadano

    # Insert credencial con token de activacion (7 dias)
    await db.execute(
        text(f"""
            INSERT INTO ciudadano_credencial
                (id_ciudadano, password_hash, token_activacion, token_activacion_expira,
                 activado, fecha_ultimo_email_activacion,
                 activo, id_municipio, fecha_alta, fecha_modificacion, id_usuario_alta)
            VALUES
                (:id_ciudadano, NULL, gen_random_uuid(), NOW() + INTERVAL '{DIAS_ACTIVACION} days',
                 FALSE, NOW(),
                 TRUE, :id_municipio, NOW(), NOW(), :id_usuario_alta)
        """),
        {
            "id_ciudadano": id_ciudadano,
            "id_municipio": id_municipio,
            "id_usuario_alta": current_agente["id_usuario"],
        },
    )

    # Insert canal preferido con defaults
    await db.execute(
        text("""
            INSERT INTO ciudadano_canal_preferido
                (id_ciudadano, canal_email, canal_push, canal_whatsapp, canal_sms,
                 activo, id_municipio, fecha_alta, fecha_modificacion, id_usuario_alta)
            VALUES
                (:id_ciudadano, TRUE, TRUE, FALSE, FALSE,
                 TRUE, :id_municipio, NOW(), NOW(), :id_usuario_alta)
        """),
        {
            "id_ciudadano": id_ciudadano,
            "id_municipio": id_municipio,
            "id_usuario_alta": current_agente["id_usuario"],
        },
    )

    # Leer token recien creado para mandarlo por mail
    res = await db.execute(
        text("SELECT token_activacion FROM ciudadano_credencial WHERE id_ciudadano = :id"),
        {"id": id_ciudadano},
    )
    token = str(res.fetchone().token_activacion)

    await db.commit()

    # Encolar mail (corre despues de cerrar la respuesta)
    municipio_nombre, municipio_logo_url = await _municipio_branding(db)
    background_tasks.add_task(
        enviar_mail_activacion_ciudadano,
        email,
        data.nombre.strip(),
        data.apellido.strip(),
        token,
        municipio_nombre,
        settings.APP_VECINOS_FRONTEND_URL,
        municipio_logo_url,
    )

    return RegistroCiudadanoOut(
        id_ciudadano=id_ciudadano,
        email=email,
        activacion_enviada=True,
    )


@router.post("/activar", response_model=ActivarOut)
async def activar_cuenta(data: ActivarIn, db: AsyncSession = Depends(get_db)):
    """Ciudadano activa cuenta con token + setea password."""
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano,
                   c.doc_nro, c.nombre, c.apellido, c.email, c.estado_validacion, c.activo AS c_activo
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE cc.token_activacion = CAST(:token AS uuid)
               AND cc.token_activacion_expira > NOW()
               AND cc.activado = FALSE
               AND cc.activo = TRUE
        """),
        {"token": data.token},
    )
    row = res.fetchone()
    if not row or not row.c_activo:
        raise HTTPException(status_code=400, detail="Token invalido o expirado")

    hashed = hash_password(data.password)
    await db.execute(
        text("""
            UPDATE ciudadano_credencial
               SET password_hash = :ph,
                   activado = TRUE,
                   activado_en = NOW(),
                   token_activacion = NULL,
                   token_activacion_expira = NULL,
                   fecha_ultimo_cambio_password = NOW(),
                   intentos_fallidos = 0,
                   bloqueada_hasta = NULL,
                   fecha_modificacion = NOW(),
                   id_usuario_modificacion = NULL
             WHERE id_ciudadano_credencial = :id
        """),
        {"ph": hashed, "id": row.id_ciudadano_credencial},
    )
    await db.commit()

    token = crear_token_ciudadano(row.id_ciudadano)
    return ActivarOut(access_token=token, ciudadano=_ciudadano_a_basico(row))


@router.post("/reenviar-activacion", response_model=GenericoOkOut)
async def reenviar_activacion(
    data: ReenviarActivacionIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Reenvia mail de activacion. Cooldown 5 minutos.
    Anti-enumeracion: si el DNI no existe O ya esta activada, devuelve 200 igual.
    """
    dni = _validar_dni(data.dni)

    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano, cc.activado,
                   cc.fecha_ultimo_email_activacion,
                   c.nombre, c.apellido, c.email
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE c.doc_nro = :dni AND cc.activo = TRUE AND c.activo = TRUE
        """),
        {"dni": dni},
    )
    row = res.fetchone()

    if not row:
        # anti-enumeracion: parece exitoso pero no manda nada
        return GenericoOkOut()

    if row.activado:
        # cuenta ya activada -> tampoco mandamos mail (no error, anti-enumeracion soft)
        return GenericoOkOut()

    # cooldown 5 min
    if row.fecha_ultimo_email_activacion is not None:
        ahora = datetime.now(timezone.utc)
        delta = ahora - row.fecha_ultimo_email_activacion
        if delta < timedelta(minutes=COOLDOWN_REENVIO_MINUTOS):
            # silencioso por anti-enumeracion (devolvemos 200 pero no reenvia)
            return GenericoOkOut()

    # generar nuevo token
    res = await db.execute(
        text(f"""
            UPDATE ciudadano_credencial
               SET token_activacion = gen_random_uuid(),
                   token_activacion_expira = NOW() + INTERVAL '{DIAS_ACTIVACION} days',
                   fecha_ultimo_email_activacion = NOW(),
                   fecha_modificacion = NOW()
             WHERE id_ciudadano_credencial = :id
             RETURNING token_activacion
        """),
        {"id": row.id_ciudadano_credencial},
    )
    token = str(res.fetchone().token_activacion)
    await db.commit()

    municipio_nombre, municipio_logo_url = await _municipio_branding(db)
    background_tasks.add_task(
        enviar_mail_activacion_ciudadano,
        row.email,
        row.nombre,
        row.apellido,
        token,
        municipio_nombre,
        settings.APP_VECINOS_FRONTEND_URL,
        municipio_logo_url,
    )

    return GenericoOkOut()


@router.post("/login", response_model=LoginCiudadanoOut)
async def login_ciudadano(data: LoginCiudadanoIn, db: AsyncSession = Depends(get_db)):
    """Login con DNI + password. Lockout 5 intentos = 15 minutos."""
    dni = _validar_dni(data.dni)
    invalido = HTTPException(status_code=401, detail="Credenciales invalidas")

    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano,
                   cc.password_hash, cc.activado, cc.intentos_fallidos, cc.bloqueada_hasta,
                   cc.activo AS cc_activo,
                   c.doc_nro, c.nombre, c.apellido, c.email, c.estado_validacion,
                   c.ficha_completa, c.activo AS c_activo
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE c.doc_nro = :dni
        """),
        {"dni": dni},
    )
    row = res.fetchone()

    if not row or not row.c_activo or not row.cc_activo or not row.activado or not row.password_hash:
        raise invalido

    # Lockout
    if row.bloqueada_hasta is not None and row.bloqueada_hasta > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=401,
            detail="Cuenta bloqueada temporalmente. Intenta en unos minutos.",
        )

    # Verificar password
    if not verify_password(data.password, row.password_hash):
        nuevos_intentos = (row.intentos_fallidos or 0) + 1
        if nuevos_intentos >= LOCKOUT_INTENTOS:
            await db.execute(
                text(f"""
                    UPDATE ciudadano_credencial
                       SET intentos_fallidos = 0,
                           bloqueada_hasta = NOW() + INTERVAL '{LOCKOUT_MINUTOS} minutes',
                           fecha_modificacion = NOW()
                     WHERE id_ciudadano_credencial = :id
                """),
                {"id": row.id_ciudadano_credencial},
            )
        else:
            await db.execute(
                text("""
                    UPDATE ciudadano_credencial
                       SET intentos_fallidos = :n,
                           fecha_modificacion = NOW()
                     WHERE id_ciudadano_credencial = :id
                """),
                {"n": nuevos_intentos, "id": row.id_ciudadano_credencial},
            )
        await db.commit()
        raise invalido

    # OK
    await db.execute(
        text("""
            UPDATE ciudadano_credencial
               SET intentos_fallidos = 0,
                   bloqueada_hasta = NULL,
                   fecha_ultimo_login = NOW(),
                   fecha_modificacion = NOW()
             WHERE id_ciudadano_credencial = :id
        """),
        {"id": row.id_ciudadano_credencial},
    )
    await db.commit()

    token = crear_token_ciudadano(row.id_ciudadano)
    return LoginCiudadanoOut(access_token=token, ciudadano=_ciudadano_a_basico(row))


@router.get("/me", response_model=CiudadanoBasicoOut)
async def me(current: dict = Depends(get_current_ciudadano)):
    return CiudadanoBasicoOut(
        id_ciudadano=current["id_ciudadano"],
        dni=current["doc_nro"],
        nombre=current["nombre"],
        apellido=current["apellido"],
        email=current["email"],
        estado_validacion=current["estado_validacion"],
        ficha_completa=bool(current.get("ficha_completa", False)),
    )


@router.post("/recuperar-password", response_model=GenericoOkOut)
async def recuperar_password(
    data: RecuperarPasswordIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Pide email de recovery. Anti-enumeracion + cooldown silencioso de 5 minutos."""
    dni = _validar_dni(data.dni)

    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.activado, cc.fecha_ultimo_email_recovery,
                   c.nombre, c.apellido, c.email
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE c.doc_nro = :dni AND cc.activo = TRUE AND c.activo = TRUE
        """),
        {"dni": dni},
    )
    row = res.fetchone()

    if not row or not row.activado:
        # anti-enumeracion: no revelamos que no existe / no esta activada
        return GenericoOkOut()

    if row.fecha_ultimo_email_recovery is not None:
        delta = datetime.now(timezone.utc) - row.fecha_ultimo_email_recovery
        if delta < timedelta(minutes=COOLDOWN_REENVIO_MINUTOS):
            return GenericoOkOut()

    res = await db.execute(
        text(f"""
            UPDATE ciudadano_credencial
               SET token_recovery = gen_random_uuid(),
                   token_recovery_expira = NOW() + INTERVAL '{HORAS_RECOVERY} hours',
                   fecha_ultimo_email_recovery = NOW(),
                   fecha_modificacion = NOW()
             WHERE id_ciudadano_credencial = :id
             RETURNING token_recovery
        """),
        {"id": row.id_ciudadano_credencial},
    )
    token = str(res.fetchone().token_recovery)
    await db.commit()

    municipio_nombre, municipio_logo_url = await _municipio_branding(db)
    background_tasks.add_task(
        enviar_mail_recovery_ciudadano,
        row.email,
        row.nombre,
        row.apellido,
        token,
        municipio_nombre,
        settings.APP_VECINOS_FRONTEND_URL,
        municipio_logo_url,
    )

    return GenericoOkOut()


@router.post("/resetear-password", response_model=ResetearPasswordOut)
async def resetear_password(data: ResetearPasswordIn, db: AsyncSession = Depends(get_db)):
    """Aplica nuevo password usando token de recovery. Devuelve JWT directo."""
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano,
                   c.doc_nro, c.nombre, c.apellido, c.email, c.estado_validacion,
                   c.ficha_completa, c.activo AS c_activo
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE cc.token_recovery = CAST(:token AS uuid)
               AND cc.token_recovery_expira > NOW()
               AND cc.activado = TRUE
               AND cc.activo = TRUE
        """),
        {"token": data.token},
    )
    row = res.fetchone()
    if not row or not row.c_activo:
        raise HTTPException(status_code=400, detail="Token invalido o expirado")

    hashed = hash_password(data.password)
    await db.execute(
        text("""
            UPDATE ciudadano_credencial
               SET password_hash = :ph,
                   token_recovery = NULL,
                   token_recovery_expira = NULL,
                   intentos_fallidos = 0,
                   bloqueada_hasta = NULL,
                   fecha_ultimo_cambio_password = NOW(),
                   fecha_modificacion = NOW()
             WHERE id_ciudadano_credencial = :id
        """),
        {"ph": hashed, "id": row.id_ciudadano_credencial},
    )
    await db.commit()

    token = crear_token_ciudadano(row.id_ciudadano)
    return ResetearPasswordOut(access_token=token, ciudadano=_ciudadano_a_basico(row))


@router.post("/completar-ficha", response_model=CompletarFichaOut)
async def completar_ficha(
    data: CompletarFichaIn,
    current: dict = Depends(get_current_ciudadano),
    db: AsyncSession = Depends(get_db),
):
    """
    PASO 2 del alta pública. El vecino YA verificado y logueado completa su ficha real
    (CUIL, sexo, fecha nac, nacionalidad, domicilio, teléfono). Reemplaza los placeholders
    cargados en el paso 1 y marca ficha_completa=TRUE.

    El id_ciudadano SIEMPRE sale del token (get_current_ciudadano), nunca del body: el
    vecino solo puede completar SU propia ficha.
    """
    id_ciudadano = current["id_ciudadano"]

    # Fecha de nacimiento
    try:
        fecha_nac = date.fromisoformat(data.fecha_nac)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Fecha de nacimiento inválida (formato YYYY-MM-DD)")
    if fecha_nac >= date.today():
        raise HTTPException(status_code=400, detail="La fecha de nacimiento debe ser anterior a hoy.")

    cuil = data.cuil  # validado módulo 11 por el schema
    telefono = _solo_digitos(data.telefono) or "0"

    # Nacionalidad debe existir
    res = await db.execute(
        text("SELECT id FROM nacionalidades WHERE id = :id LIMIT 1"),
        {"id": data.id_nacionalidad},
    )
    if not res.fetchone():
        raise HTTPException(status_code=400, detail="La nacionalidad seleccionada no es válida.")

    # CUIL real no debe chocar con OTRO ciudadano (es UNIQUE). El placeholder propio sí
    # se puede pisar (es de este mismo id_ciudadano).
    res = await db.execute(
        text("""
            SELECT id_ciudadano FROM ciudadanos
             WHERE cuil = :cuil AND activo = TRUE AND id_ciudadano <> :id
             LIMIT 1
        """),
        {"cuil": cuil, "id": id_ciudadano},
    )
    if res.fetchone():
        raise HTTPException(status_code=409, detail="Ese CUIL ya está registrado por otra persona.")

    await db.execute(
        text("""
            UPDATE ciudadanos
               SET cuil = :cuil,
                   sexo = :sexo,
                   fecha_nac = :fecha_nac,
                   id_nacionalidad = :id_nac,
                   calle = :calle,
                   localidad = :localidad,
                   provincia = :provincia,
                   latitud = :latitud,
                   longitud = :longitud,
                   telefono = :telefono,
                   observaciones = :observaciones,
                   ficha_completa = TRUE,
                   fecha_modificacion = NOW()
             WHERE id_ciudadano = :id
        """),
        {
            "cuil": cuil,
            "sexo": data.sexo,
            "fecha_nac": fecha_nac,
            "id_nac": data.id_nacionalidad,
            "calle": data.calle.strip(),
            "localidad": data.localidad.strip(),
            "provincia": data.provincia.strip(),
            "latitud": data.latitud,
            "longitud": data.longitud,
            "telefono": telefono,
            "observaciones": (data.observaciones or "").strip() or None,
            "id": id_ciudadano,
        },
    )
    await db.commit()

    return CompletarFichaOut(id_ciudadano=id_ciudadano, ficha_completa=True)
