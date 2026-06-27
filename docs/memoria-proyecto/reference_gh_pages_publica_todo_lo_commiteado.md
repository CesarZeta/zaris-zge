---
name: reference_gh_pages_publica_todo_lo_commiteado
description: "GH Pages sirve el repo zaris-zge ENTERO bajo zge.zaris.com.ar. Cualquier archivo commiteado (md, html, png, py) queda accesible públicamente por URL."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 506e05e6-fd53-4ed2-adbd-e34625d91b65
---

GitHub Pages sirve **todo el repo `zaris-zge`** desde la raíz bajo `https://zge.zaris.com.ar/` (y `cesarzeta.github.io/zaris-zge/`). No solo `web-app/dist/` — **cualquier archivo commiteado** queda accesible por su path: `docs/manual_x.html`, `landing/zaris.html`, `reporte_pruebas_*.md`, hasta scripts `.py` de `backend/` (se sirven como texto plano).

**Why:** al versionar untracked en esta sesión (landing, reportes QA, prompts, seeds) confirmé que todos quedan públicos. No hay capa de auth sobre Pages — es estático y abierto. Un reporte QA con un PoC de XSS, o un script de seed con credenciales hardcodeadas, quedaría indexable por Google al commitearlo.

**How to apply:** antes de `git add` de cualquier archivo nuevo (sobre todo `.md`/`.html`/`.py` fuera de `web-app/src`), preguntarse "¿está OK que esto sea público?":
- Reportes QA con PoCs explotables → NO commitear hasta resolver (§40). Verificar con `grep -cE "<script>|javascript:|onerror=|alert\("`.
- Scripts de seed → revisar que no tengan passwords/keys hardcodeadas (las reales viven en Railway env / `.env.local` gitignored).
- Guías QA, manuales, landing, roadmaps → OK público (no tienen secretos).
- Si algo NO debe ser público pero querés versionarlo, no va en este repo — va en uno privado o se sirve desde otro lado.

Relacionado: §6 (repo público), §40 (reportes vs guías QA), [[feedback_git_add_dir_cola_untracked]].
