// Mirror de schemas en backend/app/schemas/buc.py (UsuarioOut/Create/Update)
// y de los endpoints /api/v1/buc/usuarios/* + /subareas/buscar.

export interface Usuario {
  id_usuario: number
  nombre: string
  nivel_acceso: number
  username: string
  email: string | null
  id_cargo: string | null
  id_municipio: number
  activo: boolean
  cuil: string | null
  buc_acceso: boolean
  id_subarea: number | null
  subarea_nombre: string | null
  es_externo: boolean
  debe_cambiar_password: boolean
  fecha_alta: string
  fecha_modif: string
  fecha_ultimo_login: string | null
  modulos_permitidos: string[]
}

// El alta NO manda password: el backend genera la clave temporal y la envía
// por email (§39 Fase 3). Email obligatorio (canal de entrega).
export interface UsuarioCreatePayload {
  username: string
  nivel_acceso: number
  email: string
  buc_acceso: boolean
  es_externo: boolean
  id_subarea: number | null
}

export interface UsuarioUpdatePayload {
  nivel_acceso?: number
  email?: string
  buc_acceso?: boolean
  es_externo?: boolean
  id_subarea?: number | null
  password?: string
}

export interface SubareaHit {
  id_subarea: number
  nombre: string
  area_nombre: string | null
}

export interface LoginLogEntry {
  fecha_login: string
  ip: string | null
  user_agent: string | null
}

export const NIVELES: Record<number, string> = {
  1: 'Administrador',
  2: 'Supervisor',
  3: 'Atención',
  4: 'Gestión',
  5: 'Consultor',
}
