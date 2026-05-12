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

export interface EmpresaCreate {
  cuit: string
  nombre: string
  id_actividad: number
  calle?: string | null
  altura?: string | null
  localidad?: string | null
  provincia?: string | null
  telefono: string
  email: string
  observaciones?: string | null
}

export type EmpresaUpdate = Partial<EmpresaCreate> & {
  modificado_por?: number | null
}

export interface VerificarDuplicadoEmpresaResp {
  existe: boolean
  id?: number
  nombre?: string
  cuit?: string
}
