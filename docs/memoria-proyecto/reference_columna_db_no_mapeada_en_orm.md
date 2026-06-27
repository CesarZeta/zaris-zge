---
name: columna-de-db-no-mapeada-en-el-modelo-orm-setattr-falla-silencioso
description: "Varias columnas de ciudadanos (estado_validacion, ficha_completa) existen en la DB pero NO en el modelo SQLAlchemy Ciudadano. Setearlas con setattr no hace nada; usar UPDATE SQL directo."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 99f6b15c-9680-404f-b4c5-cc746f7462e0
---

El modelo SQLAlchemy `Ciudadano` (`backend/app/models/buc.py`) **NO mapea todas las columnas que la tabla `ciudadanos` tiene en la DB**. Confirmado no-mapeadas: **`estado_validacion`** y **`ficha_completa`** (sí están en la tabla; el modelo solo mapea `email_chk` y el resto del núcleo). Probablemente hay otras (las nacidas de migraciones de App Vecinos: mig 52/53/79).

**Síntoma del bug:** `ciudadano = Ciudadano(...); ciudadano.estado_validacion = "verificado"` (o vía `setattr`) **no hace nada** — el atributo se asigna en el objeto Python pero NO se persiste, porque SQLAlchemy no lo conoce como columna. Sin error, sin warning. La fila queda con el DEFAULT de la columna (`estado_validacion` default `'auto_registrado'`, `ficha_completa` default `FALSE`).

**Cómo lo cacé (2026-06-09 j4):** en `crear_ciudadano` (buc.py) seteé `estado_validacion='verificado'` por setattr y el smoke mostró `auto_registrado` en la DB. El `hasattr(ciudadano, "estado_validacion")` dio False → confirmó que no está mapeado.

**Patrón correcto:** setear esas columnas con **UPDATE SQL directo** tras el `db.flush()` (que ya dio el `id_ciudadano`):
```python
await db.execute(
    text("UPDATE ciudadanos SET ficha_completa = TRUE, estado_validacion = 'verificado' WHERE id_ciudadano = :id"),
    {"id": ciudadano.id_ciudadano},
)
```

**Regla operativa:** antes de setear un campo de `Ciudadano` por atributo/`setattr`, verificar que esté en el modelo ORM (`grep` en `models/buc.py`). Si no está → UPDATE SQL. Aplica a cualquier modelo que sea más viejo que sus columnas (drift de migraciones sin actualizar el ORM). Familia de [[feedback_el_backend_puede_mentir]] (el código asume algo que la realidad no cumple).
