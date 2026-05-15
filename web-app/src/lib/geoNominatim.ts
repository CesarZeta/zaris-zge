import { api } from './api'

export interface NominatimAddress {
  road?: string
  house_number?: string
  pedestrian?: string
  footway?: string
  cycleway?: string
  path?: string
  city?: string
  town?: string
  village?: string
  hamlet?: string
  municipality?: string
  suburb?: string
  neighbourhood?: string
  city_district?: string
  state?: string
  region?: string
  province?: string
  country?: string
  [key: string]: string | undefined
}

export interface GeoBuscarResult {
  display_name: string
  lat: number | null
  lon: number | null
  type: string | null
  class?: string | null
  address: NominatimAddress
}

export const geoBuscar = (q: string, limit = 5, soloDirecciones = false) =>
  api.get<GeoBuscarResult[]>(`/api/v1/geo/buscar`, {
    params: { q, limit, solo_direcciones: soloDirecciones },
  })

export interface DireccionNormalizada {
  calle: string
  localidad: string
  provincia: string
}

// Extrae calle / localidad / provincia desde el `address` de Nominatim.
// El usuario despues puede ajustar a mano si el parseo no lo convencio.
export function parseAddress(r: GeoBuscarResult): DireccionNormalizada {
  const a = r.address ?? {}
  const calleBase = a.road || a.pedestrian || a.footway || a.cycleway || a.path || ''
  const calle = a.house_number && calleBase ? `${calleBase} ${a.house_number}` : calleBase
  const localidad = a.city || a.town || a.village || a.hamlet || a.municipality || a.suburb || a.neighbourhood || a.city_district || ''
  const provincia = a.state || a.province || a.region || ''
  return { calle, localidad, provincia }
}
