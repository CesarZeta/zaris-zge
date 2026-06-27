---
name: patron-batch-helper-singular-wrapper
description: "Para endpoints con loops `for x in items: await query(x)`, crear helper batch que hace 1-2 queries totales + wrapper singular que delega al batch. Compat retro + perf en una sola refactorización."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
---

Cuando aparezca código tipo:
```python
for rec in recursos:
    disp = await disponibilidad_efectiva(db, rec["tipo"], rec["id_recurso"], fecha)
    ...
```

o peor:
```python
for d in range(dias):
    for rec in recursos:
        x = await fn(db, rec, d)
```

**no optimizar in-place borrando el await del loop**. Crear una función paralela `_batch` que acepte listas y devuelva dict indexado:

```python
async def fn_batch(session, items: list[Item], fechas: list[date]) -> dict[(item_key, fecha), Result]:
    # 1-2 queries bulk con ANY(:ids) / IN, sin importar la longitud de items × fechas.
    # Lógica de filtrado/merge en Python sobre las filas ya cargadas.
    ...

# La función singular se transforma en wrapper compat retro:
async def fn(session, item, fecha) -> Result:
    rango = await fn_batch(session, [item], [fecha])
    return rango.get((item_key(item), fecha), default)
```

**Why:** Mantener la singular evita romper consumidores existentes (en ZARIS: `/disponibilidad/efectiva`, `/calendario` 1 día son consumidores naturales del singular). El wrapper que delega al batch garantiza que ambos retornen exactamente lo mismo — automáticamente verificable con smoke regression byte-a-byte.

**How to apply:**
1. **Antes de tocar nada**, anotar todos los callers de la función singular (`grep "nombre_fn\("`). Si son <3, considerar reemplazarlos todos directos al batch. Si son >3 o están en endpoints con compat retro pública, sí mantener el wrapper.
2. Identificar el shape del input batch: lista de tuplas `(key1, key2, ...)` o `dict[key]` según convenga al algoritmo.
3. Identificar las queries que dependen del item dentro del loop. Mover cada una a 1 query bulk con `WHERE col = ANY(:ids)` (Postgres + asyncpg). Si el WHERE depende de múltiples columnas, ver "espureos" abajo.
4. Hacer toda la lógica de filtrado/merge/intersección en Python. Ahí ya tenés tipos nativos (date, time, list), no necesitás más SQL.
5. **Espureos**: si filtrás por `tipo IN (...) AND id IN (...)`, podés traer pares espureos (tipo+id que no estaban en input). Es barato descartarlos en Python con un set previo:
   ```python
   pares = set((it.tipo, it.id) for it in items)
   for r in rows:
       if (r["tipo"], r["id"]) not in pares:
           continue
   ```
6. Smoke regression: comparar response byte-a-byte entre `fn(x)` y `fn_batch([x])[x]` para varios casos (caso simple, caso vacío, caso edge).

Casos reales sesión 2026-05-14 (perf agenda):
- `disponibilidad_efectiva` (1+ queries por llamada × N recursos × M días) → `disponibilidad_efectiva_batch` (2 queries totales). `/calendario` 23s → 2.2s.
- `_eventos_del_dia` (1 query base + N queries de encargados × M días) → `_eventos_del_rango` (2 queries totales). `/semana` 4.8s → 2.6s.

Ambos casos: singular se preserva, smoke local con evento+encargado real confirmó response byte-idéntica. Cero rotura en producción.
