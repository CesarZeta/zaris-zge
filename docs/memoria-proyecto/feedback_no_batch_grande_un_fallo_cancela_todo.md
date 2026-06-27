---
name: feedback_no_batch_grande_un_fallo_cancela_todo
description: "Batches grandes en paralelo + UN comando que falla cancela TODO el grupo (se pierden Writes/Edits sin avisar); 1 Edit por mensaje, Read antes de cada Edit, nunca git restore defensivo."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 110618af-401a-47e7-8010-ad1e2e43c67b
---

Cazado repetidamente en la sesión 2026-05-31 j2 (feature "aprobaciones por etapa" de Trámites). Cuando el harness está degradado (resultados de tool vacíos intermitentes), agrupar muchas tool-calls en paralelo es contraproducente Y peligroso.

**Por qué duele:** si **una sola** call de un grupo paralelo falla (un script bash con `[ -z "$r" ]` que sale exit≠0, `node node_modules/.bin/tsc` que NO es JS y revienta, `pnpm typecheck` que sale 2 por errores reales, un `git add` con un pathspec inexistente), **el harness cancela TODAS las demás calls del grupo** con "Cancelled: parallel tool call ... errored". Se pierden silenciosamente los `Write`/`Edit` que venían después en ese mensaje. Consecuencias reales esa sesión:
- Una memoria (`feedback_no_batch_grande...`) y la edición de `CLAUDE.md §35` que YO CREÍA escritas **nunca se escribieron** → afirmé "documentado" y era falso. Solo se detectó re-verificando con `grep`/`test -f` al cierre.
- 4 archivos del frontend (types, lib/api, hooks, PanelAprobaciones) quedaron sin crear; casi commito creyéndolos hechos.
- Me asusté pensando que un archivo grande estaba corrupto y le hice `git restore` "por las dudas" DOS veces → me borré trabajo bueno. El archivo siempre estuvo limpio; la ilusión venía de reads vacíos + stale-cache, no de corrupción.

**Reglas (aplicar SIEMPRE, no solo en ventanas degradadas):**
1. **1 Edit/Write por mensaje** en archivos grandes/críticos (a lo sumo 2-3 Edits secuenciales al MISMO archivo si estoy seguro de los anchors). NO mezclar varios archivos distintos en un batch.
2. **Read inmediatamente antes de cada Edit.** "File has been modified since read" = cache stale, NO corrupción; un Read fresco lo arregla.
3. **NUNCA `git restore` defensivo** tras ediciones buenas. Verificar primero con `wc -l` + `grep -c <marcador>` + `python -c "ast.parse(...)"`. Restaurar solo con evidencia real de daño.
4. **No mezclar verificación con edición** en el mismo batch: los comandos que pueden salir ≠0 (loops, typecheck, builds) van SOLOS.
5. **Al cerrar, re-verificar que lo que digo "hecho" existe**: `test -f`, `grep -c` sobre memorias/CLAUDE.md/archivos nuevos. No confiar en que un `Write`/`Edit` reportado OK en un batch parcialmente cancelado realmente quedó.

Cara complementaria: [[feedback_el_backend_puede_mentir]] (cara 1, shape JSON ≠ tipo TS) — además perdí tiempo escribiendo componentes contra una API imaginada; el admin frontend de Trámites usa `DetalleVersion`/`crearDocRequerido`/`SeccionLista`/`Accion`/`Badge kind=`, el types real es `tramites/types.ts` (no `lib/types.ts`), y los modales usan `{idVersion, doc/aprob, estados, onCerrar}` + `ModalShell titulo/onCerrar`. **Leer el archivo real ANTES de asumir la shape.**
