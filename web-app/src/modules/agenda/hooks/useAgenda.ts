import { useQuery } from '@tanstack/react-query'
import {
  getAgendaRecurso,
  getCalendarioDia,
  getCalendarioMes,
  getCalendarioSemana,
  getRecursosConteos,
} from '../api/agendaApi'
import type { TipoRecurso } from '../types/agenda'

export function useCalendarioDia(
  fecha: string,
  idMunicipio: number,
  tipoRecurso: TipoRecurso | 'todos' = 'todos',
  idSubarea: number | null = null,
  atendido: boolean | null = null,
  scopeSubareaPropia = false,
) {
  return useQuery({
    queryKey: ['agenda', 'calendario', fecha, idMunicipio, tipoRecurso, idSubarea, atendido, scopeSubareaPropia],
    queryFn:  () => getCalendarioDia(fecha, idMunicipio, tipoRecurso, idSubarea, atendido, scopeSubareaPropia),
  })
}

export function useCalendarioSemana(
  desde: string,
  dias: number,
  idMunicipio: number,
  tipoRecurso: TipoRecurso | 'todos' = 'todos',
  idSubarea: number | null = null,
  atendido: boolean | null = null,
  scopeSubareaPropia = false,
) {
  return useQuery({
    queryKey: ['agenda', 'semana', desde, dias, idMunicipio, tipoRecurso, idSubarea, atendido, scopeSubareaPropia],
    queryFn:  () => getCalendarioSemana(desde, dias, idMunicipio, tipoRecurso, idSubarea, atendido, scopeSubareaPropia),
  })
}

export function useCalendarioMes(
  anio: number,
  mes: number,
  idMunicipio: number,
  tipoRecurso: TipoRecurso | 'todos' = 'todos',
  idSubarea: number | null = null,
) {
  return useQuery({
    queryKey: ['agenda', 'mes', anio, mes, idMunicipio, tipoRecurso, idSubarea],
    queryFn:  () => getCalendarioMes(anio, mes, idMunicipio, tipoRecurso, idSubarea),
  })
}

export function useAgendaRecurso(tipoRecurso: TipoRecurso, idRecurso: number, desde: string, hasta: string, enabled = true) {
  return useQuery({
    queryKey: ['agenda', 'recurso', tipoRecurso, idRecurso, desde, hasta],
    queryFn:  () => getAgendaRecurso(tipoRecurso, idRecurso, desde, hasta),
    enabled,
  })
}

export function useRecursosConteos(idMunicipio: number) {
  return useQuery({
    queryKey: ['agenda', 'recursos', 'conteos', idMunicipio],
    queryFn:  () => getRecursosConteos(idMunicipio),
    // Conteos cambian pocas veces; cache mas largo evita refetch en cada cambio de tab.
    staleTime: 60_000,
  })
}
