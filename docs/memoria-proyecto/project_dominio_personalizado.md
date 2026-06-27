---
name: project_dominio_personalizado
description: Configuración del dominio personalizado zge.zaris.com.ar para el frontend de ZARIS en GitHub Pages
metadata: 
  node_type: memory
  type: project
  originSessionId: 8ad34d51-7856-4388-bdbe-599e60f94ccb
---

# Dominio personalizado: zge.zaris.com.ar

**Configurado 2026-05-16.** El frontend de ZARIS (GitHub Pages) ahora es accesible desde `https://zge.zaris.com.ar` además de la URL original de GH Pages.

## DNS (Cloudflare)

- Registro CNAME: `zge` → `cesarzeta.github.io`, Proxy: **DNS only** (nube gris).
- La nube naranja (Proxied) rompe la verificación de certificado SSL de GitHub Pages — siempre DNS only.

## GitHub Pages

- Custom domain: `zge.zaris.com.ar` configurado en Settings → Pages.
- Enforce HTTPS: activar cuando GitHub emita el certificado (puede tardar hasta 1h tras configurar el dominio).
- GitHub crea automáticamente un archivo `CNAME` en la raíz del repo.

## Cambios en el código (commit `18b7e67`)

- **`web-app/vite.config.ts`**: `base` cambiado de `/zaris-zge/web-app/dist/` a `/web-app/dist/`.
- **`web-app/index.html`**: guard de redirect actualizado para detectar `/web-app/dist/` sin depender del subpath `/zaris-zge/`. Soporta ambos (dominio propio + legacy GH Pages por compat).
- **`backend/app/main.py`** (commit `3e781eb`): agregados `http://zge.zaris.com.ar` y `https://zge.zaris.com.ar` a `allow_origins` de CORS.

**Why:** sin actualizar el `base` de Vite, los assets (JS/CSS/fonts) daban 404 porque el bundle buscaba `/zaris-zge/web-app/dist/assets/...` pero el dominio propio sirve desde la raíz. Sin el CORS, el login fallaba silenciosamente con "No se pudo conectar con el servidor".

**How to apply:** al agregar un nuevo origen al CORS, agregar siempre tanto `http://` como `https://` del dominio. Si el dominio cambia nuevamente, actualizar `vite.config.ts` base + guard de `web-app/index.html` + CORS en `main.py` + rebuild del dist.

## URLs vigentes

| Superficie | URL |
|---|---|
| Frontend (prod, dominio propio) | `https://zge.zaris.com.ar` |
| Frontend (prod, GH Pages legacy) | `https://cesarzeta.github.io/zaris-zge/index.html` |
| Login | `https://zge.zaris.com.ar/frontend/login.html` |
| API (Railway) | `https://zaris-api-production-bf0b.up.railway.app` |

## Lo que NO funciona

- `www.zge.zaris.com.ar` — no hay registro DNS para ese subdominio de subdominio.
