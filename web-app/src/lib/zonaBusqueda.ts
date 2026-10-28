// Zona de búsqueda de direcciones del municipio (claves geo_bbox_*). Los mismos rangos que
// backend/app/core/geo_zona.py: fuera de ellos el buscador de direcciones responde «sin zona».
// La usan Configuración → Sistema y el asistente de alta de municipios.

export const CLAVES_ZONA = ['geo_bbox_centro_lat', 'geo_bbox_centro_lon', 'geo_bbox_delta_grados'] as const
export type ClaveZona = (typeof CLAVES_ZONA)[number]

const RANGOS: Record<ClaveZona, { min: number; max: number; minExcluido?: boolean; mensaje: string }> = {
  geo_bbox_centro_lat: { min: -90, max: 90, mensaje: 'Un número entre -90 y 90' },
  geo_bbox_centro_lon: { min: -180, max: 180, mensaje: 'Un número entre -180 y 180' },
  geo_bbox_delta_grados: { min: 0, max: 5, minExcluido: true, mensaje: 'Un número mayor que 0 y hasta 5' },
}

/** «-33,69» (coma decimal) → «-33.69»; el resto queda igual, sin espacios alrededor. */
export const normalizarNumero = (v: string) => (/^\s*-?\d+,\d+\s*$/.test(v) ? v.replace(',', '.') : v).trim()

/** Por qué `valor` no sirve para `clave`, o null si sirve. Vacío vale: es «sin cargar». */
export function problemaZona(clave: string, valor: string): string | null {
  const r = RANGOS[clave as ClaveZona]
  const v = normalizarNumero(valor)
  if (!r || v === '') return null
  if (!/^-?\d+(\.\d+)?$/.test(v)) return r.mensaje
  const n = Number(v)
  return (r.minExcluido ? n > r.min : n >= r.min) && n <= r.max ? null : r.mensaje
}

/** «-33.6948, -60.6339», como lo copia Google Maps → [latitud, longitud]; null si no es un par. */
export function parLatLon(texto: string): [string, string] | null {
  const m = texto.match(/^\s*(-?\d+\.\d+)\s*[,;]\s*(-?\d+\.\d+)\s*$/)
  return m ? [m[1], m[2]] : null
}
