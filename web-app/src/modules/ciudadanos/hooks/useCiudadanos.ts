import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  buscarCiudadanos,
  cambiarEstadoCiudadano,
  crearCiudadano,
  crearEmpresa,
  empresasVinculadas,
  getActividades,
  getNacionalidades,
  getTiposRepresentacion,
  listarCiudadanos,
  modificarCiudadano,
  obtenerCiudadano,
  verificarDuplicadoCiudadano,
} from '../api/ciudadanosApi'
import type { CiudadanoCreate, CiudadanoUpdate, EmpresaCreate } from '../types/ciudadano'

const HORA = 60 * 60 * 1000

// ── Catalogos (cache largo: cambian poco) ──
export function useNacionalidades() {
  return useQuery({ queryKey: ['buc', 'nacionalidades'], queryFn: getNacionalidades, staleTime: HORA })
}

export function useTiposRepresentacion() {
  return useQuery({ queryKey: ['buc', 'tipos-rep'], queryFn: getTiposRepresentacion, staleTime: HORA })
}

export function useActividades() {
  return useQuery({ queryKey: ['buc', 'actividades'], queryFn: getActividades, staleTime: HORA })
}

// ── Lista (preview ultimos N) ──
export function useCiudadanosRecientes(limit = 5) {
  return useQuery({
    queryKey: ['buc', 'ciudadanos', 'recientes', limit],
    queryFn: () => listarCiudadanos({ solo_activos: false, limit: 200 }),
    select: (rows) => rows.slice(0, limit),
    staleTime: 30 * 1000,
  })
}

// ── Listado completo ──
export function useCiudadanosListado() {
  return useQuery({
    queryKey: ['buc', 'ciudadanos', 'listado'],
    queryFn: () => listarCiudadanos({ solo_activos: false, limit: 1000 }),
    staleTime: 30 * 1000,
  })
}

// ── Detalle ──
export function useCiudadano(id: number | null) {
  return useQuery({
    queryKey: ['buc', 'ciudadanos', id],
    queryFn:  () => obtenerCiudadano(id as number),
    enabled:  id != null,
  })
}

// ── Empresas vinculadas ──
export function useEmpresasVinculadas(id: number | null) {
  return useQuery({
    queryKey: ['buc', 'ciudadanos', id, 'empresas-vinculadas'],
    queryFn:  () => empresasVinculadas(id as number),
    enabled:  id != null,
  })
}

// ── Mutations ──
export function useCrearCiudadano() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CiudadanoCreate) => crearCiudadano(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['buc', 'ciudadanos'] })
    },
  })
}

export function useModificarCiudadano(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CiudadanoUpdate) => modificarCiudadano(id as number, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['buc', 'ciudadanos'] })
    },
  })
}

export function useCambiarEstadoCiudadano() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) => cambiarEstadoCiudadano(id, activo),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['buc', 'ciudadanos'] })
    },
  })
}

export function useCrearEmpresaYVincular() {
  const qc = useQueryClient()
  return useMutation({
    // El backend crea empresa + vínculo ciudadano_empresa en una sola transacción
    // (ya no hay dos requests separados que podían dejar una empresa huérfana si el
    // segundo fallaba). El vecino representante viaja dentro del payload de empresa.
    mutationFn: async ({ empresa, id_ciudadano, id_tipo_representacion }: {
      empresa: Omit<EmpresaCreate, 'id_ciudadano' | 'id_tipo_representacion'>
      id_ciudadano: number
      id_tipo_representacion: number
    }) => {
      return await crearEmpresa({ ...empresa, id_ciudadano, id_tipo_representacion })
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['buc', 'ciudadanos', vars.id_ciudadano, 'empresas-vinculadas'] })
    },
  })
}

// ── Busqueda libre (no usa useQuery, retorna fn imperativa) ──
export { buscarCiudadanos, verificarDuplicadoCiudadano }
