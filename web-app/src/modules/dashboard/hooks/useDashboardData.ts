import { useQuery } from '@tanstack/react-query'
import { api } from '../../../lib/api'
import type { ReclamoListado } from '../../reclamos/types/reclamo'

// Tipos minimos de cada endpoint (no traemos los completos para no acoplarnos).
interface StatsReclamos { [estado: string]: number }
interface UsuarioLite { id_usuario: number; activo: boolean }
interface AgenteLite  { id_agente: number; activo: boolean }
interface EmpresaLite { id_empresa: number; activo: boolean }

const MINUTO = 60 * 1000

// Reclamos activos (excluye Resuelto/Cancelado) — base para el mapa.
async function getReclamosActivos(): Promise<ReclamoListado[]> {
  // El endpoint acepta filtros opcionales; sin filtros trae todos.
  const todos = await api.get<ReclamoListado[]>('/api/v1/reclamos', { params: { limit: 500 } })
  return todos.filter((r) => r.estado !== 'Resuelto' && r.estado !== 'Cancelado')
}

// Conteo de ciudadanos via header X-Total-Count.
async function getCountCiudadanos(): Promise<number> {
  const { headers } = await api.getWithHeaders<unknown[]>('/api/v1/buc/ciudadanos/buscar', {
    params: { q: 'a', limit: 1 },
  })
  const total = headers.get('X-Total-Count')
  return total ? Number(total) : 0
}

// Conteo de empresas: no expone X-Total-Count, traemos limit=500 y contamos.
// Aceptable porque tipicamente < 100 empresas en municipio chico.
async function getCountEmpresas(): Promise<number> {
  const data = await api.get<EmpresaLite[]>('/api/v1/buc/empresas/buscar', {
    params: { q: 'a', limit: 500 },
  })
  return data.length
}

// Conteos via /admin/* (limit 500).
async function getCountUsuarios(): Promise<number> {
  const data = await api.get<UsuarioLite[]>('/api/v1/admin/usuarios', { params: { limit: 500 } })
  return data.filter((u) => u.activo).length
}

async function getCountAgentes(): Promise<number> {
  const data = await api.get<AgenteLite[]>('/api/v1/admin/agentes', { params: { limit: 500 } })
  return data.filter((a) => a.activo).length
}

export function useReclamosActivos() {
  return useQuery({
    queryKey: ['dashboard', 'reclamos-activos'],
    queryFn: getReclamosActivos,
    staleTime: MINUTO,
  })
}

export function useStatsReclamos() {
  return useQuery({
    queryKey: ['dashboard', 'stats-reclamos'],
    queryFn: () => api.get<StatsReclamos>('/api/v1/reclamos/stats'),
    staleTime: MINUTO,
  })
}

export function useCountCiudadanos() {
  return useQuery({
    queryKey: ['dashboard', 'count-ciudadanos'],
    queryFn: getCountCiudadanos,
    staleTime: 5 * MINUTO,
  })
}

export function useCountEmpresas() {
  return useQuery({
    queryKey: ['dashboard', 'count-empresas'],
    queryFn: getCountEmpresas,
    staleTime: 5 * MINUTO,
  })
}

export function useCountUsuarios() {
  return useQuery({
    queryKey: ['dashboard', 'count-usuarios'],
    queryFn: getCountUsuarios,
    staleTime: 5 * MINUTO,
  })
}

export function useCountAgentes() {
  return useQuery({
    queryKey: ['dashboard', 'count-agentes'],
    queryFn: getCountAgentes,
    staleTime: 5 * MINUTO,
  })
}
