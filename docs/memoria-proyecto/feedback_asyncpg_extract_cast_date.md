---
name: asyncpg-extract-cast-date
description: "Familia asyncpg + SQLAlchemy text() con params tipados: EXTRACT exige (:f)::date inline; INTERVAL exige make_interval(days=>:p) con CAST por bind dentro de CASE; body:dict exige convertir strings a date/time en Python. Cualquier :param::tipo o :param || 'literal' es sospechoso."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1a59de23-b5dc-4929-a71b-47033fecf69e
---

asyncpg pasa los parámetros de `text()` como `unknown` (no infiere el tipo desde Python) y NO castea strings a tipos temporales. Los atajos que funcionan en psql fallan en runtime. **Regla práctica: cualquier `:param::tipo` o `:param || 'literal'` dentro de `text()` es sospechoso — resolver el tipo en Python o usar funciones SQL (`make_interval`, `CAST(:p AS tipo)`).** Cuatro variantes cazadas:

## 1. EXTRACT / comparaciones con date (sesión 2026-05-13, `services/agenda.py`)

`EXTRACT(ISODOW FROM :fecha)` falla con `function pg_catalog.extract(unknown, unknown) is not unique` (SQLAlchemy lo traduce a `ProgrammingError`). Fix: cast inline **en cada referencia** del parámetro, no solo dentro de EXTRACT:

```sql
SELECT EXTRACT(ISODOW FROM (:f)::date) FROM tabla
WHERE (:f)::date BETWEEN col_desde AND col_hasta
```

## 2. INTERVAL parametrizado (2026-05-22, `encuestas_service.py`)

```sql
-- MAL: (:dias || ' days')::interval  → "expected str, got int"
-- BIEN:
NOW() - make_interval(days => :dias)   -- campos: years,months,weeks,days,hours,mins,secs
```

- `(:hasta::date + 1)` para fin de rango también rompe (el `::` sobre bind param confunde el parser). Calcular en Python: `params["hasta_excl"] = hasta + timedelta(days=1)` y comparar `< :hasta_excl`.
- **Dentro de un CASE, castear cada bind por separado, NO el CASE entero** (2026-06-01, `services/tramites/retencion.py`):
  ```sql
  make_interval(days => CASE WHEN x THEN CAST(:da AS integer) ELSE CAST(:dr AS integer) END)
  ```
  Castear el CASE entero da "expected str, got int"; sin cast, asyncpg infiere text.
- INTERVAL con duración variable en f-string literal también vale (§38 lo usa).

## 3. Endpoints `body: dict` con columnas date/time (2026-05-14, `POST /ot/con-agenda`)

Sin schema Pydantic no hay coerción: los strings del JSON llegan tal cual y asyncpg falla con `DataError: 'str' object has no attribute 'toordinal'`. Convertir explícito antes del query:

```python
try:
    f = date.fromisoformat(str(body["fecha"]))
    hi = time.fromisoformat(str(body["hora_inicio"]))
except ValueError as e:
    raise HTTPException(422, f"Formato de fecha/hora invalido: {e}")
```

Preferible: schema Pydantic en endpoints nuevos; si ya existe con `dict` (varios de OT), convertir al menos las temporales.

## 4. UUID

`:token::uuid` parsea mal → `CAST(:token AS uuid)`. Detalle en [[feedback_sqlalchemy_cast_uuid]].

## 5. Filtro opcional `(:p IS NULL OR col = :p)` → AmbiguousParameterError (2026-06-10, `routes/emergencias.py`)

El patrón clásico de filtro opcional falla con `AmbiguousParameterError: no se pudo determinar el tipo del parámetro $1` — la PRIMERA aparición del param es el `IS NULL` y asyncpg no puede tipar desde ahí (la comparación posterior contra la columna no alcanza). Fix: castear la aparición del `IS NULL`:

```sql
WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
  AND (CAST(:id_subarea AS integer) IS NULL OR t.id_subarea = :id_subarea)
  AND (CAST(:q AS text) IS NULL OR col ILIKE '%' || :q || '%')
```

Es el mismo quirk del `CAST(:q AS text) IS NULL` de `/tramites/destinatarios` (§35). **Todo endpoint nuevo con filtros opcionales nullable nace con el CAST** — los 7 endpoints de catálogo de Emergencias fallaron 500 en el primer smoke por esto.

**Las queries VIEJAS también lo cargan**: `reprogramar_turno` (turnos.py, query de solapamiento `(:io IS NULL OR id_ocupacion <> :io)`) estuvo 500 SIEMPRE desde mig 70/71 sin que nadie lo notara, hasta que el informe QA externo lo reportó como "Failed to fetch" (2026-06-11; el 500 sin headers CORS se ve así en el browser). Si un usuario reporta "Failed to fetch" en una mutación, grep `IS NULL OR` en la ruta ANTES de sospechar red/CORS. Ojo: `mi-bandeja` de trámites usa `(:mun IS NULL OR ...)` sin CAST y FUNCIONA (la inferencia de PG a veces resuelve y a veces no) — no usarlo de contraejemplo; castear siempre.

Misma familia: [[feedback_mapeo_alias_sql_vs_claves_dict]] (claves del dict deben coincidir con los `:alias`). El quirk JSONB (`CAST(:v AS jsonb)` + `json.dumps`) vive en CLAUDE.md §35.
