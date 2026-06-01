# run-migration

Aplica una migración SQL pendiente en la base de datos. Soporta local (`zaris_dev`) y producción (Supabase).

## Uso

```
/run-migration <archivo_sql>
```

Ejemplos:
- `/run-migration backend/migrations/38_permisos_por_modulo.sql` — aplica la mig 38
- `/run-migration` — lista migraciones del directorio `backend/migrations/` y pregunta cuál aplicar

## Descubrir migraciones pendientes

Antes de elegir qué aplicar, comparar con lo ya aplicado en prod:

```
mcp__claude_ai_Supabase__list_migrations
```

Y para local, listar `backend/migrations/*.sql` ordenado por número. Las migraciones que están en disco pero no en `list_migrations` (o no aplicadas a la DB local via algún ledger informal) son las candidatas.

Para chequeos puntuales (¿la tabla X existe? ¿la columna Y existe?), CLAUDE.md §24 documenta los comandos canónicos:
- `SELECT to_regclass('public.<tabla>')` — existencia
- `information_schema.columns WHERE table_name=...` — columnas + defaults + NOT NULL
- `pg_constraint WHERE conrelid='<tabla>'::regclass` — CHECKs

## Estado actual (verificado CLAUDE.md §21)

Migraciones 20-38 ya aplicadas en local y prod al 2026-05-12. Si surge una mig nueva (39+), este comando es el flujo para aplicarla. La sección "Migraciones pendientes" se mantiene **vacía** a propósito — confiar en `list_migrations` Supabase + `git status backend/migrations/` antes que en una lista hardcodeada en doc.

## Pasos

1. Leer `backend/.env` o `backend/.env.local` para obtener `DATABASE_URL`.
2. Confirmar con el usuario si aplicar en LOCAL o PROD (Supabase). Para PROD, usar `mcp__claude_ai_Supabase__apply_migration`.
3. Si el SQL tiene **múltiples statements** (caso típico de migraciones nuevas), aplicar via `raw_connection().driver_connection.execute(sql)` o `apply_migration` MCP — `AsyncSession.execute(text(sql))` falla por límite asyncpg (CLAUDE.md §5).
4. Verificar con un `SELECT` mínimo que el cambio quedó (existencia de tabla/columna/seed).
5. Reportar resultado.

## Notas

- Siempre usar `CREATE TABLE IF NOT EXISTS` — las migraciones deben ser idempotentes.
- Toda tabla nueva debe tener los campos estándar de sección 10 del CLAUDE.md.
- Si la tabla referencia `usuarios`, verificar que la tabla `usuarios` exista primero.
- Nunca aplicar migraciones destructivas (DROP, ALTER COLUMN que borre datos) sin confirmación explícita del usuario.
