---
name: Shell principal ZARIS
description: El shell real de la app vanilla es index.html en la raíz del repo, no frontend/shell.html
type: project
---
El shell principal de la aplicación web (vanilla JS) es `index.html` en la raíz del repositorio.
- URL local: `http://localhost:8080/index.html`
- Servidor: `python -m http.server 8080` desde la raíz del repo
- El iframe tiene id `module-frame`; navegación via `window.shellNavigate(url)`
- `frontend/shell.html` es un archivo de prototipo/referencia, NO el shell activo

**Why:** Confusión recurrente — los cambios al menú se aplicaban a `frontend/shell.html` en lugar de `index.html`, y el usuario no veía los cambios en `localhost:8080`.
**How to apply:** Siempre editar `index.html` para cambios al shell/menú. Verificar en `http://localhost:8080/index.html`.
