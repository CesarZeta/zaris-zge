---
name: tipo_reclamo área — fuente única (post mig 27)
description: La columna tipo_reclamo.id_area fue dropeada en mig 27. Fuente única del área de un tipo = subarea.id_area vía JOIN. Mantener este patrón en todo código nuevo.
type: project
---
## Estado actual (post-migración 27, 2026-05-10)

`tipo_reclamo.id_area` **ya no existe** en local ni prod. La migración 27 dropeó la columna y su índice tras confirmar que el backend y el frontend ya consultaban exclusivamente vía JOIN con `subarea`.

## Fuente única del área de un tipo

**Siempre vía JOIN:** `tipo_reclamo tr → subarea s ON s.id_subarea = tr.id_subarea → area a ON a.id_area = s.id_area`.

**Why:** la estructura natural es Área → Subárea → Tipo. La columna espejo en `tipo_reclamo` se desincronizó históricamente (123/282 inconsistencias antes de mig 23-24); eliminarla cierra esa puerta para siempre.

**How to apply:**
- Endpoints que devuelven `area_nombre` para un tipo: hacer el JOIN; nunca leer columna inexistente. Ver `catalogo_tipos` en `backend/app/api/routes/reclamos.py`.
- POST /reclamos: si el body no manda `id_area`, derivarla via `tipo_reclamo.id_subarea → subarea.id_area`. Implementado en `crear_reclamo`.
- Scripts de seed nuevos: insertar tipos con `id_subarea` y dejar que el área se resuelva por JOIN, no escribir id_area en `tipo_reclamo`.
- Frontend (admin_tablas y reclamos): el form de tipo_reclamo solo expone `id_subarea`. El usuario nunca elige "área" para un tipo.

## Áreas duplicadas — deuda (cerrada en mig 26)

Migración 26 consolidó los 15 pares de áreas duplicadas con/sin tilde por nombre normalizado. 5 áreas activas finales en prod (Gobierno, Planeamiento, Servicios Públicos, Seguridad, Tránsito). Histórico: ver CLAUDE.md §21 mig 26.
