---
name: tramites-storage-efimero-deuda
description: "RESUELTO 2026-05-27: documentos de Trámites migrados de disco efímero (backend/uploads/) a Supabase Storage (bucket privado tramites-documentos). El backend sube el binario tras calcular SHA256."
metadata:
  type: project
---

**RESUELTO 2026-05-27.** Los documentos del módulo **Trámites** (`tramite_documento`) ya NO viven en `backend/uploads/` (disco efímero de Railway, que se borraba en cada deploy). Migrados a **Supabase Storage**, bucket privado **`tramites-documentos`** (creado vía `storage.buckets`, `public=false`, límite 25 MB).

**Patrón elegido (decisión del usuario): el backend sube el binario** (NO el flujo signed-upload de 2 fases que usan OT/Reclamos). Razón: el SHA256 es esencial para la verificación de integridad en firmas, y el backend necesita ver los bytes para calcularlo. El frontend sigue mandando el archivo en multipart (sin cambios), el backend calcula `hashlib.sha256(bytes)` y hace PUT al bucket con service_role.

**Cambios (commit de la sesión 2026-05-27):**
- `app/core/storage.py`: + `subir_objeto(path, contenido, content_type, bucket)` (POST con `x-upsert:true`) y `descargar_objeto(path, bucket) -> bytes` (GET, 404 si no existe). Ya tenía signed upload/download y `borrar_objeto`.
- `app/services/tramites/documentos.py`: reescrito. `guardar_archivo_mock` ahora calcula SHA256 sobre los bytes y sube al bucket (`TRAMITES_BUCKET = "tramites-documentos"`); `storage_path` = `tramites/{anio}/{expediente}/{uuid}.{ext}`. Nuevas `descargar_bytes(path)` y `borrar_archivo(path)`. Eliminadas las funciones de disco (`ruta_absoluta_mock`, `calcular_sha256_streaming_mock`, `existe_archivo_mock`, `UPLOADS_BASE`). El nombre `guardar_archivo_mock` se conservó por compat con el caller, aunque ya no es mock.
- `app/services/tramites/firmas.py`: `verificar_integridad_documento` descarga del bucket y recomputa SHA256 (antes leía de disco).
- `app/api/routes/tramites.py`: `GET /documentos/{id}/contenido` ahora devuelve `Response(content=bytes_del_bucket, ...)` en vez de `FileResponse` del disco. Quitado el import `FileResponse`.

**Verificado end-to-end (local apuntando al bucket prod, 2026-05-27):** subir PDF → objeto persiste en `storage.objects` (bucket tramites-documentos) → descargar por el endpoint → SHA256 round-trip idéntico → borrar vía `storage.borrar_objeto` (404-safe). El SHA256 del backend coincide con el local.

**Nota:** los documentos viejos del seed (`storage_path = tramites/2026/placeholder/...`) siguen siendo placeholders sin objeto real → descargarlos da 404 (antes 500). No se migraron (eran demo). El bucket arranca vacío.

Ver §35 (tabla de servicios + endpoints de documentos actualizada) y [[feedback_tramites_documentos_path_quirk]] (el quirk del path desde `__file__` ya no aplica — se eliminó UPLOADS_BASE).
