---
name: feedback_push_directo_a_main
description: "El usuario quiere push directo a main, sin crear rama feature"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a44a6e1e-1317-4ec7-9553-e4b9b5a3579f
---

Cuando el usuario pide commit/push en este repo (zaris-zge), hacerlo **directo sobre `main`** — NO crear rama feature ni PR. El usuario lo pidió explícitamente el 2026-05-22 ("que vaya a main siempre").

**Además (2026-06-13) — avanzar de corrido a prod, PERO solo en verde:** cuando el trabajo ya está **verificado localmente** y el usuario dio luz verde a "pasar a producción / completar el plan", avanzar con **commit → push → verificación en prod SIN frenar a pedir confirmación** en cada paso ("no me pidas confirmar, simplemente avanza"). Informar al terminar (hash + resultado), no consultar antes de cada git push / curl.

**La condición es "todo en verde". Si aparece un error → PARAR.** El usuario lo precisó el 2026-06-13: "a producción solo si lo productivo está OK, funcionando y verificado". Concretamente, parar y avisar (no seguir, no commitear/pushear sobre lo roto) si: un smoke/verificación falla, el deploy de prod no toma el código, un endpoint nuevo da error inesperado, o un test que pasaba se rompe. **Si el error requiere una intervención tuya específica que no puedo resolver por mis propios medios** (env var/secreto que solo el usuario setea, servicio caído en el dashboard, decisión de producto, dato que falta) → parar y preguntar, no improvisar un workaround. Avanzar autónomo NO significa empujar a prod algo que no quedó verde. La cautela sigue valiendo además para acciones irreversibles fuera del flujo normal (DROP en prod, borrado masivo, rotar secretos).

**Why:** anula la salvaguarda por defecto "if on the default branch, branch first". El flujo del usuario es trabajar directo sobre main; main es además lo que dispara los deploys (Railway backend autodeploy + GitHub Pages frontend), así que branchear solo agrega un paso de merge sin valor para él. Frenar a confirmar cada paso cuando ya aprobó la fase de producción agrega fricción sin valor.

**How to apply:** estando en main, `git add <archivos de la tarea>` (no `git add .` — hay untracked ajenos), commit con el co-author footer, y `git push origin main`. Igual rebuildear `web-app/dist/` apuntando a Railway antes de commitear si tocaste `web-app/**` (ver [[feedback_rebuild_dist_working_tree_limpio]]) y verificar prod tras push backend (Railway no es confiable, CLAUDE.md §9).
