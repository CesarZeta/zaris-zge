"""
ZARIS API - Endpoint publico de identidad del municipio.
Lo consume la PWA App Vecinos en la pantalla de login (antes de tener token).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_municipio import leer_configs
from app.core.database import get_db
from app.core.municipio import municipio_de_origen
from app.services.geo_limite import encuadre_municipio
from app.services.municipios.modulos import modulos_habilitados
from app.core.urls import url_alta_publica
from app.schemas.publico_auth import IdentidadMunicipioOut

router = APIRouter(prefix="/api/v1/publico", tags=["publico-identidad"])

CLAVES_BRANDING = [
    "municipio_nombre",
    "municipio_logo_url",
    "municipio_descripcion",
    "municipio_color_primary",
    "municipio_color_accent",
]


@router.get("/identidad-municipio", response_model=IdentidadMunicipioOut)
async def identidad_municipio(
    db: AsyncSession = Depends(get_db),
    id_municipio: int = Depends(municipio_de_origen),
):
    """
    Devuelve nombre, logo, descripcion y colores del municipio.
    Sin auth (la PWA lo lee en la pantalla de login).

    Municipio (IT-01): el de la direccion de la PWA (municipio_de_origen). Sin
    nombre propio cargado, el de la tabla municipios.
    """
    cfg = {k: (v or None) for k, v in (await leer_configs(db, CLAVES_BRANDING, id_municipio)).items()}
    muni = (await db.execute(text(
        "SELECT nombre, codigo_corto FROM municipios WHERE id_municipio = :m"
    ), {"m": id_municipio})).fetchone()

    # URL del alta publica de vecinos: dominio del shell + slug del municipio.
    # Sin slug -> None y la PWA no muestra el link (fail-silent).
    url_alta = await url_alta_publica(db, id_municipio)

    return IdentidadMunicipioOut(
        municipio_nombre=cfg.get("municipio_nombre") or (muni.nombre if muni else None),
        municipio_logo_url=cfg.get("municipio_logo_url"),
        municipio_descripcion=cfg.get("municipio_descripcion"),
        municipio_color_primary=cfg.get("municipio_color_primary"),
        municipio_color_accent=cfg.get("municipio_color_accent"),
        url_alta_publica=url_alta,
        modulos_habilitados=sorted(await modulos_habilitados(db, id_municipio)),
    )


@router.get("/encuadre-mapa", responses={200: {"description": "Recuadro inicial del mapa de la App Vecinos"}})
async def encuadre_mapa(
    db: AsyncSession = Depends(get_db),
    id_municipio: int = Depends(municipio_de_origen),
):
    """Dónde arranca el mapa de la PWA (sur, oeste, norte, este y `origen`) para el municipio de la
    dirección: el mismo encuadre que el backoffice (`/geo/encuadre`). Sin auth: el formulario de
    emergencias también lo usa. Solo el recuadro, sin el contorno: la app no lo dibuja."""
    return await encuadre_municipio(db, id_municipio)
