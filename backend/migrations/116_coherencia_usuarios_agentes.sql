-- Migracion 116 — Coherencia usuario ↔ agente (2026-10-21)
--
-- Pedido de Cesar (2026-10-21): arreglar la disparidad entre cuentas de usuario
-- y agentes. Diagnostico en prod: 93 usuarios activos y 93 agentes activos, 1:1
-- completo y sin huerfanos; pero 75 usuarios tenian una subarea distinta a la de
-- su agente (16 supervisores) y 85 agentes un email distinto al de su cuenta
-- (direcciones armadas por un seed viejo, no se usaban para enviar nada).
-- Regla: la gestion de una persona es la de su AGENTE (§3) y el email de contacto
-- del agente es el de su cuenta, salvo que tenga ficha en la BUC (ahi manda la
-- ficha, services/cuenta_zaris.py::sincronizar_agente_desde_ficha).
--
-- Solo datos e idempotente. Backup previo en prod: _backup_coherencia_2026_10_21.

-- 1) usuarios.id_subarea ← la del agente 1:1 activo.
UPDATE usuarios u
   SET id_subarea = a.id_subarea, fecha_modif = NOW()
  FROM agentes a
 WHERE a.id_usuario = u.id_usuario AND a.activo = TRUE
   AND a.id_subarea IS NOT NULL
   AND u.id_subarea IS DISTINCT FROM a.id_subarea;

-- 2) agentes.email ← email de la cuenta (solo personas sin ficha en la BUC).
UPDATE agentes a
   SET email = u.email, fecha_modificacion = NOW()
  FROM usuarios u
 WHERE u.id_usuario = a.id_usuario AND a.activo = TRUE
   AND u.id_ciudadano IS NULL
   AND u.email IS NOT NULL AND u.email <> ''
   AND LOWER(COALESCE(a.email, '')) <> LOWER(u.email);

-- 3) Tipos de reclamo de prueba sin ningun reclamo: baja logica (aparecian en
--    los buscadores de tipo de reclamo).
UPDATE tipo_reclamo t
   SET activo = FALSE, fecha_modificacion = NOW()
 WHERE t.activo = TRUE AND t.nombre ILIKE 'Tipo Reclamo Test QA%'
   AND NOT EXISTS (SELECT 1 FROM reclamos r WHERE r.id_tipo_reclamo = t.id_tipo_reclamo);
