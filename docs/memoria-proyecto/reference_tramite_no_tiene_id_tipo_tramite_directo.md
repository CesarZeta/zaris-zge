---
name: reference-tramite-no-tiene-id-tipo-tramite-directo
description: La tabla tramite NO tiene id_tipo_tramite directo. Para llegar al tipo va via id_tipo_tramite_version → tipo_tramite_version → tipo_tramite. JOIN doble obligatorio.
metadata: 
  node_type: memory
  type: reference
  originSessionId: e77756f2-e217-4421-a18c-df927d47dfb5
---

`tramite` tiene `id_tipo_tramite_version` (FK a `tipo_tramite_version`), NO `id_tipo_tramite`. Esto es a propósito: trámites instanciados quedan vinculados a la versión publicada al momento de su creación; cambios futuros del tipo no los afectan.

**Para llegar al `tipo_tramite` desde un `tramite`:**

```sql
SELECT tt.nombre, tt.codigo, ttv.version_num
  FROM tramite t
  JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
  JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite
 WHERE t.id_tramite = :tid
```

**Anti-patrón** (rompe con UndefinedColumnError, perdí 1 round de debug en sesión 2026-05-18):
```sql
JOIN tipo_tramite tt ON tt.id_tipo_tramite = t.id_tipo_tramite  -- NO existe esa columna
```

Patrón canónico ya usado en `routes/tramites.py::_cargar_tramite_dict` y `_tramite_detalle_out` — revisar esos si vas a escribir queries nuevas.
