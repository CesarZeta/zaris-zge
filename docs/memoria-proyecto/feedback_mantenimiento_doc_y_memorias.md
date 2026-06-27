---
name: mantenimiento-de-claude-md-y-memorias
description: "Cómo mantener la documentación del proyecto sin que infle ni se desactualice — separar bitácora de reglas, límite de MEMORY.md, archivar histórico, podar la bitácora de sesiones."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 05f2fbdc-1292-4c15-84d1-a6a2e99dadab
---

La documentación del proyecto (CLAUDE.md + memorias) crece sin control si nadie la poda. Patrón de mantenimiento aplicado el 2026-05-26.

**Por qué:** CLAUDE.md llegó a 271 KB / 3052 líneas mezclando reglas vigentes con bitácora histórica de migraciones ya aplicadas. `MEMORY.md` superó su límite y se cargaba parcialmente. `project_estado_sesion_y_pendientes.md` acumuló 36 secciones "Última sesión" (136 KB). Todo eso es ruido que tapa lo accionable.

**Criterios (cómo aplicar):**

- **Separar bitácora de regla.** Una *regla* dice qué hacer siempre ("usar `s.id_area`, no `r.id_area`"). Una *bitácora* dice qué pasó una vez ("mig 27 aplicada el X, snapshot en `_backup_...`"). Las reglas van en CLAUDE.md; las bitácoras van en `HISTORIAL_MIGRACIONES.md` (raíz del repo). Cuando una sección mezcla ambas (caso §27 Agenda), condensar dejando solo las reglas + un puntero al historial.
- **`MEMORY.md` debe quedar bajo ~24 KB** o se carga parcialmente (el índice de memoria desaparece a medias). Cada entrada <200 chars. **Para recuperar bytes, en este orden:** (1) borrar pointers de memorias OBSOLETAS/superadas (el archivo se borra también); (2) **consolidar redundantes** — fusionar 2-3 entradas que dicen casi lo mismo en una, conservando los archivos (recall los encuentra); (3) recién después acortar descripciones. Limar descripción byte-a-byte rinde poquísimo (los acentos son 2 bytes UTF-8) e induce errores de "alargué en vez de acortar" — verificar el tamaño tras CADA edición. NO borrar el archivo de una memoria con conocimiento vigente, solo su pointer del índice si se consolidó en otra. Apuntar a ~28 bytes de holgura, no al filo.
  - **Si vas a acortar muchos hooks, reescribí el índice ENTERO con Write, NO con Edits hook-por-hook.** Cada Edit individual rinde ~10-15 bytes y son docenas de llamadas; peor, es fácil pasar un `new_string` que solo agrega `\n` al final → **alargás en vez de acortar** (cazado 4× en la sesión 2026-06-01). Un solo Write con todos los hooks ya recortados bajó 25785→24761 de un saque. Hacé los Edits puntuales solo para los 2-3 hooks más largos que queden después del Write.
  - **La palanca de fondo cuando ya no hay redundantes que fusionar: recortar el HOOK del índice, que es opcional.** El recall NO usa la línea de MEMORY.md — usa la `description:` del frontmatter de cada archivo (son textos independientes; verificado en la sesión 2026-06-01: varias entradas tienen hook ≠ description). La línea del índice solo necesita: un **título reconocible** + el **slug** para encontrar el archivo. El texto tras "—" es contexto de lujo. Donde el hook repite lo que ya dice el título (`[Verificar siempre antes de opinar] — nunca asumir; contrastar...`), recortalo o borralo: no degrada recall y recupera ~1-2 bytes/línea × 149. Así bajé 24388→23714 (de 12 a 686 bytes de holgura) sin tocar ningún archivo de memoria ni `[[link]]`.
  - **Palancas que NO conviene usar:** (a) *fusionar el cluster "verificar"* (12 entradas) — coinciden en el slug pero los temas son distintos (drift de DB, runtime de agente, CHECKs, env vars, firmas de api.ts…); fusionar pierde granularidad de recall. (b) *renombrar slugs largos* — rompe decenas de `[[wikilinks]]` entrantes y desincroniza el `name:` del frontmatter; alto riesgo, bajo rinde. A ~149 entradas, ~6,5 KB del índice (27%) son slugs+sintaxis de link, irreducibles sin renombrar.
- **`project_estado_sesion_y_pendientes.md` se poda**: conservar pendientes + las ~2 últimas sesiones en detalle; comprimir las anteriores a 1 línea en "Histórico breve". No acumular "Última sesión" indefinidamente.
- **No renumerar secciones de CLAUDE.md** (hay huecos §8/§16/§25 históricos) — hay cientos de referencias `§N` cruzadas que se romperían. La numeración estable vale más que la prolijidad.
- **`feedback_aprendizajes_proyecto.md` NO se poda** — su redundancia con CLAUDE.md es por diseño (vista temática consolidada para releer al inicio). Es un solo archivo, no infla el índice.

**Checklist al CERRAR una sesión que tocó schema/forms/CRUD** (la doc desactualizada hace daño activo — caso 2026-05-26: §21 decía "usar 61+" cuando ya existían 61-64, una sesión futura habría reusado el número):
- **§21 estado de migraciones:** subir el rango "20-N", actualizar "mig nueva debe usar N+1", sumar las migs nuevas a "YA existen en prod". El detalle por mig va a `HISTORIAL_MIGRACIONES.md`, no a §21.
- **§15 tablas configuradas de admin_tablas:** reflejar tabla agregada/quitada/read-only.
- **Sección del módulo tocado:** bloque `> **Rediseño YYYY-MM-DD:**` con el qué-hace-ahora (no bitácora línea por línea).
- Antes de editar CLAUDE.md hay que **Read** el archivo (la tool lo exige aunque ya esté en el system-prompt).

**Chequeos extra de la pasada 2026-06-10 (sumarlos a toda sesión de mantenimiento):**
- **Memorias huérfanas:** cruzar archivos en disco vs pointers de MEMORY.md (script PS con `Compare-Object`). Una memoria sin pointer es invisible entre sesiones; resolverla por fusión en una canónica indexada (preferido) o indexándola. La pasada encontró 8.
- **Memorias fantasma:** los `[[nombre]]` citados desde CLAUDE.md deben existir. Si una se cita varias veces sin archivo (caso `feedback_columna_nueva_auditar_todos_los_select`, citada 4×), CREARLA consolidando lo que CLAUDE.md dice inline — es load-bearing. Un dangling citado 1× desde una memoria se tolera (marca "a escribir").
- **Wikilinks malformados:** buscar variantes `[[x.md]]` (sufijo), `[[con-guiones]]` (vs guion_bajo del archivo) y alias sin prefijo `feedback_`/`reference_`.
- Al fusionar memorias, **redirigir los links entrantes** (grep del slug en memoria + repo) y actualizar las refs en CLAUDE.md/HISTORIAL/skills en la misma sesión.

**Cómo verificar al terminar:** numeración de `## N.` sin saltos nuevos, todos los `[[wikilinks]]` apuntan a memorias existentes, sin referencias colgantes a secciones archivadas, tablas markdown balanceadas, `wc -c MEMORY.md` < 24400.

Relacionado: [[feedback_diff_claude_md_acumulado]] (leer el diff entero al commitear CLAUDE.md), [[reference_gh_pages_publica_todo_lo_commiteado]] (HISTORIAL_MIGRACIONES.md queda público — no tiene secretos, es seguro).
