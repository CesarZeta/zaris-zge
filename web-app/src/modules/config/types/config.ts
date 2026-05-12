// Mirror de schemas en backend/app/api/routes/admin_permisos.py

export interface ModuloCatalogo {
  modulo_codigo: string
  nombre: string
  descripcion: string | null
  min_nivel_acceso: number
  activo: boolean
}

export interface UsuarioLite {
  id_usuario: number
  nombre: string
  email: string | null
  nivel_acceso: number
  activo: boolean
}

export interface OverridePermiso {
  modulo_codigo: string
  permitido: boolean
  motivo: string | null
  fecha_modificacion: string | null
}

export interface UsuarioModulosResponse {
  id_usuario: number
  nivel_acceso: number
  modulos_permitidos: string[]    // resolucion final
  overrides: OverridePermiso[]     // overrides activos
}

export interface OverrideIn {
  modulo_codigo: string
  permitido: boolean
  motivo?: string | null
}
