import { api } from '../../lib/api'

// Endpoints exclusivos del super administrador (IT-01 F3/F4, backend/app/api/routes/super_admin.py)
// y el catálogo geográfico (backend/app/api/routes/geo.py).

export type EstadoMunicipio = 'puesta_en_marcha' | 'produccion' | 'demo' | 'modelo' | 'baja'

export const ESTADO_ETIQUETA: Record<EstadoMunicipio, string> = {
  puesta_en_marcha: 'Puesta en marcha',
  produccion: 'Producción',
  demo: 'Demo',
  modelo: 'Modelo',
  baja: 'Baja',
}

export interface MunicipioSuper {
  id_municipio: number
  nombre: string
  codigo_corto: string | null
  subdominio: string | null
  codigo_pais: string
  pais: string | null
  pais_nombre: string | null
  etiqueta_nivel_1: string | null
  etiqueta_nivel_2: string | null
  id_provincia: number | null
  provincia_nombre: string | null
  id_partido: number | null
  partido_nombre: string | null
  zona_horaria: string
  direccion_base: boolean
  activo: boolean
  estado: EstadoMunicipio
  fue_produccion: boolean
  max_usuarios_activos: number | null
  cuentas_activas: number
}

export interface MunicipioSuperUpdate {
  nombre: string
  subdominio: string | null
  codigo_pais: string
  id_provincia: number | null
  id_partido: number | null
  zona_horaria: string
}

export interface FiltrosMunicipios {
  codigo_pais?: string
  id_provincia?: number
  estado?: EstadoMunicipio
}

export interface Pais {
  codigo_pais: string
  nombre: string
  etiqueta_nivel_1: string
  etiqueta_nivel_2: string
  zona_horaria: string
  habilitado_para_alta: boolean
}

export interface Provincia { id_provincia: number; nombre: string; codigo_pais: string }
export interface Partido { id_partido: number; id_provincia: number; nombre: string }

export const listarMunicipios = (filtros: FiltrosMunicipios = {}) =>
  api.get<MunicipioSuper[]>('/api/v1/super/municipios', { params: { ...filtros } })

export const editarMunicipio = (id: number, body: MunicipioSuperUpdate) =>
  api.put<MunicipioSuper>(`/api/v1/super/municipios/${id}`, body)

export const listarPaises = (paraAlta = false) =>
  api.get<Pais[]>('/api/v1/geo/paises', { params: paraAlta ? { para_alta: true } : {} })

export const listarProvincias = (codigoPais: string) =>
  api.get<Provincia[]>('/api/v1/geo/provincias', { params: { codigo_pais: codigoPais } })

export const listarPartidos = (idProvincia: number) =>
  api.get<Partido[]>('/api/v1/geo/partidos', { params: { id_provincia: idProvincia } })
