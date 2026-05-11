/** Helpers de fechas. Sin libreria externa - Date nativo. */

const MS_DIA = 24 * 60 * 60 * 1000

/** ISO local 'YYYY-MM-DD' (sin desfasaje de UTC). */
export function toIsoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

/** Parsea 'YYYY-MM-DD' como Date local (no UTC). */
export function fromIsoDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, (m ?? 1) - 1, d ?? 1)
}

export function hoy(): Date {
  const t = new Date()
  return new Date(t.getFullYear(), t.getMonth(), t.getDate())
}

export function sumarDias(d: Date, n: number): Date {
  return new Date(d.getTime() + n * MS_DIA)
}

/** Lunes de la semana de `d` (lunes=0 ... domingo=6). */
export function lunesDeSemana(d: Date): Date {
  const day = (d.getDay() + 6) % 7
  return sumarDias(d, -day)
}

/** Domingo de la semana de `d`. */
export function domingoDeSemana(d: Date): Date {
  return sumarDias(lunesDeSemana(d), 6)
}

/** Primer dia del mes. */
export function primerDiaDelMes(anio: number, mes: number): Date {
  return new Date(anio, mes - 1, 1)
}

/** Cantidad de dias del mes (mes 1-12). */
export function diasEnMes(anio: number, mes: number): number {
  return new Date(anio, mes, 0).getDate()
}

/** Mismo dia (sin hora). */
export function mismaFecha(a: Date, b: Date): boolean {
  return toIsoDate(a) === toIsoDate(b)
}

const NOMBRES_DIAS = ['lun', 'mar', 'mie', 'jue', 'vie', 'sab', 'dom'] as const
const NOMBRES_DIAS_LARGOS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo'] as const
const NOMBRES_MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] as const

export function nombreDia(d: Date, largo = false): string {
  const idx = (d.getDay() + 6) % 7
  return largo ? NOMBRES_DIAS_LARGOS[idx] : NOMBRES_DIAS[idx]
}

export function nombreMes(mes: number): string {
  return NOMBRES_MESES[mes - 1] ?? ''
}

/** 'HH:MM' a minutos desde 00:00. */
export function timeToMinutes(t: string): number {
  const [hh, mm] = t.split(':').map(Number)
  return (hh ?? 0) * 60 + (mm ?? 0)
}

/** Devuelve un array de los `n` dias contiguos a partir de `desde`. */
export function rangoDias(desde: Date, n: number): Date[] {
  const out: Date[] = []
  for (let i = 0; i < n; i++) out.push(sumarDias(desde, i))
  return out
}

/** Etiqueta corta '11 mayo'. */
export function etiquetaFechaCorta(d: Date): string {
  return `${d.getDate()} ${nombreMes(d.getMonth() + 1).toLowerCase()}`
}

/** Etiqueta larga 'Lunes 11 mayo 2026'. */
export function etiquetaFechaLarga(d: Date): string {
  return `${nombreDia(d, true)} ${d.getDate()} de ${nombreMes(d.getMonth() + 1).toLowerCase()} ${d.getFullYear()}`
}

/** 'HH:MM' normalizado desde Date. */
export function horaActualHHMM(): string {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
