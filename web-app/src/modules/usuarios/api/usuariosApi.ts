import { api } from '../../../lib/api'
import type {
  LoginLogEntry,
  SubareaHit,
  Usuario,
  UsuarioCreatePayload,
  UsuarioUpdatePayload,
} from '../types'

const BUC = '/api/v1/buc'

// El listado devuelve TODOS (activos e inactivos) — el filtrado es client-side,
// igual que hacía el vanilla (dataset chico: decenas de usuarios).
export const listarUsuarios = () =>
  api.get<Usuario[]>(`${BUC}/usuarios`, { params: { solo_activos: false } })

export const buscarUsuarios = (q: string) =>
  api.get<Usuario[]>(`${BUC}/usuarios/buscar`, { params: { q, tipo: 'texto' } })

export const obtenerUsuario = (id: number) =>
  api.get<Usuario>(`${BUC}/usuarios/${id}`)

export const crearUsuario = (payload: UsuarioCreatePayload) =>
  api.post<Usuario>(`${BUC}/usuarios`, payload)

export const actualizarUsuario = (id: number, payload: UsuarioUpdatePayload) =>
  api.put<Usuario>(`${BUC}/usuarios/${id}`, payload)

export const cambiarEstadoUsuario = (id: number, activo: boolean) =>
  api.put<Usuario>(`${BUC}/usuarios/${id}/estado`, undefined, { params: { activo } })

export const buscarSubareas = (q: string) =>
  api.get<SubareaHit[]>(`${BUC}/subareas/buscar`, { params: { q, limit: 20 } })

export const verLoginLog = (id: number) =>
  api.get<LoginLogEntry[]>(`${BUC}/usuarios/${id}/login-log`, { params: { limit: 50 } })
