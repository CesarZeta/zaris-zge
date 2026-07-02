-- 92: Fase 3 roles — nuevo nivel 4 "Gestión" (agente de OT, scopeado por subárea).
-- Decisión del usuario 2026-07-02: 1=Administrador, 2=Supervisor, 3=Atención
-- (ex Operador, ve todo para consultas de vecinos), 4=Gestión (NUEVO, ve solo
-- su subárea), 5=Consultor (ex nivel 4, solo lectura — se renumera).
-- Los usuarios nivel 3 actuales NO se tocan (default seguro); el admin mueve a
-- Gestión (4) a los agentes de OT desde Maestros → Usuarios.

-- 1. Ampliar el CHECK a 1..5. El nombre difiere entre entornos (verificado
--    2026-07-02): prod = usuarios_nivel_acceso_check, local = ck_usuarios_nivel.
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_nivel_acceso_check;
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS ck_usuarios_nivel;
ALTER TABLE usuarios ADD CONSTRAINT usuarios_nivel_acceso_check
    CHECK (nivel_acceso BETWEEN 1 AND 5);

-- 2. Consultores: 4 → 5 (usuarios usa fecha_modif legacy, §5).
UPDATE usuarios SET nivel_acceso = 5, fecha_modif = NOW()
WHERE nivel_acceso = 4;

-- 3. modulos.min_nivel_acceso también tiene CHECK 1..4 — ampliarlo a 1..5.
ALTER TABLE modulos DROP CONSTRAINT IF EXISTS modulos_min_nivel_acceso_check;
ALTER TABLE modulos ADD CONSTRAINT modulos_min_nivel_acceso_check
    CHECK (min_nivel_acceso BETWEEN 1 AND 5);

-- 4. Módulos: los operativos que Gestión (4) debe ver pasan de 3 a 4;
--    padrones era consultor-visible (4) y sigue siéndolo en su nuevo número (5).
--    emergencias y entradas quedan en 3 (solo Atención). Ajustable en
--    Config → Catálogo de módulos.
UPDATE modulos SET min_nivel_acceso = 5, fecha_modificacion = NOW()
WHERE modulo_codigo = 'padrones' AND min_nivel_acceso = 4;

UPDATE modulos SET min_nivel_acceso = 4, fecha_modificacion = NOW()
WHERE modulo_codigo IN ('reclamos', 'ot_agente', 'agenda', 'turnos', 'tramites')
  AND min_nivel_acceso = 3;
