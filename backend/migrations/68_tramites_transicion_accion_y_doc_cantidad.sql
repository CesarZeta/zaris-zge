-- Migracion 68: editor de tipos de tramite — issues Roy 2026-05-28
--
-- BUG-04: semantica de la accion en cada transicion del FSM.
--   Nueva columna tipo_tramite_transicion.tipo_accion para distinguir
--   aprobar / rechazar / derivar / avanzar / otro. Permite colorear el boton
--   (verde aprobar, rojo rechazar) en lugar de mezclar acciones en texto libre.
--
-- BUG-05: mensaje al iniciador segun resultado.
--   Nueva columna tipo_tramite_transicion.mensaje_iniciador (texto opcional)
--   que se usa en el email cuando notifica_iniciador = TRUE. Resuelve
--   "Tu tramite fue aprobado" vs "rechazado" sin un sistema de plantillas.
--
-- BUG-06: limite de archivos por documento requerido.
--   Nueva columna tipo_tramite_documento_requerido.cantidad_max_archivos
--   (smallint, default 1). Ej: DNI = 2 (frente/dorso), Fotos = 5.
--
-- Idempotente. Aplicar en local Y prod.

BEGIN;

-- BUG-04: tipo_accion
ALTER TABLE tipo_tramite_transicion
    ADD COLUMN IF NOT EXISTS tipo_accion VARCHAR(20) NOT NULL DEFAULT 'avanzar';

ALTER TABLE tipo_tramite_transicion DROP CONSTRAINT IF EXISTS ck_transicion_tipo_accion;
ALTER TABLE tipo_tramite_transicion ADD CONSTRAINT ck_transicion_tipo_accion
    CHECK (tipo_accion = ANY (ARRAY['aprobar','rechazar','derivar','avanzar','otro']::text[]));

-- BUG-05: mensaje al iniciador
ALTER TABLE tipo_tramite_transicion
    ADD COLUMN IF NOT EXISTS mensaje_iniciador TEXT;

-- BUG-06: cantidad maxima de archivos por documento requerido
ALTER TABLE tipo_tramite_documento_requerido
    ADD COLUMN IF NOT EXISTS cantidad_max_archivos SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE tipo_tramite_documento_requerido DROP CONSTRAINT IF EXISTS ck_doc_req_cantidad_max;
ALTER TABLE tipo_tramite_documento_requerido ADD CONSTRAINT ck_doc_req_cantidad_max
    CHECK (cantidad_max_archivos BETWEEN 1 AND 20);

COMMIT;
