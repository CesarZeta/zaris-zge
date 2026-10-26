"""
URLs públicas que el backend arma para la UI y los mails (fuente única).

- `url_publica(valor)`: normaliza un setting de URL pública (Mi perfil, portal del
  vecino, app de agentes). Fail-closed: si la env var trae basura -espacios, sin
  esquema http(s), o la línea entera "APP_X=https://..." pegada como valor (caso real
  en Railway 2026-09-27)- devuelve "" y la UI dice "no configurada" en vez de publicar
  un link o QR inválido (memoria feedback_setting_url_publica_default_vacio).
- `url_alta_publica(slug)`: página pública de alta de vecinos del shell (GitHub Pages)
  para el ÚNICO municipio del deploy (mono-tenant, CLAUDE.md §38): dominio + `?m=slug`.
  Sin slug → None (la PWA y las páginas no muestran el link).
"""
import re
from typing import Optional

from app.core.config import settings


def url_publica(valor: Optional[str]) -> str:
    v = (valor or "").strip()
    if not re.match(r"^https?://[^\s]+$", v):
        return ""
    return v.rstrip("/")


def url_portal_vecino() -> str:
    """Portal del Ciudadano (PWA `zaris-vecinos`). "" si no está configurado."""
    return url_publica(settings.APP_VECINOS_FRONTEND_URL)


def url_login_backoffice() -> str:
    """Login del shell (GitHub Pages). La app de agentes lo muestra para vincular la app de
    códigos desde la computadora (IT-01 F3b). "" si FRONTEND_BASE_URL no es una URL válida."""
    base = url_publica(settings.FRONTEND_BASE_URL)
    return f"{base}/frontend/login.html" if base else ""


def url_alta_publica(slug: Optional[str]) -> Optional[str]:
    s = (slug or "").strip().lower()
    if not s:
        return None
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}/frontend/alta-vecino.html?m={s}"
