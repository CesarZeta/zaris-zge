/**
 * Cliente + hooks para notificaciones persistentes del backend
 * (separadas de los toasts efimeros en `stores/notifications`).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './api'

export interface NotificacionBackend {
  id_notificacion: number
  tipo: string
  titulo: string
  mensaje: string | null
  url_destino: string | null
  recurso_tipo: string | null
  recurso_id: number | null
  leida: boolean
  leida_en: string | null
  fecha_alta: string
}

const BASE = '/api/v1/notificaciones'

export const listarNotificaciones = (params?: { leida?: boolean; limit?: number; offset?: number }) =>
  api.get<{ items: NotificacionBackend[]; total: number }>(BASE, { params })

export const contarNoLeidas = () =>
  api.get<{ no_leidas: number }>(`${BASE}/count`)

export const marcarLeida = (id: number) =>
  api.patch<{ id_notificacion: number; leida: boolean }>(`${BASE}/${id}/leer`)

export const marcarTodasLeidas = () =>
  api.patch<{ marcadas: number }>(`${BASE}/leer-todas`)

/**
 * Hook con polling cada 30s. Si quisieramos algo mas reactivo, refactorizar a SSE/WebSocket.
 */
export function useNotificacionesCount(intervaloMs = 30_000) {
  return useQuery({
    queryKey: ['notif-backend', 'count'],
    queryFn: () => contarNoLeidas(),
    refetchInterval: intervaloMs,
    refetchOnWindowFocus: true,
    staleTime: 5_000,
  })
}

export function useNotificaciones(params?: { leida?: boolean; limit?: number }) {
  return useQuery({
    queryKey: ['notif-backend', 'list', params ?? {}],
    queryFn: () => listarNotificaciones(params),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 5_000,
  })
}

export function useMarcarLeida() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => marcarLeida(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notif-backend'] })
    },
  })
}

export function useMarcarTodasLeidas() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => marcarTodasLeidas(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notif-backend'] })
    },
  })
}
