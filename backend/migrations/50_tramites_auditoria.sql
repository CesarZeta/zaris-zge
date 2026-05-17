-- Migracion 50: Campos de auditoria (id_usuario_alta, id_usuario_modificacion)
-- en las 5 tablas de instancias del modulo Tramites.
-- Las tablas de catalogo (tipo_tramite_*) no se tocan en Fase 2.

ALTER TABLE tramite
  ADD COLUMN IF NOT EXISTS id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

ALTER TABLE tramite_movimiento
  ADD COLUMN IF NOT EXISTS id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

ALTER TABLE tramite_documento
  ADD COLUMN IF NOT EXISTS id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

ALTER TABLE tramite_firma
  ADD COLUMN IF NOT EXISTS id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;

ALTER TABLE tramite_relacion
  ADD COLUMN IF NOT EXISTS id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL;
