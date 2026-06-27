---
name: check-not-valid-se-evalua-al-update
description: "Un CHECK agregado NOT VALID igual se evalúa al UPDATE de una fila existente; NOT VALID solo evita la validación retroactiva al crear el constraint, no protege updates posteriores."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 870f8174-fc97-4e8a-808b-d61e2f49963d
---

Agregar un CHECK con `NOT VALID` a una tabla con datos NO exime a las filas viejas para siempre: **solo evita validarlas en el momento de crear el constraint.** En cuanto tocás una fila vieja con un `UPDATE`, Postgres evalúa el CHECK sobre la fila resultante y aborta si no cumple — aunque el `UPDATE` no toque las columnas del CHECK.

**Why:** sesión 2026-05-28 (mig 71, módulo Turnos/prestaciones). Agregué `ck_tipo_prestacion_recurso` (exactamente un recurso poblado) como `NOT VALID` porque las filas planas viejas de `tipo_prestacion` no tenían recurso. La migración pasó. Pero el seed que hacía `UPDATE tipo_prestacion SET activo=FALSE WHERE id_agente IS NULL AND id_espacio IS NULL` (para desactivar esas viejas) reventó con `CheckViolationError` — el UPDATE de cada fila vieja la obligó a cumplir el CHECK que justamente no cumplía.

**How to apply:** si vas a tocar (UPDATE/soft-delete) filas existentes que violan un CHECK recién agregado con NOT VALID, en el MISMO UPDATE poné las columnas en un estado que cumpla el CHECK. En el caso real: `UPDATE ... SET activo=FALSE, tipo_recurso='agente', id_agente=<primer_agente> WHERE id_agente IS NULL AND id_espacio IS NULL` (placeholder que satisface "exactamente un recurso"). Si no podés/querés backfillar, considerá `DELETE` físico de esas filas (cuando son demo sin valor y sin FKs entrantes vivas) en vez de soft-delete.

Relacionado: [[feedback_verificar_check_antes_de_select]] (grep el CHECK antes de tipar selects), [[feedback_apply_migration_parcial_aborta_todo]] (apply_migration atómico).
