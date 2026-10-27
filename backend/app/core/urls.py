"""
URLs públicas que el backend arma para la UI y los mails (fuente única).

- `url_publica(valor)`: normaliza un setting de URL pública. Fail-closed: si la env var trae
  basura -espacios, sin esquema http(s), o la línea entera "APP_X=https://..." pegada como valor
  (caso real en Railway 2026-09-27)- devuelve "" y la UI dice "no configurada" en vez de publicar
  un link o QR inválido (memoria feedback_setting_url_publica_default_vacio).
- `base_app(db, id_municipio, app)` (IT-01 F4+F5): dirección de cada app PARA el municipio de la
  persona. El municipio de las direcciones sin prefijo (y el super administrador, sin municipio)
  usa la setting de siempre; los demás, `https://<subdominio>.<app>.<DOMINIO_BASE>`. Todo link de
  mail, QR o pantalla sale de acá: `tools/barrido_links_mail.py` falla si se arma uno a mano.
- `url_portal_vecino`, `url_login_backoffice`, `url_alta_publica`: atajos sobre `base_app`.
"""
import re
from typing import Literal, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

App = Literal["zge", "vecinos", "agentes", "api"]
_SETTING_DE_APP = {"zge": "FRONTEND_BASE_URL", "vecinos": "APP_VECINOS_FRONTEND_URL",
                   "agentes": "APP_AGENTES_FRONTEND_URL", "api": "API_PUBLIC_BASE_URL"}
_SUBDOMINIO = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_DOMINIO = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")


def url_publica(valor: Optional[str]) -> str:
    v = (valor or "").strip()
    if not re.match(r"^https?://[^\s]+$", v):
        return ""
    return v.rstrip("/")


async def base_app(db: AsyncSession, id_municipio: Optional[int], app: App) -> str:
    """Dirección de `app` para el municipio, sin barra final. "" si no se puede armar (municipio sin
    subdominio, setting o dominio inválidos): el llamador no arma el link."""
    if app == "api" or id_municipio is None:
        return url_publica(getattr(settings, _SETTING_DE_APP[app]))
    row = (await db.execute(text(
        "SELECT subdominio, direccion_base FROM municipios WHERE id_municipio = :m"),
        {"m": id_municipio})).first()
    if row is None:
        return ""
    if row.direccion_base:
        return url_publica(getattr(settings, _SETTING_DE_APP[app]))
    dominio = (settings.DOMINIO_BASE or "").strip().lower()
    if not row.subdominio or not _SUBDOMINIO.match(row.subdominio) or not _DOMINIO.match(dominio):
        return ""
    return f"https://{row.subdominio}.{app}.{dominio}"


async def url_portal_vecino(db: AsyncSession, id_municipio: Optional[int]) -> str:
    """Portal del Ciudadano (PWA `zaris-vecinos`) del municipio. "" si no se puede armar."""
    return await base_app(db, id_municipio, "vecinos")


async def url_login_backoffice(db: AsyncSession, id_municipio: Optional[int]) -> str:
    """Login del shell del municipio (CTA de los mails internos y de la app de agentes). "" si no
    se puede armar."""
    base = await base_app(db, id_municipio, "zge")
    return f"{base}/frontend/login.html" if base else ""


async def url_alta_publica(db: AsyncSession, id_municipio: Optional[int]) -> Optional[str]:
    """Página pública de alta de vecinos del municipio. Con subdominio propio la página resuelve el
    municipio por el origen; el de las direcciones sin prefijo lleva `?m=<codigo_corto>`. None si no
    se puede armar."""
    if id_municipio is None:
        return None
    base = await base_app(db, id_municipio, "zge")
    if not base:
        return None
    row = (await db.execute(text(
        "SELECT codigo_corto, direccion_base FROM municipios WHERE id_municipio = :m"),
        {"m": id_municipio})).first()
    if row is None:
        return None
    if not row.direccion_base:
        return f"{base}/frontend/alta-vecino.html"
    slug = (row.codigo_corto or "").strip().lower()
    return f"{base}/frontend/alta-vecino.html?m={slug}" if slug else None
