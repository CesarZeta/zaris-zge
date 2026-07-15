"""
ZARIS API - ALTA PÚBLICA de vecinos (autoregistro desde URL pública).

Bajo /api/v1/publico/alta/*. SIN JWT (es público), rate-limited por IP.

A diferencia de publico_auth.py (donde un agente municipal da de alta al ciudadano),
acá el vecino se da de alta él mismo entrando a una URL pública diferenciada por
municipio mediante un slug (?m=<codigo_corto>).

Tenancy: mono-tenant validado (§38). El backend es de UN municipio (su identidad vive
en configuracion_general / municipios). El slug de la URL se VALIDA contra ese único
municipio: si no coincide, 404. Así la URL queda preparada para multi-deploy sin
reescribir el backend a multi-tenant.

Marcas de verificación (reusan columnas existentes):
  - ciudadano: ciudadanos.email_chk=TRUE + estado_validacion='verificado' + credencial activada.
  - empresa:   empresas.email_chk=TRUE + empresa_credencial.verificado=TRUE.

El alta de empresa EXIGE un ciudadano ya creado (BUC §2): la empresa se vincula a él
vía ciudadano_empresa.
"""
import re
import html as _html
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password, get_current_ciudadano
from app.core.config import settings
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip
from app.api.routes.geo import geocodificar_direccion
from app.services.email import (
    enviar_mail_verificacion_alta_ciudadano,
    enviar_mail_verificacion_alta_empresa,
)
from app.services.cuenta_vecino import asegurar_cuenta_vecino
from app.schemas.publico_alta import (
    IdentidadAltaOut,
    AltaCuentaIn,
    AltaCuentaOut,
    ActivarExistenteIn,
    ActivarExistenteOut,
    AltaEmpresaIn,
    AltaEmpresaOut,
)

router = APIRouter(prefix="/api/v1/publico/alta", tags=["publico-alta"])

DIAS_VERIFICACION = 7
RATE_MAX = 5          # altas por ventana
RATE_WINDOW = 60      # segundos


# ─── helpers ────────────────────────────────────────────────────────────────

def _solo_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _validar_dni(dni: str) -> str:
    limpio = _solo_digitos(dni)
    if not (7 <= len(limpio) <= 8):
        raise HTTPException(status_code=400, detail="DNI inválido: debe tener 7 u 8 dígitos")
    return limpio


def _validar_cuit(cuit: str) -> str:
    limpio = _solo_digitos(cuit)
    if len(limpio) != 11:
        raise HTTPException(status_code=400, detail="CUIT inválido: debe tener 11 dígitos")
    return limpio


def _cuil_desde_cuit(cuit_digits: str) -> str:
    """Para el ciudadano representante no pedimos CUIL real; placeholder digit-only basado
    en su DNI lo arma el alta del ciudadano. Acá no se usa, queda por claridad."""
    return cuit_digits


async def _resolver_municipio(db: AsyncSession, slug: str) -> dict:
    """
    Valida el slug contra el ÚNICO municipio del deploy (mono-tenant).
    Devuelve {id_municipio, nombre, slug}. 404 si el slug no coincide.
    """
    slug_norm = (slug or "").strip().lower()
    if not slug_norm:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")

    res = await db.execute(
        text("""
            SELECT id_municipio, nombre, codigo_corto
              FROM municipios
             WHERE LOWER(codigo_corto) = :slug AND activo = TRUE
             LIMIT 1
        """),
        {"slug": slug_norm},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")
    return {"id_municipio": row.id_municipio, "nombre": row.nombre, "slug": row.codigo_corto}


async def _branding(db: AsyncSession) -> dict:
    """Lee branding de configuracion_general (mono-tenant: una sola fila por clave)."""
    res = await db.execute(
        text("""
            SELECT clave, valor FROM configuracion_general
             WHERE clave IN ('municipio_nombre','municipio_logo_url',
                             'municipio_color_primary','municipio_color_accent')
        """)
    )
    cfg = {r.clave: (r.valor or None) for r in res.fetchall()}
    return cfg


def _frontend_verificar_url(slug: str, token: str) -> str:
    """
    Link de verificación que se manda por mail. Apunta al endpoint público del backend
    (que devuelve la página de confirmación). Usa FRONTEND_BASE_URL como dominio base.
    """
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}/api/v1/publico/alta/verificar?token={token}&m={slug}"


def _pagina_confirmacion(titulo: str, mensaje: str, ok: bool, municipio_nombre: str) -> str:
    """HTML mínimo y autocontenido para la pantalla de verificación (la abre el navegador)."""
    color = "#1f8a65" if ok else "#cf2d56"
    icono = "&#10003;" if ok else "&#10007;"
    t = _html.escape(titulo)
    m = _html.escape(mensaje)
    mn = _html.escape(municipio_nombre or "")
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title></head>
<body style="margin:0;padding:48px 16px;background:#f2f1ed;font-family:'Helvetica Neue',Arial,sans-serif;color:#26251e;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border:1px solid rgba(38,37,30,.1);border-radius:10px;padding:40px 32px;text-align:center;">
    <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:rgba(38,37,30,.6);margin-bottom:24px;">{mn}</div>
    <div style="width:64px;height:64px;border-radius:50%;background:{color};color:#fff;font-size:34px;line-height:64px;margin:0 auto 20px;">{icono}</div>
    <h1 style="margin:0 0 12px;font-size:22px;font-weight:600;">{t}</h1>
    <p style="margin:0;font-size:15px;line-height:1.55;color:rgba(38,37,30,.85);">{m}</p>
  </div>
</body></html>"""


# ─── endpoints ──────────────────────────────────────────────────────────────

@router.get("/identidad", response_model=IdentidadAltaOut)
async def identidad_alta(m: str, db: AsyncSession = Depends(get_db)):
    """Branding del municipio para pintar el header de la página pública. Valida el slug."""
    muni = await _resolver_municipio(db, m)
    cfg = await _branding(db)
    return IdentidadAltaOut(
        municipio_slug=muni["slug"],
        municipio_nombre=cfg.get("municipio_nombre") or muni["nombre"],
        municipio_logo_url=cfg.get("municipio_logo_url"),
        municipio_color_primary=cfg.get("municipio_color_primary"),
        municipio_color_accent=cfg.get("municipio_color_accent"),
    )


@router.get("/actividades")
async def listar_actividades(m: str, db: AsyncSession = Depends(get_db)):
    """
    Lista de actividades para el select de empresa de la página pública. Valida el slug.
    Público (sin JWT). Devuelve {actividades: [{id, descripcion}]}.
    """
    await _resolver_municipio(db, m)
    res = await db.execute(
        text("""
            SELECT id, descripcion FROM actividades
             WHERE activo IS NOT FALSE
             ORDER BY descripcion
        """)
    )
    return {"actividades": [{"id": r.id, "descripcion": r.descripcion} for r in res.fetchall()]}


@router.get("/nacionalidades")
async def listar_nacionalidades(m: str, db: AsyncSession = Depends(get_db)):
    """Catálogo de nacionalidades para el select del alta de ciudadano. Valida el slug."""
    await _resolver_municipio(db, m)
    res = await db.execute(
        text("SELECT id, pais FROM nacionalidades WHERE activo IS NOT FALSE ORDER BY pais")
    )
    return {"nacionalidades": [{"id": r.id, "pais": r.pais} for r in res.fetchall()]}


@router.get("/geo/buscar")
async def geo_buscar_publico(
    request: Request,
    m: str,
    q: str = Query(..., min_length=3, description="Texto a geocodificar"),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """
    Geocoding OSM público para el buscador de domicilio del alta de vecinos.
    Reusa la lógica de filtrado de POIs de geo.py (solo_direcciones=True).
    Valida el slug + rate-limit por IP (Nominatim ya tiene su rate-limit global).
    """
    await _resolver_municipio(db, m)
    check_rate_limit(get_real_ip(request), max_requests=20, window_seconds=60)
    return await geocodificar_direccion(q, limit, solo_direcciones=True)


@router.post("/cuenta", response_model=AltaCuentaOut, status_code=201)
async def alta_cuenta(
    data: AltaCuentaIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Autoregistro del vecino en UN PASO con la ficha COMPLETA (decisión 2026-06-12,
    reemplaza al modelo de 2 pasos de la Fase 4). El registro BUC nace completo y
    válido: NUNCA se escriben placeholders falsos (fecha 1900, CUIL inventado).

    Validaciones canónicas del ciudadano: CUIL módulo 11 (schema), fecha de nacimiento
    plausible, nacionalidad existente, DNI/CUIL/email sin duplicar contra activos.
    La credencial guarda el password elegido + token de verificación; activado=FALSE
    hasta confirmar el email. ficha_completa=TRUE desde el origen.
    """
    check_rate_limit(get_real_ip(request), max_requests=RATE_MAX, window_seconds=RATE_WINDOW)

    muni = await _resolver_municipio(db, data.municipio_slug)
    id_municipio = muni["id_municipio"]
    doc_nro = _validar_dni(_solo_digitos(data.doc_nro))
    email = data.email.lower().strip()
    cuil = data.cuil  # validado módulo 11 por el schema (digit-only)
    telefono = _solo_digitos(data.telefono) or "0"

    # Fecha de nacimiento plausible
    try:
        fecha_nac = date.fromisoformat(data.fecha_nac)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Fecha de nacimiento inválida (formato YYYY-MM-DD)")
    if fecha_nac >= date.today() or fecha_nac.year < 1900:
        raise HTTPException(status_code=400, detail="La fecha de nacimiento no es válida.")

    # Nacionalidad debe existir
    res = await db.execute(
        text("SELECT id FROM nacionalidades WHERE id = :id LIMIT 1"),
        {"id": data.id_nacionalidad},
    )
    if not res.fetchone():
        raise HTTPException(status_code=400, detail="La nacionalidad seleccionada no es válida.")

    # Documento ya existe en BUC -> no creamos duplicado: la vía correcta es
    # "activar cuenta existente" (POST /alta/activar-existente).
    res = await db.execute(
        text("SELECT id_ciudadano FROM ciudadanos WHERE doc_nro = :doc AND activo = TRUE LIMIT 1"),
        {"doc": doc_nro},
    )
    if res.fetchone():
        raise HTTPException(
            status_code=409,
            detail="Ya existe un registro con ese documento. Si sos vos, usá la opción "
                   "\"Ya estoy registrado en el municipio\" para activar tu cuenta.",
        )

    # CUIL ya registrado por otro ciudadano activo (es UNIQUE)
    res = await db.execute(
        text("SELECT id_ciudadano FROM ciudadanos WHERE cuil = :cuil AND activo = TRUE LIMIT 1"),
        {"cuil": cuil},
    )
    if res.fetchone():
        raise HTTPException(status_code=409, detail="Ese CUIL ya está registrado.")

    # Email ya usado por otra credencial activa
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
        raise HTTPException(status_code=409, detail="Ya hay una cuenta registrada con ese correo.")

    ins = await db.execute(
        text("""
            INSERT INTO ciudadanos
                (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                 id_nacionalidad, ren_chk, calle, localidad, provincia,
                 latitud, longitud, telefono, email, email_chk, emp_chk,
                 observaciones, activo, estado_validacion, ficha_completa, id_municipio,
                 fecha_alta, fecha_modificacion)
            VALUES
                ('DNI', :doc_nro, :cuil, :nombre, :apellido, :sexo, :fecha_nac,
                 :id_nacionalidad, FALSE, :calle, :localidad, :provincia,
                 :latitud, :longitud, :telefono, :email, FALSE, FALSE,
                 :observaciones, TRUE, 'auto_registrado', TRUE, :id_municipio,
                 NOW(), NOW())
            RETURNING id_ciudadano
        """),
        {
            "doc_nro": doc_nro,
            "cuil": cuil,
            "nombre": data.nombre.strip(),
            "apellido": data.apellido.strip(),
            "sexo": data.sexo,
            "fecha_nac": fecha_nac,
            "id_nacionalidad": data.id_nacionalidad,
            "calle": data.calle.strip(),
            "localidad": data.localidad.strip(),
            "provincia": data.provincia.strip(),
            "latitud": data.latitud,
            "longitud": data.longitud,
            "telefono": telefono,
            "email": email,
            "observaciones": (data.observaciones or "").strip() or None,
            "id_municipio": id_municipio,
        },
    )
    id_ciudadano = ins.fetchone().id_ciudadano

    # Credencial con password elegido + token de verificación. activado=FALSE: la cuenta
    # se habilita recién al verificar el email. debe_cambiar_password=FALSE (el vecino
    # eligió su clave; el Camino B sí la deja TRUE).
    hashed = hash_password(data.password)
    res = await db.execute(
        text(f"""
            INSERT INTO ciudadano_credencial
                (id_ciudadano, password_hash, token_activacion, token_activacion_expira,
                 activado, debe_cambiar_password, fecha_ultimo_email_activacion,
                 activo, id_municipio, fecha_alta, fecha_modificacion)
            VALUES
                (:id_ciudadano, :ph, gen_random_uuid(), NOW() + INTERVAL '{DIAS_VERIFICACION} days',
                 FALSE, FALSE, NOW(),
                 TRUE, :id_municipio, NOW(), NOW())
            RETURNING token_activacion
        """),
        {"id_ciudadano": id_ciudadano, "ph": hashed, "id_municipio": id_municipio},
    )
    token = str(res.fetchone().token_activacion)

    # Canal preferido con defaults
    await db.execute(
        text("""
            INSERT INTO ciudadano_canal_preferido
                (id_ciudadano, canal_email, canal_push, canal_whatsapp, canal_sms,
                 activo, id_municipio, fecha_alta, fecha_modificacion)
            VALUES
                (:id_ciudadano, TRUE, TRUE, FALSE, FALSE, TRUE, :id_municipio, NOW(), NOW())
            ON CONFLICT (id_ciudadano) DO NOTHING
        """),
        {"id_ciudadano": id_ciudadano, "id_municipio": id_municipio},
    )

    await db.commit()

    cfg = await _branding(db)
    cta_url = _frontend_verificar_url(muni["slug"], token)
    background_tasks.add_task(
        enviar_mail_verificacion_alta_ciudadano,
        email,
        data.nombre.strip(),
        data.apellido.strip(),
        cta_url,
        cfg.get("municipio_nombre") or muni["nombre"],
        cfg.get("municipio_logo_url"),
    )

    return AltaCuentaOut(id_ciudadano=id_ciudadano, email=email, verificacion_enviada=True)


@router.post("/activar-existente", response_model=ActivarExistenteOut)
async def activar_cuenta_existente(
    data: ActivarExistenteIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Vecino que YA figura en la BUC (cargado por el municipio o por un agente) pide su
    cuenta de portal: se crea la credencial sobre el MISMO registro (nunca duplica) y
    se manda el mail de activación al email que YA figura en la BUC — el click en ese
    mail prueba la identidad y ahí elige su contraseña.

    Anti-enumeración: SIEMPRE devuelve 200 con el mismo mensaje (exista o no el DNI,
    tenga o no email, esté o no ya activada la cuenta). Reusa asegurar_cuenta_vecino
    (idempotente: cuenta activada -> no toca nada; sin activar -> regenera token).
    """
    check_rate_limit(get_real_ip(request), max_requests=RATE_MAX, window_seconds=RATE_WINDOW)
    muni = await _resolver_municipio(db, data.municipio_slug)

    doc_nro = _solo_digitos(data.doc_nro)
    if not (7 <= len(doc_nro) <= 8):
        return ActivarExistenteOut()  # DNI inválido: misma respuesta genérica

    res = await db.execute(
        text("""
            SELECT id_ciudadano, nombre, apellido, email
              FROM ciudadanos
             WHERE doc_nro = :doc AND activo = TRUE
             LIMIT 1
        """),
        {"doc": doc_nro},
    )
    row = res.fetchone()
    if not row or not (row.email or "").strip():
        return ActivarExistenteOut()  # no existe o no tiene email: silencio

    await asegurar_cuenta_vecino(
        db,
        id_ciudadano=row.id_ciudadano,
        nombre=row.nombre or "",
        apellido=row.apellido or "",
        email=row.email.strip(),
        id_municipio=muni["id_municipio"],
        id_usuario_alta=None,
        background_tasks=background_tasks,
    )
    await db.commit()
    return ActivarExistenteOut()


@router.post("/empresa", response_model=AltaEmpresaOut, status_code=201)
async def alta_empresa(
    data: AltaEmpresaIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
):
    """
    Alta de empresa por el vecino LOGUEADO (JWT scope 'publico'). La empresa se vincula
    al ciudadano del token — NUNCA a un id que venga del cliente (BUC §2 + regla "el
    id_ciudadano SIEMPRE sale del JWT": el vecino no puede operar sobre terceros).

    Crea empresa + ciudadano_empresa + empresa_credencial con token de verificación y
    manda mail a la casilla de la empresa.
    """
    check_rate_limit(get_real_ip(request), max_requests=RATE_MAX, window_seconds=RATE_WINDOW)

    muni = await _resolver_municipio(db, data.municipio_slug)
    id_municipio = muni["id_municipio"]
    # El representante es el ciudadano del token — get_current_ciudadano ya garantizó
    # que existe, está activo y su credencial está activada.
    id_ciudadano = ciudadano["id_ciudadano"]
    cuit = data.cuit  # ya validado/normalizado (módulo 11) por el schema
    email = data.email.lower().strip()
    telefono = _solo_digitos(data.telefono) or "0"

    # Actividad debe existir (la PK de `actividades` es `id`, no `id_actividad` — tabla legacy)
    res = await db.execute(
        text("SELECT id FROM actividades WHERE id = :id AND activo IS NOT FALSE LIMIT 1"),
        {"id": data.id_actividad},
    )
    if not res.fetchone():
        raise HTTPException(status_code=400, detail="La actividad seleccionada no es válida.")

    # CUIT ya registrado -> no duplicar
    res = await db.execute(
        text("SELECT id_empresa FROM empresas WHERE cuit = :cuit AND activo = TRUE LIMIT 1"),
        {"cuit": cuit},
    )
    if res.fetchone():
        raise HTTPException(status_code=409, detail="Ya existe una empresa registrada con ese CUIT.")

    ins = await db.execute(
        text("""
            INSERT INTO empresas
                (cuit, nombre, id_actividad, calle, altura, localidad, provincia,
                 latitud, longitud, telefono, email, email_chk, observaciones,
                 activo, id_municipio, fecha_alta)
            VALUES
                (:cuit, :nombre, :id_actividad, :calle, NULL, :localidad, :provincia,
                 :latitud, :longitud, :telefono, :email, FALSE, :observaciones,
                 TRUE, :id_municipio, NOW())
            RETURNING id_empresa
        """),
        {
            "cuit": cuit,
            "nombre": data.razon_social.strip(),
            "id_actividad": data.id_actividad,
            "calle": data.calle.strip(),
            "localidad": data.localidad.strip(),
            "provincia": data.provincia.strip(),
            "latitud": data.latitud,
            "longitud": data.longitud,
            "telefono": telefono,
            "email": email,
            "observaciones": (data.observaciones or "").strip() or None,
            "id_municipio": id_municipio,
        },
    )
    id_empresa = ins.fetchone().id_empresa

    # Vínculo ciudadano ↔ empresa (representación)
    await db.execute(
        text("""
            INSERT INTO ciudadano_empresa (id_ciudadano, id_empresa, id_tipo_representacion, fecha_alta, activo)
            VALUES (:id_ciudadano, :id_empresa, :id_tipo, NOW(), TRUE)
            ON CONFLICT (id_ciudadano, id_empresa, id_tipo_representacion) DO NOTHING
        """),
        {
            "id_ciudadano": id_ciudadano,
            "id_empresa": id_empresa,
            "id_tipo": data.id_tipo_representacion or 1,
        },
    )

    # Credencial de verificación de email de la empresa
    res = await db.execute(
        text(f"""
            INSERT INTO empresa_credencial
                (id_empresa, token_verificacion, token_verificacion_expira,
                 verificado, fecha_ultimo_email_verificacion,
                 activo, id_municipio, fecha_alta, fecha_modificacion)
            VALUES
                (:id_empresa, gen_random_uuid(), NOW() + INTERVAL '{DIAS_VERIFICACION} days',
                 FALSE, NOW(),
                 TRUE, :id_municipio, NOW(), NOW())
            RETURNING token_verificacion
        """),
        {"id_empresa": id_empresa, "id_municipio": id_municipio},
    )
    token = str(res.fetchone().token_verificacion)

    await db.commit()

    cfg = await _branding(db)
    cta_url = _frontend_verificar_url(muni["slug"], token)
    background_tasks.add_task(
        enviar_mail_verificacion_alta_empresa,
        email,
        data.razon_social.strip(),
        cta_url,
        cfg.get("municipio_nombre") or muni["nombre"],
        cfg.get("municipio_logo_url"),
    )

    return AltaEmpresaOut(id_empresa=id_empresa, email=email, verificacion_enviada=True)


@router.get("/verificar", response_class=HTMLResponse)
async def verificar(token: str, m: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    Verifica el email del alta (ciudadano o empresa) a partir del token UUID.
    Devuelve una página HTML de confirmación (la abre el navegador del vecino).

    El token puede ser de un ciudadano (ciudadano_credencial.token_activacion) o de una
    empresa (empresa_credencial.token_verificacion). Probamos primero ciudadano.
    """
    cfg = await _branding(db)
    municipio_nombre = cfg.get("municipio_nombre") or "Tu municipio"

    # ── Ciudadano ──
    res = await db.execute(
        text("""
            SELECT cc.id_ciudadano_credencial, cc.id_ciudadano, c.nombre, c.apellido
              FROM ciudadano_credencial cc
              JOIN ciudadanos c ON c.id_ciudadano = cc.id_ciudadano
             WHERE cc.token_activacion = CAST(:token AS uuid)
               AND cc.token_activacion_expira > NOW()
               AND cc.activo = TRUE AND c.activo = TRUE
        """),
        {"token": token},
    )
    row = res.fetchone()
    if row:
        await db.execute(
            text("""
                UPDATE ciudadanos
                   SET email_chk = TRUE,
                       estado_validacion = 'verificado',
                       fecha_modificacion = NOW()
                 WHERE id_ciudadano = :id
            """),
            {"id": row.id_ciudadano},
        )
        await db.execute(
            text("""
                UPDATE ciudadano_credencial
                   SET activado = TRUE,
                       activado_en = COALESCE(activado_en, NOW()),
                       token_activacion = NULL,
                       token_activacion_expira = NULL,
                       fecha_modificacion = NOW()
                 WHERE id_ciudadano_credencial = :id
            """),
            {"id": row.id_ciudadano_credencial},
        )
        await db.commit()
        nombre = (row.nombre or "").strip() or row.apellido or "vecino"
        return HTMLResponse(_pagina_confirmacion(
            "¡Correo verificado!",
            f"Listo, {nombre}. Tu correo quedó verificado. Ya podés iniciar sesión en el "
            f"Portal del Ciudadano con tu DNI y la contraseña que elegiste.",
            ok=True, municipio_nombre=municipio_nombre,
        ))

    # ── Empresa ──
    res = await db.execute(
        text("""
            SELECT ec.id_empresa_credencial, ec.id_empresa, e.nombre AS razon_social
              FROM empresa_credencial ec
              JOIN empresas e ON e.id_empresa = ec.id_empresa
             WHERE ec.token_verificacion = CAST(:token AS uuid)
               AND ec.token_verificacion_expira > NOW()
               AND ec.activo = TRUE AND e.activo = TRUE
        """),
        {"token": token},
    )
    row = res.fetchone()
    if row:
        await db.execute(
            text("UPDATE empresas SET email_chk = TRUE, fecha_modif = NOW() WHERE id_empresa = :id"),
            {"id": row.id_empresa},
        )
        await db.execute(
            text("""
                UPDATE empresa_credencial
                   SET verificado = TRUE,
                       verificado_en = NOW(),
                       token_verificacion = NULL,
                       token_verificacion_expira = NULL,
                       fecha_modificacion = NOW()
                 WHERE id_empresa_credencial = :id
            """),
            {"id": row.id_empresa_credencial},
        )
        await db.commit()
        return HTMLResponse(_pagina_confirmacion(
            "¡Empresa verificada!",
            f"El alta de {row.razon_social} quedó verificada correctamente.",
            ok=True, municipio_nombre=municipio_nombre,
        ))

    # Token inválido o expirado
    return HTMLResponse(
        _pagina_confirmacion(
            "Enlace inválido o vencido",
            "Este enlace de verificación no es válido o ya expiró. Si te diste de alta hace poco, "
            "volvé a intentarlo o pedí un nuevo correo desde la página de alta.",
            ok=False, municipio_nombre=municipio_nombre,
        ),
        status_code=400,
    )
