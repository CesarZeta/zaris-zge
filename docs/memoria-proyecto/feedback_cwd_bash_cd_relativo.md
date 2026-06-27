---
name: cwd-bash-cd-relativo
description: "El working directory del Bash tool persiste entre llamadas, pero `cd` relativo se acumula. No asumir cwd después de `cd ..` o `cd subdir` — usar `pwd && cmd` o paths absolutos."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4ed10f75-1110-405b-a93b-8ba08aa79fe3
---

El Bash tool persiste cwd entre llamadas (a diferencia de variables de shell). Pero un `cd ..` o `cd subdir` se acumula sobre el cwd previo, no sobre la raíz del repo.

**Why:** Sesión 2026-05-12, fase de cierre del módulo Ciudadanos React. Estaba en `web-app/` después de un `cd web-app && vite build`. Hice `cd ..` para borrar archivos del frontend vanilla, después `cd web-app` para rebuildar — pero el `cd` se aplicó al cwd nuevo de raíz, no a "subir y entrar". El siguiente comando `node_modules/.bin/vite build` fallaba con "No such file or directory" porque corría en raíz, no en `web-app/`. Perdí 2 round-trips diagnosticando.

**How to apply:**
1. **Antes de cualquier comando con path relativo**, hacer `pwd` o pegarlo dentro del mismo comando: `pwd && node_modules/.bin/vite build`.
2. **Para tareas multi-directorio**, preferir paths absolutos: `node_modules/.bin/vite build` en `web-app/` o `web-app/node_modules/.bin/vite build` desde raíz.
3. Si se sospecha que el cwd se desplazó, **resetear con `cd /c/Users/Cesar/Documents/ZARIS/Desarrollo/ZGE`** (path absoluto de la raíz) antes de la siguiente operación.
4. La operación más segura para `git`/`rm` que afecten múltiples directorios: usar paths relativos desde raíz, después de un `cd` absoluto explícito.

**Write/Edit con ruta relativa también usan el cwd desplazado (cazado 2026-06-01).** Las tools Write/Edit resuelven rutas relativas contra el cwd actual del shell. Tras correr comandos con `cd backend` (uvicorn, psql), el cwd quedó en `backend/`, así que `Write("frontend/alta-vecino.html")` escribió en **`backend/frontend/alta-vecino.html`** — un archivo fantasma — mientras el `frontend/alta-vecino.html` real quedó con la versión vieja. Síntoma confuso: el http.server servía HTML viejo aunque "había escrito el archivo". Diagnostiqué con `grep` en disco (raíz vs backend) y encontré el duplicado. **Regla: SIEMPRE usar rutas ABSOLUTAS en Write/Edit** (`c:\Users\Cesar\...\frontend\X.html`), o verificar `pwd` antes. El harness además pierde el tracking del archivo al cambiar el cwd (pide re-Read). Esto vale doble para sesiones full-stack donde se alterna entre `backend/` (uvicorn/psql) y la raíz (http.server/git).

Relacionado: [[feedback_shell_ps_vs_bash]] sobre cuándo usar PowerShell vs Bash. PowerShell con `Set-Location` tiene el mismo issue.
