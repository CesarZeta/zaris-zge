import { api } from '../../../lib/api'
import type {
  Ciudadano,
  CiudadanoConNacionalidad,
  CiudadanoCreate,
  CiudadanoUpdate,
  Nacionalidad,
  TipoRepresentacion,
  Actividad,
  VerificarDuplicadoResp,
  EmpresaVinculada,
  EmpresaCreate,
  CiudadanoEmpresaCreate,
} from '../types/ciudadano'

const BASE = '/api/v1/buc'

// ── Catalogos ──
export const getNacionalidades = () =>
  api.get<Nacionalidad[]>(`${BASE}/nacionalidades`)

export const getTiposRepresentacion = () =>
  api.get<TipoRepresentacion[]>(`${BASE}/tipo-representacion`)

export const getActividades = () =>
  api.get<Actividad[]>(`${BASE}/actividades`)

// ── Ciudadanos ──
export const listarCiudadanos = (params: { solo_activos?: boolean; limit?: number; offset?: number } = {}) =>
  api.get<Ciudadano[]>(`${BASE}/ciudadanos`, { params })

export const buscarCiudadanos = (params: { q: string; tipo?: 'numero' | 'texto' | 'auto'; limit?: number; offset?: number }) =>
  api.getWithHeaders<Ciudadano[]>(`${BASE}/ciudadanos/buscar`, { params })

export const obtenerCiudadano = (id: number) =>
  api.get<CiudadanoConNacionalidad>(`${BASE}/ciudadanos/${id}`)

export const verificarDuplicadoCiudadano = (campo: string, valor: string, excluir_id?: number | null) =>
  api.get<VerificarDuplicadoResp>(`${BASE}/ciudadanos/verificar-duplicado`, {
    params: { campo, valor, excluir_id: excluir_id ?? undefined },
  })

export const crearCiudadano = (data: CiudadanoCreate) =>
  api.post<Ciudadano>(`${BASE}/ciudadanos`, data)

export const modificarCiudadano = (id: number, data: CiudadanoUpdate) =>
  api.put<Ciudadano>(`${BASE}/ciudadanos/${id}`, data)

export const cambiarEstadoCiudadano = (id: number, activo: boolean) =>
  api.put<Ciudadano>(`${BASE}/ciudadanos/${id}/estado`, undefined, { params: { activo } })

export const empresasVinculadas = (id: number) =>
  api.get<EmpresaVinculada[]>(`${BASE}/ciudadanos/${id}/empresas-vinculadas`)

// ── Empresa (solo lo necesario para sub-form vinculada) ──
export const crearEmpresa = (data: EmpresaCreate) =>
  api.post<{ id_empresa: number }>(`${BASE}/empresas`, data)

export const vincularCiudadanoEmpresa = (data: CiudadanoEmpresaCreate) =>
  api.post(`${BASE}/ciudadano-empresa`, data)
