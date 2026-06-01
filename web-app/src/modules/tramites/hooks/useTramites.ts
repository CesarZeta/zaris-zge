import { useCallback, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listarTipos,
  obtenerTipo,
  listarBandeja,
  listarMiBandeja,
  obtenerTramite,
  obtenerMovimientos,
  obtenerTransicionesPermitidas,
  obtenerDocumentos,
  crearTramite,
  tomarTramite,
  liberarTramite,
  transicionarTramite,
  pasarTramite,
  comentarTramite,
  relacionarTramite,
  resolverAprobacion,
  marcarResultadoTramite,
} from '../lib/api'
import type { BandejaParams, CrearTramiteBody, TramiteResultado } from '../types'

const MIN = 60 * 1000
const HORA = 60 * MIN

/* ── Catálogo de tipos ───────────────────────────────────── */

export function useTiposTramite(params?: { iniciador?: string; q?: string }) {
  return useQuery({
    queryKey: ['tramites', 'tipos', params ?? {}],
    queryFn: () => listarTipos(params),
    staleTime: HORA,
  })
}

export function useTipoTramiteDetalle(id: number | null) {
  return useQuery({
    queryKey: ['tramites', 'tipo', id],
    queryFn: () => obtenerTipo(id!),
    enabled: id != null,
    staleTime: HORA,
  })
}

/* ── Bandeja ─────────────────────────────────────────────── */

export function useBandeja(params: BandejaParams) {
  return useQuery({
    queryKey: ['tramites', 'bandeja', params],
    queryFn: () => listarBandeja(params),
    staleTime: 15 * 1000,
    placeholderData: (prev) => prev,
  })
}

export type MiBandejaParams = {
  estado_codigo?: string
  tipo_codigo?: string
  sin_tomar?: boolean
  q?: string
  limit?: number
  offset?: number
}

export function useMiBandeja(params: MiBandejaParams) {
  return useQuery({
    queryKey: ['tramites', 'mi-bandeja', params],
    queryFn: () => listarMiBandeja(params),
    staleTime: 15 * 1000,
    placeholderData: (prev) => prev,
  })
}

/* ── Detalle + timeline + transiciones ──────────────────── */

export function useTramite(numero: string | null) {
  const qc = useQueryClient()

  const detalle = useQuery({
    queryKey: ['tramites', 'detalle', numero],
    queryFn: () => obtenerTramite(numero!),
    enabled: numero != null && numero !== '',
    staleTime: 10 * 1000,
  })

  const movimientos = useQuery({
    queryKey: ['tramites', 'movimientos', numero],
    queryFn: () => obtenerMovimientos(numero!, { limit: 200 }),
    enabled: numero != null && numero !== '',
    staleTime: 10 * 1000,
  })

  const transiciones = useQuery({
    queryKey: ['tramites', 'transiciones', numero],
    queryFn: () => obtenerTransicionesPermitidas(numero!),
    enabled: numero != null && numero !== '',
    staleTime: 5 * 1000,
  })

  const documentos = useQuery({
    queryKey: ['tramites', 'documentos', numero],
    queryFn: () => obtenerDocumentos(numero!),
    enabled: numero != null && numero !== '',
    staleTime: 10 * 1000,
  })

  const refetch = useCallback(async () => {
    if (!numero) return
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['tramites', 'detalle', numero] }),
      qc.invalidateQueries({ queryKey: ['tramites', 'movimientos', numero] }),
      qc.invalidateQueries({ queryKey: ['tramites', 'transiciones', numero] }),
      qc.invalidateQueries({ queryKey: ['tramites', 'documentos', numero] }),
    ])
  }, [qc, numero])

  return { detalle, movimientos, transiciones, documentos, refetch }
}

/* ── Mutaciones ──────────────────────────────────────────── */

export function useCrearTramite() {
  return useMutation({ mutationFn: (body: CrearTramiteBody) => crearTramite(body) })
}

export function useTomarTramite(numero: string) {
  return useMutation({ mutationFn: () => tomarTramite(numero) })
}

export function useLiberarTramite(numero: string) {
  return useMutation({ mutationFn: () => liberarTramite(numero) })
}

export function useTransicionarTramite(numero: string) {
  return useMutation({
    mutationFn: (body: { id_tipo_tramite_transicion: number; comentario?: string }) =>
      transicionarTramite(numero, body),
  })
}

export function usePasarTramite(numero: string) {
  return useMutation({
    mutationFn: (body: { destinatario_tipo: 'subarea' | 'equipo' | 'agente'; destinatario_id: number; comentario?: string }) =>
      pasarTramite(numero, body),
  })
}

export function useComentarTramite(numero: string) {
  return useMutation({
    mutationFn: (comentario: string) => comentarTramite(numero, comentario),
  })
}

export function useRelacionarTramite(numero: string) {
  return useMutation({
    mutationFn: (body: { id_tramite_b: number; comentario?: string }) =>
      relacionarTramite(numero, body),
  })
}

export function useResolverAprobacion(numero: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: {
      idAprob: number
      decision: 'aprobada' | 'rechazada'
      comentario?: string
    }) => resolverAprobacion(numero, vars.idAprob, { decision: vars.decision, comentario: vars.comentario }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tramites', 'detalle', numero] })
      void qc.invalidateQueries({ queryKey: ['tramites', 'movimientos', numero] })
      void qc.invalidateQueries({ queryKey: ['tramites', 'transiciones', numero] })
    },
  })
}

export function useMarcarResultado(numero: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { resultado: TramiteResultado; comentario?: string }) =>
      marcarResultadoTramite(numero, vars),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tramites', 'detalle', numero] })
      void qc.invalidateQueries({ queryKey: ['tramites', 'movimientos', numero] })
    },
  })
}

/* ── Autocompletar búsqueda de trámites ─────────────────── */

export function useBuscarTramite(_q?: string) {
  const [resultados, setResultados] = useState<Array<{ id_tramite: number; numero_expediente: string; asunto: string }>>([])
  const [loading, setLoading] = useState(false)

  const buscar = useCallback(async (texto: string) => {
    if (texto.trim().length < 3) { setResultados([]); return }
    setLoading(true)
    try {
      const res = await listarBandeja({ q: texto, limit: 10 })
      setResultados(res.items.map((i) => ({
        id_tramite: i.id_tramite,
        numero_expediente: i.numero_expediente,
        asunto: i.asunto,
      })))
    } catch {
      setResultados([])
    } finally {
      setLoading(false)
    }
  }, [])

  return { resultados, loading, buscar }
}
