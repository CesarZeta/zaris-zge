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
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.utils.request_helpers import get_real_ip
from app.middleware.rate_limit import check_rate_limit
from app.core.sistema import fijar_por_token
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    hash_password,
    verify_password,
    get_current_user,
    get_current_ciudadano,
    crear_token_ciudadano,
)
from app.core.config_municipio import leer_configs
from app.core.database import get_db
from app.core.municipio import resolver_municipio_de_origen
from app.core.urls import base_app
from app.services.cuenta_vecino import asignar_numero_usuario
from app.services.email import (
    enviar_mail_activacion_ciudadano,
    enviar_mail_recovery_ciudadano,
    enviar_mail_usuario_generado_ciudadano,
)
from app.schemas.publico_auth import (
    ActivarIn,
    ActivarOut,
    ConfirmarCorreoIn,
    ConfirmarCorreoOut,
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


def _token_uuid(token: str) -> str:
    """Un token que no es un UUID es el mismo caso que uno inexistente: 400, nunca un 500 (§5)."""
    try:
        return str(uuid.UUID(token))
    except ValueError:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")


def _validar_dni(dni: str) -> str:
    """Devuelve DNI digits-only. Levanta 400 si no es 7-8 chars."""
    limpio = _solo_digitos(dni)
    if not (7 <= len(limpio) <= 8):
        raise HTTPException(status_code=400, detail="DNI inválido: debe tener 7 u 8 dígitos")
    return limpio


def _condicion_identificador(identificador: str) -> tuple[str, dict]:
    """Condición SQL del ingreso: número de usuario (6 dígitos, mig 143) o DNI (7 u 8)."""
    limpio = _solo_digitos(identificador)
    if len(limpio) == 6:
        return "cc.numero_usuario = :ident", {"ident": int(limpio)}
    if 7 <= len(limpio) <= 8:
        return "c.doc_nro = :ident", {"ident": limpio}
    raise HTTPException(status_code=400,
                        detail="Ingresá tu DNI (7 u 8 dígitos) o tu número de usuario (6 dígitos)")


def _ciudadano_a_basico(row, numero_usuario: int | None = None) -> CiudadanoBasicoOut:
    return CiudadanoBasicoOut(
        id_ciudadano=row.id_ciudadano,
        dni=row.doc_nro,
        nombre=row.nombre,
        apellido=row.apellido,
        email=row.email,
        estado_validacion=row.estado_validacion,
        ficha_completa=bool(getattr(row, "ficha_completa", False)),
        numero_usuario=numero_usuario if numero_usuario is not None else getattr(row, "numero_usuario", None),
    )


async def _municipio_branding(db: AsyncSession, id_municipio: int) -> tuple[str, str | None]:
    """Devuelve (municipio_nombre, municipio_logo_url) del municipio, leyendo configuracion_general."""
    cfg = await leer_configs(db, ["municipio_nombre", "municipio_logo_url"], id_municipio)
    return (
        cfg.get("municipio_nombre") or "Tu municipio",
        cfg.get("municipio_logo_url") or None,
    )


# ─── endpoints ──────────────────────────────────────────────────────────────

@router.post("/registrar", status_code=410, responses={410: {"description": "Retirado"}})
async def registrar_ciudadano(current_agente: dict = Depends(get_current_user)):
    """Retirado (2026-11-24): creaba personas con datos de relleno (PLAN_REGISTRO_PREVIO.md §2).
    El agente registra al vecino con su ficha completa en `POST /api/v1/buc/ciudadanos`."""
    raise HTTPException(status_code=410, detail="El alta se hace con la ficha completa del vecino.")


@router.post("/confirmar-correo", response_model=ConfirmarCorreoOut)
async def confirmar_correo(data: ConfirmarCorreoIn, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Paso 1 del link del correo: el vecino demuestra que la casilla es suya y queda dado de alta
    (PLAN_REGISTRO_PREVIO.md §6). No consume el token: con él genera después su usuario. Va por
    POST a propósito: los antivirus de correo abren los links con GET.
    """
    check_rate_limit(f"vecinoconfirma:{get_real_ip(request)}", max_requests=20, window_seconds=60)
    token = _token_uuid(data.token)
    await fijar_por_token(db, token, "activacion_vecino")  # segunda barrera (IT-01 F6): municipio del token
    row = (await db.execute(
        text("""
            SELECT cc.id_ciudadano, c.nombre, c.apellido
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE cc.token_activacion = CAST(:token AS uuid)
               AND cc.token_activacion_expira > NOW()
               AND cc.activado = FALSE
               AND cc.activo = TRUE AND c.activo = TRUE
        """),
        {"token": token},
    )).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")
    await db.execute(
        text("""
            UPDATE ciudadanos
               SET email_chk = TRUE, estado_validacion = 'verificado', fecha_modificacion = NOW()
             WHERE id_ciudadano = :id
               AND (email_chk IS NOT TRUE OR estado_validacion <> 'verificado')
        """),
        {"id": row.id_ciudadano},
    )
    await db.commit()
    return ConfirmarCorreoOut(nombre=row.nombre or "", apellido=row.apellido or "")


@router.post("/activar", response_model=ActivarOut)
async def activar_cuenta(data: ActivarIn, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """El vecino genera su usuario: elige la contraseña y el sistema le asigna el número. El click
    en el correo también confirma la casilla."""
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    token_activacion = _token_uuid(data.token)
    await fijar_por_token(db, token_activacion, "activacion_vecino")  # segunda barrera (IT-01 F6): municipio del token
    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano,
                   c.doc_nro, c.nombre, c.apellido, c.email, c.estado_validacion,
                   c.ficha_completa, c.activo AS c_activo, c.id_municipio
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE cc.token_activacion = CAST(:token AS uuid)
               AND cc.token_activacion_expira > NOW()
               AND cc.activado = FALSE
               AND cc.activo = TRUE
        """),
        {"token": token_activacion},
    )
    row = res.fetchone()
    if not row or not row.c_activo:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

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
    numero = await asignar_numero_usuario(db, row.id_ciudadano_credencial, row.id_municipio)
    await db.execute(
        text("""
            UPDATE ciudadanos
               SET email_chk = TRUE, estado_validacion = 'verificado', fecha_modificacion = NOW()
             WHERE id_ciudadano = :id
               AND (email_chk IS NOT TRUE OR estado_validacion <> 'verificado')
        """),
        {"id": row.id_ciudadano},
    )
    await db.commit()

    municipio_nombre, municipio_logo_url = await _municipio_branding(db, row.id_municipio)
    background_tasks.add_task(
        enviar_mail_usuario_generado_ciudadano,
        row.email,
        row.nombre,
        row.apellido,
        numero,
        municipio_nombre,
        await base_app(db, row.id_municipio, "vecinos"),
        municipio_logo_url,
        id_municipio=row.id_municipio,
    )

    token = crear_token_ciudadano(row.id_ciudadano, row.id_municipio)
    basico = _ciudadano_a_basico(row, numero)
    basico.estado_validacion = "verificado"
    return ActivarOut(access_token=token, ciudadano=basico)


@router.post("/reenviar-activacion", response_model=GenericoOkOut)
async def reenviar_activacion(
    data: ReenviarActivacionIn,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Reenvia mail de activacion. Cooldown 5 minutos.
    Anti-enumeracion: si el DNI no existe O ya esta activada, devuelve 200 igual.
    """
    # Rate limit por IP: frena el mail-bombing (aunque haya cooldown por cuenta,
    # una IP podría rotar DNIs para spamear mails de activación).
    check_rate_limit(f"vecinoreenvio:{get_real_ip(request)}", max_requests=8, window_seconds=60)
    dni = _validar_dni(data.dni)
    id_municipio = await resolver_municipio_de_origen(request, db)

    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano, cc.activado,
                   cc.fecha_ultimo_email_activacion,
                   c.nombre, c.apellido, c.email
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE c.doc_nro = :dni AND cc.activo = TRUE AND c.activo = TRUE
               AND c.id_municipio = :mun
        """),
        {"dni": dni, "mun": id_municipio},
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

    municipio_nombre, municipio_logo_url = await _municipio_branding(db, id_municipio)
    background_tasks.add_task(
        enviar_mail_activacion_ciudadano,
        row.email,
        row.nombre,
        row.apellido,
        token,
        municipio_nombre,
        await base_app(db, id_municipio, "vecinos"),
        municipio_logo_url,
        id_municipio=id_municipio,
    )

    return GenericoOkOut()


@router.post("/login", response_model=LoginCiudadanoOut)
async def login_ciudadano(data: LoginCiudadanoIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Login con DNI o número de usuario + password. Lockout 5 intentos = 15 minutos."""
    # Rate limit por IP y por DNI ANTES de tocar la DB/bcrypt: complementa el
    # lockout por-cuenta (que no frena un ataque distribuido por muchas cuentas
    # desde una IP). Claves prefijadas por flujo (§5).
    _ip = get_real_ip(request)
    check_rate_limit(f"vecinologin-ip:{_ip}", max_requests=10, window_seconds=60)
    check_rate_limit(f"vecinologin-dni:{_solo_digitos(data.identificador)}", max_requests=6, window_seconds=60)
    cond, params = _condicion_identificador(data.identificador)
    invalido = HTTPException(status_code=401, detail="Credenciales inválidas")
    # Una cuenta por municipio: se busca en el municipio de la dirección de origen.
    id_municipio = await resolver_municipio_de_origen(request, db)

    res = await db.execute(
        text(f"""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano, cc.numero_usuario,
                   cc.password_hash, cc.activado, cc.intentos_fallidos, cc.bloqueada_hasta,
                   cc.activo AS cc_activo,
                   c.doc_nro, c.nombre, c.apellido, c.email, c.estado_validacion,
                   c.ficha_completa, c.activo AS c_activo, c.id_municipio
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE {cond} AND c.id_municipio = :mun
        """),
        {**params, "mun": id_municipio},
    )
    row = res.fetchone()

    if not row or not row.c_activo or not row.cc_activo or not row.activado or not row.password_hash:
        raise invalido

    # Lockout
    if row.bloqueada_hasta is not None and row.bloqueada_hasta > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=401,
            detail="Cuenta bloqueada temporalmente. Intentá en unos minutos.",
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

    token = crear_token_ciudadano(row.id_ciudadano, row.id_municipio)
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
        numero_usuario=current.get("numero_usuario"),
    )


@router.get("/nacionalidades")
async def listar_nacionalidades_publico(
    current: dict = Depends(get_current_ciudadano),
    db: AsyncSession = Depends(get_db),
):
    """Catálogo de nacionalidades para el PASO 2 (completar ficha) del vecino logueado.

    A diferencia de /publico/alta/nacionalidades (sin JWT, valida slug), este lo consume
    el vecino YA logueado con su token scope 'publico' — la PWA mono-deploy no maneja slug.
    Espeja el patrón del geocoding del vecino (/publico/reclamos/geo/buscar).
    PK real de la tabla es `id` (no `id_nacionalidad`, §5 PK legacy).
    """
    res = await db.execute(
        text("SELECT id, pais FROM nacionalidades WHERE activo IS NOT FALSE ORDER BY pais")
    )
    return {"nacionalidades": [{"id": r.id, "pais": r.pais} for r in res.fetchall()]}


@router.post("/recuperar-password", response_model=GenericoOkOut)
async def recuperar_password(
    data: RecuperarPasswordIn,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Pide email de recovery. Anti-enumeracion + cooldown silencioso de 5 minutos."""
    # Rate limit por IP: frena el mail-bombing de recovery (cooldown es por cuenta).
    check_rate_limit(f"vecinorecovery:{get_real_ip(request)}", max_requests=8, window_seconds=60)
    cond, params = _condicion_identificador(data.identificador)
    id_municipio = await resolver_municipio_de_origen(request, db)

    res = await db.execute(
        text(f"""
            SELECT cc.id_ciudadano_credencial, cc.activado, cc.fecha_ultimo_email_recovery,
                   c.nombre, c.apellido, c.email
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE {cond} AND cc.activo = TRUE AND c.activo = TRUE
               AND c.id_municipio = :mun
        """),
        {**params, "mun": id_municipio},
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

    municipio_nombre, municipio_logo_url = await _municipio_branding(db, id_municipio)
    background_tasks.add_task(
        enviar_mail_recovery_ciudadano,
        row.email,
        row.nombre,
        row.apellido,
        token,
        municipio_nombre,
        await base_app(db, id_municipio, "vecinos"),
        municipio_logo_url,
        id_municipio=id_municipio,
    )

    return GenericoOkOut()


@router.post("/resetear-password", response_model=ResetearPasswordOut)
async def resetear_password(data: ResetearPasswordIn, db: AsyncSession = Depends(get_db)):
    """Aplica nuevo password usando token de recovery. Devuelve JWT directo."""
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    token_recovery = _token_uuid(data.token)
    await fijar_por_token(db, token_recovery, "recuperacion_vecino")  # segunda barrera (IT-01 F6): municipio del token
    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano, cc.numero_usuario,
                   c.doc_nro, c.nombre, c.apellido, c.email, c.estado_validacion,
                   c.ficha_completa, c.activo AS c_activo, c.id_municipio
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE cc.token_recovery = CAST(:token AS uuid)
               AND cc.token_recovery_expira > NOW()
               AND cc.activado = TRUE
               AND cc.activo = TRUE
        """),
        {"token": token_recovery},
    )
    row = res.fetchone()
    if not row or not row.c_activo:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

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

    token = crear_token_ciudadano(row.id_ciudadano, row.id_municipio)
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
             WHERE cuil = :cuil AND activo = TRUE AND id_ciudadano <> :id AND id_municipio = :mun
             LIMIT 1
        """),
        {"cuil": cuil, "id": id_ciudadano, "mun": current["id_municipio"]},
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
