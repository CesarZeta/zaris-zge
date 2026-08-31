import type { BiFiltros } from './types'

// Período del filtro EN LETRAS, para el título de cada sección del Ejecutivo
// (pedido de César 2026-08-30: "las tarjetas hablan del período seleccionado —
// decilo en letras al costado del título"). `anterior` espeja la regla del
// backend (_rango_anterior de bi_ejecutivo.py): meses elegidos → el bloque
// contiguo inmediatamente anterior; año completo → año-1; rango manual → mismo
// largo hacia atrás. Si se cambia allá, cambiar acá.

const MES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
  'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

function listaEnLetras(xs: string[]): string {
  if (xs.length <= 1) return xs[0] ?? ''
  return `${xs.slice(0, -1).join(', ')} y ${xs[xs.length - 1]}`
}

/** Nombra un bloque de pares (año*100+mes) contiguos, agrupando por año. */
function nombrarPares(pares: number[]): string {
  const porAnio = new Map<number, number[]>()
  for (const p of [...pares].sort((a, b) => a - b)) {
    const a = Math.floor(p / 100)
    porAnio.set(a, [...(porAnio.get(a) ?? []), p % 100])
  }
  return listaEnLetras(
    Array.from(porAnio.entries()).map(([a, ms]) => `${listaEnLetras(ms.map((m) => MES[m - 1]))} de ${a}`),
  )
}

function fechaCorta(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  return `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}/${a}`
}

export function periodoEnLetras(f: BiFiltros): { actual: string; anterior: string | null } {
  const meses = f.meses ?? []
  if ((f.anio || meses.length) && meses.length && meses.length < 12) {
    const anio = f.anio ?? new Date().getFullYear()
    const actual = nombrarPares(meses.map((m) => anio * 100 + m))
    // Bloque contiguo de N meses que termina antes del primero seleccionado.
    let a = anio
    let m = Math.min(...meses)
    const pares: number[] = []
    for (let i = 0; i < meses.length; i++) {
      m -= 1
      if (m === 0) { a -= 1; m = 12 }
      pares.push(a * 100 + m)
    }
    return { actual, anterior: nombrarPares(pares) }
  }
  if (f.anio || meses.length === 12) {
    const anio = f.anio ?? new Date().getFullYear()
    return { actual: `año ${anio} completo`, anterior: `año ${anio - 1} completo` }
  }
  if (f.desde && f.hasta) {
    const desde = new Date(`${f.desde}T00:00:00`)
    const hasta = new Date(`${f.hasta}T00:00:00`)
    const largoMs = hasta.getTime() - desde.getTime() + 86_400_000
    const antHasta = new Date(desde.getTime() - 86_400_000)
    const antDesde = new Date(desde.getTime() - largoMs)
    const iso = (x: Date) => x.toISOString().slice(0, 10)
    return {
      actual: `${fechaCorta(f.desde)} al ${fechaCorta(f.hasta)}`,
      anterior: `${fechaCorta(iso(antDesde))} al ${fechaCorta(iso(antHasta))}`,
    }
  }
  if (f.desde) return { actual: `desde el ${fechaCorta(f.desde)}`, anterior: null }
  if (f.hasta) return { actual: `hasta el ${fechaCorta(f.hasta)}`, anterior: null }
  return { actual: 'todo el histórico', anterior: null }
}
