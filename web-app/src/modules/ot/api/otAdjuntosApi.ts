import { api } from '../../../lib/api'
import type { Adjunto } from '../../reclamos/types/reclamo'

// Adjuntos de OT (evidencia del trabajo). Espeja el flujo de reclamo_adjuntos.
// Reusa el tipo Adjunto (mismo shape de respuesta).

const BASE = '/api/v1/ot'

export interface UploadUrlResponse {
  id_adjunto: number
  upload_url: string
  token: string
  storage_path: string
  bucket: string
}

export const listarAdjuntosOT = (idOt: number) =>
  api.get<Adjunto[]>(`${BASE}/${idOt}/adjuntos`)

export const crearUploadUrlOT = (
  idOt: number,
  body: { nombre_archivo: string; mime_type: string; tamano_bytes: number; descripcion?: string },
) => api.post<UploadUrlResponse>(`${BASE}/${idOt}/adjuntos/upload-url`, body)

export const confirmarAdjuntoOT = (idOt: number, idAdjunto: number) =>
  api.post<{ ok: boolean; id_adjunto: number; ya_confirmado?: boolean }>(
    `${BASE}/${idOt}/adjuntos/${idAdjunto}/confirm`,
    {},
  )

export const borrarAdjuntoOT = (idOt: number, idAdjunto: number) =>
  api.delete<{ ok: boolean; id_adjunto: number }>(`${BASE}/${idOt}/adjuntos/${idAdjunto}`)
