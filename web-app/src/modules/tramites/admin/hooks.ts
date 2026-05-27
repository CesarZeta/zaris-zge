/**
 * Hooks react-query para el admin del catalogo de tramites.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarCampo,
  actualizarDocRequerido,
  actualizarEstado,
  actualizarTipo,
  actualizarTransicion,
  archivarVersion,
  crearBorrador,
  crearCampo,
  crearDocRequerido,
  crearEstado,
  crearTipo,
  crearTransicion,
  detalleTipoAdmin,
  detalleVersion,
  eliminarCampo,
  eliminarDocRequerido,
  eliminarEstado,
  eliminarTipo,
  eliminarTransicion,
  publicarVersion,
  type CampoCreateBody,
  type CampoUpdateBody,
  type DocReqCreateBody,
  type DocReqUpdateBody,
  type EstadoCreateBody,
  type EstadoUpdateBody,
  type TipoCreateBody,
  type TipoUpdateBody,
  type TransicionCreateBody,
  type TransicionUpdateBody,
} from './api'
import { listarTiposAdmin } from './api'

const HORA = 60 * 60 * 1000

/* ── Queries ──────────────────────────────────────────── */

export function useTiposCatalogo() {
  // Endpoint admin dedicado: lista TODOS los tipos (publicados, borradores y
  // sin publicar) con es_sistema + estado_version. El endpoint publico
  // /tramites/tipos solo devuelve publicados, por eso no sirve acá.
  return useQuery({
    queryKey: ['tramites', 'admin', 'tipos'],
    queryFn: () => listarTiposAdmin(),
    staleTime: HORA,
  })
}

export function useTipoAdmin(id: number | null) {
  return useQuery({
    queryKey: ['tramites', 'admin', 'tipo', id],
    queryFn: () => detalleTipoAdmin(id!),
    enabled: id != null,
    staleTime: 10 * 1000,
  })
}

export function useVersionDetalle(idVersion: number | null) {
  return useQuery({
    queryKey: ['tramites', 'admin', 'version', idVersion],
    queryFn: () => detalleVersion(idVersion!),
    enabled: idVersion != null,
    staleTime: 5 * 1000,
  })
}

/* ── Tipos: mutations ─────────────────────────────────── */

function useInvalidarCatalogo() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['tramites', 'tipos'] })
    qc.invalidateQueries({ queryKey: ['tramites', 'admin'] })
  }
}

export function useCrearTipo() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (body: TipoCreateBody) => crearTipo(body),
    onSuccess: () => inv(),
  })
}

export function useActualizarTipo(id: number) {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (body: TipoUpdateBody) => actualizarTipo(id, body),
    onSuccess: () => inv(),
  })
}

export function useEliminarTipo() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (id: number) => eliminarTipo(id),
    onSuccess: () => inv(),
  })
}

/* ── Versiones ────────────────────────────────────────── */

export function useCrearBorrador() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (idTipo: number) => crearBorrador(idTipo),
    onSuccess: () => inv(),
  })
}

export function usePublicarVersion() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (idVersion: number) => publicarVersion(idVersion),
    onSuccess: () => inv(),
  })
}

export function useArchivarVersion() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (idVersion: number) => archivarVersion(idVersion),
    onSuccess: () => inv(),
  })
}

/* ── Campos ──────────────────────────────────────────── */

export function useCrearCampo() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idVersion, body }: { idVersion: number; body: CampoCreateBody }) =>
      crearCampo(idVersion, body),
    onSuccess: () => inv(),
  })
}

export function useActualizarCampo() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idCampo, body }: { idCampo: number; body: CampoUpdateBody }) =>
      actualizarCampo(idCampo, body),
    onSuccess: () => inv(),
  })
}

export function useEliminarCampo() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (idCampo: number) => eliminarCampo(idCampo),
    onSuccess: () => inv(),
  })
}

/** Reordena dos campos intercambiando su `orden` (BUG-05: botones ↑↓).
 *  Reusa el PUT de campo: 2 requests, 1 sola invalidación. */
export function useReordenarCampo() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: async (args: { aId: number; aOrden: number; bId: number; bOrden: number }) => {
      await actualizarCampo(args.aId, { orden: args.bOrden })
      await actualizarCampo(args.bId, { orden: args.aOrden })
    },
    onSuccess: () => inv(),
  })
}

/* ── Estados ─────────────────────────────────────────── */

export function useCrearEstado() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idVersion, body }: { idVersion: number; body: EstadoCreateBody }) =>
      crearEstado(idVersion, body),
    onSuccess: () => inv(),
  })
}

export function useActualizarEstado() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idEstado, body }: { idEstado: number; body: EstadoUpdateBody }) =>
      actualizarEstado(idEstado, body),
    onSuccess: () => inv(),
  })
}

export function useEliminarEstado() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (idEstado: number) => eliminarEstado(idEstado),
    onSuccess: () => inv(),
  })
}

/* ── Transiciones ────────────────────────────────────── */

export function useCrearTransicion() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idVersion, body }: { idVersion: number; body: TransicionCreateBody }) =>
      crearTransicion(idVersion, body),
    onSuccess: () => inv(),
  })
}

export function useActualizarTransicion() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idTrans, body }: { idTrans: number; body: TransicionUpdateBody }) =>
      actualizarTransicion(idTrans, body),
    onSuccess: () => inv(),
  })
}

export function useEliminarTransicion() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (idTrans: number) => eliminarTransicion(idTrans),
    onSuccess: () => inv(),
  })
}

/* ── Documentos requeridos ───────────────────────────── */

export function useCrearDocReq() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idVersion, body }: { idVersion: number; body: DocReqCreateBody }) =>
      crearDocRequerido(idVersion, body),
    onSuccess: () => inv(),
  })
}

export function useActualizarDocReq() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: ({ idDoc, body }: { idDoc: number; body: DocReqUpdateBody }) =>
      actualizarDocRequerido(idDoc, body),
    onSuccess: () => inv(),
  })
}

export function useEliminarDocReq() {
  const inv = useInvalidarCatalogo()
  return useMutation({
    mutationFn: (idDoc: number) => eliminarDocRequerido(idDoc),
    onSuccess: () => inv(),
  })
}
