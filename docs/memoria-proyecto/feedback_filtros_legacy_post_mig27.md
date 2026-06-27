---
name: feedback-filtros-legacy-post-mig27
description: "Cualquier WHERE/filtro que use `r.id_area` o `r.id_subarea` para reclamos rompe en filas viejas (NULL). Fuente única post-mig 27 es vía JOIN con subarea — aplicar también en filtros, no solo en SELECT/JOIN."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8a7ed55b-b83e-4f0a-a792-52d4f2df39fc
---

Familia de [[project_tipo_reclamo_area_inconsistencia]] (mig 27 dropeó `tipo_reclamo.id_area`; el área se obtiene SIEMPRE vía JOIN con subarea). Aquel patrón cubre el JOIN del SELECT; esta sesión (2026-05-19) cazó el mismo bug en el **WHERE** del filtro: `GET /reclamos?id_area=N` filtraba `r.id_area = :id_area`, dejando invisibles los reclamos legacy con `r.id_area=NULL`.

**Why:** mig 27 dropeó `tipo_reclamo.id_area` pero NO `reclamos.id_area`. Esa columna sobrevive llena de NULL para filas viejas y poblada para nuevas (porque el backend la setea al crear). Resultado: el filtro `r.id_area=:x` matchea solo lo nuevo. El JOIN+SELECT con `s.id_area` derivado por `r → tr → s → a` ya mostraba el área correcta visualmente, pero el filtro nunca llamaba a ese row porque el WHERE eliminaba la fila antes.

**How to apply:**
- En cualquier endpoint que filtre por área/subárea sobre `reclamos`, usar `s.id_area = :x` (no `r.id_area`) y `tr.id_subarea = :x` (no `r.id_subarea`).
- El JOIN base es siempre `LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea` — verificar que esté antes de meter el WHERE.
- Grep que se debe hacer cuando se toca un endpoint con filtro de área: `grep -n "r\.id_area\|r\.id_subarea"` en el archivo. Si aparece en un WHERE, refactorizar.

**Caso real (sesión 2026-05-19):**
- `backend/app/api/routes/reclamos.py:142` filtraba `r.id_area = :id_area`. 2 reclamos en local (REC-2026-000027/028 con `r.id_area=NULL` pero `s.id_area=6`) invisibles al filtrar área 6. Fix: `s.id_area = :id_area`. Smoke OK.

**Buscar también si aparece en:**
- agenda (ya verificado 2026-05-19: usa `s.id_area`)
- OT (ya verificado: usa el JOIN correcto)
- catalogo_tipos en reclamos.py (ya usa `s.id_area`)
- dashboard (no existe `dashboard.py` backend; consume stats y mesas que ya están OK)
