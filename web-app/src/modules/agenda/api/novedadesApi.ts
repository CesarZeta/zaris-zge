import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../../lib/api'

const BASE = '/api/v1/agenda'

// ===== Tipos ================================================================
export type TipoNovedad = 'inasistencia' | 'licencia' | 'vacaciones' | 'comision' | 'otro'
export type AmbitoFeriado = 'NACIONAL' | 'PROVINCIAL' | 'MUNICIPAL'

export interface Novedad {
  id_agente_novedad: number
  id_agente: number
  agente_nombre: string | null
  tipo: TipoNovedad
  fecha_desde: string
  fecha_hasta: string
  hora_inicio: string | null
  hora_fin: string | null
  motivo: string | null
  activo: boolean
  fecha_alta: string
}

export interface NovedadCreate {
  id_agente: number
  tipo: TipoNovedad
  fecha_desde: string
  fecha_hasta: string
  hora_inicio?: string | null
  hora_fin?: string | null
  motivo?: string | null
}

export interface Feriado {
  id_agenda_feriado: number
  fecha: string
  descripcion: string | null
  ambito: AmbitoFeriado | null
  activo: boolean
}

export interface FeriadoCreate {
  fecha: string
  descripcion: string
  ambito: AmbitoFeriado
}

// ===== API ==================================================================
export function listarNovedades(params?: { id_agente?: number; desde?: string }) {
  return api.get<Novedad[]>(`${BASE}/novedades`, { params })
}
export function crearNovedad(payload: NovedadCreate) {
  return api.post<Novedad>(`${BASE}/novedades`, payload)
}
export function eliminarNovedad(id: number) {
  return api.delete<void>(`${BASE}/novedades/${id}`)
}

export function listarFeriados(params?: { anio?: number }) {
  return api.get<Feriado[]>(`${BASE}/feriados`, { params })
}
export function crearFeriado(payload: FeriadoCreate) {
  return api.post<Feriado>(`${BASE}/feriados`, payload)
}
export function eliminarFeriado(id: number) {
  return api.delete<void>(`${BASE}/feriados/${id}`)
}

// ===== Hooks ================================================================
// Mutar novedades/feriados cambia la disponibilidad efectiva -> invalidar calendarios.
function invalidarTodo(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['agenda', 'novedades'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'feriados'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'calendario'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'semana'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'mes'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'disponibilidad'] })
}

export function useNovedades(params?: { id_agente?: number; desde?: string }) {
  return useQuery({ queryKey: ['agenda', 'novedades', params], queryFn: () => listarNovedades(params) })
}
export function useCrearNovedad() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: crearNovedad, onSuccess: () => invalidarTodo(qc) })
}
export function useEliminarNovedad() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: eliminarNovedad, onSuccess: () => invalidarTodo(qc) })
}

export function useFeriados(params?: { anio?: number }) {
  return useQuery({ queryKey: ['agenda', 'feriados', params], queryFn: () => listarFeriados(params) })
}
export function useCrearFeriado() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: crearFeriado, onSuccess: () => invalidarTodo(qc) })
}
export function useEliminarFeriado() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: eliminarFeriado, onSuccess: () => invalidarTodo(qc) })
}
