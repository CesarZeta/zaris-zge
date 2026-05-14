// Bitmask de dias_semana usado por la tabla disponibilidad_recurso (mig 41).
// Convencion: Lun=bit0 (1), Mar=1 (2), Mie=2 (4), Jue=3 (8), Vie=4 (16),
// Sab=5 (32), Dom=6 (64). Rango valido: 0..127. CLAUDE.md §27.

export const DIA_BIT = {
  lunes: 1,
  martes: 2,
  miercoles: 4,
  jueves: 8,
  viernes: 16,
  sabado: 32,
  domingo: 64,
} as const

export const DIA_LABEL_CORTO = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'] as const
export const DIA_LABEL_LARGO = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo'] as const

export type DiaIndex = 0 | 1 | 2 | 3 | 4 | 5 | 6

/** Convierte un array de indices de dias [0..6] en bitmask 0..127. */
export function serialize(indices: DiaIndex[]): number {
  let mask = 0
  for (const i of indices) mask |= 1 << i
  return mask
}

/** Convierte bitmask 0..127 en array de indices ordenados [0..6]. */
export function deserialize(mask: number): DiaIndex[] {
  const out: DiaIndex[] = []
  for (let i = 0; i < 7; i++) {
    if (mask & (1 << i)) out.push(i as DiaIndex)
  }
  return out
}

/** Toggle de un dia en el bitmask. */
export function togglearDia(mask: number, dia: DiaIndex): number {
  return mask ^ (1 << dia)
}

/** Devuelve true si el bitmask incluye el dia. */
export function incluye(mask: number, dia: DiaIndex): boolean {
  return (mask & (1 << dia)) !== 0
}

/**
 * Formatea para UI con atajos comunes:
 *   127 → "Todos los dias"
 *   31  → "Lun a Vie"
 *   96  → "Sab y Dom"
 *   1   → "Lun"
 *   resto → "Lun, Mie, Vie"
 */
export function format(mask: number): string {
  if (mask === 127) return 'Todos los dias'
  if (mask === 31) return 'Lun a Vie'
  if (mask === 96) return 'Sab y Dom'
  if (mask === 0) return '(sin dias)'
  const idx = deserialize(mask)
  if (idx.length === 1) return DIA_LABEL_CORTO[idx[0]]
  return idx.map((i) => DIA_LABEL_CORTO[i]).join(', ')
}

/**
 * dia_iso_a_index: convierte ISO weekday (1=lun, 7=dom — convencion Postgres
 * EXTRACT(ISODOW)) al indice del bitmask (0=lun, 6=dom).
 */
export function isoDowAIndex(isodow: number): DiaIndex {
  // ISODOW: 1=Lun..7=Dom. Bitmask: 0=Lun..6=Dom.
  return (isodow - 1) as DiaIndex
}

/** Devuelve el indice del bitmask para una Date (0=Lun..6=Dom). */
export function fechaAIndice(d: Date): DiaIndex {
  // Date.getDay(): 0=Dom, 1=Lun..6=Sab. Mapeo a 0=Lun..6=Dom.
  const jsDay = d.getDay()
  return (jsDay === 0 ? 6 : jsDay - 1) as DiaIndex
}
