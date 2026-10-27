"""
ZARIS API — Lo exclusivo del super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md, Tarea 5).

GET  /api/v1/super/municipios                   → todos los municipios, por país, provincia y nombre
                                                  (?codigo_pais=&id_provincia=&estado=)
PUT  /api/v1/super/municipios/{id_municipio}    → editar nombre, subdominio, país, provincia, partido y
                                                  zona horaria (el texto de país y provincia se deriva)
POST /api/v1/super/seleccion                    → el selector del shell eligió un municipio
GET  /api/v1/super/config-global                → parámetros globales (sin las claves vapid_*)
PUT  /api/v1/super/config-global/{id_config}    → editar un parámetro global

No usan `municipio_actual`: operan sobre lo global. Cada edición y cada selección queda en el
registro de accesos. `codigo_corto` (prefijo de los números), `direccion_base` y `activo` no se
editan acá: los da el alta y la baja de F4.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_super_admin
from app.core.config_municipio import leer_configs
from app.core.database import get_db
from app.core.municipio import invalidar_cache_municipios
from app.services.accesos_super import registrar_acceso_super, registrar_acceso_super_en
from app.services.municipios.constantes import ESTADOS

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
