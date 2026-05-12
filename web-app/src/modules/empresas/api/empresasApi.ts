import { api } from '../../../lib/api'
import type {
  Empresa,
  EmpresaConActividad,
  EmpresaCreate,
  EmpresaUpdate,
  VerificarDuplicadoEmpresaResp,
} from '../types/empresa'

const BASE = '/api/v1/buc'

export const listarEmpresas = (params: { solo_activos?: boolean; limit?: number; offset?: number } = {}) =>
  api.get<Empresa[]>(`${BASE}/empresas`, { params })

export const buscarEmpresas = (params: { q: string; tipo?: 'numero' | 'texto' | 'auto'; limit?: number; offset?: number }) =>
  api.get<Empresa[]>(`${BASE}/empresas/buscar`, { params })

export const obtenerEmpresa = (id: number) =>
  api.get<EmpresaConActividad>(`${BASE}/empresas/${id}`)

export const verificarDuplicadoEmpresa = (campo: 'cuit' | 'email' | 'telefono', valor: string, excluir_id?: number | null) =>
  api.get<VerificarDuplicadoEmpresaResp>(`${BASE}/empresas/verificar-duplicado`, {
    params: { campo, valor, excluir_id: excluir_id ?? undefined },
  })

export const crearEmpresa = (data: EmpresaCreate) =>
  api.post<Empresa>(`${BASE}/empresas`, data)

export const modificarEmpresa = (id: number, data: EmpresaUpdate) =>
  api.put<Empresa>(`${BASE}/empresas/${id}`, data)

export const cambiarEstadoEmpresa = (id: number, activo: boolean) =>
  api.put<Empresa>(`${BASE}/empresas/${id}/estado`, undefined, { params: { activo } })
