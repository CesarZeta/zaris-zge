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

// Permisos por usuario.
// El handler genérico de admin_tablas (GET /{tabla}) devuelve todos los usuarios
// activos sin paginar — no acepta limit/offset, así que no los mandamos.
export const listarUsuarios = () =>
  api.get<UsuarioLite[]>(`${ADMIN}/usuarios`)

export const verPermisosUsuario = (id_usuario: number) =>
  api.get<UsuarioModulosResponse>(`${PERMS}/usuarios/${id_usuario}/modulos`)

export const setPermisosUsuario = (id_usuario: number, overrides: OverrideIn[]) =>
  api.put<UsuarioModulosResponse>(`${PERMS}/usuarios/${id_usuario}/modulos`, { overrides })

// Identidad del topbar (nombre app + logo/nombre municipio)
const IDENTIDAD = '/api/v1/config/identidad'

export interface IdentidadValues {
  // `app_nombre` ('GESTION ESTADO') es interno del producto — el backend lo
  // devuelve por compat con el shell vanilla pero NO es editable (§14). Por eso
  // no figura en IdentidadUpdate: el PUT lo ignoraría.
  app_nombre: string
  municipio_nombre: string
  municipio_logo_url: string
}

export interface IdentidadUpdate {
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

// Parámetros del sistema (tabla key/value configuracion_general).
// Reusa el handler genérico de admin_tablas: GET lista todas las filas,
// PUT /{id_config} actualiza las columnas editables (acá solo `valor`).
export interface ConfigParam {
  id_config: number
  clave: string
  valor: string
  tipo: string
  descripcion: string | null
  activo: boolean
}

export const listarConfigGeneral = () =>
  api.get<ConfigParam[]>(`${ADMIN}/configuracion_general`)

export const actualizarConfigParam = (id_config: number, valor: string) =>
  api.put<ConfigParam>(`${ADMIN}/configuracion_general/${id_config}`, { valor })
