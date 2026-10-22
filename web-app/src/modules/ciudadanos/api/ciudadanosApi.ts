import { api } from '../../../lib/api'
import type {
  Ciudadano,
  CiudadanoConNacionalidad,
  CiudadanoCreate,
  CiudadanoUpdate,
  Nacionalidad,
  TipoRepresentacion,
  Actividad,
  VerificarDuplicadoResp,
  EmpresaVinculada,
  EmpresaCreate,
  CiudadanoEmpresaCreate,
  CuentasCiudadano,
  SubareaHit,
} from '../types/ciudadano'

const BASE = '/api/v1/buc'

// ── Catalogos ──
export const getNacionalidades = () =>
  api.get<Nacionalidad[]>(`${BASE}/nacionalidades`)

export const getTiposRepresentacion = () =>
  api.get<TipoRepresentacion[]>(`${BASE}/tipo-representacion`)

export const getActividades = () =>
  api.get<Actividad[]>(`${BASE}/actividades`)

// ── Ciudadanos ──
export const listarCiudadanos = (params: { solo_activos?: boolean; limit?: number; offset?: number } = {}) =>
  api.get<Ciudadano[]>(`${BASE}/ciudadanos`, { params })

/** Columnas ordenables del padrón (espejo de `_ORDEN_CIUDADANOS` en buc.py). */
export type OrdenCiudadanos = 'nombre' | 'documento' | 'cuil' | 'email' | 'estado' | 'alta'

export interface ParamsPadronCiudadanos {
  q?: string
  desde?: string
  hasta?: string
  orden?: OrdenCiudadanos
  dir?: 'asc' | 'desc'
  limit: number
  offset: number
}

/** Página del padrón + total sin paginar (`X-Total-Count`). Texto, fechas y
 *  orden los resuelve el backend (§23): el padrón no entra entero en pantalla. */
export async function listarPadronCiudadanos(params: ParamsPadronCiudadanos) {
  const { data, headers } = await api.getWithHeaders<Ciudadano[]>(`${BASE}/ciudadanos`, {
    params: { ...params, solo_activos: false },
  })
  return { filas: data, total: Number(headers.get('X-Total-Count') ?? data.length) }
}

export const buscarCiudadanos = (params: { q: string; tipo?: 'numero' | 'texto' | 'auto'; limit?: number; offset?: number }) =>
  api.getWithHeaders<Ciudadano[]>(`${BASE}/ciudadanos/buscar`, { params })

export const obtenerCiudadano = (id: number) =>
  api.get<CiudadanoConNacionalidad>(`${BASE}/ciudadanos/${id}`)

/** Crea (o reenvía la activación de) la cuenta de App Vecinos de un ciudadano existente.
 *  Idempotente: ya_activada=true si la cuenta ya estaba activa (no se manda nada). */
export const crearCuentaVecino = (id: number) =>
  api.post<{ enviado: boolean; ya_activada: boolean; email: string }>(
    `${BASE}/ciudadanos/${id}/cuenta-vecino`,
    {},
  )

/** Estado de las dos cuentas (App Vecinos / ZARIS) para los chips de la ficha. */
export const estadoCuentasCiudadano = (id: number) =>
  api.get<CuentasCiudadano>(`${BASE}/ciudadanos/${id}/cuentas`)

/** Buscador predictivo de subáreas (mismo endpoint que usa el módulo Usuarios). */
export const buscarSubareas = (q: string) =>
  api.get<SubareaHit[]>(`${BASE}/subareas/buscar`, { params: { q, limit: 20 } })

export const verificarDuplicadoCiudadano = (campo: string, valor: string, excluir_id?: number | null) =>
  api.get<VerificarDuplicadoResp>(`${BASE}/ciudadanos/verificar-duplicado`, {
    params: { campo, valor, excluir_id: excluir_id ?? undefined },
  })

export const crearCiudadano = (data: CiudadanoCreate) =>
  api.post<Ciudadano>(`${BASE}/ciudadanos`, data)

export const modificarCiudadano = (id: number, data: CiudadanoUpdate) =>
  api.put<Ciudadano>(`${BASE}/ciudadanos/${id}`, data)

export const cambiarEstadoCiudadano = (id: number, activo: boolean) =>
  api.put<Ciudadano>(`${BASE}/ciudadanos/${id}/estado`, undefined, { params: { activo } })

export const empresasVinculadas = (id: number) =>
  api.get<EmpresaVinculada[]>(`${BASE}/ciudadanos/${id}/empresas-vinculadas`)

// Nota: el alta de ciudadano (crearCiudadano → POST /buc/ciudadanos) ya crea
// automáticamente la cuenta de App Vecinos + el mail de activación en el backend.
// No hay un endpoint frontend separado para "crear cuenta".

// ── Empresa (solo lo necesario para sub-form vinculada) ──
export const crearEmpresa = (data: EmpresaCreate) =>
  api.post<{ id_empresa: number }>(`${BASE}/empresas`, data)

export const vincularCiudadanoEmpresa = (data: CiudadanoEmpresaCreate) =>
  api.post(`${BASE}/ciudadano-empresa`, data)
