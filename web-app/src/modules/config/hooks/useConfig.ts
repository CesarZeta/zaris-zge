import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarModulo,
  getIdentidad,
  listarModulos,
  listarUsuarios,
  setPermisosUsuario,
  updateIdentidad,
  verPermisosUsuario,
  type IdentidadUpdate,
} from '../api/configApi'
import type { OverrideIn } from '../types/config'

const HORA = 60 * 60 * 1000

// Catalogo modulos
export function useModulosCatalogo() {
  return useQuery({
    queryKey: ['config', 'modulos'],
    queryFn: listarModulos,
    staleTime: HORA,
  })
}

export function useActualizarModulo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ codigo, min_nivel_acceso }: { codigo: string; min_nivel_acceso: number }) =>
      actualizarModulo(codigo, min_nivel_acceso),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  })
}

// Usuarios + permisos
export function useUsuarios() {
  return useQuery({
    queryKey: ['config', 'usuarios'],
    queryFn: listarUsuarios,
    staleTime: 30 * 1000,
  })
}

export function usePermisosUsuario(id_usuario: number | null) {
  return useQuery({
    queryKey: ['config', 'permisos', id_usuario],
    queryFn: () => verPermisosUsuario(id_usuario as number),
    enabled: id_usuario != null,
    staleTime: 15 * 1000,
  })
}

export function useSetPermisosUsuario(id_usuario: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (overrides: OverrideIn[]) => setPermisosUsuario(id_usuario as number, overrides),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  })
}

// Identidad del topbar
export function useIdentidad() {
  return useQuery({
    queryKey: ['config', 'identidad'],
    queryFn: getIdentidad,
    staleTime: 5 * 60 * 1000,
  })
}

export function useUpdateIdentidad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: IdentidadUpdate) => updateIdentidad(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config', 'identidad'] }),
  })
}
