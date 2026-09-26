import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../../../stores/auth'
import {
  cambiarPassword,
  crearFotoUploadUrl,
  getIdentidad,
  persistirFoto,
  type IdentidadPerfil,
} from '../api/perfilApi'

const MINUTO = 60 * 1000

// Misma queryKey que useIdentidadMunicipio (Dashboard) porque es el mismo
// endpoint público: la caché se comparte entre módulos.
export function useIdentidadPerfil() {
  return useQuery<IdentidadPerfil>({
    queryKey: ['config', 'identidad'],
    queryFn: getIdentidad,
    staleTime: 10 * MINUTO,
  })
}

/** Sube la foto (URL firmada → PUT a Storage → persistir) y refresca la sesión
 *  del store: la vista y el shell (vía evento `storage`) ven la foto nueva. */
export function useSubirFoto() {
  const qc = useQueryClient()
  const refreshSession = useAuthStore((s) => s.refreshSession)
  return useMutation({
    mutationFn: async (file: File): Promise<string> => {
      const signed = await crearFotoUploadUrl(file.type, file.size)
      const put = await fetch(signed.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': file.type, 'x-upsert': 'true' },
        body: file,
      })
      if (!put.ok) throw new Error(`No se pudo subir la imagen (Storage ${put.status}).`)
      await persistirFoto(signed.public_url)
      return signed.public_url
    },
    onSuccess: async () => {
      await refreshSession()
      await qc.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}

/** Quita la foto (foto_url vacía → NULL en usuarios.foto_url) y refresca la sesión. */
export function useQuitarFoto() {
  const qc = useQueryClient()
  const refreshSession = useAuthStore((s) => s.refreshSession)
  return useMutation({
    mutationFn: () => persistirFoto(''),
    onSuccess: async () => {
      await refreshSession()
      await qc.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}

export function useCambiarPassword() {
  return useMutation({
    mutationFn: (v: { actual: string; nueva: string }) => cambiarPassword(v.actual, v.nueva),
  })
}
