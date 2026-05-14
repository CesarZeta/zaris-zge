import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarDisponibilidad,
  crearDisponibilidad,
  eliminarDisponibilidad,
  getDisponibilidadEfectiva,
  listarDisponibilidad,
} from '../api/agendaApi'
import type {
  DisponibilidadRecursoCreatePayload,
  DisponibilidadRecursoUpdatePayload,
  TipoRecurso,
} from '../types/agenda'

export function useDisponibilidad(params?: { tipo_recurso?: TipoRecurso; id_recurso?: number; id_municipio?: number }) {
  return useQuery({
    queryKey: ['agenda', 'disponibilidad', params],
    queryFn:  () => listarDisponibilidad(params),
  })
}

export function useDisponibilidadEfectiva(tipoRecurso: TipoRecurso, idRecurso: number, fecha: string, enabled = true) {
  return useQuery({
    queryKey: ['agenda', 'disponibilidad', 'efectiva', tipoRecurso, idRecurso, fecha],
    queryFn:  () => getDisponibilidadEfectiva(tipoRecurso, idRecurso, fecha),
    enabled,
  })
}

function invalidateCalendariosYDisp(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['agenda', 'disponibilidad'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'calendario'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'semana'] })
  qc.invalidateQueries({ queryKey: ['agenda', 'mes'] })
}

export function useCrearDisponibilidad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: DisponibilidadRecursoCreatePayload) => crearDisponibilidad(payload),
    onSuccess: () => invalidateCalendariosYDisp(qc),
  })
}

export function useActualizarDisponibilidad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: DisponibilidadRecursoUpdatePayload }) =>
      actualizarDisponibilidad(id, payload),
    onSuccess: () => invalidateCalendariosYDisp(qc),
  })
}

export function useEliminarDisponibilidad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => eliminarDisponibilidad(id),
    onSuccess: () => invalidateCalendariosYDisp(qc),
  })
}
