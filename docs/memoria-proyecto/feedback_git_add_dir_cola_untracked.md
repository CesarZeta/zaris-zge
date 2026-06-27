---
name: feedback_git_add_dir_cola_untracked
description: "No usar `git add <dir>` amplio en este repo — la raíz y backend/ tienen untracked permanentes que se cuelan al commit."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 506e05e6-fd53-4ed2-adbd-e34625d91b65
---

`git add backend/` (o cualquier `git add <directorio>` amplio) **cola archivos untracked** que no eran parte del cambio. En esta sesión `git add backend/` metió `seed_prod_agentes_usuarios.py` y `seed_agentes_usuarios_empate.py` (seeds del usuario, untracked de otra tarea) en un commit de trámites. Hubo que sacarlos con `git rm --cached` + commit + (durante el rebase) moverlos temporalmente del árbol porque el checkout los pisaba.

**Why:** este repo mantiene untracked permanentes a propósito (regla §40 reportes QA sin PoCs, scripts de seed a medias, `landing/`, prompts sueltos). `git status` al inicio de cada sesión los muestra. Un `add` por directorio los arrastra.

**How to apply:** stagear **archivos explícitos**, nunca directorios:
- `git add backend/app/api/routes/tramites_admin.py backend/migrations/56_x.sql` ✅
- `git add backend/` ❌ (cola untracked)
- Excepción segura: `web-app/dist/` (todo su contenido es generado y va junto) y `web-app/src/modules/<modulo>/` (acotado a un módulo sin untracked).
- Antes de commitear, mirar `git status --short | grep -v '^??'` para confirmar que solo se stageó lo intencional.
