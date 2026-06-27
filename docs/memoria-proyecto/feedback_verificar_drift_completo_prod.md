---
name: verificar-drift-completo-prod
description: "Antes de codear backend que INSERTe, verificar en prod no solo existencia de columnas sino también CHECK constraints, defaults, y seeds dependientes. Sesión 2026-05-12 cazó 3 drifts en una sola pasada."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 83e325ac-8a2f-40d1-9474-e4ae554eba9e
---

**Regla:** la verificación previa a codear backend con `execute_sql` en prod (CLAUDE.md §24) tiene que cubrir TRES dimensiones del schema, no solo una:

1. **Existencia** de tablas/columnas (lo más básico, ya hecho rutinariamente).
2. **NOT NULL + defaults**: lo que local resuelve con `DEFAULT TRUE` puede no estar en prod. El backend `INSERT INTO tabla (col_a, col_b) VALUES (...)` que omite `activo` confiando en su default fallará con 500.
3. **CHECK constraints**: prod puede tener constraints que local no tiene. Caso real: `ciudadanos_sexo_check` solo en prod requiere `'HOMBRE'|'MUJER'|'OTROS'` uppercase; local acepta cualquier string.
4. **Seeds dependientes**: tabla creada ≠ tabla con seeds. Caso real: `municipios`/`estado_evento`/`estado_reserva` creadas vacías en prod aunque las migs 30+31 incluían los INSERTs (probablemente los inserts no corrieron por algún error que pasó silencioso o las tablas se crearon en otra pasada).

**Why:** sesión 2026-05-12 al hacer E2E del autoservicio en prod cacé los 3 tipos de drift en una sola tarde. Cada uno costó un round-trip de debugging (HTTP 500 → logs Supabase → diagnóstico → fix → push → esperar redeploy Railway) que un `execute_sql` de 5 segundos antes de pushear hubiera evitado.

**How to apply:** antes de pushear código que toque INSERTs nuevos a tablas en prod, correr este pack de queries via MCP:

```sql
-- 1. Existencia
SELECT to_regclass('public.<tabla>') AS existe;

-- 2. NOT NULL + defaults sobre las columnas que el INSERT omitirá
SELECT column_name, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_name='<tabla>'
   AND column_name IN ('activo', '<col_que_omitire>');

-- 3. CHECK constraints sobre columnas con valores enumerados
SELECT conname, pg_get_constraintdef(oid)
  FROM pg_constraint
 WHERE conrelid='<tabla>'::regclass AND contype='c';

-- 4. Seeds del catálogo que mi INSERT referencia (FK)
SELECT COUNT(*) FROM <catalogo> WHERE activo;
```

Si encuentras drift, aplicar mig de fix ANTES de pushear el código que asume la nueva forma del schema.

Ver también: CLAUDE.md §24 (workflow de seed) y §21 (estado de migraciones — mig 36 documenta el caso `agenda activo defaults`).
