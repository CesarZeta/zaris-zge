"""
ZARIS API — Segundo factor de las cuentas de nivel 0 y 1 (IT-01 F3b).

El login con clave no entrega el token a estas cuentas: responde un DESAFÍO de 5 minutos y el
estado (`codigo` | `vincular` | `sin_habilitar`). Con el desafío, estos endpoints verifican el
código de la app (o un código de emergencia) o vinculan la app, y recién ahí emiten el token
(claim `sf`). Spec: PLAN_MULTI_MUNICIPIO_F3B_DISENO.md §4.

POST /api/v1/auth/segundo-factor/verificar              {desafio, codigo} → token
POST /api/v1/auth/segundo-factor/emergencia             {desafio, codigo} → desafío para revincular
POST /api/v1/auth/segundo-factor/vinculacion            {desafio}         → QR y secreto
POST /api/v1/auth/segundo-factor/vinculacion/confirmar  {desafio, codigo} → códigos de emergencia + token

Y para el backoffice (Usuarios), con el municipio de la request:
GET  /api/v1/auth/segundo-factor/cuentas/{id}            estado (administrador o super)
POST /api/v1/auth/segundo-factor/cuentas/{id}/habilitar  restablece y habilita 24 h (solo el super)
"""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (ALGORITHM, NIVELES_CON_SEGUNDO_FACTOR, get_current_user, require_super_admin,
                           requiere_segundo_factor)
from app.core.config import settings
from app.core.database import get_db
from app.core.municipio import municipio_actual
from app.core.urls import url_login_backoffice
from app.middleware.rate_limit import check_rate_limit
from app.services import segundo_factor as sf
from app.services.accesos_super import registrar_acceso_super_en
from app.services.login_interno import LoginResponse, cargar_usuario, completar_login
from app.utils.request_helpers import get_real_ip

router = APIRouter(prefix="/api/v1/auth/segundo-factor", tags=["Auth"])

TEXTO_SIN_HABILITAR = "Tu cuenta necesita que el soporte de ZARIS habilite la vinculación de la app de códigos."
TEXTO_CODIGO_INVALIDO = "El código no es válido. Revisá la app y probá de nuevo."
TEXTO_BLOQUEO = "Demasiados códigos incorrectos. Probá de nuevo en 15 minutos."
TEXTO_DESAFIO = "Pasaron más de 5 minutos. Volvé a ingresar tu clave."
TEXTO_NO_CONFIGURADO = ("El ingreso con segundo factor no está configurado en el servidor. "
                        "Avisá al soporte de ZARIS.")
SCOPE_DESAFIO = "segundo_factor"
Fin = Literal["codigo", "vincular", "revincular"]


class SegundoFactorRequerido(BaseModel):
    requiere_segundo_factor: Literal[True] = True
    estado: Literal["codigo", "vincular", "sin_habilitar"]
    desafio: Optional[str] = None
    mensaje: Optional[str] = None
    url_backoffice: str


class DesafioIn(BaseModel):
    desafio: str = Field(max_length=2000)


class CodigoIn(DesafioIn):
    codigo: str = Field(max_length=40)


class DesafioOut(BaseModel):
    desafio: str


class VinculacionOut(BaseModel):
    qr: str
    secreto: str
    emisor: str
    cuenta: str


class VinculacionConfirmada(LoginResponse):
    codigos_emergencia: list[str]


def no_configurado() -> HTTPException:
    return HTTPException(status_code=503, detail=TEXTO_NO_CONFIGURADO)


def crear_desafio(id_usuario: int, *, fin: Fin, id_municipio: Optional[int]) -> str:
    """Desafío entre la clave y el código: JWT de 5 min con un scope propio, que get_current_user
    rechaza (no sirve como token). `id_municipio` None = super administrador."""
    claims = {"sub": str(id_usuario), "scope": SCOPE_DESAFIO, "fin": fin,
              "exp": datetime.now(timezone.utc) + timedelta(minutes=sf.DESAFIO_MINUTOS)}
    if id_municipio is None:
        claims["sa"] = True
    else:
        claims["mun"] = id_municipio
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM)


async def leer_desafio(db: AsyncSession, token: str, fines: set[str]):
    """(fin, cuenta) de un desafío vigente cuya cuenta sigue activa, sigue requiriendo segundo
    factor y sigue en el mismo municipio. Si no, 401."""
    no_vale = HTTPException(status_code=401, detail=TEXTO_DESAFIO)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        id_usuario = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise no_vale
    if payload.get("scope") != SCOPE_DESAFIO or payload.get("fin") not in fines:
        raise no_vale
    user = await cargar_usuario(db, id_usuario)
    if user is None or not user.activo or not requiere_segundo_factor(user.nivel_acceso):
        raise no_vale
    if payload.get("sa") is True:
        if user.nivel_acceso != 0 or user.id_municipio is not None:
            raise no_vale
    elif user.nivel_acceso == 0 or payload.get("mun") != user.id_municipio:
        raise no_vale
    return payload["fin"], user


async def respuesta_login(db: AsyncSession, user) -> SegundoFactorRequerido:
    """Lo que devuelve el login con clave a una cuenta con segundo factor. Lanza
    SegundoFactorNoConfigurado si falta la clave de cifrado."""
    sf.comprobar_configuracion()
    est = await sf.estado_cuenta(db, user.id_usuario)
    base = {"url_backoffice": url_login_backoffice()}
    if est.vinculada:
        return SegundoFactorRequerido(estado="codigo", **base, desafio=crear_desafio(
            user.id_usuario, fin="codigo", id_municipio=user.id_municipio))
    if est.habilitada:
        return SegundoFactorRequerido(estado="vincular", **base, desafio=crear_desafio(
            user.id_usuario, fin="vincular", id_municipio=user.id_municipio))
    return SegundoFactorRequerido(estado="sin_habilitar", mensaje=TEXTO_SIN_HABILITAR, **base)


def _limitar(request: Request) -> None:
    check_rate_limit(f"segfac-ip:{get_real_ip(request)}", max_requests=10, window_seconds=60)


async def _exigir_no_bloqueada(db: AsyncSession, user) -> None:
    if await sf.bloqueada(db, user.id_usuario):
        raise HTTPException(status_code=429, detail=TEXTO_BLOQUEO)


async def _exigir_habilitada(db: AsyncSession, user) -> None:
    if not (await sf.estado_cuenta(db, user.id_usuario)).habilitada:
        raise HTTPException(status_code=403, detail=TEXTO_SIN_HABILITAR)


async def _fallo(db: AsyncSession, user, request: Request) -> HTTPException:
    """Registra un código mal puesto y devuelve la excepción a lanzar (429 si bloqueó)."""
    bloqueo = await sf.registrar_fallo(db, id_usuario=user.id_usuario)
    await sf.registrar_evento(db, id_usuario=user.id_usuario, id_municipio=user.id_municipio,
                              evento="fallido", ip=get_real_ip(request),
                              user_agent=request.headers.get("user-agent"))
    await db.commit()
    if bloqueo:
        return HTTPException(status_code=429, detail=TEXTO_BLOQUEO)
    return HTTPException(status_code=401, detail=TEXTO_CODIGO_INVALIDO)


async def _evento(db: AsyncSession, user, request: Request, evento: str) -> None:
    await sf.registrar_evento(db, id_usuario=user.id_usuario, id_municipio=user.id_municipio,
                              evento=evento, ip=get_real_ip(request),
                              user_agent=request.headers.get("user-agent"))


async def _etiqueta(db: AsyncSession, user) -> str:
    """Cómo se ve la cuenta en la app de autenticación: el email, y para un administrador el
    código del municipio, para distinguir dos cuentas."""
    if user.id_municipio is None:
        return user.email
    codigo = (await db.execute(text("SELECT codigo_corto FROM municipios WHERE id_municipio = :m"),
                               {"m": user.id_municipio})).scalar()
    return f"{user.email} · {codigo}" if codigo else user.email


@router.post("/verificar", response_model=LoginResponse,
             responses={401: {"description": "Código inválido o desafío vencido"},
                        429: {"description": "Cuenta bloqueada 15 minutos"}})
async def verificar(body: CodigoIn, request: Request, db: AsyncSession = Depends(get_db)):
    _limitar(request)
    _, user = await leer_desafio(db, body.desafio, {"codigo"})
    await _exigir_no_bloqueada(db, user)
    try:
        ok = await sf.verificar_codigo(db, id_usuario=user.id_usuario, codigo=body.codigo)
    except sf.SegundoFactorNoConfigurado:
        raise no_configurado()
    if not ok:
        raise await _fallo(db, user, request)
    await _evento(db, user, request, "ingreso")
    await db.commit()
    return await completar_login(db, request, user, segundo_factor=True)


@router.post("/emergencia", response_model=DesafioOut)
async def emergencia(body: CodigoIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Un código de emergencia no entrega token: obliga a vincular la app de nuevo en el mismo
    flujo. La app vieja sigue valiendo hasta que se confirma la nueva."""
    _limitar(request)
    _, user = await leer_desafio(db, body.desafio, {"codigo"})
    await _exigir_no_bloqueada(db, user)
    if not await sf.usar_codigo_emergencia(db, id_usuario=user.id_usuario, codigo=body.codigo):
        raise await _fallo(db, user, request)
    await _evento(db, user, request, "emergencia")
    await db.commit()
    return DesafioOut(desafio=crear_desafio(user.id_usuario, fin="revincular", id_municipio=user.id_municipio))


@router.post("/vinculacion", response_model=VinculacionOut)
async def vinculacion(body: DesafioIn, request: Request, db: AsyncSession = Depends(get_db)):
    _limitar(request)
    fin, user = await leer_desafio(db, body.desafio, {"vincular", "revincular"})
    if fin == "vincular":
        await _exigir_habilitada(db, user)
    try:
        datos = await sf.iniciar_vinculacion(db, id_usuario=user.id_usuario, id_municipio=user.id_municipio,
                                             etiqueta=await _etiqueta(db, user))
    except sf.SegundoFactorNoConfigurado:
        raise no_configurado()
    await db.commit()
    return VinculacionOut(**datos)


@router.post("/vinculacion/confirmar", response_model=VinculacionConfirmada)
async def confirmar_vinculacion(body: CodigoIn, request: Request, db: AsyncSession = Depends(get_db)):
    _limitar(request)
    fin, user = await leer_desafio(db, body.desafio, {"vincular", "revincular"})
    await _exigir_no_bloqueada(db, user)
    if fin == "vincular":
        await _exigir_habilitada(db, user)
    try:
        codigos = await sf.confirmar_vinculacion(db, id_usuario=user.id_usuario, codigo=body.codigo)
    except sf.SegundoFactorNoConfigurado:
        raise no_configurado()
    if codigos is None:
        raise await _fallo(db, user, request)
    await _evento(db, user, request, "vinculado")
    await db.commit()
    sesion = await completar_login(db, request, user, segundo_factor=True)
    return VinculacionConfirmada(codigos_emergencia=codigos, **sesion)


# ── Backoffice: estado y habilitación ────────────────────────────────────────

class EstadoSegundoFactorOut(BaseModel):
    """Solo estado: nunca secretos ni códigos."""
    nivel: int
    requiere: bool
    vinculada: bool
    confirmado_en: Optional[datetime] = None
    habilitada: bool
    habilitado_hasta: Optional[datetime] = None
    bloqueado_hasta: Optional[datetime] = None


async def _cuenta_del_municipio(db: AsyncSession, id_usuario: int, id_municipio: int):
    """Cuenta del municipio de la request. Una de otro municipio, o del super (sin municipio),
    responde 404 como una inexistente."""
    fila = (await db.execute(text("""
        SELECT id_usuario, nombre, email, nivel_acceso, id_municipio FROM usuarios
         WHERE id_usuario = :u AND id_municipio = :m"""), {"u": id_usuario, "m": id_municipio})).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Cuenta inexistente")
    return fila


async def _estado_out(db: AsyncSession, cuenta) -> EstadoSegundoFactorOut:
    est = await sf.estado_cuenta(db, cuenta.id_usuario)
    return EstadoSegundoFactorOut(
        nivel=cuenta.nivel_acceso, requiere=cuenta.nivel_acceso in NIVELES_CON_SEGUNDO_FACTOR,
        vinculada=est.vinculada, confirmado_en=est.confirmado_en, habilitada=est.habilitada,
        habilitado_hasta=est.habilitado_hasta, bloqueado_hasta=est.bloqueado_hasta)


@router.get("/cuentas/{id_usuario}", response_model=EstadoSegundoFactorOut)
async def estado_de_cuenta(
    id_usuario: int = Path(ge=1, le=2_147_483_647),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
    db: AsyncSession = Depends(get_db),
):
    if current_user["nivel_acceso"] != 1:  # nivel efectivo: administrador o super
        raise HTTPException(status_code=403, detail="Requiere nivel administrador")
    return await _estado_out(db, await _cuenta_del_municipio(db, id_usuario, id_municipio))


@router.post("/cuentas/{id_usuario}/habilitar", response_model=EstadoSegundoFactorOut,
             responses={404: {"description": "Cuenta de nivel 1 inexistente en el municipio"}})
async def habilitar_cuenta(
    request: Request,
    id_usuario: int = Path(ge=1, le=2_147_483_647),
    current_user: dict = Depends(require_super_admin),
    id_municipio: int = Depends(municipio_actual),
    db: AsyncSession = Depends(get_db),
):
    """Restablece el segundo factor de un administrador del municipio y habilita la vinculación
    por 24 h: borra la app y los códigos, y corta sus sesiones. Solo el super administrador; queda
    en su registro en la misma transacción (si no se puede registrar, el cambio no queda)."""
    cuenta = await _cuenta_del_municipio(db, id_usuario, id_municipio)
    if cuenta.nivel_acceso != 1:
        raise HTTPException(status_code=404, detail="Cuenta inexistente")
    await sf.habilitar(db, id_usuario=cuenta.id_usuario, id_municipio=cuenta.id_municipio,
                      id_actor=current_user["id_usuario"])
    await registrar_acceso_super_en(
        db, id_usuario=current_user["id_usuario"], accion="segundo_factor", id_municipio=id_municipio,
        metodo=request.method, ruta=request.url.path,
        detalle=f"Restableció y habilitó la vinculación de {cuenta.nombre} ({cuenta.email})",
        ip=get_real_ip(request), user_agent=request.headers.get("user-agent"))
    await db.commit()
    return await _estado_out(db, cuenta)
