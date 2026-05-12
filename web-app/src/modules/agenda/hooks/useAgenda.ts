import { useQuery } from '@tanstack/react-query'
import {
  getCalendarioDia,
  getCalendarioMes,
  getAgendaRecurso,
} from '../api/agendaApi'
import type { TipoRecurso } from '../types/agenda'

export function useCalendarioDia(
  fecha: string,
  idMunicipio: number,
  tipoRecurso: 'agente' | 'equipo' | 'todos' = 'todos',
  idSubarea: number | null = null,
) {
  return useQuery({
    queryKey: ['agenda', 'calendario', fecha, idMunicipio, tipoRecurso, idSubarea],
    queryFn:  () => getCalendarioDia(fecha, idMunicipio, tipoRecurso, idSubarea),
  })
}

export function useCalendarioMes(anio: number, mes: number, idMunicipio: number) {
  return useQuery({
    queryKey: ['agenda', 'mes', anio, mes, idMunicipio],
    queryFn:  () => getCalendarioMes(anio, mes, idMunicipio),
  })
}

export function useAgendaRecurso(tipoRecurso: TipoRecurso, idRecurso: number, desde: string, hasta: string, enabled = true) {
  return useQuery({
    queryKey: ['agenda', 'recurso', tipoRecurso, idRecurso, desde, hasta],
    queryFn:  () => getAgendaRecurso(tipoRecurso, idRecurso, desde, hasta),
    enabled,
  })
}
