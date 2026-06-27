---
name: fks-entrantes-son-alcance
description: "Antes de dropear una tabla, listar TODOS los FKs entrantes desde tablas que sobreviven — son alcance oculto, no opcional. Caso real mig 39 (areas legacy)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7b42a67a-8e3a-4a5a-ab72-3649c0ac5106
---

Cuando vas a dropear una tabla legacy, los FKs **salientes** son obvios (los ves en el schema de la tabla a dropear). Los FKs **entrantes** desde tablas que sobreviven son el alcance que te toma por sorpresa.

**Regla:** antes de armar el plan, listar todo entrante con:

```sql
SELECT tc.table_name AS desde, kcu.column_name AS col,
       ccu.table_name AS hacia, ccu.column_name AS hacia_col
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND ccu.table_name IN ('tabla1', 'tabla2', ...);  -- las que van al drop
```

Cada FK entrante desde una tabla que NO se va al drop te obliga a una decisión: (a) limpiar la columna a NULL antes de dropear, (b) re-puntar a una tabla canónica, (c) dropear la columna también, (d) dropear la tabla emisora también.

**Por qué:** la doc del proyecto puede haber mencionado solo los FKs internos del cluster que se elimina y haberse olvidado del exterior. CASCADE en el DROP "funciona" pero deja columnas zombie con datos huérfanos.

**Caso real (mig 39, 2026-05-13):**
- Plan inicial: dropear 9 tablas legacy de Agenda (incluyendo `areas` plural).
- Lo que el plan no dijo: `lugares_atencion.id_area`, `servicios.id_area` y `agenda_clase.id_area` apuntaban a `areas`. Si dropeaba con CASCADE sin limpiar, las 3 tablas quedaban con columnas `id_area` poblando IDs que ya no existían (DBs reciben CASCADE distinto: en PG el DROP TABLE CASCADE sí dropea los FKs pero no limpia las columnas, te quedan integers huérfanos).
- Decisión que sumó al alcance: `UPDATE ... SET id_area = NULL` en las 3 tablas, drop FKs explícito, después drop tabla.

**Heurística:** si el listado entrante toca ≥1 tabla viva, **siempre pedí decisión al usuario** ("¿qué hacemos con id_area en lugares_atencion?") antes de avanzar. No asumas. Caso típico: el plan ahorra 50% del trabajo si el usuario dice "dropea la columna entera"; el plan se duplica si dice "mapeala a la tabla canónica nueva".

Relacionado: [[feedback_verificar_drift_completo_prod]] (mismo espíritu, otro foco: defaults y CHECKs).
