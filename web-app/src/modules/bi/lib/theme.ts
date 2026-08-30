// Paleta de colores del módulo BI. Derivada del Design System ZARIS (§13) y de
// los colores de estado ya usados en el DashboardMap (§4). Coherente con el brand
// naranja/cream; NO replica la paleta violeta/verde de los tableros de referencia.

// Colores por ESTADO de reclamo. Mismos criterios que el mapa del Dashboard:
// verde teal para "resuelto/en gestión", rojo para "sin asignar", etc. El naranja
// del brand (--zaris-orange) se reserva para acentos de UI, no para estados.
export const COLOR_ESTADO: Record<string, string> = {
  'Resuelto': '#1f8a65',       // verde teal (success del DS)
  'En gestión': '#2f7fd1',     // azul
  'En espera': '#f57f17',      // amarillo/ámbar
  'En auditoría': '#6a1b9a',   // violeta
  'Sin asignar': '#c62828',    // rojo
  'Cancelado': '#9e9e9e',      // gris
}

export const COLOR_ESTADO_FALLBACK = '#b0a9a0'

export function colorEstado(estado: string): string {
  return COLOR_ESTADO[estado] ?? COLOR_ESTADO_FALLBACK
}

// Colores para las barras apiladas resuelto/pendiente/cancelado.
export const COLOR_RESUELTO = '#1f8a65'
export const COLOR_PENDIENTE = '#f57f17'
export const COLOR_CANCELADO = '#9e9e9e'

// "Otros" en series dinámicas (histograma por tipo: top 6 + Otros).
export const COLOR_OTROS = '#b0a9a0'

// Tramos de tiempo de respuesta (fase 2). Semáforo semántico: rápido=verde,
// medio=ámbar, lento=rojo. Es tiempo, no estado, así que el semáforo es correcto
// (no choca con la regla de colores de estado).
export const COLOR_TRAMO_0_3 = '#1f8a65'  // verde — dentro de lo esperable
export const COLOR_TRAMO_4_7 = '#f5b800'  // amarillo — atención
export const COLOR_TRAMO_MAS7 = '#cf2d56' // rojo (color-error del DS) — demorado

// Color de semáforo según días (cierre o demora). Lo usa el mapa de pendientes
// (como el "Pendientes geoposicionados" de Power BI) y las tablas exportadas no.
export function colorTramo(dias: number | null | undefined): string {
  if (dias == null) return COLOR_ESTADO_FALLBACK
  if (dias <= 3) return COLOR_TRAMO_0_3
  if (dias <= 7) return COLOR_TRAMO_4_7
  return COLOR_TRAMO_MAS7
}

// Etiquetas legibles para canales de origen.
export const LABEL_CANAL: Record<string, string> = {
  web: 'Web',
  whatsapp: 'WhatsApp',
  telefono: 'Teléfono',
  presencial: 'Presencial',
  oficio: 'Oficio',
  app_movil: 'App móvil',
  otro: 'Otro',
  sin_dato: 'Sin dato',
}

export function labelCanal(canal: string): string {
  return LABEL_CANAL[canal] ?? canal
}

// Paleta categórica para donas (canales) y series dinámicas. Tonos del DS + complementarios suaves.
export const PALETA_CATEGORICA = [
  '#f54e00', // zaris-orange
  '#1f8a65', // teal
  '#2f7fd1', // azul
  '#6a1b9a', // violeta
  '#f57f17', // ámbar
  '#c62828', // rojo
  '#00897b', // teal oscuro
  '#9e9e9e', // gris
]

// Convierte 'YYYY-MM' a etiqueta corta 'may 26'.
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
export function labelMes(ym: string): string {
  const [y, m] = ym.split('-')
  const mi = parseInt(m, 10) - 1
  return `${MESES[mi] ?? m} ${y.slice(2)}`
}

// Convierte 'YYYY-MM-DD' a 'DD/MM'.
export function labelDia(ymd: string): string {
  const [, m, d] = ymd.split('-')
  return `${d}/${m}`
}

// Nombre completo del mes para títulos: 'YYYY-MM' -> 'Mayo 2026'.
const MESES_LARGO = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
export function labelMesLargo(ym: string): string {
  const [y, m] = ym.split('-')
  const mi = parseInt(m, 10) - 1
  return `${MESES_LARGO[mi] ?? m} ${y}`
}
