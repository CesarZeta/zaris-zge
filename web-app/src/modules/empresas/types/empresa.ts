// Tipos del modulo Empresas (BUC). Mirror de backend/app/schemas/buc.py.
// Reusa Actividad de ciudadanos para no duplicar.

export type { Actividad } from '../../ciudadanos/types/ciudadano'

export interface Empresa {
  id_empresa: number
  fecha_alta: string
  cuit: string
  nombre: string
  id_actividad: number
  calle: string | null
  altura: string | null
  localidad: string | null
  provincia: string | null
  latitud: number | null
  longitud: number | null
  telefono: string
  email: string
  email_chk: boolean
  observaciones: string | null
  fecha_modif: string | null
  activo: boolean
  modificado_por: number | null
}

export interface EmpresaConActividad extends Empresa {
  actividad: {
    id: number
    codigo_clae: number
    descripcion: string
    categoria_tasa: string
  } | null
}

export interface EmpresaDatos {
  cuit: string
  nombre: string
  id_actividad: number
  calle?: string | null
  altura?: string | null
  localidad?: string | null
  provincia?: string | null
  latitud?: number | null
  longitud?: number | null
  telefono: string
  email: string
  observaciones?: string | null
}

export interface EmpresaCreate extends EmpresaDatos {
  // Toda empresa nace con su vecino representante (BUC §2). El backend crea
  // empresa + vínculo ciudadano_empresa en una sola transacción.
  id_ciudadano: number
  id_tipo_representacion: number
}

export type EmpresaUpdate = Partial<EmpresaDatos> & {
  modificado_por?: number | null
}

export interface TipoRepresentacion {
  id: number
  tipo: string
}

export interface VerificarDuplicadoEmpresaResp {
  existe: boolean
  id?: number
  nombre?: string
  cuit?: string
}
