import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { encuestasApi, type ResumenParams } from '../lib/api'

// Las queries de dashboard exigen nivel <= 2 en el backend. El gating de la UI
// vive en index.tsx (WrapNivel); estos hooks se montan solo dentro de las vistas
// ya gateadas, asi que no re-chequean nivel.

export function useResumen(p: ResumenParams) {
  return useQuery({
    queryKey: ['encuestas', 'resumen', p],
    queryFn: () => encuestasApi.resumen(p),
  })
}

export function usePorArea(p: { desde?: string; hasta?: string } = {}) {
  return useQuery({
    queryKey: ['encuestas', 'por-area', p],
    queryFn: () => encuestasApi.porArea(p),
  })
}

export function useEvolucion(meses = 6) {
  return useQuery({
    queryKey: ['encuestas', 'evolucion', meses],
    queryFn: () => encuestasApi.evolucion({ meses }),
  })
}

export function useComentarios(p: { clasificacion?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ['encuestas', 'comentarios', p],
    queryFn: () => encuestasApi.comentarios(p),
  })
}

export function usePendientesContacto() {
  return useQuery({
    queryKey: ['encuestas', 'pendientes-contacto'],
    queryFn: () => encuestasApi.pendientesContacto({ limit: 200 }),
  })
}

export function useAtenderContacto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (idRespuesta: number) => encuestasApi.atender(idRespuesta),
    onSuccess: () => {
      // Atender saca la respuesta de la bandeja y baja el contador de alertas.
      qc.invalidateQueries({ queryKey: ['encuestas', 'pendientes-contacto'] })
      qc.invalidateQueries({ queryKey: ['encuestas', 'resumen'] })
    },
  })
}

export function useEnvios(p: { estado?: string; tipo?: string; id_plantilla?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ['encuestas', 'envios', p],
    queryFn: () => encuestasApi.envios(p),
  })
}

export function useEnvioDetalle(idEnvio: number | null) {
  return useQuery({
    queryKey: ['encuestas', 'envio', idEnvio],
    queryFn: () => encuestasApi.envioDetalle(idEnvio as number),
    enabled: idEnvio != null,
  })
}

export function usePlantillas() {
  return useQuery({
    queryKey: ['encuestas', 'plantillas'],
    queryFn: () => encuestasApi.plantillas(),
  })
}

export function usePlantillaDetalle(idPlantilla: number | null) {
  return useQuery({
    queryKey: ['encuestas', 'plantilla', idPlantilla],
    queryFn: () => encuestasApi.plantillaDetalle(idPlantilla as number),
    enabled: idPlantilla != null,
  })
}
