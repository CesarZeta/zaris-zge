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
