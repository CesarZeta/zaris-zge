---
name: feedback_verificar_trigger_existe_no_confiar_doc
description: CLAUDE.md afirma triggers/objetos de DB que pueden no existir en prod. Verificar pg_trigger/pg_proc antes de confiar.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 36788751-bb5e-4f15-9590-bd49e399b804
---

CLAUDE.md §18/§21 daban por existente el trigger `trg_nro_ot` (numeración `OT-YYYY-XXXXXX`), pero **no existía en prod** — por eso toda OT creada vía `POST /ot` y `/ot/con-agenda` quedaba con `nro_ot` NULL (el backend devolvía un fallback `OT-{id}` solo en la respuesta, nunca lo persistía). Lo creé en mig 59 (espejo de `fn_generar_nro_reclamo`) + backfill.

**Why:** la doc del proyecto describe objetos de DB (triggers, funciones, columnas con default) que pueden ser drift — documentados pero nunca aplicados, o dropeados sin actualizar el .md. Es la misma clase de problema que [[feedback_verificar_drift_completo_prod]] pero para objetos de schema, no solo datos.

**How to apply:** antes de asumir que un trigger/función/constraint hace su trabajo, verificá su existencia:
`SELECT tgname, proname FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='tabla'::regclass AND NOT t.tgisinternal;`
Si el backend tiene un patrón `valor = row.x or fallback`, ese `or fallback` suele delatar que alguien ya sospechó que el trigger podía fallar — y el fallback no persiste. Caso real sesión 2026-05-25 (reclamos+OT en prod). Relacionado: [[project_supabase_estado_schema]].
