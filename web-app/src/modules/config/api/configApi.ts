import { api } from '../../../lib/api'
import type {
  ModuloCatalogo,
  OverrideIn,
  UsuarioLite,
  UsuarioModulosResponse,
} from '../types/config'

const PERMS = '/api/v1/admin/permisos'
const ADMIN = '/api/v1/admin'

// Catalogo de modulos
export const listarModulos = () =>
  api.get<ModuloCatalogo[]>(`${PERMS}/modulos`)

export const actualizarModulo = (codigo: string, min_nivel_acceso: number) =>
  api.put<ModuloCatalogo>(`${PERMS}/modulos/${encodeURIComponent(codigo)}`, { min_nivel_acceso })

// Permisos por usuario
export const listarUsuarios = () =>
  api.get<UsuarioLite[]>(`${ADMIN}/usuarios`, { params: { limit: 200 } })

export const verPermisosUsuario = (id_usuario: number) =>
  api.get<UsuarioModulosResponse>(`${PERMS}/usuarios/${id_usuario}/modulos`)

export const setPermisosUsuario = (id_usuario: number, overrides: OverrideIn[]) =>
  api.put<UsuarioModulosResponse>(`${PERMS}/usuarios/${id_usuario}/modulos`, { overrides })

// Identidad del topbar (nombre app + logo/nombre municipio)
const IDENTIDAD = '/api/v1/config/identidad'

export interface IdentidadValues {
  app_nombre: string
  municipio_nombre: string
  municipio_logo_url: string
}

export interface IdentidadUpdate {
  app_nombre?: string
  municipio_nombre?: string
  municipio_logo_url?: string
}

export interface LogoUploadResponse {
  upload_url: string
  public_url: string
  path: string
  bucket: string
}

export const getIdentidad = () => api.get<IdentidadValues>(IDENTIDAD)

export const updateIdentidad = (payload: IdentidadUpdate) =>
  api.put<IdentidadValues>(IDENTIDAD, payload)

export const crearLogoUploadUrl = (mime_type: string, tamano_bytes: number) =>
  api.post<LogoUploadResponse>(`${IDENTIDAD}/logo-upload-url`, { mime_type, tamano_bytes })
