---
name: cache-bust-assets-estaticos
description: "Cuando edites JS/CSS estáticos servidos desde HTML (frontend/css/menu.css, frontend/js/menu.js), bumpear el sufijo ?v=YYYY-MM-DDx en el HTML o el navegador puede servir versión vieja durante horas."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76abb031-f1fc-41a4-97a8-16b043ddea10
---

Browser caché y CDN caché pueden servir versiones viejas de `menu.css` / `menu.js` (y cualquier asset estático que no tenga hash en el nombre) durante horas o días. Si editás esos archivos y no bumpeás la versión, el cambio aparenta "no aplicar" — agujero ENORME para perder tiempo debuggeando código que ya está correcto en disco.

**Why:** GitHub Pages tiene CDN cache. El navegador (incluyendo el browser-MCP integrado) también cachea agresivamente JS/CSS estáticos. A diferencia del bundle React (que Vite renombra con hash `index-XXXX.js` en cada build), los archivos vanilla mantienen el nombre y se cachean hasta que se mande un `Cache-Control: no-cache` o cambie la URL.

**How to apply:**
- En `index.html` y cualquier otro HTML que cargue assets locales editables, usar el patrón `?v=YYYY-MM-DDx`:
  ```html
  <link rel="stylesheet" href="frontend/css/menu.css?v=2026-05-13c">
  <script src="frontend/js/menu.js?v=2026-05-13a"></script>
  ```
- Al editar el JS/CSS subyacente, bumpear el sufijo en el HTML (próxima letra del día o nuevo día). Es un find/replace en un solo archivo.
- Aplica también a `frontend/js/config.js`, `frontend/js/usuarios.js`, cualquier `frontend/css/*.css` cargado desde HTMLs.
- **NO aplica al bundle React** (`web-app/dist/assets/index-XXX.js`) — Vite ya pone hash en el nombre y el HTML del bundle se regenera con el hash nuevo cada build.

**Diagnóstico cuando "no aparece el cambio":**
1. Verificar contenido del archivo vía `fetch(url, { cache: 'no-store' })` en el devtools — si el archivo descargado tiene el cambio pero el comportamiento del browser no lo refleja, es cache del browser.
2. Recargar con Ctrl+F5 (bypass cache) para confirmar.
3. Si solo Ctrl+F5 lo soluciona, bumpear el `?v=` y commitear para que afecte a todos los usuarios.

Cazado 2026-05-13: edité `menu.js` para sumar el reloj del topbar, browser cargaba la versión sin reloj durante 3 navegaciones (~10 min de debug). Fix: agregar `?v=2026-05-13a` al `<script>` del HTML, problema resuelto.
