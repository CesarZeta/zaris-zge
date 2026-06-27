---
name: reference_tipo_tramite_sin_usuario_alta
description: tipo_tramite (catálogo) NO tiene id_usuario_alta/modificacion — solo fecha_alta/modificacion. Para distinguir seed vs custom se usa la columna es_sistema (mig 56).
metadata: 
  node_type: memory
  type: reference
  originSessionId: 506e05e6-fd53-4ed2-adbd-e34625d91b65
---

La tabla **`tipo_tramite`** (catálogo de tipos de trámite) **no tiene `id_usuario_alta` ni `id_usuario_modificacion`** — solo `fecha_alta` y `fecha_modificacion`. La mig 50 (`50_tramites_auditoria.sql`) agregó los campos de usuario SOLO a las 5 tablas de **instancias** (`tramite`, `tramite_movimiento`, `tramite_documento`, `tramite_firma`, `tramite_relacion`), NO al catálogo.

**Why:** en esta sesión asumí que podía distinguir "tipo creado por usuario" vs "tipo del seed" mirando `id_usuario_alta IS NULL`. Falso: la columna no existe en `tipo_tramite`. El `execute_sql` de `information_schema.columns` lo confirmó tras un `column does not exist`.

**How to apply:**
- Para distinguir seed vs custom usar **`tipo_tramite.es_sistema`** (BOOLEAN, mig 56): `TRUE` = precargado por `seed_tramites.py`, `FALSE` = creado por usuario desde el editor admin. El seed setea `es_sistema=TRUE`; el `POST /admin/tramites/tipos` lo deja en el default `FALSE`.
- Antes de codear "quién creó X" sobre cualquier tabla, **verificar con `execute_sql` que la columna de auditoría exista** — no asumir §10 completo. El proyecto-id correcto de Supabase es `lshfwsscvfsklrmbvkwl` (no confundir con otros que dan permission denied).
- Verifica drift como siempre: ver [[feedback_verificar_drift_completo_prod]].
