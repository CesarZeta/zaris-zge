import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarUsuario,
  buscarUsuarios,
  cambiarEstadoUsuario,
  crearUsuario,
  listarUsuarios,
  obtenerUsuario,
  verLoginLog,
} from '../api/usuariosApi'
import type { UsuarioCreatePayload, UsuarioUpdatePayload } from '../types'

const KEY = ['usuarios', 'maestro']

export const useUsuariosLista = () =>
  useQuery({ queryKey: [...KEY, 'lista'], queryFn: listarUsuarios })

export const useBuscarUsuarios = (q: string) =>
  useQuery({
    queryKey: [...KEY, 'buscar', q],
    queryFn: () => buscarUsuarios(q),
    enabled: q.trim().length >= 1,
  })

export const useUsuarioDetalle = (id: number | null) =>
  useQuery({
    queryKey: [...KEY, 'detalle', id],
    queryFn: () => obtenerUsuario(id as number),
    enabled: id != null,
  })

export const useLoginLog = (id: number | null, abierto: boolean) =>
  useQuery({
    queryKey: [...KEY, 'login-log', id],
    queryFn: () => verLoginLog(id as number),
    enabled: id != null && abierto,
  })

function useInvalidarUsuarios() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: KEY })
    // Cambiar nivel/estado de un usuario altera los defaults de su matriz de
    // permisos (PermisosPanel usa los hooks de config con key ['config',...]).
    qc.invalidateQueries({ queryKey: ['config', 'permisos'] })
    qc.invalidateQueries({ queryKey: ['config', 'usuarios'] })
  }
}

export function useCrearUsuario() {
  const invalidar = useInvalidarUsuarios()
  return useMutation({
    mutationFn: (payload: UsuarioCreatePayload) => crearUsuario(payload),
    onSuccess: invalidar,
  })
}

export function useActualizarUsuario() {
  const invalidar = useInvalidarUsuarios()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UsuarioUpdatePayload }) =>
      actualizarUsuario(id, payload),
    onSuccess: invalidar,
  })
}

export function useCambiarEstadoUsuario() {
  const invalidar = useInvalidarUsuarios()
  return useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) =>
      cambiarEstadoUsuario(id, activo),
    onSuccess: invalidar,
  })
}
