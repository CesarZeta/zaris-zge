-- =============================================================================
-- Migracion 33 — Agenda sub-fase 1.A — Ocupaciones (tabla unica)
-- =============================================================================
-- Una sola tabla 'ocupaciones' que representa el bloqueo de agenda de un
-- recurso (agente|equipo) en un dia/franja. Discrimina por 'tipo':
--    ot      -> bloqueo por orden de trabajo  (id_orden_trabajo NOT NULL)
--    evento  -> bloqueo por evento           (id_evento NOT NULL)
--    turno   -> bloqueo por turno con ciudadano (id_ciudadano NOT NULL)
-- El CHECK garantiza consistencia: solo una de las 3 FKs especificas se
-- popula segun el tipo.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ocupaciones (
    id_ocupacion            SERIAL PRIMARY KEY,
    tipo                    VARCHAR(10) NOT NULL,
    tipo_recurso            VARCHAR(10) NOT NULL,
    id_recurso              INTEGER NOT NULL,
    fecha                   DATE NOT NULL,
    hora_inicio             TIME NOT NULL,
    hora_fin                TIME NOT NULL,
    -- FKs especificas por tipo (todas nullable, validadas por CHECK)
    id_orden_trabajo        INTEGER REFERENCES ordenes_trabajo(id_ot)       ON DELETE SET NULL,
    id_evento               INTEGER REFERENCES eventos(id_evento)           ON DELETE SET NULL,
    id_ciudadano            INTEGER REFERENCES ciudadanos(id_ciudadano)     ON DELETE SET NULL,
    -- Atributos especificos
    duracion_aplicada_min   INTEGER,
    rol_en_evento           VARCHAR(50),
    motivo                  TEXT,
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,
    id_municipio            INTEGER NOT NULL DEFAULT 1 REFERENCES municipios(id_municipio) ON DELETE RESTRICT,
    fecha_alta              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_modificacion      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,

    CONSTRAINT ck_ocup_tipo          CHECK (tipo IN ('ot','evento','turno')),
    CONSTRAINT ck_ocup_tipo_recurso  CHECK (tipo_recurso IN ('agente','equipo')),
    CONSTRAINT ck_ocup_horario       CHECK (hora_fin > hora_inicio),
    CONSTRAINT ck_ocupacion_consistencia CHECK (
        (tipo = 'ot'     AND id_orden_trabajo IS NOT NULL AND id_evento IS NULL    AND id_ciudadano IS NULL)
     OR (tipo = 'evento' AND id_evento        IS NOT NULL AND id_orden_trabajo IS NULL AND id_ciudadano IS NULL)
     OR (tipo = 'turno'  AND id_ciudadano     IS NOT NULL AND id_evento IS NULL    AND id_orden_trabajo IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_ocup_recurso_fecha ON ocupaciones (tipo_recurso, id_recurso, fecha);
CREATE INDEX IF NOT EXISTS idx_ocup_mun_fecha     ON ocupaciones (id_municipio, fecha);
CREATE INDEX IF NOT EXISTS idx_ocup_tipo          ON ocupaciones (tipo);
CREATE INDEX IF NOT EXISTS idx_ocup_evento        ON ocupaciones (id_evento)       WHERE id_evento        IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ocup_ot            ON ocupaciones (id_orden_trabajo) WHERE id_orden_trabajo IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ocup_ciudadano     ON ocupaciones (id_ciudadano)    WHERE id_ciudadano     IS NOT NULL;

COMMIT;
