# verify-prod-schema

Preflight check: antes de codear backend que dependa de tablas/columnas, verifica que esas tablas/columnas existan en prod (Supabase) Y en local, y que tengan los datos mínimos esperados. Detecta divergencias local↔prod **antes** de pushear.

## Cuándo usar

Invocar al inicio de cualquier tarea que vaya a:
- Agregar/modificar un endpoint backend que lee una columna específica.
- Crear seeds o lógica que asume filas existentes.
- Aplicar una migración con `ALTER TABLE ... ADD COLUMN`.

**Especialmente útil** cuando uno se acuerda de "lo arreglé en local hace un par de sesiones" sin commit de migración formal.

## Cómo invocar

`/verify-prod-schema tabla:agentes columns:es_auditor,id_usuario rows:>=1`

Argumentos (todos opcionales pero usar al menos uno):
- `tabla:<nombre>` — la tabla a verificar.
- `columns:<col1,col2,...>` — columnas que voy a referenciar en código.
- `rows:<expr>` — expectativa de filas activas (`>=1`, `>0`, `=N`).

Si paso varias tablas: `tablas:agentes,equipos,equipo_agentes`.

## Pasos que ejecuta

1. **Local** (psql via script Python o `Bash psql`): verificar que la tabla existe, listar columnas, contar filas activas.
2. **Prod** (Supabase MCP `execute_sql`): verificar lo mismo.
3. **Comparar**:
   - Si columnas locales ⊃ columnas prod → flag "columna falta en prod, crear migración".
   - Si filas activas local > 0 y prod = 0 → flag "datos solo en local, considerar seed prod".
   - Si tabla no existe en prod → flag bloqueante "crear migración antes de codear".
4. **Reportar** una tabla resumen:
   ```
   tabla       | columna       | local | prod | acción
   ------------|---------------|-------|------|--------
   agentes     | es_auditor    | ✓     | ✗    | crear migración 30
   agentes     | id_usuario    | ✓     | ✓    | OK
   agentes     | (filas)       | 3     | 0    | seedear prod o aceptar vacío
   ```

## Patrones SQL

**Existencia de tabla:**
```sql
SELECT to_regclass('public.<tabla>') AS existe;
```

**Existencia de columnas:**
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name='<tabla>' AND column_name IN ('col1','col2');
```

**Conteo de filas activas:**
```sql
SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE activo) AS activas
FROM <tabla>;
```

## Reglas

- **No** auto-aplicar migraciones — solo reportar y dejar que el usuario decida.
- **No** seedear datos automáticamente — solo flag "considerar seed".
- Si solo verifico **una** tabla con `to_regclass`, es 1 query — inline, no slash command.

## Lecciones del proyecto que motivan esta skill

Ver `feedback_aprendizajes_proyecto.md` A3 + E4 + E5:
- 2026-05-10: backend `/ot/auditor/me` referenciaba `agentes.es_auditor` que existía solo en local. Detectado por casualidad.
- 2026-05-10: `agentes` vacío en prod hizo que las mesas Agente/Auditoría queden inútiles silenciosamente tras deploy.
