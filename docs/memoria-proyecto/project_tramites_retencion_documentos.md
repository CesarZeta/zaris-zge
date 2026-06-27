---
name: project_tramites_retencion_documentos
description: "Trámites: política de retención/depuración de documentos COMPLETA (migs 74+75, Fases 1-5) — flag por tipo, auto-archivado por inactividad, purga del binario en dry-run, cron diario."
metadata: 
  node_type: memory
  type: project
  originSessionId: 6150fb7a-949b-4a2b-a4cd-f2b2872bbd07
---

**Política de retención de documentos de Trámites — COMPLETA al 2026-06-01** (migs 74 + 75, las 5 fases). CLAUDE.md §35 ("Marca resultado + política de retención") + §21 (mig 75).

**Modelo: el REGISTRO del documento (metadatos + `hash_sha256`) nunca se borra; solo se depura el binario físico del bucket.** `tramite_documento.binario_purgado=TRUE` + `fecha_purga_binario` marcan que el archivo ya no está, pero la fila persiste.

- **Fase 1 (mig 74):** `tramite.resultado` (`pendiente|aprobado|rechazado`), marca paralela al estado FSM. Decide el plazo de retención.
- **Fase 2 (mig 75):** `tipo_tramite.retencion_nunca_depurar` (BOOL). TRUE = nunca purga (ej. Habilitaciones). Checkbox en `NuevoTipoModal`/`EditarTipoModal` + detalle del tipo.
- **Fase 3 (mig 75):** auto-archivado. Trámite sin movimiento ≥ `tramite_inactividad_dias` y NO en estado final → `fecha_archivado`/`archivado_motivo='inactividad'`/`resultado='rechazado'` + movimiento `archivado_inactividad`. El archivado es marca de mantenimiento **paralela al estado FSM** (no fuerza un estado "archivado").
- **Fase 4 (mig 75):** purga. Docs de trámites concluidos (archivados o `resultado≠pendiente`), vencido el plazo según resultado, EXCEPTO tipos `retencion_nunca_depurar`. Plazo desde `COALESCE(fecha_archivado, último mov, fecha_alta)`. **Dry-run por default** (switch `tramite_purga_binarios_real='true'` la activa). `GET /documentos/{id}/contenido` → **410** si purgado; front muestra "Archivo depurado".
- **Fase 5 (mig 75):** cron. `POST /api/v1/tramites/mantenimiento/ejecutar` (`routes/tramites_mantenimiento.py`, SIN guard JWT, auth `X-Dispatcher-Token` = `DISPATCHER_TOKEN` Railway, igual que encuestas §42). **Registrado ANTES de `tramites_router`** (param greedy §5). `.github/workflows/tramites-mantenimiento.yml` diario 04:10 UTC. Motores en `services/tramites/retencion.py`.

**Plazos configurables** en `configuracion_general` (Config → Sistema §41): `retencion_dias_aprobado=3650`, `retencion_dias_rechazado=365`, `tramite_inactividad_dias=180`, `tramite_purga_binarios_real=false`.

**Trampas cazadas:**
- **DRIFT prod**: `configuracion_general.tipo` NOT NULL (`string|boolean|integer`) existe en prod, NO en local. La mig `75b` arma el INSERT con/sin esa columna según exista; en prod el seed fue por `execute_sql` con `tipo` explícito. [[feedback_verificar_drift_completo_prod]].
- **asyncpg `make_interval`**: castear cada bind dentro del CASE — `CASE WHEN ... THEN CAST(:da AS integer) ELSE CAST(:dr AS integer) END`, NO castear el CASE entero (infiere `text`). [[feedback_asyncpg_extract_cast_date]].
- Movimientos del cron: `id_agente_iniciador` del trámite (col NOT NULL, no hay "agente sistema") + `id_usuario=None`.

Smoke local 10/10 (archivado + idempotencia + purga dry-run + teardown sin basura). Ver [[project_tramites_storage_efimero_deuda]] (storage subyacente) y [[feedback_columna_nueva_auditar_todos_los_select]] (los 2 builders del detalle).
