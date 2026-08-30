-- ============================================================================
-- 101: Ciclo de vida del tramite hacia el vecino (decisiones de Cesar 2026-08-30).
--
--   a) SLA por tipo de tramite (tipo_tramite.sla_dias; NULL = default global
--      configuracion_general.tramite_sla_dias_default).
--   b) Flag "espera al iniciador" por estado del catalogo
--      (tipo_tramite_estado.espera_iniciador): SOLO en esos estados corre el
--      timer de desistimiento — si la demora es del municipio no se desiste
--      al vecino.
--   c) Timer de desistimiento (services/tramites/ciclo_vida.py, cron diario):
--      vencido el SLA, aviso 1 a los +30 dias, aviso 2 a los +60, aviso final
--      72 h antes de los +90, y a los +90 se marca DESISTIDO solo. Tracking
--      del nivel de aviso en tramite.desist_aviso_nivel / desist_aviso_en
--      (se resetea en cada transicion).
--   d) 'desistido' como MARCA PARALELA (tramite.resultado + archivado_motivo
--      = 'desistimiento'), igual que el archivado por inactividad: no obliga
--      a agregar un estado a los circuitos.
--   e) Resultado derivado de la transicion final (tipo_accion aprobar ->
--      aprobado, rechazar -> rechazado): sin cambio de schema, va en codigo.
--   f) Avisos al vecino en la bandeja de la PWA (mig 99): tipos nuevos
--      'tramite_estado' (termino / resultado / desistido) y
--      'tramite_pendiente' (avisos del timer).
--   g) Encuestas CSAT de tramites: cuarta rama del polimorfismo de
--      encuesta_envio (id_tramite), patron migs 72/98. El disparo lo hace el
--      backend al terminar con resultado aprobado/rechazado.
--   h) Ledger: tipo 'aviso_iniciador' para asentar cada aviso del timer.
--
-- DDL puro; el seed (plantilla de encuesta + claves de config) va SEPARADO
-- en 101b (apply_migration es atomico, §21). Idempotente. Tablas existentes:
-- sin cambios de RLS.
-- ============================================================================

-- a) SLA por tipo
ALTER TABLE tipo_tramite
    ADD COLUMN IF NOT EXISTS sla_dias INTEGER;

-- b) Flag por estado
ALTER TABLE tipo_tramite_estado
    ADD COLUMN IF NOT EXISTS espera_iniciador BOOLEAN NOT NULL DEFAULT FALSE;

-- c) Tracking del timer en la instancia
ALTER TABLE tramite
    ADD COLUMN IF NOT EXISTS desist_aviso_nivel SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS desist_aviso_en TIMESTAMPTZ;

-- d) 'desistido' en resultado + 'desistimiento' en archivado_motivo.
--    No hay ALTER de CHECK: DROP IF EXISTS + ADD (par idempotente). Los
--    valores existentes estan dentro del set nuevo -> valida sin NOT VALID.
ALTER TABLE tramite DROP CONSTRAINT IF EXISTS ck_tramite_resultado;
ALTER TABLE tramite
    ADD CONSTRAINT ck_tramite_resultado
    CHECK (resultado IN ('pendiente', 'aprobado', 'rechazado', 'desistido'));

ALTER TABLE tramite DROP CONSTRAINT IF EXISTS ck_tramite_archivado_motivo;
ALTER TABLE tramite
    ADD CONSTRAINT ck_tramite_archivado_motivo
    CHECK (archivado_motivo IS NULL
           OR archivado_motivo IN ('inactividad', 'manual', 'desistimiento'));

-- h) Ledger: + 'aviso_iniciador' (lista completa verificada en prod 2026-08-30;
--    'desistido' ya existia desde mig 48).
ALTER TABLE tramite_movimiento DROP CONSTRAINT IF EXISTS tramite_movimiento_tipo_check;
ALTER TABLE tramite_movimiento
    ADD CONSTRAINT tramite_movimiento_tipo_check
    CHECK (tipo IN ('creacion', 'numeracion', 'pase', 'toma', 'liberacion',
                    'cambio_estado', 'transicion', 'adjunto',
                    'firma_solicitada', 'firma_realizada', 'firma_rechazada',
                    'comentario', 'relacion', 'desistido', 'reapertura',
                    'aprobacion', 'resultado', 'archivado_inactividad',
                    'purga_binario', 'aviso_iniciador'));

-- f) Bandeja de avisos del vecino (mig 99): tipos de tramites.
ALTER TABLE ciudadano_aviso DROP CONSTRAINT IF EXISTS ck_ciudadano_aviso_tipo;
ALTER TABLE ciudadano_aviso
    ADD CONSTRAINT ck_ciudadano_aviso_tipo
    CHECK (tipo IN ('reclamo_estado', 'emergencia_estado', 'municipio',
                    'tramite_estado', 'tramite_pendiente'));

-- g) Encuestas: cuarta rama id_tramite (ON DELETE RESTRICT como id_turno /
--    id_evento_reserva). XOR de 4, NOT VALID como el original (las filas
--    viejas ya cumplen: exactamente un origen y la columna nueva nace NULL).
ALTER TABLE encuesta_envio
    ADD COLUMN IF NOT EXISTS id_tramite INTEGER
    REFERENCES tramite(id_tramite) ON DELETE RESTRICT;

ALTER TABLE encuesta_envio DROP CONSTRAINT IF EXISTS ck_encuesta_envio_origen;
ALTER TABLE encuesta_envio
    ADD CONSTRAINT ck_encuesta_envio_origen
    CHECK ( (id_reclamo IS NOT NULL)::int
          + (id_turno IS NOT NULL)::int
          + (id_evento_reserva IS NOT NULL)::int
          + (id_tramite IS NOT NULL)::int = 1 )
    NOT VALID;

CREATE INDEX IF NOT EXISTS idx_encuesta_envio_tramite
    ON encuesta_envio (id_tramite) WHERE id_tramite IS NOT NULL;

-- Timer: candidatos = tramites vivos no archivados (el JOIN al estado filtra
-- espera_iniciador). Indice parcial chico para la corrida diaria.
CREATE INDEX IF NOT EXISTS idx_tramite_vivo_no_archivado
    ON tramite (id_tipo_tramite_estado_actual)
    WHERE activo = TRUE AND fecha_archivado IS NULL;
