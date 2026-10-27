# Cloudflare Pages — configuración de los tres frontends

IT-01 F4+F5. El shell (`zge.`), la app del vecino (`vecinos.`) y la app de agentes (`agentes.`) se publican en Cloudflare Pages, conectados a sus repos de GitHub: cada push a `main` buildea y publica; cada push a otra rama publica una vista previa en `<rama>.<proyecto>.pages.dev`. Este documento no lleva credenciales.

## Proyectos

Los nombres son fijos: el CORS del backend (`ORIGEN_ZARIS_REGEX` en `backend/app/main.py`) y `tools/dominios_municipio.py` los usan.

| Proyecto | Repo | Rama de producción | Comando de build | Directorio de salida |
|---|---|---|---|---|
| `zaris-zge` | `CesarZeta/zaris-zge` | `main` | `bash tools/cloudflare_pages_build.sh` | `_site` |
| `zaris-vecinos` | `CesarZeta/zaris-vecinos` | `main` | `pnpm build` | `dist` |
| `zaris-agentes` | `CesarZeta/zaris-agentes` | `main` | `pnpm build` | `dist` |

En los tres: «Framework preset» = None, «Root directory» vacío.

**Variables de entorno** (Settings → Variables and Secrets, en Production y Preview):

| Proyecto | Variables |
|---|---|
| `zaris-zge` | `NODE_VERSION=22`, `PNPM_VERSION=10.33.2` |
| `zaris-vecinos`, `zaris-agentes` | `NODE_VERSION=22`, `PNPM_VERSION=9.0.0` (el `packageManager` de su `package.json`), `VITE_API_URL=https://zaris-api-production-bf0b.up.railway.app`, `VITE_APP_VERSION=0.1.0` |

La imagen de build v3 trae pnpm, pero no toma la versión del lockfile: se fija con `PNPM_VERSION` ([build image](https://developers.cloudflare.com/pages/configuration/build-image/)). La API del shell no necesita variable: sale de `web-app/.env.production`.

## Qué publica cada proyecto

- **Shell:** `tools/cloudflare_pages_build.sh` buildea `web-app` y arma `_site/` con `index.html`, `frontend/`, `design-system/`, `docs/`, `landing/` y `web-app/dist/`, en las mismas rutas que servía GitHub Pages. El resto del repo (backend, sql, planes, CSV) ya no se publica. Agrega un `404.html` en la raíz: sin él, Pages trata el sitio como SPA y una ruta inexistente serviría el shell.
- **Apps:** `public/_headers` replica los headers de `/sw.js` que tenía `vercel.json` (`Cache-Control: public, max-age=0, must-revalidate` y `Service-Worker-Allowed: /`). No llevan `_redirects`: sin `404.html` en la raíz, Pages «assumes that you are deploying a single-page application» y sirve la raíz para cualquier ruta que no sea un archivo ([serving pages](https://developers.cloudflare.com/pages/configuration/serving-pages/)), lo mismo que hacía el rewrite de Vercel.

**Diferencia con GitHub Pages:** Pages redirige los `.html` a la ruta sin extensión («`/contact.html` will be redirected to `/contact`»). Los links que arman los mails (`/frontend/login.html?recovery=…`, `/frontend/alta-vecino.html?m=…`, `/frontend/encuesta.html?t=…`) y el iframe del shell (`web-app/dist/index.html#/…`) pasan por esa redirección: se verifican en el corte A que conserven el query string y el hash.

## Dominios

- Cada proyecto lleva su dominio sin prefijo (el del municipio demo) y uno por municipio: `<sub>.zge.zaris.com.ar` → `zaris-zge`, `<sub>.vecinos.zaris.com.ar` → `zaris-vecinos`, `<sub>.agentes.zaris.com.ar` → `zaris-agentes`.
- **Primero se asocia el dominio al proyecto y después se crea el CNAME** a `<proyecto>.pages.dev`. La documentación lo advierte: un CNAME creado sin asociar antes el dominio en Pages hace que el dominio no resuelva y dé `522` ([custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)). Si se hace desde el panel con la zona en la misma cuenta, el panel crea el CNAME solo.
- **Modo del CNAME:** la documentación no lo indica. `tools/dominios_municipio.py` lo crea proxied (nube naranja); al mover `agentes.` en el corte A se mira cómo lo dejó el panel y, si difiere, se ajusta el script y esta línea. La regla vieja de «DNS only» era de GitHub Pages, que emitía su propio certificado.
- **Municipio nuevo:** `python tools/dominios_municipio.py <subdominio>` asocia los 3 dominios y crea los 3 CNAME (idempotente; `--solo-verificar` no escribe, `--quitar` borra). Usa un token de la API con permisos `Zone → DNS → Edit` sobre `zaris.com.ar` y `Account → Cloudflare Pages → Edit`, guardado fuera del repo, en `credenciales-testing/cloudflare_api_token.txt`. El backend no tiene credenciales de Cloudflare.

## Límites y términos (leídos el 2026-10-27)

- **Plan gratuito** ([limits](https://developers.cloudflare.com/pages/platform/limits/)): 500 builds por mes, 1 build a la vez por cuenta, 20 minutos por build, **100 dominios propios por proyecto** (= 99 municipios además del demo), 20.000 archivos por sitio, 25 MiB por archivo, 100 proyectos por cuenta.
- **Uso comercial:** el [Self-Serve Subscription Agreement](https://www.cloudflare.com/terms/) no limita los servicios gratuitos a uso personal o no comercial. Sí dice que un servicio gratuito termina por «termination of the Free Service by Cloudflare in our sole discretion» (§2.6) y que Cloudflare puede «modify or discontinue the Service at any time» (§8).
- **Términos de la plataforma** ([service-specific terms](https://www.cloudflare.com/service-specific-terms-developer-platform/), Developer Platform): Cloudflare «may temporarily limit your storage and/or the number of requests» si el tráfico carga la red; somos responsables de los actos de los usuarios finales; Cloudflare puede cambiar los subdominios `pages.dev` con una semana de aviso (no afecta a los dominios propios).
