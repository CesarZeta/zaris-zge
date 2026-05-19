/**
 * Cliente HTTP para el admin del catalogo de tramites.
 * Endpoints bajo /api/v1/admin/tramites. Permisos: nivel_acceso <= 2.
 */
import { api } from '../../../lib/api'
import type {
  TipoTramiteAdmin,
  VersionAdmin,
  TipoTramiteCampo,
  TipoTramiteEstado,
  TipoTramiteTransicion,
  TipoTramiteDocRequerido,
} from '../types'

const BASE = '/api/v1/admin/tramites'

/* ── Tipos (POST/PUT/DELETE) ────────────────────────────── */

export interface TipoCreateBody {
  codigo: string
  nombre: string
  descripcion?: string | null
  prefijo: string
  iniciadores_permitidos: string[]
  permite_representante?: boolean
  incluye_municipio?: boolean
  incluye_anio?: boolean
  largo_correlativo?: number
  separador?: string
  correlativo_reinicia_anual?: boolean
  icono?: string | null
  color?: string | null
  id_municipio?: number
}

export interface TipoUpdateBody {
  nombre?: string
  descripcion?: string | null
  prefijo?: string
  iniciadores_permitidos?: string[]
  permite_representante?: boolean
  incluye_municipio?: boolean
  incluye_anio?: boolean
  largo_correlativo?: number
  separador?: string
  correlativo_reinicia_anual?: boolean
  icono?: string | null
  color?: string | null
}

export const crearTipo = (body: TipoCreateBody) =>
  api.post<TipoTramiteAdmin>(`${BASE}/tipos`, body)

export const actualizarTipo = (id: number, body: TipoUpdateBody) =>
  api.put<TipoTramiteAdmin>(`${BASE}/tipos/${id}`, body)

export const eliminarTipo = (id: number) =>
  api.delete(`${BASE}/tipos/${id}`)

export const detalleTipoAdmin = (id: number) =>
  api.get<TipoTramiteAdmin>(`${BASE}/tipos/${id}/admin`)

/* ── Versiones ──────────────────────────────────────────── */

export interface DetalleVersion {
  id_tipo_tramite_version: number
  id_tipo_tramite: number
  version_num: number
  estado: 'borrador' | 'publicado' | 'archivado'
  publicada_en: string | null
  cant_tramites: number
  campos: TipoTramiteCampo[]
  estados: TipoTramiteEstado[]
  transiciones: TipoTramiteTransicion[]
  documentos_requeridos: TipoTramiteDocRequerido[]
}

export const detalleVersion = (idVersion: number) =>
  api.get<DetalleVersion>(`${BASE}/versiones/${idVersion}`)

export const crearBorrador = (idTipo: number) =>
  api.post<VersionAdmin>(`${BASE}/tipos/${idTipo}/versiones`)

export const publicarVersion = (idVersion: number) =>
  api.post<VersionAdmin>(`${BASE}/versiones/${idVersion}/publicar`)

export const archivarVersion = (idVersion: number) =>
  api.post<VersionAdmin>(`${BASE}/versiones/${idVersion}/archivar`)

/* ── Campos ─────────────────────────────────────────────── */

export interface CampoCreateBody {
  nombre_interno: string
  etiqueta: string
  tipo_dato: string
  obligatorio?: boolean
  orden?: number
  opciones_jsonb?: unknown
  validacion_jsonb?: unknown
  ayuda?: string | null
  visible_en_listado?: boolean
}

export interface CampoUpdateBody {
  etiqueta?: string
  tipo_dato?: string
  obligatorio?: boolean
  orden?: number
  opciones_jsonb?: unknown
  validacion_jsonb?: unknown
  ayuda?: string | null
  visible_en_listado?: boolean
}

export const crearCampo = (idVersion: number, body: CampoCreateBody) =>
  api.post<TipoTramiteCampo>(`${BASE}/versiones/${idVersion}/campos`, body)

export const actualizarCampo = (idCampo: number, body: CampoUpdateBody) =>
  api.put<TipoTramiteCampo>(`${BASE}/campos/${idCampo}`, body)

export const eliminarCampo = (idCampo: number) =>
  api.delete(`${BASE}/campos/${idCampo}`)

/* ── Estados ────────────────────────────────────────────── */

export interface EstadoCreateBody {
  codigo: string
  etiqueta: string
  descripcion?: string | null
  color?: string | null
  orden?: number
  es_inicial?: boolean
  es_final?: boolean
  permite_adjuntar?: boolean
  permite_comentar?: boolean
  oculto_para_iniciador?: boolean
}

export interface EstadoUpdateBody {
  etiqueta?: string
  descripcion?: string | null
  color?: string | null
  orden?: number
  es_inicial?: boolean
  es_final?: boolean
  permite_adjuntar?: boolean
  permite_comentar?: boolean
  oculto_para_iniciador?: boolean
}

export const crearEstado = (idVersion: number, body: EstadoCreateBody) =>
  api.post<TipoTramiteEstado>(`${BASE}/versiones/${idVersion}/estados`, body)

export const actualizarEstado = (idEstado: number, body: EstadoUpdateBody) =>
  api.put<TipoTramiteEstado>(`${BASE}/estados/${idEstado}`, body)

export const eliminarEstado = (idEstado: number) =>
  api.delete(`${BASE}/estados/${idEstado}`)

/* ── Transiciones ──────────────────────────────────────── */

export interface TransicionCreateBody {
  id_estado_origen: number
  id_estado_destino: number
  etiqueta_accion: string
  orden?: number
  quien_puede_jsonb?: unknown
  requiere_comentario?: boolean
  requiere_adjunto?: boolean
  destino_automatico_jsonb?: unknown
  notifica_iniciador?: boolean
}

export interface TransicionUpdateBody {
  id_estado_origen?: number
  id_estado_destino?: number
  etiqueta_accion?: string
  orden?: number
  quien_puede_jsonb?: unknown
  requiere_comentario?: boolean
  requiere_adjunto?: boolean
  destino_automatico_jsonb?: unknown
  notifica_iniciador?: boolean
}

export const crearTransicion = (idVersion: number, body: TransicionCreateBody) =>
  api.post<TipoTramiteTransicion>(`${BASE}/versiones/${idVersion}/transiciones`, body)

export const actualizarTransicion = (idTrans: number, body: TransicionUpdateBody) =>
  api.put<TipoTramiteTransicion>(`${BASE}/transiciones/${idTrans}`, body)

export const eliminarTransicion = (idTrans: number) =>
  api.delete(`${BASE}/transiciones/${idTrans}`)

/* ── Documentos requeridos ─────────────────────────────── */

export interface DocReqCreateBody {
  nombre: string
  descripcion?: string | null
  id_tipo_tramite_estado?: number | null
  obligatorio?: boolean
  formatos_permitidos?: string[]
  tamano_max_mb?: number
  requiere_firma?: boolean
  firmantes_jsonb?: unknown
  aporta_quien?: string
  orden?: number
}

export interface DocReqUpdateBody {
  nombre?: string
  descripcion?: string | null
  id_tipo_tramite_estado?: number | null
  obligatorio?: boolean
  formatos_permitidos?: string[]
  tamano_max_mb?: number
  requiere_firma?: boolean
  firmantes_jsonb?: unknown
  aporta_quien?: string
  orden?: number
}

export const crearDocRequerido = (idVersion: number, body: DocReqCreateBody) =>
  api.post<TipoTramiteDocRequerido>(`${BASE}/versiones/${idVersion}/documentos-requeridos`, body)

export const actualizarDocRequerido = (idDoc: number, body: DocReqUpdateBody) =>
  api.put<TipoTramiteDocRequerido>(`${BASE}/documentos-requeridos/${idDoc}`, body)

export const eliminarDocRequerido = (idDoc: number) =>
  api.delete(`${BASE}/documentos-requeridos/${idDoc}`)
