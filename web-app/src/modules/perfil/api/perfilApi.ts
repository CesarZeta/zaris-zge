import { api } from '../../../lib/api'
import type { User } from '../../../lib/types'
import { useAuthStore } from '../../../stores/auth'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

// Subconjunto de GET /api/v1/config/identidad que usa la vista (endpoint público,
// misma queryKey que el Dashboard: ['config', 'identidad']).
export interface IdentidadPerfil {
  municipio_nombre: string
  municipio_logo_url: string
  // URL pública de la App Vecinos. Opcional: un backend anterior al 2026-09-26
  // no la manda (la vista muestra "no configurada" en ese caso).
  app_vecinos_url?: string
  // URL pública de la App de agentes (zaris-agentes). Backends anteriores al
  // 2026-09-27 no la mandan (la vista muestra "no configurada" en ese caso).
  app_agentes_url?: string
}

export interface FotoUploadSigned {
  upload_url: string
  public_url: string
  path: string
  bucket: string
}

export const getMe = () => api.get<User>('/api/v1/auth/me')
export const getIdentidad = () => api.get<IdentidadPerfil>('/api/v1/config/identidad')

// Foto de perfil: mismo flujo que el shell vanilla (menu.js) y el logo del
// municipio (§26): el backend firma la URL, el navegador hace PUT del binario
// directo a Storage y después se persiste la URL pública en usuarios.foto_url.
export const crearFotoUploadUrl = (mime_type: string, tamano_bytes: number) =>
  api.post<FotoUploadSigned>('/api/v1/auth/me/foto-upload-url', { mime_type, tamano_bytes })

export const persistirFoto = (foto_url: string) =>
  api.put<{ ok: boolean; foto_url: string | null }>('/api/v1/auth/me/foto', { foto_url })

/** Error del cambio de contraseña con el `status` HTTP (401 = actual incorrecta,
 *  422 = regla de la nueva). El `message` es el `detail` del backend, tal cual. */
export class CambioPasswordError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'CambioPasswordError'
    this.status = status
  }
}

/**
 * Cambio voluntario de contraseña. NO usa `api.post` a propósito: el helper
 * trata TODO 401 como sesión vencida (borra `zaris_session` y manda al login),
 * pero acá el 401 significa "la contraseña actual no coincide" y el usuario
 * tiene que poder corregirla sin perder la sesión. Fetch directo, mismo token.
 */
export async function cambiarPassword(password_actual: string, password_nueva: string): Promise<void> {
  const token = useAuthStore.getState().accessToken
  const res = await fetch(`${BASE}/api/v1/auth/cambiar-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ password_actual, password_nueva }),
  })
  if (res.ok) return
  const err = await res.json().catch(() => ({ detail: res.statusText }))
  const msg = typeof err?.detail === 'string' ? err.detail : JSON.stringify(err?.detail ?? err)
  throw new CambioPasswordError(res.status, msg || 'No se pudo cambiar la contraseña.')
}
