import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { encuestasApi, type ParamsEnvios, type ResumenParams } from '../lib/api'
import type { Circuito } from '../lib/types'

// Las queries de dashboard exigen nivel <= 2 en el backend. El gating de la UI
// vive en index.tsx (WrapNivel); estos hooks se montan solo dentro de las vistas
// ya gateadas, asi que no re-chequean nivel.

export function useResumen(p: ResumenParams) {
  return useQuery({
    queryKey: ['encuestas', 'resumen', p],
    queryFn: () => encuestasApi.resumen(p),
  })
}

export function usePorArea(p: { desde?: string; hasta?: string; limit?: number; tipo?: Circuito } = {}) {
  return useQuery({
    queryKey: ['encuestas', 'por-area', p],
    queryFn: () => encuestasApi.porArea(p),
  })
}

export function usePorCircuito(p: { desde?: string; hasta?: string } = {}) {
  return useQuery({
    queryKey: ['encuestas', 'por-circuito', p],
    queryFn: () => encuestasApi.porCircuito(p),
  })
}

export function useEvolucion(meses = 6, tipo?: Circuito) {
  return useQuery({
    queryKey: ['encuestas', 'evolucion', meses, tipo],
    queryFn: () => encuestasApi.evolucion({ meses, tipo }),
  })
}

export function useComentarios(p: { clasificacion?: number; limit?: number; tipo?: Circuito } = {}) {
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

/** Opciones del listado de envíos. `enabled: false` = búsqueda diferida (§23:
 *  la pantalla no pide nada al entrar); `version` en la queryKey para que
 *  Buscar con los mismos filtros vuelva a la red (ver `ui/busqueda.tsx`). */
export interface OpcionesListado {
  enabled?: boolean
  version?: number
}

export function useEnvios(p: ParamsEnvios = {}, opts: OpcionesListado = {}) {
  return useQuery({
    queryKey: ['encuestas', 'envios', p, opts.version ?? 0],
    queryFn: () => encuestasApi.envios(p),
    enabled: opts.enabled ?? true,
    // Cambiar el orden no vacía la tabla mientras llega la respuesta.
    placeholderData: keepPreviousData,
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
