import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarEspacio,
  crearEspacio,
  desvincularAgenteDeEspacio,
  detalleEspacio,
  eliminarEspacio,
  listarEspacios,
  vincularAgenteAEspacio,
} from '../api/agendaApi'
import type { EspacioAgendaCreatePayload, EspacioAgendaUpdatePayload } from '../types/agenda'

export function useEspacios(params?: { atendido?: boolean; q?: string; id_municipio?: number; limit?: number }) {
  return useQuery({
    queryKey: ['agenda', 'espacios', params],
    queryFn:  async () => (await listarEspacios(params)).data,
  })
}

export function useEspacio(idEspacio: number | null) {
  return useQuery({
    queryKey: ['agenda', 'espacio', idEspacio],
    queryFn:  () => detalleEspacio(idEspacio!),
    enabled:  idEspacio != null,
  })
}

export function useCrearEspacio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: EspacioAgendaCreatePayload) => crearEspacio(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agenda', 'espacios'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'recursos', 'conteos'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'calendario'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'semana'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'mes'] })
    },
  })
}

export function useActualizarEspacio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: EspacioAgendaUpdatePayload }) => actualizarEspacio(id, payload),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['agenda', 'espacios'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'espacio', vars.id] })
      qc.invalidateQueries({ queryKey: ['agenda', 'recursos', 'conteos'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'calendario'] })
    },
  })
}

export function useEliminarEspacio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => eliminarEspacio(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agenda', 'espacios'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'recursos', 'conteos'] })
      qc.invalidateQueries({ queryKey: ['agenda', 'calendario'] })
    },
  })
}

export function useVincularAgente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ idEspacio, id_agente }: { idEspacio: number; id_agente: number }) =>
      vincularAgenteAEspacio(idEspacio, id_agente),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['agenda', 'espacio', vars.idEspacio] })
      qc.invalidateQueries({ queryKey: ['agenda', 'calendario'] })
    },
  })
}

export function useDesvincularAgente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ idEspacio, idEspacioAgente }: { idEspacio: number; idEspacioAgente: number }) =>
      desvincularAgenteDeEspacio(idEspacio, idEspacioAgente),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['agenda', 'espacio', vars.idEspacio] })
      qc.invalidateQueries({ queryKey: ['agenda', 'calendario'] })
    },
  })
}
