---
name: feedback_columna_not_null_sin_default
description: Columnas NOT NULL sin DEFAULT en tablas admin_tablas causan INSERT 500 cuando el campo no es requerido en el form frontend — patrón de detección y fix doble
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e7b5da85-1482-4943-b52c-9c40bbde7b8d
---

Cuando una columna de una tabla administrada por `admin_tablas` es `NOT NULL` en la DB pero no tiene `DEFAULT` y no está marcada como `required: true` en el SCHEMAS del frontend, el INSERT falla con 500/400 porque el backend envía `null` para ese campo y asyncpg lo rechaza.

**Caso real sesión 2026-05-17:** `servicios.capacidad_agentes NOT NULL` sin DEFAULT. El form no lo marcaba como required, el usuario podía dejarlo vacío, y el INSERT explotaba.

**Fix doble (ambos necesarios):**
1. **DB:** `ALTER TABLE <tabla> ALTER COLUMN <col> SET DEFAULT <valor>;` — aplicar en local Y prod.
2. **Backend `crear()`:** excluir `None` del dict del INSERT (`{k: v for k, v in body.items() if k in allowed and v is not None}`) para que la DB aplique el DEFAULT. Sin esto, el backend envía `null` explícito y Postgres rechaza incluso con DEFAULT definido.

**Why:** el `crear()` original incluía los `None` en el INSERT, anulando cualquier DEFAULT de la columna. El fix en backend es generalizable — ahora todos los INSERTs a través de admin_tablas respetan los DEFAULTs de la DB.

**How to apply:** antes de agregar una tabla a admin_tablas, verificar que todas las columnas en `cols[]` que no sean `required: true` en el frontend tengan DEFAULT en la DB. Si no tienen DEFAULT, o se agrega el DEFAULT o se marca el campo como required en el SCHEMAS.

**Comando de verificación:**
```sql
SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = '<tabla>'
  AND column_name = ANY(ARRAY['col1','col2','col3']);
```
