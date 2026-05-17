-- Migracion 48: Modulo Tramites/Expedientes - Tablas de instancias
-- Prerequisito: migracion 47 (catalogos) ya aplicada

-- Instancia del tramite. Estado actual y destinatario denormalizados para bandeja.
CREATE TABLE IF NOT EXISTS tramite (
  id_tramite                       SERIAL PRIMARY KEY,
  numero_expediente                VARCHAR(60) NOT NULL,
  id_tipo_tramite_version          INT NOT NULL REFERENCES tipo_tramite_version(id_tipo_tramite_version),
  asunto                           VARCHAR(500) NOT NULL,
  datos_jsonb                      JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Iniciador polimorfco: exactamente uno
  iniciador_tipo                   VARCHAR(20) NOT NULL CHECK (iniciador_tipo IN ('ciudadano','empresa','area_interna')),
  id_ciudadano_iniciador           INT REFERENCES ciudadanos(id_ciudadano),
  id_empresa_iniciadora            INT REFERENCES empresas(id_empresa),
  id_ciudadano_representante       INT REFERENCES ciudadanos(id_ciudadano),
  id_subarea_iniciadora            INT REFERENCES subarea(id_subarea),
  id_agente_iniciador              INT NOT NULL REFERENCES agentes(id_agente),

  -- Estado actual (denormalizado)
  id_tipo_tramite_estado_actual    INT NOT NULL REFERENCES tipo_tramite_estado(id_tipo_tramite_estado),
  fecha_entrada_estado_actual      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Destinatario actual: solo subarea o equipo, nunca agente directo
  destinatario_actual_tipo         VARCHAR(20) CHECK (destinatario_actual_tipo IN ('subarea','equipo')),
  id_subarea_actual                INT REFERENCES subarea(id_subarea),
  id_equipo_actual                 INT REFERENCES equipos(id_equipo),
  id_agente_tomado_por             INT REFERENCES agentes(id_agente),
  tomado_en                        TIMESTAMPTZ,

  activo                           BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                     INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(numero_expediente, id_municipio),

  CONSTRAINT ck_tramite_iniciador CHECK (
    (iniciador_tipo = 'ciudadano' AND id_ciudadano_iniciador IS NOT NULL AND id_empresa_iniciadora IS NULL AND id_subarea_iniciadora IS NULL) OR
    (iniciador_tipo = 'empresa' AND id_empresa_iniciadora IS NOT NULL AND id_ciudadano_iniciador IS NULL AND id_subarea_iniciadora IS NULL) OR
    (iniciador_tipo = 'area_interna' AND id_subarea_iniciadora IS NOT NULL AND id_ciudadano_iniciador IS NULL AND id_empresa_iniciadora IS NULL)
  ),

  CONSTRAINT ck_tramite_destinatario CHECK (
    (destinatario_actual_tipo IS NULL AND id_subarea_actual IS NULL AND id_equipo_actual IS NULL) OR
    (destinatario_actual_tipo = 'subarea' AND id_subarea_actual IS NOT NULL AND id_equipo_actual IS NULL) OR
    (destinatario_actual_tipo = 'equipo' AND id_equipo_actual IS NOT NULL AND id_subarea_actual IS NULL)
  ),

  CONSTRAINT ck_tramite_tomado CHECK (
    (id_agente_tomado_por IS NULL AND tomado_en IS NULL) OR
    (id_agente_tomado_por IS NOT NULL AND tomado_en IS NOT NULL)
  )
);

-- Ledger append-only. Toda accion sobre un tramite genera una fila.
CREATE TABLE IF NOT EXISTS tramite_movimiento (
  id_tramite_movimiento        BIGSERIAL PRIMARY KEY,
  id_tramite                   INT NOT NULL REFERENCES tramite(id_tramite),
  orden_secuencial             INT NOT NULL,
  tipo                         VARCHAR(30) NOT NULL CHECK (tipo IN (
    'creacion','numeracion','pase','toma','liberacion','cambio_estado','transicion',
    'adjunto','firma_solicitada','firma_realizada','firma_rechazada',
    'comentario','relacion','desistido','reapertura'
  )),
  id_tipo_tramite_transicion   INT REFERENCES tipo_tramite_transicion(id_tipo_tramite_transicion),
  id_estado_origen             INT REFERENCES tipo_tramite_estado(id_tipo_tramite_estado),
  id_estado_destino            INT REFERENCES tipo_tramite_estado(id_tipo_tramite_estado),
  -- origen_jsonb/destino_jsonb: {"tipo":"subarea","id":5,"nombre":"Mesa de Entradas"}
  origen_jsonb                 JSONB,
  destino_jsonb                JSONB,
  comentario                   TEXT,
  metadata_jsonb               JSONB,
  id_agente                    INT NOT NULL REFERENCES agentes(id_agente),
  ip                           VARCHAR(45),
  user_agent                   TEXT,
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(id_tramite, orden_secuencial)
);

-- Adjuntos. El binario vive en Supabase Storage; aca solo metadata.
-- Path: tramites/{anio}/{numero_expediente}/{slug}.{ext}
CREATE TABLE IF NOT EXISTS tramite_documento (
  id_tramite_documento         SERIAL PRIMARY KEY,
  id_tramite                   INT NOT NULL REFERENCES tramite(id_tramite),
  id_tipo_tramite_documento_requerido INT REFERENCES tipo_tramite_documento_requerido(id_tipo_tramite_documento_requerido),
  nombre                       VARCHAR(300) NOT NULL,
  nombre_archivo_original      VARCHAR(300) NOT NULL,
  storage_path                 VARCHAR(500) NOT NULL,
  mime_type                    VARCHAR(100) NOT NULL,
  tamano_bytes                 BIGINT NOT NULL,
  hash_sha256                  VARCHAR(64) NOT NULL,
  requiere_firma               BOOLEAN NOT NULL DEFAULT FALSE,
  estado_firma                 VARCHAR(20) NOT NULL DEFAULT 'no_requiere' CHECK (estado_firma IN ('no_requiere','pendiente','firmado','rechazado')),
  posicion_orden               INT NOT NULL,
  id_agente_subio              INT NOT NULL REFERENCES agentes(id_agente),
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Firmantes y visadores. Firma electronica auditable (no tiene valor legal Ley 25506 en v1).
-- Integracion con proveedor externo reservada en proveedor_externo/evidencia_externa_jsonb.
CREATE TABLE IF NOT EXISTS tramite_firma (
  id_tramite_firma             SERIAL PRIMARY KEY,
  id_tramite_documento         INT NOT NULL REFERENCES tramite_documento(id_tramite_documento),
  rol_intervencion             VARCHAR(20) NOT NULL CHECK (rol_intervencion IN ('firma','visado','notificacion')),
  orden                        SMALLINT NOT NULL,

  -- A quien le toca (polimorfco): exactamente uno
  id_agente_asignado           INT REFERENCES agentes(id_agente),
  id_subarea_asignada          INT REFERENCES subarea(id_subarea),
  id_equipo_asignado           INT REFERENCES equipos(id_equipo),

  estado                       VARCHAR(20) NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','firmado','rechazado')),
  id_agente_firmante           INT REFERENCES agentes(id_agente),
  firmado_en                   TIMESTAMPTZ,
  ip_firma                     VARCHAR(45),
  user_agent_firma             TEXT,
  hash_documento_firmado       VARCHAR(64),
  motivo_rechazo               TEXT,
  rechazado_en                 TIMESTAMPTZ,

  proveedor_externo            VARCHAR(50),
  evidencia_externa_jsonb      JSONB,

  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT ck_firma_asignado CHECK (
    (id_agente_asignado IS NOT NULL AND id_subarea_asignada IS NULL AND id_equipo_asignado IS NULL) OR
    (id_subarea_asignada IS NOT NULL AND id_agente_asignado IS NULL AND id_equipo_asignado IS NULL) OR
    (id_equipo_asignado IS NOT NULL AND id_agente_asignado IS NULL AND id_subarea_asignada IS NULL)
  )
);

-- Asociacion entre tramites. Solo asociacion_simple en v1.
CREATE TABLE IF NOT EXISTS tramite_relacion (
  id_tramite_relacion          SERIAL PRIMARY KEY,
  id_tramite_a                 INT NOT NULL REFERENCES tramite(id_tramite),
  id_tramite_b                 INT NOT NULL REFERENCES tramite(id_tramite),
  tipo_relacion                VARCHAR(20) NOT NULL CHECK (tipo_relacion IN ('asociacion_simple','conjunta','fusion')),
  id_agente_creador            INT NOT NULL REFERENCES agentes(id_agente),
  comentario                   TEXT,
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (id_tramite_a < id_tramite_b),
  UNIQUE(id_tramite_a, id_tramite_b, tipo_relacion)
);
