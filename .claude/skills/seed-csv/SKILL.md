---
name: seed-csv
description: Receta para escribir scripts de seed de catálogos desde los CSVs de Tablas Iniciales/ (subáreas, tipos de reclamo, agentes, cargos, ciudadanos, actividades, nacionalidades). Usar al crear o modificar un backend/seed_*.py, poblar tablas desde CSV, o cargar catálogos en local/prod. Cubre idempotencia, encoding en Windows, resolución de IDs por nombre entre entornos, inspección previa del CSV y mapping de IDs legacy. NO cubre la regla de verificar drift en prod con execute_sql (esa vive en CLAUDE.md §24 porque aplica a TODO backend, no solo seeds).
---

# Workflow de seed desde CSVs en `Tablas Iniciales/`

Los CSVs en `Tablas Iniciales/` son la **fuente autoritativa** de catálogos. Recetas para escribir scripts de seed.

## Idempotencia obligatoria
Todo seed debe poder correrse múltiples veces sin duplicar ni romper. Patrón:
1. Soft-delete (`activo=FALSE`) lo activo previo.
2. Para cada row del CSV: buscar por nombre (case-insensitive, trim) — si existe, `UPDATE activo=TRUE` + actualizar campos. Si no, `INSERT`.
3. Soft-delete entidades padre que quedaron huérfanas tras el seed.

Patrón mínimo reforzado:
1. **Dedupe sobre lo existente, no por contador**: leer `SELECT key FROM tabla` al inicio y descartar filas del CSV cuya key ya esté en DB. Anti-patrón: `if existing > 0: return` (lo que hace `seed_inicial.py` — se saltea TODO si hay 1 fila, incluso si faltan 499).
2. **`--confirm-prod` flag** cuando la conexión apunta a Supabase. Default a local.
3. **`--limite N`** parametrizable. No hardcodear 500/1000 en el código.
4. **Defaults compatibles con prod**: pasar **siempre** todos los campos NOT NULL aunque tengan default — el default puede no existir en prod aunque sí en local.

Ejemplos canónicos: `backend/seed_ciudadanos_csv.py` y `backend/seed_agentes_csv.py`.

## Encoding
- Lectura del CSV: `open(path, encoding="utf-8-sig")` (incluye BOM removal).
- Output del script en Windows: setear `$env:PYTHONIOENCODING="utf-8"` antes de correr Python, sino `cp1252` rompe en `print` con caracteres unicode (✓, →, ñ, tildes).
- Evitar caracteres unicode decorativos (━, →, ❌) en `print()` de scripts; usar ASCII (`-`, `->`, `[FAIL]`).

## NO hardcodear IDs entre entornos
Local y prod tienen IDs distintos para las mismas entidades (ej: en local `id_area=1` puede ser "Salud" mientras en prod es "Gobierno"). Resolver siempre **por nombre** dentro del script con `conn.fetchrow`:

- SQL: `SELECT id_area, activo FROM area WHERE LOWER(nombre) LIKE <ph> ORDER BY activo DESC, id_area LIMIT 1` — donde `<ph>` es el placeholder posicional de asyncpg (dólar + número: el primero es dólar-uno).
- Param: `"%gobierno%"`.
- Lógica: si existe → reactivar (`activo=TRUE`); si no → crear.

Esto vale para áreas, tipos de usuario, cargos, nacionalidades, actividades — cualquier catálogo cuyos IDs no estén garantizados estables entre entornos.

## Aplicar en local Y prod en la misma sesión
Una migración aplicada solo en uno desincroniza los entornos. Si aplicaste en prod via MCP, corré también el script en local (o viceversa) antes de cerrar la tarea. Documentar el paso en el commit.

## Backup antes de operaciones destructivas en prod
Para `UPDATE`/`DELETE` masivos en prod: snapshot previo en tabla `_backup_<tabla>_YYYY_MM_DD`. Permite revert manual sin necesidad de point-in-time recovery.

## Antes de codear un seed, inspeccionar el CSV
Los CSVs en `Tablas Iniciales/` no son confiables ciegamente:
- Pueden estar **mal/duplicados**: `agente.csv` era idéntico a `cargo.csv` hasta 2026-05-12 (cargos por área, NO personas). Si el script lo usaba para insertar agentes, hubiera creado basura.
- Pueden estar **vacíos** o tener columnas distintas a las esperadas.
- Pueden referenciar IDs legacy que no existen en otros CSVs.

**Antes de escribir el seed, mirar:**
```bash
head -3 "Tablas Iniciales/<nombre>.csv"     # columnas reales + sample
wc -l    "Tablas Iniciales/<nombre>.csv"     # ¿está vacío?
```

Si los datos no son lo que esperabas, **avisar al usuario inmediatamente** en lugar de improvisar mapeos. Los CSVs reales los conoce el municipio; un placeholder mal hecho es deuda nueva.

## CSVs y mapping de IDs legacy
- Los CSVs traen IDs del sistema legacy (ej: `id_area_servicio=6361`) que **no se usan** en la DB nueva. El mapeo es por nombre.
- Los CSVs pueden tener referencias a IDs huérfanos (ej: `tipo_reclamo.id_area_servicio=7984` que no está en `subarea.csv`). Inferir nombres del contenido de los tipos que las usan, agregar como subáreas extra.
- `subarea.csv` viene con `id_area=1` genérico. La asignación real de área se hace por **heurística por keyword** sobre el nombre de la subárea (ver `seed_subareas_tipos_csv.py`).
- **Agentes con cargo huérfano:** si el `id_cargo` legacy no matchea con `cargo.csv` y no hay info real, NO inventar nombre de cargo. Distribuir entre cargos genéricos (id 1-5: Director/Coordinador/Técnico/Administrativo/Operario) via hash determinístico de `apellido||nombre` para que sea reproducible.

## Scripts de seed disponibles
| Script | Tablas | Origen |
|---|---|---|
| `seed_geo_argentina.py` | provincias, partidos, localidades | hardcoded AR |
| `seed_subareas_tipos_csv.py` | subarea, tipo_reclamo | `Tablas Iniciales/*.csv` |
| `seed_activos_local.py` | tipos_activo, activos | `Tablas Iniciales/Activos.csv` |
| `seed_ciudadanos_csv.py` | ciudadanos | `Tablas Iniciales/ciudadano.csv` |
| `seed_agentes_csv.py` | agentes | `Tablas Iniciales/agente.csv` + `cargo.csv` |
| `seed_auth.py` | usuarios | hardcoded dev |
| `seed_demo.py` / `seed_prod.py` | varios | hardcoded mínimo |

> **CRÍTICO antes de codear cualquier seed/backend**: verificar el estado real de prod (existencia + NOT NULL + DEFAULT + CHECKs + seeds) con `execute_sql`, NO confiar en la doc ni en la simetría con local. Detalle y casos reales en CLAUDE.md §24 + [[feedback_verificar_drift_completo_prod]].
