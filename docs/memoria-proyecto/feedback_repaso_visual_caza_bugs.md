---
name: repaso-visual-caza-bugs
description: "Cuando el backlog formal esta vacio, repasar un modulo end-to-end en navegador. Saca pendientes nuevos REALES (bugs UX que typecheck/tests no capturan)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 27c74ea3-2e69-4115-a25a-69ddf39a7d17
---

Cuando el usuario pregunta "que sigue?" y el backlog formal esta vacio, ofrecer **repaso visual de un modulo completo en navegador** como opcion. No es solo "matar tiempo" — produce pendientes reales.

**Why:** sesion 2026-05-15 repaso 4 modulos (Reclamos, OT, Turnos, Entradas) y cazo **5 bugs UX reales que typecheck + tests no detectaban**:
- `area_nombre` con guion espureo en ListView de Reclamos (JOIN mal en backend).
- `<select>` con 4 agentes que en prod son 84 (PlanificadorOT).
- Mismo patron en TurnoFormModal.
- RecursoPicker no reseteaba input al cambiar tipo.
- Drift local de "Servicios Publicos" con tildes vs sin tildes.

Ninguno de estos los habria visto solo leyendo codigo o corriendo smoke tests. Hay que ABRIR el modulo en navegador y caminar el flujo del usuario.

**How to apply:**
- Antes de proponer repaso, asegurate de que el backlog formal esta vacio (no robar tiempo a trabajo real).
- Caminar todos los puntos de entrada: lista, alta, edicion, accion principal (cumplir/cancelar/asignar), flujo publico si tiene.
- Crear datos demo SI hace falta para probar (memoria `feedback_seedear_cuando_mesa_vacia`), limpiarlos al cierre.
- En cada paso, **buscar inconsistencias visuales**: caracteres espureos, etiquetas vacias, selects largos, redirects inesperados. No te quedes con "compila y devuelve 200".
- Cuando encuentres un bug, NO te quedes en uno solo: cuando estas dentro del modulo es el mejor momento para barrerlo entero.

**Patron repetido a buscar:** un bug que aparece en un modulo (ej. select largo de agentes) muchas veces esta replicado en otros 3 modulos. Cuando lo arregles en uno, busca el patron en los demas.
