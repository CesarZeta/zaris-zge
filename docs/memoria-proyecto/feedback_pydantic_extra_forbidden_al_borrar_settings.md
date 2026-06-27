---
name: feedback_pydantic_extra_forbidden_al_borrar_settings
description: "Antes de borrar vars de un modelo pydantic-settings, verificar si está en extra_forbidden — si lo está, el backend no arranca mientras las env vars viejas sigan en .env/Railway."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4f23e568-0771-4048-bd3c-71fdccc3d3dd
---

Al **borrar campos de un `Settings(BaseSettings)`** (ej. quitar las 6 `SMTP_*` al migrar a Resend), el backend puede **no arrancar** si pydantic-settings está en modo `extra="forbid"`. En el proyecto ZGE esa es la situación: la versión instalada rechaza env vars desconocidas por default (`extra_forbidden`), así que apenas las `SMTP_*` viejas seguían en `.env.local`/Railway pero ya no estaban en el modelo, `Settings()` levantaba `ValidationError: Extra inputs are not permitted` al importar.

**Why:** asumí lo contrario en la planificación ("pydantic ignora extras"). Cazado al hacer `from app.services import email` (que importa `settings`), no en runtime tarde — pero igual habría tumbado prod si lo pusheaba sin verificar, porque las env vars viven en Railway y no se limpian en el mismo instante que el código.

**How to apply:**
- Antes de borrar settings, **importar el módulo con el `.env` real** (`ENV_FILE=.env.local python -c "from app.core.config import settings"`) y ver si explota.
- Si está en `extra_forbidden`, agregar `extra = "ignore"` al `class Config` (o `model_config = SettingsConfigDict(extra="ignore")` en pydantic v2 puro). Esto desacopla la limpieza del modelo de la limpieza de env vars en los N entornos — sino tenés que limpiar `.env.local` Y Railway en el mismo deploy o el backend cae.
- Regla general: borrar un setting es seguro solo si el modelo ignora extras. Verificar, no asumir. Familia de [[feedback_verificar_env_vars_railway]] y [[feedback_set_content_utf8_bom]] (cosas de config que rompen silencioso).
