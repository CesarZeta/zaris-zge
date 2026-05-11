import { useQuery } from '@tanstack/react-query'
import { api } from '../../../lib/api'
import type { OTPendiente } from './types'

// Devuelve OTs en estado Pendiente. Filtramos client-side las que no tienen
// agente ni equipo asignado (las que estan "huerfanas" esperando planificacion).
//
// Fuente: GET /api/v1/ot?estado=Pendiente. El backend NO expone "sin asignar"
// como flag, asi que el filtro vive aca.
export function useOTsPendientes(soloSinAsignar = true) {
  return useQuery({
    queryKey: ['ot-pendientes', soloSinAsignar],
    queryFn:  async () => {
      const rows = await api.get<OTPendiente[]>('/api/v1/ot', {
        params: { estado: 'Pendiente', limit: 200 },
      })
      if (!soloSinAsignar) return rows
      return rows.filter((r) => r.id_agente == null && r.id_equipo == null)
    },
    staleTime: 30_000,
  })
}
