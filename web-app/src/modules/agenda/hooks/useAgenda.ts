import { useQuery } from '@tanstack/react-query'
import {
  getAgendaRecurso,
  getCalendarioDia,
  getCalendarioMes,
  getCalendarioSemana,
  getRecursosConteos,
  listarUbicacionesAtencion,
} from '../api/agendaApi'
import type { TipoRecurso } from '../types/agenda'

/** Opciones de las queries de grilla/listado. `enabled: false` = búsqueda
 *  diferida (§23: la pantalla no pide nada al entrar); `version` va a la
 *  queryKey para que presionar Buscar con los mismos filtros vuelva a la red
 *  (ver `ui/busqueda.tsx`). Default `enabled: true`: los consumidores que no
 *  pasan opts se comportan igual que antes. Los prefijos de invalidación
 *  (`['agenda']`, `['agenda', 'calendario', ...]`) siguen matcheando. */
export interface OpcionesListado {
  enabled?: boolean
  version?: number
}

export function useCalendarioDia(
  fecha: string,
  tipoRecurso: TipoRecurso | 'todos' = 'todos',
  idSubarea: number | null = null,
  atendido: boolean | null = null,
  scopeSubareaPropia = false,
  idEspacioUbicacion: number | null = null,
  opts: OpcionesListado = {},
) {
  return useQuery({
    queryKey: ['agenda', 'calendario', fecha, tipoRecurso, idSubarea, atendido, scopeSubareaPropia, idEspacioUbicacion, opts.version ?? 0],
    queryFn:  () => getCalendarioDia(fecha, tipoRecurso, idSubarea, atendido, scopeSubareaPropia, idEspacioUbicacion),
    enabled:  opts.enabled ?? true,
  })
}

export function useCalendarioSemana(
  desde: string,
  dias: number,
  tipoRecurso: TipoRecurso | 'todos' = 'todos',
  idSubarea: number | null = null,
  atendido: boolean | null = null,
  scopeSubareaPropia = false,
  idEspacioUbicacion: number | null = null,
  opts: OpcionesListado = {},
) {
  return useQuery({
    queryKey: ['agenda', 'semana', desde, dias, tipoRecurso, idSubarea, atendido, scopeSubareaPropia, idEspacioUbicacion, opts.version ?? 0],
    queryFn:  () => getCalendarioSemana(desde, dias, tipoRecurso, idSubarea, atendido, scopeSubareaPropia, idEspacioUbicacion),
    enabled:  opts.enabled ?? true,
  })
}

/** Ubicaciones de atención para el modo 'ubicacion' de la grilla (F2b). */
export function useUbicacionesAtencion(enabled = true) {
  return useQuery({
    queryKey: ['agenda', 'ubicaciones-atencion'],
    queryFn:  () => listarUbicacionesAtencion(),
    staleTime: 60_000,
    enabled,
  })
}

export function useCalendarioMes(
  anio: number,
  mes: number,
  tipoRecurso: TipoRecurso | 'todos' = 'todos',
  idSubarea: number | null = null,
  opts: OpcionesListado = {},
) {
  return useQuery({
    queryKey: ['agenda', 'mes', anio, mes, tipoRecurso, idSubarea, opts.version ?? 0],
    queryFn:  () => getCalendarioMes(anio, mes, tipoRecurso, idSubarea),
    enabled:  opts.enabled ?? true,
  })
}

export function useAgendaRecurso(tipoRecurso: TipoRecurso, idRecurso: number, desde: string, hasta: string, enabled = true) {
  return useQuery({
    queryKey: ['agenda', 'recurso', tipoRecurso, idRecurso, desde, hasta],
    queryFn:  () => getAgendaRecurso(tipoRecurso, idRecurso, desde, hasta),
    enabled,
  })
}

export function useRecursosConteos() {
  return useQuery({
    queryKey: ['agenda', 'recursos', 'conteos'],
    queryFn:  () => getRecursosConteos(),
    // Conteos cambian pocas veces; cache mas largo evita refetch en cada cambio de tab.
    staleTime: 60_000,
  })
}
