import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  buscarEmpresas,
  cambiarEstadoEmpresa,
  crearEmpresa,
  getTiposRepresentacion,
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
/** Opciones de las queries de listado. `enabled: false` = búsqueda diferida
 *  (§23: la pantalla no pide nada al entrar); `version` va a la queryKey para
 *  que "Ver listado" vuelva a la red aunque no cambie nada (ver
 *  `ui/busqueda.tsx`). El prefijo de invalidación `['buc','empresas']` sigue
 *  matcheando. */
export interface OpcionesListado {
  enabled?: boolean
  version?: number
}

export function useEmpresasListado(opts: OpcionesListado = {}) {
  return useQuery({
    queryKey: ['buc', 'empresas', 'listado', opts.version ?? 0],
    queryFn: () => listarEmpresas({ solo_activos: false, limit: 1000 }),
    staleTime: 30 * 1000,
    enabled: opts.enabled ?? true,
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

// ── Catálogo tipos de representación ──
export function useTiposRepresentacion() {
  return useQuery({
    queryKey: ['buc', 'tipo-representacion'],
    queryFn: getTiposRepresentacion,
    staleTime: 5 * 60 * 1000,
  })
}

// Re-export imperativos
export { buscarEmpresas, verificarDuplicadoEmpresa }

// El catalogo de actividades vive en el modulo ciudadanos. Re-export para conveniencia.
export { useActividades } from '../../ciudadanos/hooks/useCiudadanos'
