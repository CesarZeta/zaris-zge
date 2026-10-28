import { useQuery } from '@tanstack/react-query'
import L from 'leaflet'
import { api } from './api'
import { getMunicipioActivo } from './municipioActivo'

// Dónde arrancan los mapas del municipio (GET /geo/encuadre): su contorno; si no hay, la zona de
// búsqueda de Configuración → Sistema; si tampoco, el país. Ningún mapa arranca en un municipio
// fijo (César, 2026-10-28: antes los tres mapas tenían Vicente López escrito en el código).

export interface EncuadreMapa {
  sur: number
  oeste: number
  norte: number
  este: number
  origen: 'contorno' | 'zona' | 'pais'
}

/** Mientras llega la respuesta (o si falla): la Argentina completa. Igual que ENCUADRE_PAIS del backend. */
export const ENCUADRE_ARGENTINA: EncuadreMapa = { sur: -55.1, oeste: -73.6, norte: -21.7, este: -53.6, origen: 'pais' }

export const aBounds = (e: EncuadreMapa) => L.latLngBounds([e.sur, e.oeste], [e.norte, e.este])

export function useEncuadreMapa() {
  return useQuery({
    // El super administrador cambia de municipio con el selector: el encuadre es de cada uno.
    queryKey: ['geo', 'encuadre', getMunicipioActivo()],
    queryFn: () => api.get<EncuadreMapa>('/api/v1/geo/encuadre'),
    staleTime: 5 * 60_000,
    retry: false,
  })
}
