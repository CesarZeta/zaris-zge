---
name: win-quirks
description: Recetas de build del bundle React (web-app/dist) y de operar el entorno local en Windows/PowerShell. Usar al buildear/commitear web-app/dist/, levantar servers locales (http.server, uvicorn, pnpm dev), correr psql, lanzar procesos detached con Start-Process, o diagnosticar redirects rotos bajo el subpath /zaris-zge/. Cubre los quirks que rompen silenciosamente en Windows (Start-Process con .cmd, localhost vs 127.0.0.1 para CORS, http.server zombie, etc.).
---

# Build de `web-app/dist/` y entorno local (Windows/PowerShell)

Recetas operativas verificadas. Muchas tienen memoria asociada (`[[...]]`) con el detalle del caso real.

## Build / dist

- **Q1 — `pnpm build` toma `VITE_API_BASE` del shell por sobre los `.env`.** Antes de commitear `dist/`, buildear en terminal limpia modo prod (default) y verificar `grep -o 'zaris-api-production' web-app/dist/assets/index-*.js` da match (no `127.0.0.1`). Ver Q14.
- **Q2 — `dist/index.html` tiene `base: '/zaris-zge/...'`** (GH Pages). Abrirlo directo en `localhost:8080` da assets 404. Para probar la integración shell+bundle local, levantar un server que sirva el repo bajo `/zaris-zge/` ([[project_proxy_local_zaris_zge]]).
- **Q6 — usar `node_modules/.bin/vite` o `pnpm build`, NUNCA `npx vite`** (baja otra versión y rompe el build PostCSS).
- **Q7 — favicon/title del scaffold Vite**: antes del 1er push a prod de un módulo React, en `web-app/index.html` `<title>` = "ZARIS · …" y `<link rel="icon">` = `/zaris-favicon.svg`; `web-app/public/` solo `zaris-favicon.svg` (sin `vite.svg`/`favicon.svg`).
- **Q14 — `vite build` compila el WORKING TREE, no lo staged.** Commitear fuentes primero, rebuildear con el tree acotado, commitear dist (o todo junto). Stash lo ajeno antes de rebuildear. [[feedback_rebuild_dist_working_tree_limpio]].

## Levantar servers local (Windows/PowerShell)

- **Q3 — CORS**: nuevo origen local → agregar a `allow_origins` en `main.py` + reiniciar uvicorn (sin `--reload` no toma cambios).
- **Q4 — uvicorn**: chequear puerto 8000 libre antes de levantar (`[Errno 10048]` si choca).
- **Q8 — `localhost` ≠ `127.0.0.1` para CORS del browser** (orígenes distintos); el allowlist tiene `localhost`. Curl/psql/IWR no se afectan. [[feedback_localhost_vs_127_cors]].
- **Q9 — `python -m http.server`**: lanzar detached con `Start-Process -WindowStyle Hidden` (Bash bg queda zombie en Windows). [[feedback_http_server_detached]].
- **Q10 — credenciales dev local**: admin es `ciudadanovl@municipio.gob.ar` (no `admin@`); pass `123456`. Listar usuarios con psql antes de smoke. [[feedback_smoke_credenciales_dev]].
- **Q11 — `Start-Process pnpm/npm/npx` falla** (son `.cmd`): usar `Start-Process cmd.exe -ArgumentList "/c","pnpm dev > log 2> err"`. [[feedback_ps_quirks_startprocess_psql]].
- **Q5 — QR**: solo render cliente (`qrcode` ~26KB sobre canvas); el backend solo genera el string `EVT<id>-RES<id>-<ts>`.
- **Q16 — git commit multilínea (Bash tool)**: el here-string `git commit -m @'...'@` mete un `@` LITERAL al inicio del subject (`@ feat(...)`). Verificar con `git log -1 --format='%s'`; si quedó el `@`, amendar con archivo: `cat > /tmp/cmsg.txt <<'EOF' ... EOF` + `git commit --amend -F /tmp/cmsg.txt`. Default: para commits con cuerpo, escribir el mensaje a archivo y usar `-F`, no here-string. (verif. 2026-06-09)
- **Q15 — `& "C:\Program Files\...\psql.exe"` lo bloquea el PowerShell tool** como falso positivo "Remove-Item path protegido" (parsea mal ruta-con-espacios + `&`). Para DB LOCAL en smokes usar script Python+psycopg2 (`@"...import psycopg2..."@ | python`), no `& $psql`. Prod = `execute_sql`/`apply_migration` MCP. [[feedback_ps_quirks_startprocess_psql]] (Quirk 3).
- **Q17 — uvicorn detached con `ENV_FILE` (receta canónica, verif. 2026-05-16)**: `Start-Process` en PS 5.1 **NO hereda env vars del shell padre** (`$env:ENV_FILE` seteado antes NO llega al hijo) y `-Environment` no existe. La única forma confiable:
  ```powershell
  Start-Process cmd.exe -ArgumentList "/c","set ENV_FILE=.env.local && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > _uvicorn.log 2> _uvicorn.err.log" -WorkingDirectory "...\backend" -WindowStyle Hidden
  ```
  Sin `ENV_FILE`, `config.py` usa el default (puede apuntar a PROD). Si no hace falta env var, `Start-Process python` directo con `-WorkingDirectory` + `-RedirectStandardOutput/Error` es más simple (python es .exe, no necesita el rodeo `cmd /c` de Q11). Si el log queda vacío tras lanzar, probar primero en foreground para ver el error real. Tras lanzar, verificar entorno correcto: un request a algo que solo exista en local debe dar 200. Para matar/reiniciar (código viejo en memoria), matar **por puerto**: ver [[feedback_uvicorn_restart_tras_registrar_routers]].

## Q12/Q13 — redirects bajo subpath `/zaris-zge/` (reglas con código)

**Q12 — el bundle standalone en prod debe redirigir al shell vanilla.** Si alguien abre `…/web-app/dist/index.html` directo ve el AppShell React standalone (viola §14). Script inline en `<head>` de `web-app/index.html` (antes de que React monte):

```html
<script>(function(){try{
  if (window.self !== window.top) return;                   // OK embebido
  if ((window.location.pathname||'').indexOf('/zaris-zge/web-app/dist/') === -1) return; // dev local
  var hash = window.location.hash || '', target = '/zaris-zge/index.html';
  if (hash.length > 1) target += '?modulo=' + encodeURIComponent('web-app/dist/index.html' + hash);
  window.location.replace(target);
}catch(e){}})();</script>
```
**Complemento obligatorio** en `menu.js`: la whitelist de `?modulo=` debe aceptar el bundle React (`/^web-app\/dist\/index\.html(#\/.*)?$/i`) además de los HTML vanilla, sino el shell descarta el redirect. Hacen falta las DOS piezas.

**Q13 — `window.location.href='/foo'` desde el bundle salta a `cesarzeta.github.io/foo` SIN `/zaris-zge/`** → 404 de GH Pages dentro del iframe (shell padre OK, iframe roto). Aplica a handler 401 de `api.ts`, "Cerrar sesión", `<a href="/...">`. Patrón correcto: detectar subpath del parent y redirigirlo. Ver helper `shellNav.ts` (§41 de CLAUDE.md) y [[feedback_redirect_iframe_subpath]].
