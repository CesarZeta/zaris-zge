// Tipos del modulo Ciudadanos (BUC). Mirror de backend/app/schemas/buc.py.

export type DocTipo = 'DNI' | 'PASAPORTE'
export type Sexo = 'HOMBRE' | 'MUJER' | 'OTROS'

export interface Nacionalidad {
  id: number
  pais: string
  region: string
}

export interface TipoRepresentacion {
  id: number
  tipo: string
  descripcion: string
}

export interface Actividad {
  id: number
  codigo_clae: number
  descripcion: string
  categoria_tasa: string
}

export interface Ciudadano {
  id_ciudadano: number
  fecha_alta: string
  doc_tipo: DocTipo
  doc_nro: string
  cuil: string
  nombre: string
  apellido: string
  sexo: Sexo
  fecha_nac: string
  id_nacionalidad: number
  ren_chk: boolean
  calle: string | null
  altura: string | null
  localidad: string | null
  provincia: string | null
  latitud: number | null
  longitud: number | null
  telefono: string
  email: string
  email_chk: boolean
  emp_chk: boolean
  observaciones: string | null
  fecha_modif: string | null
  activo: boolean
  modificado_por: number | null
}

export interface CiudadanoConNacionalidad extends Ciudadano {
  nacionalidad: Nacionalidad | null
}

export interface CiudadanoCreate {
  doc_tipo: DocTipo
  doc_nro: string
  cuil: string
  nombre: string
  apellido: string
  sexo: Sexo
  fecha_nac: string
  id_nacionalidad: number
  calle?: string | null
  altura?: string | null
  localidad?: string | null
  provincia?: string | null
  latitud?: number | null
  longitud?: number | null
  telefono: string
  email: string
  emp_chk?: boolean
  observaciones?: string | null
}

export type CiudadanoUpdate = Partial<CiudadanoCreate> & {
  modificado_por?: number | null
}

export interface VerificarDuplicadoResp {
  existe: boolean
  id?: number
  nombre?: string
  cuil?: string
}

export interface EmpresaVinculada {
  id_relacion: number
  id_empresa: number
  cuit: string
  nombre: string
  telefono: string
  email: string
  calle: string | null
  localidad: string | null
  provincia: string | null
  id_actividad: number
  tipo_representacion: string | null
  id_tipo_representacion: number
}

export interface EmpresaCreate {
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

export interface CiudadanoEmpresaCreate {
  id_ciudadano: number
  id_empresa: number
  id_tipo_representacion: number
}
