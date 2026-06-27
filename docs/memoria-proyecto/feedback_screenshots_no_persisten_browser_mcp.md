---
name: screenshots-no-persisten-browser-mcp
description: "El tool browser_screenshot de integrated-browser-mcp NO persiste el PNG en disco aunque se le pase `filename`; solo devuelve la imagen al modelo. Para guardar capturas usar Playwright headless local con npm install --no-save."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fc045d9c-7164-4f89-9bb2-bbede897fec8
---

`mcp__integrated-browser-mcp__browser_screenshot` con parámetro `filename:` **NO guarda el archivo en disco**. Solo devuelve la imagen al modelo (output_image visible al asistente). El parámetro existe pero no tiene efecto real.

**Why:** lo intenté para generar manuales HTML con capturas embebidas en base64 (sesión 2026-05-18, manual_admin_tramites + manual_reclamos + manual_ot). Perdí ~10 minutos probando variantes con `fullPage`, paths absolutos, paths con forward/back slashes — ninguna persiste. Verificable con `Get-ChildItem -Recurse` en `%LOCALAPPDATA%` y `/tmp`.

**How to apply:** cuando necesites capturas reproducibles en disco para construir docs / manuales / reports, **NO uses browser MCP**. Usar Playwright headless directo:

```bash
# 1. Setup local sin contaminar package.json
mkdir _caps && cd _caps
echo '{"name":"caps","type":"module","private":true}' > package.json
npm install playwright --no-save --no-package-lock
npx --yes -p playwright@latest playwright install chromium

# 2. Script captura
cat > capture.mjs <<'JS'
import { chromium } from 'playwright'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } })
// Inyectar localStorage para que el guard React no redirija a /login
await ctx.addInitScript(({ token, userJson }) => {
  const user = JSON.parse(userJson)
  const session = { state: { accessToken: token, user }, version: 0, access_token: token, user }
  localStorage.setItem('zaris_session', JSON.stringify(session))
}, { token, userJson })
// ... resto del script
JS

# 3. Una página fresca por captura para evitar estado residual
async function shot(name, url, prepFn) {
  const page = await ctx.newPage()
  await page.goto(url, { waitUntil: 'networkidle' })
  // ...
  await page.close()
}
```

**Quirk relacionado:** PowerShell `Out-File -NoNewline` con strings cortos (un solo número entero) escribe **UTF-8 con BOM**, no UTF-16. Pero con strings largos (JSON, tokens largos) escribe **UTF-16 LE con BOM**. Leer con `fs.readFile(path, 'utf8').replace(/^﻿/, '')` cubre ambos casos (el BOM UTF-8 ya viene strip-eado en utf8 mode pero no siempre — better safe). Si falla con UTF-8 utf-16, leer como Buffer y probar `.toString('utf16le').replace(/^﻿/, '')`.

**Usado en:** manual_reclamos, manual_ot, manual_admin_tramites (sesión 2026-05-18). Receta limpia, repetible. Cleanup: `rm -rf _caps` al final, los HTMLs ya quedaron generados via build_html.mjs.

Relacionado: [[feedback_acortar_alcance_html_autocontenido]] (decide tamaño antes de pelearte con base64), skill `win-quirks` Q17 (cómo levantar servers para tests).
