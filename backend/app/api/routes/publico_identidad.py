"""
ZARIS API - Endpoint publico de identidad del municipio.
Lo consume la PWA App Vecinos en la pantalla de login (antes de tener token).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
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
async def identidad_municipio(db: AsyncSession = Depends(get_db)):
    """
    Devuelve nombre, logo, descripcion y colores del municipio.
    Sin auth (la PWA lo lee en la pantalla de login).

    Multi-tenancy: por ahora cada municipio tiene su deploy Railway propio,
    asi que este endpoint lee la unica config del proyecto. Si en el futuro
    consolidamos a multi-tenant compartido, este endpoint recibira un slug
    por header/query param.
    """
    res = await db.execute(
        text("""
            SELECT clave, valor FROM configuracion_general
             WHERE clave = ANY(:claves) AND activo = TRUE
        """),
        {"claves": CLAVES_BRANDING},
    )
    cfg = {r.clave: (r.valor or None) for r in res.fetchall()}

    # URL del alta publica de vecinos: dominio del shell + slug del UNICO
    # municipio activo del deploy (mono-tenant, §38). Sin slug -> None y la
    # PWA no muestra el link (fail-silent).
    url_alta = None
    slug = await db.scalar(text(
        "SELECT codigo_corto FROM municipios WHERE activo = TRUE ORDER BY id_municipio LIMIT 1"
    ))
    if slug:
        base = settings.FRONTEND_BASE_URL.rstrip("/")
        url_alta = f"{base}/frontend/alta-vecino.html?m={str(slug).strip().lower()}"

    return IdentidadMunicipioOut(
        municipio_nombre=cfg.get("municipio_nombre"),
        municipio_logo_url=cfg.get("municipio_logo_url"),
        municipio_descripcion=cfg.get("municipio_descripcion"),
        municipio_color_primary=cfg.get("municipio_color_primary"),
        municipio_color_accent=cfg.get("municipio_color_accent"),
        url_alta_publica=url_alta,
    )
