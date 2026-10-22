import { api } from '../../../lib/api'
import type {
  Empresa,
  EmpresaConActividad,
  EmpresaCreate,
  EmpresaUpdate,
  TipoRepresentacion,
  VerificarDuplicadoEmpresaResp,
} from '../types/empresa'

const BASE = '/api/v1/buc'

export const getTiposRepresentacion = () =>
  api.get<TipoRepresentacion[]>(`${BASE}/tipo-representacion`)

export const listarEmpresas = (params: { solo_activos?: boolean; limit?: number; offset?: number } = {}) =>
  api.get<Empresa[]>(`${BASE}/empresas`, { params })

/** Columnas ordenables del padrón (espejo de `_ORDEN_EMPRESAS` en buc.py). */
export type OrdenEmpresas = 'nombre' | 'cuit' | 'localidad' | 'provincia' | 'estado' | 'alta'

export interface ParamsPadronEmpresas {
  q?: string
  desde?: string
  hasta?: string
  orden?: OrdenEmpresas
  dir?: 'asc' | 'desc'
  limit: number
  offset: number
}

/** Página del padrón + total sin paginar (`X-Total-Count`). Texto, fechas y
 *  orden los resuelve el backend (§23): el padrón no entra entero en pantalla. */
export async function listarPadronEmpresas(params: ParamsPadronEmpresas) {
  const { data, headers } = await api.getWithHeaders<Empresa[]>(`${BASE}/empresas`, {
    params: { ...params, solo_activos: false },
  })
  return { filas: data, total: Number(headers.get('X-Total-Count') ?? data.length) }
}

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
