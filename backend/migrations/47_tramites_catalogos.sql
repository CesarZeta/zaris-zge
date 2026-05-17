-- Migracion 47: Modulo Tramites/Expedientes - Tablas de catalogo (versionadas)
-- Prerequisito: municipios, agentes, subarea, equipos ya existen

-- Agregar codigo_corto a municipios si no existe
ALTER TABLE municipios ADD COLUMN IF NOT EXISTS codigo_corto VARCHAR(3);

UPDATE municipios SET codigo_corto = 'LPL' WHERE id_municipio = 1 AND codigo_corto IS NULL;

-- Tipo de tramite (identidad estable, el prefijo y codigo no cambian entre versiones)
CREATE TABLE IF NOT EXISTS tipo_tramite (
  id_tipo_tramite              SERIAL PRIMARY KEY,
  codigo                       VARCHAR(50) NOT NULL,
  nombre                       VARCHAR(200) NOT NULL,
  descripcion                  TEXT,
  prefijo                      VARCHAR(20) NOT NULL,
  incluye_municipio            BOOLEAN NOT NULL DEFAULT TRUE,
  incluye_anio                 BOOLEAN NOT NULL DEFAULT TRUE,
  largo_correlativo            SMALLINT NOT NULL DEFAULT 4 CHECK (largo_correlativo BETWEEN 1 AND 8),
  separador                    CHAR(1) NOT NULL DEFAULT '-',
  correlativo_reinicia_anual   BOOLEAN NOT NULL DEFAULT TRUE,
  iniciadores_permitidos       TEXT[] NOT NULL,
  permite_representante        BOOLEAN NOT NULL DEFAULT FALSE,
  id_version_publicada         INT,
  icono                        VARCHAR(50),
  color                        VARCHAR(7),
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(codigo, id_municipio),
  CHECK (iniciadores_permitidos <@ ARRAY['ciudadano','empresa','area_interna']::TEXT[])
);

-- Version publicada de un tipo. Una vez publicada, queda inmutable.
CREATE TABLE IF NOT EXISTS tipo_tramite_version (
  id_tipo_tramite_version      SERIAL PRIMARY KEY,
  id_tipo_tramite              INT NOT NULL REFERENCES tipo_tramite(id_tipo_tramite),
  version_num                  SMALLINT NOT NULL,
  estado                       VARCHAR(20) NOT NULL CHECK (estado IN ('borrador','publicado','archivado')),
  publicada_en                 TIMESTAMPTZ,
  id_agente_publicador         INT REFERENCES agentes(id_agente),
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(id_tipo_tramite, version_num)
);

-- FK circular diferida: tipo_tramite -> tipo_tramite_version (version publicada)
ALTER TABLE tipo_tramite
  DROP CONSTRAINT IF EXISTS fk_tipo_tramite_version_publicada;

ALTER TABLE tipo_tramite
  ADD CONSTRAINT fk_tipo_tramite_version_publicada
  FOREIGN KEY (id_version_publicada) REFERENCES tipo_tramite_version(id_tipo_tramite_version)
  DEFERRABLE INITIALLY DEFERRED;

-- Campos del formulario inicial
CREATE TABLE IF NOT EXISTS tipo_tramite_campo (
  id_tipo_tramite_campo        SERIAL PRIMARY KEY,
  id_tipo_tramite_version      INT NOT NULL REFERENCES tipo_tramite_version(id_tipo_tramite_version),
  nombre_interno               VARCHAR(50) NOT NULL,
  etiqueta                     VARCHAR(200) NOT NULL,
  tipo_dato                    VARCHAR(30) NOT NULL CHECK (tipo_dato IN (
    'texto','texto_largo','numero','decimal','fecha','fecha_hora','booleano',
    'seleccion','seleccion_multiple','ciudadano','empresa','agente','subarea','equipo','archivo','moneda'
  )),
  obligatorio                  BOOLEAN NOT NULL DEFAULT FALSE,
  orden                        SMALLINT NOT NULL,
  opciones_jsonb               JSONB,
  validacion_jsonb             JSONB,
  ayuda                        TEXT,
  visible_en_listado           BOOLEAN NOT NULL DEFAULT FALSE,
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(id_tipo_tramite_version, nombre_interno)
);

-- Nodos de la maquina de estados
CREATE TABLE IF NOT EXISTS tipo_tramite_estado (
  id_tipo_tramite_estado       SERIAL PRIMARY KEY,
  id_tipo_tramite_version      INT NOT NULL REFERENCES tipo_tramite_version(id_tipo_tramite_version),
  codigo                       VARCHAR(50) NOT NULL,
  etiqueta                     VARCHAR(200) NOT NULL,
  descripcion                  TEXT,
  color                        VARCHAR(7) DEFAULT '#6b7280',
  orden                        SMALLINT NOT NULL,
  es_inicial                   BOOLEAN NOT NULL DEFAULT FALSE,
  es_final                     BOOLEAN NOT NULL DEFAULT FALSE,
  permite_adjuntar             BOOLEAN NOT NULL DEFAULT TRUE,
  permite_comentar             BOOLEAN NOT NULL DEFAULT TRUE,
  oculto_para_iniciador        BOOLEAN NOT NULL DEFAULT FALSE,
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(id_tipo_tramite_version, codigo)
);

-- Aristas de la FSM (botones disponibles en cada estado)
-- quien_puede_jsonb: {"subareas":[3,5],"equipos":[2],"roles":["supervisor"],"iniciador":false}
-- destino_automatico_jsonb: {"tipo":"subarea","id":5} o {"tipo":"equipo","id":2}
CREATE TABLE IF NOT EXISTS tipo_tramite_transicion (
  id_tipo_tramite_transicion   SERIAL PRIMARY KEY,
  id_tipo_tramite_version      INT NOT NULL REFERENCES tipo_tramite_version(id_tipo_tramite_version),
  id_estado_origen             INT NOT NULL REFERENCES tipo_tramite_estado(id_tipo_tramite_estado),
  id_estado_destino            INT NOT NULL REFERENCES tipo_tramite_estado(id_tipo_tramite_estado),
  etiqueta_accion              VARCHAR(200) NOT NULL,
  orden                        SMALLINT NOT NULL DEFAULT 0,
  quien_puede_jsonb            JSONB NOT NULL DEFAULT '{}'::jsonb,
  requiere_comentario          BOOLEAN NOT NULL DEFAULT FALSE,
  requiere_adjunto             BOOLEAN NOT NULL DEFAULT FALSE,
  destino_automatico_jsonb     JSONB,
  notifica_iniciador           BOOLEAN NOT NULL DEFAULT TRUE,
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Documentos exigibles, vinculados a un estado (NULL = al iniciar)
CREATE TABLE IF NOT EXISTS tipo_tramite_documento_requerido (
  id_tipo_tramite_documento_requerido SERIAL PRIMARY KEY,
  id_tipo_tramite_version      INT NOT NULL REFERENCES tipo_tramite_version(id_tipo_tramite_version),
  id_tipo_tramite_estado       INT REFERENCES tipo_tramite_estado(id_tipo_tramite_estado),
  nombre                       VARCHAR(200) NOT NULL,
  descripcion                  TEXT,
  obligatorio                  BOOLEAN NOT NULL DEFAULT TRUE,
  formatos_permitidos          TEXT[] NOT NULL DEFAULT ARRAY['pdf','jpg','png']::TEXT[],
  tamano_max_mb                SMALLINT NOT NULL DEFAULT 10,
  requiere_firma               BOOLEAN NOT NULL DEFAULT FALSE,
  firmantes_jsonb              JSONB,
  aporta_quien                 VARCHAR(20) NOT NULL DEFAULT 'iniciador' CHECK (aporta_quien IN ('iniciador','oficina_actual','cualquiera')),
  orden                        SMALLINT NOT NULL DEFAULT 0,
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Secuencia atomica por (tipo, anio, municipio)
-- Para obtener el proximo numero (sin race condition):
-- INSERT INTO tipo_tramite_numerador ... ON CONFLICT DO UPDATE SET ultimo_numero = ultimo_numero + 1 RETURNING ultimo_numero
CREATE TABLE IF NOT EXISTS tipo_tramite_numerador (
  id_tipo_tramite              INT NOT NULL REFERENCES tipo_tramite(id_tipo_tramite),
  anio                         SMALLINT NOT NULL,
  id_municipio                 INT NOT NULL REFERENCES municipios(id_municipio),
  ultimo_numero                INT NOT NULL DEFAULT 0,
  activo                       BOOLEAN NOT NULL DEFAULT TRUE,
  fecha_alta                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fecha_modificacion           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (id_tipo_tramite, anio, id_municipio)
);
