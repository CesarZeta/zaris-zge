-- Migración 88 — Foto de perfil del usuario interno (avatar del topbar).
-- La sube el propio usuario desde el menú de usuario del shell (PNG/JPG, 2MB).
-- El binario vive en el bucket público `config-assets` (paths usuarios/{id}/...);
-- acá solo se persiste la URL pública. Vacía/NULL = sin foto (se muestran iniciales).
-- Idempotente.

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS foto_url VARCHAR(500);

COMMENT ON COLUMN usuarios.foto_url IS
  'URL pública del avatar (bucket config-assets). NULL/vacía = iniciales.';
