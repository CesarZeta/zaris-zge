---
name: verificar-check-antes-de-codear-selects
description: "Antes de exponer un valor en un `<select>` o `<option>` de UI (estado, prioridad, canal, sexo, etc.), verificar el `CHECK` constraint en prod via `pg_constraint`. La doc puede mentir; el contrato real es la DB."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0897cd7-1f6d-48cb-8ad7-2a9362f457e8
---

**Regla:** ningún valor de UI que vaya a un campo con CHECK en DB se agrega sin antes correr un query como:

```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'tabla'::regclass AND contype = 'c';
```

Aplica especialmente a: prioridad, estado, sexo, canal_origen, doc_tipo, tipo_recurso, asignacion_a, tipo_qr, y cualquier enum implícito que el backend modele con VARCHAR + CHECK.

**Why:** Caso real sesión 2026-05-12. Introduje `'Crítica'` en `type Prioridad` de Reclamos asumiendo que era un valor común. `reclamos_prioridad_check` en prod solo acepta `Alta|Media|Baja`. Cualquier alta/edición con 'Crítica' explota con `IntegrityError` desde asyncpg. El vanilla ya sabía esto (sus 3 selects solo expusieron los 3 valores) — la falla fue mía por no chequear. Costó:
- 1 smoke API fallido
- 1 commit de fix (`4efcacb`)
- Una memoria `[[reference_reclamos_prioridad_check]]` nueva

**How to apply:**
1. Antes de definir un `type Foo = 'a' | 'b' | 'c'` que represente valores de DB, correr la query del CHECK.
2. Si el CHECK no existe pero el campo lo manejaba el backend con un enum implícito, igual buscar el set permitido — `grep -rn "Field(..., pattern=" backend/app/schemas/` o el equivalente del validador.
3. Si querés agregar un valor nuevo, primero migración del CHECK (en local Y prod), después el frontend. NO al revés.

Complementa [[feedback_verificar_drift_completo_prod]]: ese caza drift entre local↔prod, este caza drift entre código↔CHECK.

**Ejemplos de CHECKs vivos en prod (verificados 2026-05-12):**
- `reclamos_prioridad_check`: `(Alta, Media, Baja)`
- `reclamos_estado_check` / `ck_reclamo_estado`: `(Sin asignar, En gestión, En espera, En auditoría, Resuelto, Cancelado)` con tildes.
- `ciudadanos_sexo_check`: `(HOMBRE, MUJER, OTROS)` UPPERCASE (caso real previo cazado).
- `tipo_reclamo_asignacion_a_check`: `(agente, equipo)` lowercase.

Verifica antes de tocar cualquiera de estos campos.
