"""
ZARIS API — Lo exclusivo del super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md, Tarea 5).

GET  /api/v1/super/municipios                   → todos los municipios (también los inactivos)
PUT  /api/v1/super/municipios/{id_municipio}    → editar nombre, subdominio, país y zona horaria
POST /api/v1/super/seleccion                    → el selector del shell eligió un municipio
GET  /api/v1/super/config-global                → parámetros globales (sin las claves vapid_*)
PUT  /api/v1/super/config-global/{id_config}    → editar un parámetro global

No usan `municipio_actual`: operan sobre lo global. Cada edición y cada selección queda en el
registro de accesos. `codigo_corto` (prefijo de los números), `direccion_base` y `activo` no se
editan acá: los da el alta y la baja de F4.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_super_admin
from app.core.config_municipio import leer_configs
from app.core.database import get_db
from app.core.municipio import invalidar_cache_municipios
from app.services.accesos_super import registrar_acceso_super, registrar_acceso_super_en

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
    zona_horaria: str
    direccion_base: bool
    activo: bool


class MunicipioSuperUpdate(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=150)
    subdominio: Optional[str] = Field(None, max_length=63, pattern=_SUBDOMINIO)
    codigo_pais: str = Field(..., pattern=r"^[A-Z]{2}$")
    pais: Optional[str] = Field(None, max_length=100)
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
    SELECT id_municipio, nombre, codigo_corto, subdominio, codigo_pais, pais, zona_horaria,
           direccion_base, activo
      FROM municipios"""


@router.get("/municipios", response_model=list[MunicipioSuperOut])
async def listar_municipios(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(text(_SELECT_MUNICIPIO + " ORDER BY id_municipio"))
    return [dict(r._mapping) for r in rows.fetchall()]


@router.put("/municipios/{id_municipio}", response_model=MunicipioSuperOut,
            responses={409: {"description": "El subdominio ya lo usa otro municipio"}})
async def editar_municipio(
    id_municipio: int,
    body: MunicipioSuperUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    sa: dict = Depends(require_super_admin),
):
    antes = (await db.execute(text(_SELECT_MUNICIPIO + " WHERE id_municipio = :id"),
                              {"id": id_municipio})).mappings().first()
    if antes is None:
        raise HTTPException(404, "Municipio no encontrado")
    # La zona se valida contra la base de husos de Postgres: es la que usan las conversiones
    # de fechas (F5b), y no depende de que el servidor tenga tzdata.
    if not await db.scalar(text("SELECT 1 FROM pg_timezone_names WHERE name = :z"), {"z": body.zona_horaria}):
        raise HTTPException(422, "Zona horaria inválida")
    if body.subdominio and await db.scalar(text(
            "SELECT 1 FROM municipios WHERE subdominio = :s AND id_municipio <> :id"),
            {"s": body.subdominio, "id": id_municipio}):
        raise HTTPException(409, "Ese subdominio ya lo usa otro municipio")
    nuevo = (await db.execute(text("""
        UPDATE municipios
           SET nombre = :nombre, subdominio = :subdominio, codigo_pais = :codigo_pais, pais = :pais,
               zona_horaria = :zona_horaria, fecha_modificacion = NOW(), id_usuario_modificacion = :u
         WHERE id_municipio = :id
     RETURNING id_municipio, nombre, codigo_corto, subdominio, codigo_pais, pais, zona_horaria,
               direccion_base, activo"""),
        {**body.model_dump(), "u": sa["id_usuario"], "id": id_municipio})).mappings().first()
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
