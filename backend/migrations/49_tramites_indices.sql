-- Migracion 49: Modulo Tramites/Expedientes - Indices
-- Prerequisito: migraciones 47 y 48 ya aplicadas

CREATE INDEX IF NOT EXISTS idx_tramite_destinatario_subarea
  ON tramite(id_subarea_actual) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_tramite_destinatario_equipo
  ON tramite(id_equipo_actual) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_tramite_estado_actual
  ON tramite(id_tipo_tramite_estado_actual) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_tramite_iniciador_ciudadano
  ON tramite(id_ciudadano_iniciador) WHERE id_ciudadano_iniciador IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tramite_iniciador_empresa
  ON tramite(id_empresa_iniciadora) WHERE id_empresa_iniciadora IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tramite_numero
  ON tramite(numero_expediente);

CREATE INDEX IF NOT EXISTS idx_tramite_municipio_activo
  ON tramite(id_municipio, activo, fecha_alta DESC);

CREATE INDEX IF NOT EXISTS idx_tramite_movimiento_tramite
  ON tramite_movimiento(id_tramite, orden_secuencial);

CREATE INDEX IF NOT EXISTS idx_tramite_documento_tramite
  ON tramite_documento(id_tramite) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_tramite_firma_doc
  ON tramite_firma(id_tramite_documento);

CREATE INDEX IF NOT EXISTS idx_tramite_firma_pendientes_subarea
  ON tramite_firma(id_subarea_asignada, estado) WHERE estado = 'pendiente';

CREATE INDEX IF NOT EXISTS idx_tramite_firma_pendientes_equipo
  ON tramite_firma(id_equipo_asignado, estado) WHERE estado = 'pendiente';
