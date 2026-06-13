---
name: generar-manual
description: Receta para generar o regenerar un manual operativo HTML autocontenido (docs/manual_<modulo>.html) con capturas reales embebidas en base64, usando Playwright headless local. Usar al crear un manual nuevo de un módulo, regenerar capturas de uno existente tras un cambio de UI, o armar el HTML con el estilo ZARIS. Cubre el setup de Playwright sin contaminar el package.json, el patrón de captura, las convenciones del HTML, el patch con guardas de archivos grandes y el cleanup obligatorio.
---

# Generación de manuales operativos (HTML autocontenidos)

Receta probada para producir `docs/manual_<modulo>.html` autocontenido (capturas reales en base64).

## Patrón fundamental

1. **Carpeta temporal `_<modulo>_caps/`** (gitignored, borrar al final) con:
   - `package.json` mínimo con `"type": "module"`
   - `_token.txt` y `_user.json` (auth para inyectar en localStorage)
   - `_id<entidad>.txt` (ids de demo para deep-links)
   - `capture.mjs` (script Playwright)
   - `build_html.mjs` (ensambla HTML con base64 inline)
2. **Setup Playwright local sin contaminar** `package.json` del web-app:
   ```bash
   cd _modulo_caps
   echo '{"name":"caps","type":"module","private":true}' > package.json
   npm install playwright --no-save --no-package-lock
   npx --yes -p playwright@latest playwright install chromium
   ```
3. **Datos demo** en DB para que las capturas tengan contenido rico. Sembrar vía API (no SQL crudo) para respetar reglas de negocio.
4. **Script Playwright** con UNA página fresca por captura para evitar estado residual de modales:
   ```js
   async function shot(name, url, prepFn) {
     const page = await ctx.newPage()
     // NO usar 'networkidle': los modulos React mantienen conexiones abiertas
     // (polling/notificaciones) y nunca llega a idle -> timeout 30s. Usar
     // domcontentloaded + espera fija + waitFor del primer elemento real.
     await page.goto(url, { waitUntil: 'domcontentloaded' })
     await page.waitForTimeout(2500)
     if (prepFn) try { await prepFn(page) } catch (e) { console.warn(e.message) }
     await page.screenshot({ path: path.join(OUT, name) })
     await page.close()
   }
   ```
5. **Build HTML** con `dataUrl(filename)` → `data:image/png;base64,...` y look ZARIS (tokens del DS: `--zaris-orange`, `--zaris-cream`, etc.).
6. **Cleanup OBLIGATORIO al final:** borrar data demo, restaurar flags tocados (ej. `es_auditor`), eliminar carpeta `_<modulo>_caps/`, bajar servers.

## Capturar un MÓDULO REACT (leer ANTES de empezar — cuesta 4 iteraciones si no)

El `web-app/dist/` commiteado se compila contra **prod (Railway)** — `VITE_API_BASE` apunta a `zaris-api-production`. Esto define todo el approach:

- **Logueate en PROD, no en local.** Un token de login local da **401 en todas las requests** del módulo (el bundle pega a Railway, que no conoce ese token) → el handler de 401 redirige y la captura sale en login/dashboard. Credencial prod admin: `cesar@municipio.gob.ar` / `123456`. Usá entidades reales de prod para los deep-links (`GET /api/v1/tramites?limit=8` y elegí un nº de expediente real). *(Alternativa si necesitás datos locales controlados: rebuildear `pnpm build --mode development` y NO commitear ese dist — ver memoria `proxy-local-zaris-zge`. Para un manual, prod suele alcanzar.)*
  - **Manual que mezcla una pantalla VANILLA (admin_tablas/usuarios) con el bundle React: sesión HÍBRIDA.** El shell vanilla en `localhost:8080` y sus módulos vanilla (`frontend/admin_tablas.html`) pegan a la API **LOCAL** (token local); el iframe default que carga el dashboard React pega a **Railway** (token prod). Si seteás solo uno, el otro tira 401 y el handler nukea `zaris_session` ([[feedback_token_local_contra_dist_prod_nuke_sesion]]). El truco para capturar, p.ej., la sección "Horario de atención" de Agentes (vanilla) sin que el dashboard React de fondo borre la sesión: armar **una sola key `zaris_session` con las dos formas apuntando a entornos distintos** — `access_token`/`user` (shape plana) con el token LOCAL, `state.accessToken`/`state.user` con el token PROD. Cazado 2026-06-12 (manual de Agenda, captura de franjas). Login local dev: `ciudadanovl@municipio.gob.ar` / `123456` (Q10 de win-quirks).
  - **Título real en la UI ≠ lo que dice la doc:** antes de scrollear/anclar a un heading, leé el HTML/JSX real (`grep`). La sección de franjas de agentes era "Horario de atención" (id `#horarioSec`), no "Horario de asistencia" como decía CLAUDE.md — el `waitFor` por el texto viejo timeouteaba. Anclá por `id`/selector estable, no por texto que asumís.
- **Cargá el módulo DENTRO del iframe del shell vanilla** (modo embebido: `self !== top` ⇒ AppShell sin guard de login, igual que producción). Dos trampas que NO funcionan:
  - Navegar directo a `http://localhost:8080/web-app/dist/index.html#/...` → el script standalone de `web-app/index.html` hace `location.replace` al shell (path con `/web-app/dist/`), y si lo neutralizás, el AppShell standalone redirige a `/login`.
  - `window.parent.shellNavigate(...)` sobre un iframe ya montado → cambia el hash pero el HashRouter NO re-rutea.
  - **Lo que SÍ funciona:** abrir el shell (`localhost:8080/index.html`), esperar, y setear `document.getElementById('module-frame').src = 'web-app/dist/index.html?_cb='+Date.now()+'#/<ruta>'` (cache-bust fuerza remount en el hash). Capturar contra `page.frameLocator('#module-frame')`. La sesión se inyecta con `addInitScript` (ambos shapes, §29) ANTES de navegar.
- **Verificar antes de juzgar:** si la captura sale en login/dashboard, mirá `page.on('response')` por 401 contra Railway (= token de entorno equivocado) y `page.frames().map(f=>f.url())` (= el iframe quedó en `#/dashboard` porque el `?modulo=` del shell cayó al default). Ambos son síntomas del environment, no del script.
- **Las capturas del uploader NO ensucian prod:** `input.setInputFiles([...])` solo stagea client-side; mientras no cliquees "Subir", nada llega al backend. Igual, no clickees acciones que muten.
- **Páginas PÚBLICAS top-level (autoservicio de turnos/eventos) — recortar al `<main>`.** Rutas como `#/turnos-autoservicio` o `#/autoservicio/:token` NO viven en el iframe del shell; son top-level del bundle. Capturarlas tiene una trampa: **sin sesión** el AppShell standalone redirige a `/login` (su guard); **con sesión** renderiza el contenido correcto pero **envuelto en el sidebar+topbar de admin** (que en prod el ciudadano nunca ve). Lo que funciona: navegar directo al bundle CON sesión inyectada (`addInitScript`) y capturar **solo el `<main>`** (`page.locator('main').first().screenshot(...)`), que aísla la tarjeta pública sin el shell admin. Verificá la captura: si salió la pantalla de login, te faltó la sesión; si salió con sidebar, no recortaste al `main`. Cazado generando los manuales de Turnos/Entradas (2 reintentos).
- **Agenda/grilla con datos por fecha: posicionarse en una fecha CON datos.** Una grilla día/semana capturada en "hoy" puede salir vacía si los datos demo caen en otros días. Pasar a vista Semana y/o navegar a la semana correcta en el `prepFn` antes del screenshot.
- **Lista React no muestra lo recién sembrado → es `staleTime` de react-query, no un filtro roto.** Antes de sospechar un bug de filtrado en el front, clickeá "refrescar" del módulo (o esperá el `staleTime`, ~15s) y verificá que el backend ya lo devuelve (`GET` directo). Cazado: un evento finalizado "no aparecía" en Entradas; era cache de query, el backend lo devolvía bien.

## Convenciones del HTML
- **Tamaño esperado:** 1-3 MB con 9-12 capturas embebidas. Si pasa de 5 MB, revisar (probable capturas gigantes o demasiadas).
- **Estructura:** hero con borde naranja izquierdo + breadcrumb tag + h1, índice con anchors, secciones numeradas (1-N), tablas de errores comunes + glosario al final.
- **Componentes:** `blockquote` con variantes `.warn` (ámbar), `.danger` (rojo), `.info` (azul). `.badge` con clases por estado. `.flow` para diagramas tipo "paso 1 → paso 2".
- **Footer:** "Manual generado el YYYY-MM-DD · ZARIS · Gestión Estatal · Capturas reales del entorno local".

## Almacenamiento y serving
- Los HTMLs viven en **`docs/`** en la raíz del repo. GH Pages los sirve como `https://zge.zaris.com.ar/docs/manual_X.html`. En dev local: `http://localhost:8080/docs/manual_X.html`.
- **NO embeber en iframe** (lento + pierde sidebar). Servir como pestaña nueva vía `target="_blank"`. Ver [[feedback_acortar_alcance_html_autocontenido]].

## Quirks operativos
- **`browser_screenshot` del MCP NO persiste el PNG.** Solo Playwright headless guarda en disco. [[feedback_screenshots_no_persisten_browser_mcp]].
- **Verificar el manual en el browser MCP: `loading="lazy"` da falso "imágenes rotas".** Si el `<img>` lleva `loading="lazy"` (recomendado en el HTML), las que están fuera del viewport reportan `naturalWidth===0` / `!complete` aunque el base64 esté perfecto. NO es un bug del manual. Para chequear de verdad: quitar el attr y esperar (`document.querySelectorAll('img[loading="lazy"]').forEach(i=>i.removeAttribute('loading'))` + `setTimeout` 1.5s) o hacer scroll. Cazado 2026-06-12 (manual de Agenda: las 12 daban "rotas" hasta forzar la carga).
- **PowerShell `Out-File -NoNewline` encoding:** strings cortos = UTF-8 con BOM, strings largos = UTF-16 LE con BOM. Leer en Node con `replace(/^﻿/, '').trim()` cubre UTF-8; UTF-16 requiere `Buffer.toString('utf16le').replace(...)`.
- **El `addInitScript` de Playwright** debe inyectar la sesión ANTES de navegar, no después, para que el guard React no redirija a `/login`.
- **Sembrar data con API, NO con SQL crudo:** SQL crudo puede saltarse triggers/validaciones y dejar la DB inconsistente.

## Variante sin capturas (válida)
Para módulos **analíticos/simples** (dashboards de lectura, pocas pantallas), un manual de texto + tablas + diagramas de flujo con el estilo ZARIS es suficiente — entregable sin el setup de Playwright. Ej: `manual_encuestas.html` (0 capturas). Reservar el manual con capturas para flujos operativos multi-paso donde "ver la pantalla" agrega valor (Reclamos, OT, Trámites).

## Regenerar capturas tras un cambio de UI (patch de archivo grande)
- **UNA regeneración por sesión, AL FINAL.** Si la sesión tiene más cambios de UI en cola (un informe QA por triagear, mejoras pedidas a continuación, feedback del usuario pendiente), NO regeneres el manual tras cada entrega: diferilo al cierre, cuando la UI quedó estable. Caso real 2026-06-11 (Turnos): se regeneró 3 veces en una misma sesión (historia de atención → filtros del informe QA → filtro de área) — los 2 últimos ciclos de Playwright eran evitables esperando al final.
- **Detectar desfasaje:** extraer el texto del HTML (quitar `data:image/...;base64` con regex, luego tags) y grepear los términos que tu cambio tocó (botones, tabs, tipos). Si el manual nombra algo que renombraste/quitaste, está desfasado.
- **Regenerar solo las capturas afectadas:** identificá qué `<figure>` corresponde a la pantalla cambiada (por su `<figcaption>`/heading) y regenerá esas + insertá nuevas. El resto siguen válidas.
- **Patch con guardas:** para swaps de base64 y ediciones de texto en un archivo de ~3 MB, usar un script Node/Python con `assert`/`must()` sobre cada anchor antes de escribir. **Al anclar texto dentro de markup, incluí los tags inline** (`El pase <strong>libera la toma</strong>...`, no el texto pelado) o el match falla. Verificar en el browser (imágenes no rotas, secciones nuevas) antes de commitear.
- **Alternativa al patch (verificada 2×, Emergencias 2026-06-10/11): extraer las capturas del manual existente y RE-ENSAMBLAR completo.** Si conservás el template (`build_html.mjs`), no hace falta re-capturar las pantallas que no cambiaron: un `extract.mjs` saca los base64 del HTML publicado (`[...html.matchAll(/data:image\/png;base64,([A-Za-z0-9+/=]+)/g)]`) y los guarda con sus nombres **en el orden de aparición de los `{{IMG:}}` del template** (mantené esa lista en el extract). Después: re-capturás solo las afectadas (pisan los archivos extraídos), tocás el template y re-ensamblás. Más simple y verificable que el patch in-place.

## Tablas de referencia (taxonomías/catálogos) — generarlas desde la DB
Cuando el manual incluye tablas de referencia (tipos, subtipos, organismos, estados), **NO transcribirlas a mano** (se desfasan y meten typos): generarlas con una query que emita las `<tr>` directamente y un placeholder `{{ROWS:archivo}}` en el template.

```powershell
$env:PGPASSWORD='145236'; $env:PGCLIENTENCODING='UTF8'   # sin UTF8, las tildes salen rotas
@"
SELECT '<tr><td>' || col1 || '</td><td>' || COALESCE(col2,'&mdash;') || '</td></tr>'
FROM tabla WHERE activo ORDER BY nombre;
"@ | & $psql -h 127.0.0.1 -U postgres -d zaris_dev -t -A -o fragmento.html
```

- Joins útiles: `string_agg(s.nombre || COALESCE(' (' || override.codigo || ')', ''), ' &middot; ')` vía LATERAL para listas compactas de hijos (subtipos) con sus excepciones.
- `Get-Content` sin `-Encoding UTF8` MUESTRA mojibake ("MÃ³vil") pero el archivo está bien — verificar con `-Encoding UTF8` o directo en Node, no "arreglar" el archivo.
- En el build: `html.replace(/\{\{ROWS:([^}]+)\}\}/g, (_, f) => fs.readFileSync(f, 'utf8').trim())`.
- Footer del manual: agregar "Taxonomía generada desde la base de datos".
