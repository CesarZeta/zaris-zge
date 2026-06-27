---
name: sqlalchemy-cast-uuid
description: ":token::uuid en sqlalchemy text() rompe con 'error de sintaxis en o cerca de :'. Usar CAST(:token AS uuid)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 968dd960-d9fd-4b19-b7f9-d0cd0c693b80
---

`text("... WHERE col = :token::uuid")` con sqlalchemy + asyncpg falla con `PostgresSyntaxError: error de sintaxis en o cerca de «:»`.

**Por qué**: sqlalchemy parsea el SQL buscando `:nombre` como bind params. Cuando ve `:token::uuid`, la combinación `::` después del param confunde el parser — un parser lo trata como prefijo de bind (`::uuid` como param "uuid") o como secuencia ambigua. asyncpg recibe el SQL final mal armado.

**Fix**: usar la sintaxis estándar SQL `CAST(... AS tipo)` en lugar del shorthand `::tipo`:

```python
# MAL:
text("SELECT ... WHERE cc.token_activacion = :token::uuid")

# BIEN:
text("SELECT ... WHERE cc.token_activacion = CAST(:token AS uuid)")
```

Aplica a cualquier cast después de un bind param: `:x::int`, `:x::jsonb`, `:x::timestamptz`. Reemplazar por `CAST(:x AS int)`, etc.

**Caso real**: `app/api/routes/publico_auth.py` (sesión 2026-05-19, App Vecinos Etapa 0). El error apareció en el PASO 6 del smoke (`POST /publico/auth/activar` → 500) — typecheck + boot del backend no lo cazaron. Solo se manifiesta cuando el query realmente se ejecuta.

**How to apply**: cualquier query nueva con `text()` que necesite castear un param a un tipo Postgres. Si el smoke da `error de sintaxis en o cerca de «:»` después de un `:nombre::tipo`, es esto.

**Relación con [[feedback_asyncpg_extract_cast_date]]**: misma familia (cast inline obligatorio) pero distinto root cause. Aquel es ambigüedad de overload Postgres con params `unknown`. Este es parser de bind params sqlalchemy que se confunde con `::`. Patrón único: nunca uses `:param::tipo`; siempre `CAST(:param AS tipo)`.
