---
name: feedback-apply-migration-parcial-aborta-todo
description: "apply_migration corre en una transacción; si un statement falla, TODO el script se revierte aunque otros statements ya \"pasaron\""
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ab06eddc-2f01-4047-a0bd-b830bc546a2d
---

`mcp__claude_ai_Supabase__apply_migration` (y cualquier multi-statement en una sola transacción) es **atómico**: si un statement falla, se revierte el script entero. No quedan aplicados "los que pasaron antes".

**Why:** Caso real 2026-05-28 (mig 69). El script tenía `CREATE TABLE agente_novedad` + `INSERT INTO configuracion_general`. El INSERT falló (faltaban columnas NOT NULL `tipo`/`activo`). Asumí que el CREATE TABLE sí había quedado y solo reintenté el INSERT a mano. Pero el rollback se llevó el CREATE TABLE también. La tabla NO existía en prod. El backend nuevo (`disponibilidad_efectiva` la consulta) tiró **500 en todos los `/slots`** — y costó un rato de debugging porque `/recursos` (que no toca esa tabla) sí andaba, y local andaba (ahí la mig se aplicó por psql que sí completó). El body del 500 venía vacío (FastAPI debug=False), no apuntaba a la tabla.

**How to apply:**
- Tras un `apply_migration` que devuelve error, NO asumas que parte se aplicó. Verificá con `to_regclass('public.tabla')` / `information_schema.columns` qué quedó realmente, y re-aplicá el script COMPLETO (es idempotente con `IF NOT EXISTS`), no solo el statement que falló.
- Si un backend nuevo depende de una tabla/columna de una migración recién aplicada y da 500 con body vacío en prod pero anda en local: **primer sospechoso = la migración quedó a medias en prod**. Replicá el query del service directo con `execute_sql` para cazar el `relation ... does not exist`.
- Espeja [[feedback_verificar_drift_completo_prod]] y la regla §24: verificar el estado REAL del schema en prod, no confiar en "ya lo apliqué".
