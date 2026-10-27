import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  actualizarConfigParam,
  crearConfigParam,
  actualizarModulo,
  getIdentidad,
  listarConfigGeneral,
  listarModulos,
  listarUsuarios,
  setPermisosUsuario,
  updateIdentidad,
  verPermisosUsuario,
  type IdentidadUpdate,
} from '../api/configApi'
import type { ModuloCambio, OverrideIn } from '../types/config'

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
    mutationFn: ({ codigo, ...cambio }: { codigo: string } & ModuloCambio) =>
      actualizarModulo(codigo, cambio),
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

// Parámetros del sistema (configuracion_general)
export function useConfigGeneral() {
  return useQuery({
    queryKey: ['config', 'general'],
    queryFn: listarConfigGeneral,
    staleTime: 60 * 1000,
  })
}

export function useActualizarConfigParam() {
  const qc = useQueryClient()
  return useMutation({
    // id_config 0 = la clave no existe en el municipio: se crea con su tipo.
    mutationFn: ({ id_config, valor, clave, tipo }: { id_config: number; valor: string; clave?: string; tipo?: string }) =>
      id_config === 0 && clave ? crearConfigParam(clave, valor, tipo ?? 'string') : actualizarConfigParam(id_config, valor),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config', 'general'] }),
  })
}
