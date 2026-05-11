import { useMutation, useQueryClient } from '@tanstack/react-query'
import { actualizarOcupacion, crearOcupacion } from '../api/agendaApi'
import { useNotificationsStore } from '../../../stores/notifications'
import type { OcupacionCreatePayload, OcupacionUpdatePayload } from '../types/agenda'

export function useDragMutations() {
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)

  const moverOcupacion = useMutation({
    mutationFn: (args: { id: number; payload: OcupacionUpdatePayload }) =>
      actualizarOcupacion(args.id, args.payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['agenda'] })
      if (data.conflictos.length > 0) {
        push({
          kind: 'info',
          title: 'Movimiento con conflicto',
          body: `${data.conflictos.length} solapamiento(s) detectado(s). Revisar Conflictos.`,
        })
      } else {
        push({ kind: 'success', title: 'Ocupacion actualizada' })
      }
    },
    onError: (err: Error) => {
      push({ kind: 'error', title: 'No se pudo mover', body: err.message })
    },
  })

  const crearDesdeOT = useMutation({
    mutationFn: (payload: OcupacionCreatePayload) => crearOcupacion(payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['agenda'] })
      qc.invalidateQueries({ queryKey: ['ot-pendientes'] })
      if (data.conflictos.length > 0) {
        push({
          kind: 'info',
          title: 'OT planificada con conflicto',
          body: `${data.conflictos.length} solapamiento(s) detectado(s).`,
        })
      } else {
        push({ kind: 'success', title: 'OT planificada en agenda' })
      }
    },
    onError: (err: Error) => {
      push({ kind: 'error', title: 'No se pudo planificar', body: err.message })
    },
  })

  return { moverOcupacion, crearDesdeOT }
}
