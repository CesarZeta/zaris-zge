import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  buscarEmpresas,
  cambiarEstadoEmpresa,
  crearEmpresa,
  listarEmpresas,
  modificarEmpresa,
  obtenerEmpresa,
  verificarDuplicadoEmpresa,
} from '../api/empresasApi'
import type { EmpresaCreate, EmpresaUpdate } from '../types/empresa'

// ── Lista (preview) ──
export function useEmpresasRecientes(limit = 5) {
  return useQuery({
    queryKey: ['buc', 'empresas', 'recientes', limit],
    queryFn: () => listarEmpresas({ solo_activos: false, limit: 200 }),
    select: (rows) => rows.slice(0, limit),
    staleTime: 30 * 1000,
  })
}

// ── Listado completo ──
export function useEmpresasListado() {
  return useQuery({
    queryKey: ['buc', 'empresas', 'listado'],
    queryFn: () => listarEmpresas({ solo_activos: false, limit: 1000 }),
    staleTime: 30 * 1000,
  })
}

// ── Detalle ──
export function useEmpresa(id: number | null) {
  return useQuery({
    queryKey: ['buc', 'empresas', id],
    queryFn:  () => obtenerEmpresa(id as number),
    enabled:  id != null,
  })
}

// ── Mutations ──
export function useCrearEmpresa() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: EmpresaCreate) => crearEmpresa(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['buc', 'empresas'] })
    },
  })
}

export function useModificarEmpresa(id: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: EmpresaUpdate) => modificarEmpresa(id as number, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['buc', 'empresas'] })
    },
  })
}

export function useCambiarEstadoEmpresa() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) => cambiarEstadoEmpresa(id, activo),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['buc', 'empresas'] })
    },
  })
}

// Re-export imperativos
export { buscarEmpresas, verificarDuplicadoEmpresa }

// El catalogo de actividades vive en el modulo ciudadanos. Re-export para conveniencia.
export { useActividades } from '../../ciudadanos/hooks/useCiudadanos'
