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
     await page.goto(url, { waitUntil: 'networkidle' })
     if (prepFn) try { await prepFn(page) } catch (e) { console.warn(e.message) }
     await page.screenshot({ path: path.join(OUT, name) })
     await page.close()
   }
   ```
5. **Build HTML** con `dataUrl(filename)` → `data:image/png;base64,...` y look ZARIS (tokens del DS: `--zaris-orange`, `--zaris-cream`, etc.).
6. **Cleanup OBLIGATORIO al final:** borrar data demo, restaurar flags tocados (ej. `es_auditor`), eliminar carpeta `_<modulo>_caps/`, bajar servers.

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
- **PowerShell `Out-File -NoNewline` encoding:** strings cortos = UTF-8 con BOM, strings largos = UTF-16 LE con BOM. Leer en Node con `replace(/^﻿/, '').trim()` cubre UTF-8; UTF-16 requiere `Buffer.toString('utf16le').replace(...)`.
- **El `addInitScript` de Playwright** debe inyectar la sesión ANTES de navegar, no después, para que el guard React no redirija a `/login`.
- **Sembrar data con API, NO con SQL crudo:** SQL crudo puede saltarse triggers/validaciones y dejar la DB inconsistente.

## Variante sin capturas (válida)
Para módulos **analíticos/simples** (dashboards de lectura, pocas pantallas), un manual de texto + tablas + diagramas de flujo con el estilo ZARIS es suficiente — entregable sin el setup de Playwright. Ej: `manual_encuestas.html` (0 capturas). Reservar el manual con capturas para flujos operativos multi-paso donde "ver la pantalla" agrega valor (Reclamos, OT, Trámites).

## Regenerar capturas tras un cambio de UI (patch de archivo grande)
- **Detectar desfasaje:** extraer el texto del HTML (quitar `data:image/...;base64` con regex, luego tags) y grepear los términos que tu cambio tocó (botones, tabs, tipos). Si el manual nombra algo que renombraste/quitaste, está desfasado.
- **Regenerar solo las capturas afectadas:** identificá qué `<figure>` corresponde a la pantalla cambiada (por su `<figcaption>`/heading) y regenerá esas + insertá nuevas. El resto siguen válidas.
- **Patch con guardas:** para swaps de base64 y ediciones de texto en un archivo de ~3 MB, usar un script Node/Python con `assert`/`must()` sobre cada anchor antes de escribir. **Al anclar texto dentro de markup, incluí los tags inline** (`El pase <strong>libera la toma</strong>...`, no el texto pelado) o el match falla. Verificar en el browser (imágenes no rotas, secciones nuevas) antes de commitear.
