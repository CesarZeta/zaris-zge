import { api } from '../../lib/api'

// Endpoints exclusivos del super administrador (IT-01 F3, backend/app/api/routes/super_admin.py).

export interface MunicipioSuper {
  id_municipio: number
  nombre: string
  codigo_corto: string | null
  subdominio: string | null
  codigo_pais: string
  pais: string | null
  zona_horaria: string
  direccion_base: boolean
  activo: boolean
}

export interface MunicipioSuperUpdate {
  nombre: string
  subdominio: string | null
  codigo_pais: string
  pais: string | null
  zona_horaria: string
}

export const listarMunicipios = () => api.get<MunicipioSuper[]>('/api/v1/super/municipios')

export const editarMunicipio = (id: number, body: MunicipioSuperUpdate) =>
  api.put<MunicipioSuper>(`/api/v1/super/municipios/${id}`, body)
