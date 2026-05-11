import { useMutation, useQueryClient } from '@tanstack/react-query'
import { actualizarOcupacion, crearOcupacion, eliminarOcupacion } from '../api/agendaApi'
import type { OcupacionCreatePayload, OcupacionUpdatePayload } from '../types/agenda'

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['agenda'] })
}

export function useCrearOcupacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: OcupacionCreatePayload) => crearOcupacion(p),
    onSuccess:  () => invalidate(qc),
  })
}

export function useActualizarOcupacion(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: OcupacionUpdatePayload) => actualizarOcupacion(id, p),
    onSuccess:  () => invalidate(qc),
  })
}

export function useEliminarOcupacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => eliminarOcupacion(id),
    onSuccess:  () => invalidate(qc),
  })
}

export function useAsignarEncargado() {
  const qc = useQueryClient()
  // delegamos en el modulo agenda directamente
  // este hook lo importamos solo si hace falta; lo dejamos disponible
  return useMutation({
    mutationFn: async (args: { idEvento: number; tipo_recurso: 'agente' | 'equipo'; id_recurso: number }) => {
      const { asignarEncargado } = await import('../api/agendaApi')
      return asignarEncargado(args.idEvento, args.tipo_recurso, args.id_recurso)
    },
    onSuccess: () => invalidate(qc),
  })
}

export function useDesasignarEncargado() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (args: { idEvento: number; idEncargado: number }) => {
      const { desasignarEncargado } = await import('../api/agendaApi')
      return desasignarEncargado(args.idEvento, args.idEncargado)
    },
    onSuccess: () => invalidate(qc),
  })
}
