-- Migración 64: reforzar la relación 1:1 entre agentes y usuarios.
-- Un usuario interno tiene exactamente un agente. El alta de un usuario interno
-- fuerza la creación de su agente (lógica en POST /buc/usuarios); los externos
-- no tienen agente. Este índice impide que dos agentes apunten al mismo usuario.
-- Los agentes legacy con id_usuario NULL (sin vincular) se permiten.
-- Idempotente.

CREATE UNIQUE INDEX IF NOT EXISTS uq_agentes_id_usuario
    ON agentes (id_usuario)
    WHERE id_usuario IS NOT NULL;
