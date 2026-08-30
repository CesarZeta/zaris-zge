-- ============================================================================
-- 102: Foto de perfil del vecino (App Vecinos) — esquema propuesto por Roy
--      (2026-07-06) y aprobado por Cesar (2026-08-30).
--
--   La foto vive en Supabase Storage, bucket privado de adjuntos
--   (reclamos-adjuntos, mismo que reclamos/OT), path FIJO
--   `perfiles/{id_ciudadano}.jpg` con upsert: re-subir pisa la anterior, no
--   quedan huerfanos, 1 foto por vecino. El backend recibe el binario
--   (multipart), valida (solo JPEG, 1 KB..512 KB, >= 100x100 px) y sube con
--   service_role; se sirve por URL firmada (TTL 1 h) en GET /publico/perfil.
--
--   Columnas nuevas en ciudadanos (NULL = sin foto). Idempotente. Tabla
--   existente: sin cambios de RLS.
-- ============================================================================

ALTER TABLE ciudadanos
    ADD COLUMN IF NOT EXISTS foto_path VARCHAR(300),
    ADD COLUMN IF NOT EXISTS foto_actualizada_en TIMESTAMPTZ;
