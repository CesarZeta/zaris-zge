-- Migración 51: Agregar 'direccion' al CHECK constraint de tipo_tramite_campo.tipo_dato
-- Permite campos de formulario con buscador OSM integrado.
-- Idempotente: usa DROP CONSTRAINT IF EXISTS + ADD CONSTRAINT.

ALTER TABLE tipo_tramite_campo
  DROP CONSTRAINT IF EXISTS tipo_tramite_campo_tipo_dato_check;

ALTER TABLE tipo_tramite_campo
  ADD CONSTRAINT tipo_tramite_campo_tipo_dato_check CHECK (tipo_dato IN (
    'texto','texto_largo','numero','decimal','fecha','fecha_hora','booleano',
    'seleccion','seleccion_multiple','ciudadano','empresa','agente','subarea','equipo',
    'archivo','moneda','direccion'
  ));
