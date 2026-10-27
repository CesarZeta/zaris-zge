"""
ZARIS API — Lo exclusivo del super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md, Tarea 5).

GET  /api/v1/super/municipios                   → todos los municipios, por país, provincia y nombre
                                                  (?codigo_pais=&id_provincia=&estado=)
PUT  /api/v1/super/municipios/{id_municipio}    → editar nombre, subdominio, país, provincia, partido y
                                                  zona horaria (el texto de país y provincia se deriva)
POST /api/v1/super/seleccion                    → el selector del shell eligió un municipio
GET  /api/v1/super/administradores             → super administradores (activos primero)
POST /api/v1/super/administradores             → alta por invitación (Tarea 15)
POST /api/v1/super/administradores/{id}/baja   → baja (ni la propia ni la del último activo)
GET  /api/v1/super/config-global                → parámetros globales (sin las claves vapid_*)
PUT  /api/v1/super/config-global/{id_config}    → editar un parámetro global

No usan `municipio_actual`: operan sobre lo global. Cada edición y cada selección queda en el
registro de accesos. `codigo_corto` (prefijo de los números), `direccion_base` y `activo` no se
editan acá: los da el alta y la baja de F4.
"""
import asyncio
import uuid
import re
from typing import Literal, Optional

import httpx

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_super_admin
from app.core.config_municipio import leer_configs
from app.core.database import get_db
from app.core.municipio import invalidar_cache_municipios
from app.services.accesos_super import registrar_acceso_super, registrar_acceso_super_en
from app.core.urls import base_app
from app.services.municipios.alta import CATALOGOS_ETIQUETAS, SIN_CONTORNO, AltaMunicipioIn, dar_de_alta
from app.services.municipios.constantes import DEPENDENCIAS_MODULOS, ESTADOS, MODULOS_FIJOS
from app.services.municipios.invitacion import crear_invitacion
from app.services.municipios.tope import cupo
from app.services.municipios.super_admins import crear_super, dar_de_baja_super, listar_supers
from app.services.municipios.modulos import invalidar_modulos, validar_dependencias

router = APIRouter(prefix="/api/v1/super", tags=["Super administrador"],
                   dependencies=[Depends(require_super_admin)])

_SUBDOMINIO = r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$"
_ENTERO = re.compile(r"^-?[0-9]{1,9}$")


class MunicipioSuperOut(BaseModel):
    id_municipio: int
    nombre: str
    codigo_corto: Optional[str] = None
    subdominio: Optional[str] = None
    codigo_pais: str
    pais: Optional[str] = None
    pais_nombre: Optional[str] = None
    etiqueta_nivel_1: Optional[str] = None
    etiqueta_nivel_2: Optional[str] = None
    id_provincia: Optional[int] = None
    provincia_nombre: Optional[str] = None
    id_partido: Optional[int] = None
    partido_nombre: Optional[str] = None
    zona_horaria: str
    direccion_base: bool
    activo: bool
    estado: str
    fue_produccion: bool
    max_usuarios_activos: Optional[int] = None
    cuentas_activas: int = 0


class MunicipioSuperUpdate(BaseModel):
    """`pais` y `provincia` en texto ya no se aceptan (si llegan se ignoran): se derivan del catálogo."""
    nombre: str = Field(..., min_length=3, max_length=150)
    subdominio: Optional[str] = Field(None, max_length=63, pattern=_SUBDOMINIO)
    codigo_pais: str = Field(..., pattern=r"^[A-Z]{2}$")
    id_provincia: Optional[int] = Field(None, ge=1, le=2_147_483_647)
    id_partido: Optional[int] = Field(None, ge=1, le=2_147_483_647)
    zona_horaria: str = Field(..., min_length=3, max_length=64)


class SeleccionIn(BaseModel):
    id_municipio: int = Field(..., ge=1, le=2_147_483_647)


class SeleccionOut(BaseModel):
    id_municipio: int
    nombre: str
    logo_url: Optional[str] = None


class ConfigGlobalOut(BaseModel):
    id_config: int
    clave: str
    valor: Optional[str] = None
    tipo: Optional[str] = None
    descripcion: Optional[str] = None


class ConfigGlobalUpdate(BaseModel):
    valor: str = Field(..., max_length=2000)


_SELECT_MUNICIPIO = """
    SELECT m.id_municipio, m.nombre, m.codigo_corto, m.subdominio, m.codigo_pais, m.pais, m.zona_horaria,
           m.direccion_base, m.activo, m.estado, m.fue_produccion, m.max_usuarios_activos,
           m.id_provincia, pr.nombre AS provincia_nombre, m.id_partido, pa.nombre AS partido_nombre,
           ps.nombre AS pais_nombre, ps.etiqueta_nivel_1, ps.etiqueta_nivel_2,
           (SELECT count(*) FROM usuarios u
             WHERE u.id_municipio = m.id_municipio AND u.activo AND u.nivel_acceso BETWEEN 1 AND 5
           ) AS cuentas_activas
      FROM municipios m
      LEFT JOIN provincias pr ON pr.id_provincia = m.id_provincia
      LEFT JOIN partidos pa ON pa.id_partido = m.id_partido
      LEFT JOIN paises ps ON ps.codigo_pais = m.codigo_pais"""

_ORDEN_MUNICIPIOS = " ORDER BY ps.nombre NULLS LAST, pr.nombre NULLS LAST, m.nombre, m.id_municipio"


@router.get("/municipios", response_model=list[MunicipioSuperOut])
async def listar_municipios(
    codigo_pais: Optional[str] = Query(None, pattern=r"^[A-Z]{2}$"),
    id_provincia: Optional[int] = Query(None, ge=1, le=2_147_483_647),
    estado: Optional[str] = Query(None, pattern="^(" + "|".join(ESTADOS) + ")$"),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(text(
        _SELECT_MUNICIPIO
        + " WHERE (CAST(:pais AS text) IS NULL OR m.codigo_pais = :pais)"
          " AND (CAST(:prov AS integer) IS NULL OR m.id_provincia = :prov)"
          " AND (CAST(:estado AS text) IS NULL OR m.estado = :estado)"
        + _ORDEN_MUNICIPIOS), {"pais": codigo_pais, "prov": id_provincia, "estado": estado})
    return [dict(r._mapping) for r in rows.fetchall()]


@router.get("/alta/opciones")
async def opciones_alta(db: AsyncSession = Depends(get_db)):
    """Lo que el asistente de alta ofrece elegir: grupos de catálogos del modelo y módulos (sin
    «Municipios», que es del super y no de un municipio)."""
    mods = await db.execute(text(
        "SELECT modulo_codigo, nombre FROM modulos WHERE activo AND min_nivel_acceso >= 1 ORDER BY nombre"))
    return {
        "catalogos": [{"codigo": c, "nombre": n} for c, n in CATALOGOS_ETIQUETAS.items()],
        "modulos": [{"codigo": r.modulo_codigo, "nombre": r.nombre, "fijo": r.modulo_codigo in MODULOS_FIJOS,
                     "dependencias": sorted(DEPENDENCIAS_MODULOS.get(r.modulo_codigo, ()))} for r in mods],
    }


@router.get("/municipios/{id_municipio}", responses={404: {"description": "Municipio inexistente"}})
async def ficha_municipio(id_municipio: int = Path(..., ge=1, le=2_147_483_647),
                          db: AsyncSession = Depends(get_db)):
    """Ficha: el municipio, sus módulos, sus administradores (con la invitación pendiente), el cupo de
    cuentas y las advertencias del alta que siguen vigentes."""
    m = (await db.execute(text(_SELECT_MUNICIPIO + " WHERE m.id_municipio = :m"), {"m": id_municipio})).first()
    if m is None:
        raise HTTPException(404, "Municipio no encontrado")
    mods = await db.execute(text("""
        SELECT mo.modulo_codigo AS codigo, mo.nombre, COALESCE(mm.habilitado, FALSE) AS habilitado
          FROM modulos mo
          LEFT JOIN municipio_modulo mm ON mm.modulo_codigo = mo.modulo_codigo AND mm.id_municipio = :m
         WHERE mo.activo AND mo.min_nivel_acceso >= 1
         ORDER BY mo.nombre"""), {"m": id_municipio})
    admins = await db.execute(text("""
        SELECT u.id_usuario, u.nombre, u.email, u.activo,
               EXISTS (SELECT 1 FROM usuario_invitacion i WHERE i.id_usuario = u.id_usuario AND i.activo
                          AND i.usada_en IS NULL AND i.vence_en > NOW()) AS invitacion_pendiente
          FROM usuarios u
         WHERE u.id_municipio = :m AND u.nivel_acceso = 1
         ORDER BY u.activo DESC, u.nombre"""), {"m": id_municipio})
    geo = await leer_configs(db, ["geo_limite_geojson", "geo_bbox_centro_lat"], id_municipio)
    advertencias = [] if m.direccion_base or any((v or "").strip() for v in geo.values()) else [SIN_CONTORNO]
    return {
        "municipio": dict(m._mapping),
        "modulos": [dict({**r._mapping, "fijo": r.codigo in MODULOS_FIJOS,
                          "dependencias": sorted(DEPENDENCIAS_MODULOS.get(r.codigo, ()))}) for r in mods],
        "administradores": [dict(r._mapping) for r in admins],
        "cupo": await cupo(db, id_municipio),
        "advertencias": advertencias,
    }


class TopeIn(BaseModel):
    maximo: Optional[int] = Field(None, ge=1, le=100_000)


@router.put("/municipios/{id_municipio}/tope", response_model=MunicipioSuperOut,
            responses={404: {"description": "Municipio inexistente"}})
async def cambiar_tope(id_municipio: int, body: TopeIn, request: Request, db: AsyncSession = Depends(get_db),
                       sa: dict = Depends(require_super_admin)):
    """Tope de cuentas internas activas (null = sin tope). Bajarlo por debajo de las activas no
    desactiva a nadie: solo impide crear o reactivar (spec §4.5)."""
    ok = await db.scalar(text("UPDATE municipios SET max_usuarios_activos = :t WHERE id_municipio = :m "
                              "RETURNING id_municipio"), {"t": body.maximo, "m": id_municipio})
    if ok is None:
        raise HTTPException(404, "Municipio no encontrado")
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="municipio_editar",
                                    id_municipio=id_municipio, detalle=f"tope de cuentas: {body.maximo or 'sin tope'}",
                                    **_registro(request))
    await db.commit()
    return dict((await db.execute(text(_SELECT_MUNICIPIO + " WHERE m.id_municipio = :m"),
                                  {"m": id_municipio})).one()._mapping)


async def _validar_ubicacion(db: AsyncSession, body: "MunicipioSuperUpdate", estado: str) -> tuple[str, Optional[str]]:
    """País del catálogo, provincia de ese país y partido de esa provincia (422 si no). Devuelve el
    texto derivado (país, provincia) que se guarda en las columnas viejas."""
    pais = await db.scalar(text("SELECT nombre FROM paises WHERE codigo_pais = :p AND activo"),
                           {"p": body.codigo_pais})
    if pais is None:
        raise HTTPException(422, "País inexistente")
    provincia = None
    if body.id_provincia is not None:
        provincia = await db.scalar(text(
            "SELECT nombre FROM provincias WHERE id_provincia = :i AND codigo_pais = :p"),
            {"i": body.id_provincia, "p": body.codigo_pais})
        if provincia is None:
            raise HTTPException(422, "La provincia no es del país del municipio")
    elif estado not in ("baja", "modelo"):
        raise HTTPException(422, "Elegí la provincia del municipio")
    if body.id_partido is not None and not await db.scalar(text(
            "SELECT 1 FROM partidos WHERE id_partido = :i AND id_provincia = :p"),
            {"i": body.id_partido, "p": body.id_provincia}):
        raise HTTPException(422, "El partido no es de la provincia del municipio")
    return pais, provincia


@router.put("/municipios/{id_municipio}", response_model=MunicipioSuperOut,
            responses={409: {"description": "El subdominio ya lo usa otro municipio"}})
async def editar_municipio(
    id_municipio: int,
    body: MunicipioSuperUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    antes = (await db.execute(text(_SELECT_MUNICIPIO + " WHERE m.id_municipio = :id"),
                              {"id": id_municipio})).mappings().first()
    if antes is None:
        raise HTTPException(404, "Municipio no encontrado")
    pais, provincia = await _validar_ubicacion(db, body, antes["estado"])
    # La zona se valida contra la base de husos de Postgres: es la que usan las conversiones
    # de fechas (F5b), y no depende de que el servidor tenga tzdata.
    if not await db.scalar(text("SELECT 1 FROM pg_timezone_names WHERE name = :z"), {"z": body.zona_horaria}):
        raise HTTPException(422, "Zona horaria inválida")
    if body.subdominio and await db.scalar(text(
            "SELECT 1 FROM municipios WHERE subdominio = :s AND id_municipio <> :id"),
            {"s": body.subdominio, "id": id_municipio}):
        raise HTTPException(409, "Ese subdominio ya lo usa otro municipio")
    await db.execute(text("""
        UPDATE municipios
           SET nombre = :nombre, subdominio = :subdominio, codigo_pais = :codigo_pais, pais = :pais,
               id_provincia = :id_provincia, provincia = :provincia, id_partido = :id_partido,
               zona_horaria = :zona_horaria, fecha_modificacion = NOW(), id_usuario_modificacion = :u
         WHERE id_municipio = :id"""),
        {**body.model_dump(), "pais": pais, "provincia": provincia, "u": sa["id_usuario"], "id": id_municipio})
    nuevo = (await db.execute(text(_SELECT_MUNICIPIO + " WHERE m.id_municipio = :id"),
                              {"id": id_municipio})).mappings().first()
    cambios = "; ".join(f"{k}: {antes[k]} → {nuevo[k]}" for k in body.model_dump() if antes[k] != nuevo[k])
    # El registro va en la misma transacción: si no se puede registrar, el cambio no queda.
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="municipio_editar",
                                    id_municipio=id_municipio, metodo=request.method, ruta=request.url.path,
                                    detalle=cambios or "sin cambios",
                                    user_agent=request.headers.get("user-agent"))
    await db.commit()
    invalidar_cache_municipios()
    return dict(nuevo)


@router.post("/seleccion", response_model=SeleccionOut)
async def seleccionar_municipio(
    body: SeleccionIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    row = (await db.execute(text("SELECT nombre FROM municipios WHERE id_municipio = :id AND activo = TRUE"),
                            {"id": body.id_municipio})).fetchone()
    if row is None:
        raise HTTPException(404, "Municipio no encontrado")
    cfg = await leer_configs(db, ["municipio_nombre", "municipio_logo_url"], body.id_municipio)
    await registrar_acceso_super(id_usuario=sa["id_usuario"], accion="seleccion",
                                 id_municipio=body.id_municipio, metodo=request.method, ruta=request.url.path,
                                 user_agent=request.headers.get("user-agent"))
    return SeleccionOut(id_municipio=body.id_municipio, nombre=cfg.get("municipio_nombre") or row.nombre,
                        logo_url=cfg.get("municipio_logo_url") or None)


_WHERE_GLOBAL = "id_municipio IS NULL AND activo = TRUE AND clave NOT LIKE 'vapid\\_%'"


@router.get("/config-global", response_model=list[ConfigGlobalOut])
async def listar_config_global(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(text(
        f"SELECT id_config, clave, valor, tipo, descripcion FROM configuracion_general "
        f"WHERE {_WHERE_GLOBAL} ORDER BY clave"))
    return [dict(r._mapping) for r in rows.fetchall()]


@router.put("/config-global/{id_config}", response_model=ConfigGlobalOut)
async def editar_config_global(
    id_config: int,
    body: ConfigGlobalUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    fila = (await db.execute(text(
        f"SELECT id_config, clave, valor, tipo FROM configuracion_general WHERE id_config = :id AND {_WHERE_GLOBAL}"),
        {"id": id_config})).fetchone()
    if fila is None:
        raise HTTPException(404, "Parámetro global no encontrado")
    valor = body.valor.strip()
    if fila.tipo == "integer" and not _ENTERO.match(valor):
        raise HTTPException(422, "El valor tiene que ser un número entero")
    if fila.tipo == "boolean" and valor not in ("true", "false"):
        raise HTTPException(422, "El valor tiene que ser true o false")
    nuevo = (await db.execute(text("""
        UPDATE configuracion_general SET valor = :v, fecha_modificacion = NOW()
         WHERE id_config = :id
     RETURNING id_config, clave, valor, tipo, descripcion"""), {"v": valor, "id": id_config})).mappings().first()
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="config_global", id_municipio=None,
                                    metodo=request.method, ruta=request.url.path,
                                    detalle=f"{fila.clave}: {fila.valor} → {valor}",
                                    user_agent=request.headers.get("user-agent"))
    await db.commit()
    return dict(nuevo)



# ── Alta, estado, módulos y dominios de un municipio (IT-01 F4+F5, Tarea 11) ─────────────────────

def _registro(request: Request) -> dict:
    return {"metodo": request.method, "ruta": request.url.path, "user_agent": request.headers.get("user-agent")}


@router.post("/municipios", status_code=201,
             responses={409: {"description": "Subdominio o código corto en uso"},
                        422: {"description": "Datos inválidos, país no habilitado o módulos sin sus dependencias"}})
async def alta_municipio(
    body: AltaMunicipioIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    """Alta completa en una transacción (spec §4.4). Si algo falla, no queda nada."""
    res = await dar_de_alta(db, body, id_super=sa["id_usuario"], background_tasks=background_tasks)
    await registrar_acceso_super_en(
        db, id_usuario=sa["id_usuario"], accion="municipio_alta", id_municipio=res["id_municipio"],
        detalle=f"alta de {body.nombre} ({body.subdominio}, {body.codigo_corto})", **_registro(request))
    await db.commit()
    invalidar_cache_municipios()
    invalidar_modulos(res["id_municipio"])
    return res


class EstadoIn(BaseModel):
    estado: Literal["produccion", "baja", "reactivar", "puesta_en_marcha", "demo"]
    confirmacion: Optional[str] = Field(None, max_length=150)


@router.post("/municipios/{id_municipio}/estado", response_model=MunicipioSuperOut,
             responses={422: {"description": "Transición no permitida o confirmación incorrecta"}})
async def cambiar_estado(
    id_municipio: int,
    body: EstadoIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    """puesta_en_marcha → produccion (escribiendo el nombre; sin vuelta atrás) · cualquiera → baja
    (salvo el municipio de las direcciones sin prefijo) · baja → reactivar (vuelve al estado anterior).
    demo y modelo no se asignan desde la API."""
    actual = (await db.execute(text(
        "SELECT nombre, estado, estado_antes_baja, direccion_base FROM municipios WHERE id_municipio = :m FOR UPDATE"),
        {"m": id_municipio})).first()
    if actual is None:
        raise HTTPException(404, "Municipio no encontrado")
    if body.estado == "produccion":
        if actual.estado != "puesta_en_marcha":
            raise HTTPException(422, "Solo un municipio en puesta en marcha pasa a producción")
        if (body.confirmacion or "").strip() != actual.nombre:
            raise HTTPException(422, "Escribí el nombre del municipio para confirmar.")
        nuevo = "produccion"
    elif body.estado == "baja":
        if actual.estado == "baja":
            raise HTTPException(422, "El municipio ya está de baja")
        if actual.direccion_base:
            raise HTTPException(422, "El municipio de las direcciones sin prefijo no se da de baja")
        nuevo = "baja"
    elif body.estado == "reactivar":
        if actual.estado != "baja":
            raise HTTPException(422, "Solo se reactiva un municipio de baja")
        nuevo = actual.estado_antes_baja or "puesta_en_marcha"
    else:
        raise HTTPException(422, f"No se puede pasar a {body.estado} desde la API")
    await db.execute(text("""
        UPDATE municipios SET estado = :e, fecha_modificacion = NOW(), id_usuario_modificacion = :u
         WHERE id_municipio = :m"""), {"e": nuevo, "u": sa["id_usuario"], "m": id_municipio})
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="municipio_estado",
                                    id_municipio=id_municipio, detalle=f"{actual.estado} → {nuevo}",
                                    **_registro(request))
    await db.commit()
    invalidar_cache_municipios()
    invalidar_modulos(id_municipio)
    return dict((await db.execute(text(_SELECT_MUNICIPIO + " WHERE m.id_municipio = :id"),
                                  {"id": id_municipio})).mappings().first())


class ModuloEstadoIn(BaseModel):
    codigo: str = Field(..., max_length=50)
    habilitado: bool


class ModulosIn(BaseModel):
    modulos: list[ModuloEstadoIn]


@router.put("/municipios/{id_municipio}/modulos",
            responses={422: {"description": "Dependencia entre módulos o módulo fijo"}})
async def cambiar_modulos(
    id_municipio: int,
    body: ModulosIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    if not await db.scalar(text("SELECT 1 FROM municipios WHERE id_municipio = :m"), {"m": id_municipio}):
        raise HTTPException(404, "Municipio no encontrado")
    catalogo = {r.modulo_codigo: r.min_nivel_acceso for r in (await db.execute(text(
        "SELECT modulo_codigo, min_nivel_acceso FROM modulos WHERE activo"))).all()}
    actuales = {r[0] for r in (await db.execute(text(
        "SELECT modulo_codigo FROM municipio_modulo WHERE id_municipio = :m AND habilitado"),
        {"m": id_municipio})).all()}
    nuevos = set(actuales)
    for mod in body.modulos:
        if mod.codigo not in catalogo:
            raise HTTPException(422, f"Módulo desconocido: {mod.codigo}")
        if not mod.habilitado and mod.codigo in MODULOS_FIJOS:
            raise HTTPException(422, "Ese módulo no se puede deshabilitar: el municipio no funciona sin él.")
        if mod.habilitado:
            nuevos.add(mod.codigo)
        else:
            nuevos.discard(mod.codigo)
    await validar_dependencias(nuevos)
    for mod in body.modulos:
        await db.execute(text("""
            INSERT INTO municipio_modulo (id_municipio, modulo_codigo, habilitado, min_nivel_acceso,
                                          id_usuario_alta, id_usuario_modificacion)
            VALUES (:m, :c, :h, :n, :u, :u)
            ON CONFLICT (id_municipio, modulo_codigo) DO UPDATE
               SET habilitado = EXCLUDED.habilitado, fecha_modificacion = NOW(),
                   id_usuario_modificacion = EXCLUDED.id_usuario_modificacion"""),
            {"m": id_municipio, "c": mod.codigo, "h": mod.habilitado, "n": catalogo[mod.codigo],
             "u": sa["id_usuario"]})
    await registrar_acceso_super_en(
        db, id_usuario=sa["id_usuario"], accion="municipio_modulos", id_municipio=id_municipio,
        detalle="; ".join(f"{m.codigo}={'sí' if m.habilitado else 'no'}" for m in body.modulos), **_registro(request))
    await db.commit()
    invalidar_modulos(id_municipio)
    return {"habilitados": sorted(nuevos)}


async def _hosts(db: AsyncSession, id_municipio: int) -> dict[str, str]:
    hosts = {}
    for app_ in ("zge", "vecinos", "agentes"):
        base = await base_app(db, id_municipio, app_)
        hosts[app_] = base.split("://", 1)[-1] if base else ""
    return hosts


@router.get("/municipios/{id_municipio}/dominios")
async def verificar_dominios(id_municipio: int, db: AsyncSession = Depends(get_db)):
    """Por cada app: el host, si el DNS resuelve y el código del GET por HTTPS. Sin credenciales de
    Cloudflare: los dominios los crea tools/dominios_municipio.py."""
    if not await db.scalar(text("SELECT 1 FROM municipios WHERE id_municipio = :m"), {"m": id_municipio}):
        raise HTTPException(404, "Municipio no encontrado")
    salida = []
    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as cliente:
        for app_, host in (await _hosts(db, id_municipio)).items():
            dns, https = False, None
            if host:
                try:
                    await asyncio.get_running_loop().getaddrinfo(host, 443)
                    dns = True
                except OSError:
                    dns = False
                if dns:
                    try:
                        https = (await cliente.get(f"https://{host}/")).status_code
                    except httpx.HTTPError:
                        https = None
            salida.append({"app": app_, "host": host, "dns": dns, "https": https})
    return salida


@router.post("/municipios/{id_municipio}/prueba")
async def prueba_puesta_en_marcha(id_municipio: int, db: AsyncSession = Depends(get_db)):
    """Chequeos de la puesta en marcha (spec §4.4), sin loguear a nadie."""
    from app.main import app as aplicacion
    from app.services.municipios.modulos import modulos_habilitados
    if not await db.scalar(text("SELECT 1 FROM municipios WHERE id_municipio = :m"), {"m": id_municipio}):
        raise HTTPException(404, "Municipio no encontrado")
    hosts = await _hosts(db, id_municipio)
    chequeos = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=aplicacion), base_url="http://interno") as c:
        for app_ in ("zge", "vecinos", "agentes"):
            if not hosts[app_]:
                chequeos.append({"nombre": f"identidad pública ({app_})", "ok": False, "detalle": "sin dirección"})
                continue
            r = await c.get("/api/v1/publico/identidad-municipio", headers={"Origin": f"https://{hosts[app_]}"})
            chequeos.append({"nombre": f"identidad pública ({hosts[app_]})", "ok": r.status_code == 200,
                             "detalle": str(r.status_code)})
        r = await c.post("/api/v1/auth/login", json={"identificador": "prueba@prueba.invalido", "password": "x" * 8},
                         headers={"Origin": f"https://{hosts['zge']}"} if hosts["zge"] else {})
        chequeos.append({"nombre": "el login resuelve el municipio por su dirección", "ok": r.status_code == 401,
                         "detalle": f"{r.status_code} (401 = resolvió el municipio; 404 = no)"})
    vigente = await db.scalar(text("""
        SELECT count(*) FROM usuario_invitacion i JOIN usuarios u ON u.id_usuario = i.id_usuario
         WHERE u.id_municipio = :m AND u.nivel_acceso = 1 AND i.activo AND i.usada_en IS NULL AND i.vence_en > NOW()"""),
        {"m": id_municipio})
    usada = await db.scalar(text("""
        SELECT count(*) FROM usuario_invitacion i JOIN usuarios u ON u.id_usuario = i.id_usuario
         WHERE u.id_municipio = :m AND i.usada_en IS NOT NULL"""), {"m": id_municipio})
    chequeos.append({"nombre": "invitación del administrador", "ok": bool(vigente or usada),
                     "detalle": "aceptada" if usada else ("vigente" if vigente else "sin invitación vigente")})
    base = await base_app(db, id_municipio, "zge")
    pagina = None
    if base:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                pagina = (await c.get(f"{base}/frontend/invitacion.html", follow_redirects=True)).status_code
        except httpx.HTTPError:
            pagina = None
    chequeos.append({"nombre": "la página de la invitación responde", "ok": pagina == 200, "detalle": str(pagina)})
    hab = sorted(await modulos_habilitados(db, id_municipio))
    chequeos.append({"nombre": "módulos habilitados", "ok": bool(hab), "detalle": ", ".join(hab)})
    return chequeos


@router.post("/usuarios/{id_usuario}/invitacion",
             responses={404: {"description": "La cuenta no existe o no es administrador"}})
async def reenviar_invitacion(
    id_usuario: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    """Reenvía la invitación del primer administrador de un municipio (nivel 1) o de un super (nivel 0).
    Desactiva las anteriores."""
    u = (await db.execute(text(
        "SELECT id_municipio, nivel_acceso FROM usuarios WHERE id_usuario = :u AND activo"), {"u": id_usuario})).first()
    if u is None or u.nivel_acceso not in (0, 1):
        raise HTTPException(404, "Cuenta no encontrada")
    await crear_invitacion(db, id_usuario=id_usuario, id_municipio=u.id_municipio, id_actor=sa["id_usuario"],
                           background_tasks=background_tasks)
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"],
                                    accion="super_alta" if u.nivel_acceso == 0 else "municipio_alta",
                                    id_municipio=u.id_municipio, detalle=f"reenvío de invitación a {id_usuario}",
                                    **_registro(request))
    await db.commit()
    return {"enviada": True}


# ── Super administradores (IT-01 F4+F5, Tarea 15) ──────────────────────────────────────────────

class SuperAdminIn(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=70)
    apellido: str = Field(..., min_length=1, max_length=70)
    email: str = Field(..., max_length=150)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        from app.schemas.buc import _validar_email_fmt
        return _validar_email_fmt(v.strip())


@router.get("/administradores")
async def listar_administradores(db: AsyncSession = Depends(get_db)):
    return await listar_supers(db)


@router.post("/administradores", status_code=201,
             responses={409: {"description": "El email ya es de otra cuenta"}})
async def alta_administrador(
    body: SuperAdminIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    """Cuenta de nivel 0 sin municipio; elige su clave con la invitación (el mail sale como ZARIS)."""
    nuevo = await crear_super(db, nombre=body.nombre, apellido=body.apellido, email=body.email,
                              id_actor=sa["id_usuario"], background_tasks=background_tasks)
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="super_alta", id_municipio=None,
                                    detalle=f"alta del super {nuevo} ({body.email.strip().lower()})",
                                    **_registro(request))
    await db.commit()
    return {"id_usuario": nuevo}


@router.post("/administradores/{id_usuario}/baja",
             responses={404: {"description": "No es un super administrador"},
                        409: {"description": "Baja propia o del último super activo"}})
async def baja_administrador(
    id_usuario: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    await dar_de_baja_super(db, id_usuario=id_usuario, id_actor=sa["id_usuario"])
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="super_baja", id_municipio=None,
                                    detalle=f"baja del super {id_usuario}", **_registro(request))
    await db.commit()
    return {"baja": True}


# ── Exportación y vaciado (IT-01 F4+F5, Tarea 16) ─────────────────────────────────────────────

class GruposIn(BaseModel):
    grupos: list[str] = Field(..., min_length=1, max_length=4)


class VaciadoIn(GruposIn):
    confirmacion: str = Field(..., max_length=150)


async def _existe(db: AsyncSession, id_municipio: int) -> None:
    if not await db.scalar(text("SELECT 1 FROM municipios WHERE id_municipio = :m"), {"m": id_municipio}):
        raise HTTPException(404, "Municipio no encontrado")


@router.get("/tareas/{id_tarea}")
async def estado_tarea(id_tarea: uuid.UUID, db: AsyncSession = Depends(get_db)):
    t = (await db.execute(text("""
        SELECT id_tarea, id_municipio, tipo, estado, detalle, archivo, vence_en, fecha_alta, fecha_modificacion
          FROM municipio_tarea WHERE id_tarea = :t"""), {"t": id_tarea})).first()
    if t is None:
        raise HTTPException(404, "Tarea no encontrada")
    return dict(t._mapping)


@router.get("/municipios/{id_municipio}/exportaciones")
async def listar_exportaciones(id_municipio: int, db: AsyncSession = Depends(get_db)):
    """Exportaciones vigentes (no vencidas ni purgadas), la más nueva primero."""
    await _existe(db, id_municipio)
    rows = await db.execute(text("""
        SELECT id_tarea, estado, detalle, archivo, vence_en, fecha_alta FROM municipio_tarea
         WHERE id_municipio = :m AND tipo = 'exportacion'
           AND (estado IN ('pendiente', 'corriendo') OR (estado = 'ok' AND archivo IS NOT NULL AND vence_en > NOW()))
         ORDER BY fecha_alta DESC"""), {"m": id_municipio})
    return [dict(r._mapping) for r in rows]


@router.post("/municipios/{id_municipio}/exportaciones", status_code=202)
async def pedir_exportacion(id_municipio: int, request: Request, background_tasks: BackgroundTasks,
                            db: AsyncSession = Depends(get_db), sa: dict = Depends(require_super_admin)):
    from app.services.municipios.exportacion import crear_tarea, ejecutar_exportacion
    await _existe(db, id_municipio)
    id_tarea = await crear_tarea(db, id_municipio, "exportacion", sa["id_usuario"])
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="exportacion", id_municipio=id_municipio,
                                    detalle=f"pedido de exportación {id_tarea}", **_registro(request))
    await db.commit()
    background_tasks.add_task(ejecutar_exportacion, id_tarea, id_municipio)
    return {"id_tarea": id_tarea}


@router.get("/municipios/{id_municipio}/exportaciones/{id_tarea}/descarga",
            responses={404: {"description": "La exportación no existe, venció o no es de ese municipio"}})
async def descargar_exportacion(id_municipio: int, id_tarea: uuid.UUID, request: Request,
                                db: AsyncSession = Depends(get_db), sa: dict = Depends(require_super_admin)):
    """URL firmada de 10 minutos. Cada descarga queda en el registro del super."""
    from app.core import storage
    from app.services.municipios.exportacion import BUCKET
    archivo = await db.scalar(text("""
        SELECT archivo FROM municipio_tarea WHERE id_tarea = :t AND id_municipio = :m AND tipo = 'exportacion'
           AND estado = 'ok' AND archivo IS NOT NULL AND vence_en > NOW()"""), {"t": id_tarea, "m": id_municipio})
    if archivo is None:
        raise HTTPException(404, "Exportación no encontrada")
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="exportacion", id_municipio=id_municipio,
                                    detalle=f"descarga de la exportación {id_tarea}", **_registro(request))
    await db.commit()
    return {"url": await storage.crear_signed_download_url(archivo, ttl_sec=600, bucket=BUCKET)}


@router.post("/municipios/{id_municipio}/vaciado/plan",
             responses={409: {"description": "El municipio está o estuvo en producción"}})
async def plan_de_vaciado(id_municipio: int, body: GruposIn, db: AsyncSession = Depends(get_db)):
    """Qué se borraría y qué se desvincularía, tabla por tabla, sin escribir nada."""
    from app.services.municipios.vaciado import calcular, resumen, validar
    await validar(db, id_municipio, set(body.grupos))
    return resumen(await calcular(db, id_municipio, set(body.grupos)))


@router.post("/municipios/{id_municipio}/vaciado", status_code=202,
             responses={409: {"description": "En producción o con otro vaciado en curso"},
                        422: {"description": "Grupos inválidos o confirmación incorrecta"}})
async def pedir_vaciado(id_municipio: int, body: VaciadoIn, request: Request, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db), sa: dict = Depends(require_super_admin)):
    """Exporta y, si la exportación terminó bien, vacía (en segundo plano: el estado se consulta en
    /super/tareas/{id})."""
    from app.services.municipios.exportacion import crear_tarea
    from app.services.municipios.vaciado import EN_CURSO, ejecutar_vaciado, validar
    await db.execute(text("SELECT pg_advisory_xact_lock(:m)"), {"m": id_municipio})
    await validar(db, id_municipio, set(body.grupos), body.confirmacion)
    if await db.scalar(text("""
        SELECT 1 FROM municipio_tarea WHERE id_municipio = :m AND tipo = 'vaciado'
           AND estado IN ('pendiente', 'corriendo') AND fecha_modificacion > NOW() - interval '1 hour'"""),
            {"m": id_municipio}):
        raise HTTPException(409, EN_CURSO)
    id_tarea = await crear_tarea(db, id_municipio, "vaciado", sa["id_usuario"], {"grupos": sorted(body.grupos)})
    await registrar_acceso_super_en(db, id_usuario=sa["id_usuario"], accion="vaciado", id_municipio=id_municipio,
                                    detalle=f"pedido de vaciado {id_tarea}: {', '.join(sorted(body.grupos))}",
                                    **_registro(request))
    await db.commit()
    background_tasks.add_task(ejecutar_vaciado, id_tarea, id_municipio, set(body.grupos), sa["id_usuario"])
    return {"id_tarea": id_tarea}
