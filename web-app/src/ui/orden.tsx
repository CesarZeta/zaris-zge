import { useCallback, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react'

/**
 * Ordenamiento por columnas — estándar de la suite (pedido de César,
 * 2026-10-20): clic en el encabezado ordena ascendente, el segundo clic
 * invierte; una flecha marca la columna activa.
 *
 * DÓNDE se ordena depende de la pantalla:
 *   - Listado con tope (limit / paginado: reclamos, trámites…): en el BACKEND,
 *     mandando `orden` + `dir`. Ordenar solo lo cargado mentiría — la fila
 *     buscada puede no estar en la página traída.
 *   - Listado que trae TODO (las mesas de OT): en pantalla con `ordenarFilas`.
 */
export type DirOrden = 'asc' | 'desc'
export interface Orden<K extends string> {
  campo: K
  dir: DirOrden
}

export function useOrden<K extends string>(inicial: Orden<K> | null = null) {
  const [orden, setOrden] = useState<Orden<K> | null>(inicial)
  const alternar = useCallback((campo: K) => {
    setOrden((prev) => (prev?.campo === campo
      ? { campo, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { campo, dir: 'asc' }))
  }, [])
  return { orden, alternar, setOrden }
}

type Valor = string | number | null | undefined

const comparador = new Intl.Collator('es', { sensitivity: 'base', numeric: true })

/**
 * Orden en pantalla para listados completos. `valores[campo](fila)` devuelve
 * el valor a comparar; los vacíos van siempre al final (en ambas direcciones),
 * y el orden es estable (empates conservan el orden que trajo el backend).
 */
export function ordenarFilas<T, K extends string>(
  filas: T[],
  orden: Orden<K> | null,
  valores: Record<K, (fila: T) => Valor>,
): T[] {
  if (!orden) return filas
  const valorDe = valores[orden.campo]
  const signo = orden.dir === 'asc' ? 1 : -1
  return filas
    .map((fila, i) => ({ fila, i, v: valorDe(fila) }))
    .sort((a, b) => {
      const va = a.v ?? null
      const vb = b.v ?? null
      if (va === null || va === '') return vb === null || vb === '' ? a.i - b.i : 1
      if (vb === null || vb === '') return -1
      const c = typeof va === 'number' && typeof vb === 'number'
        ? va - vb
        : comparador.compare(String(va), String(vb))
      return c !== 0 ? c * signo : a.i - b.i
    })
    .map((x) => x.fila)
}

/** Botón de orden para poner dentro de un encabezado (sirve también para dos
 *  criterios en la misma celda, p. ej. «N° · Tipo»). */
export function BotonOrden<K extends string>({
  campo, orden, onOrdenar, children,
}: {
  campo: K
  orden: Orden<K> | null
  onOrdenar: (campo: K) => void
  children: React.ReactNode
}) {
  const activo = orden?.campo === campo
  const Icono = !activo ? ChevronsUpDown : orden.dir === 'asc' ? ArrowUp : ArrowDown
  return (
    <button
      type="button"
      onClick={() => onOrdenar(campo)}
      title={activo
        ? (orden.dir === 'asc' ? 'Orden ascendente — clic para invertir' : 'Orden descendente — clic para invertir')
        : 'Ordenar por esta columna'}
      style={{ ...botonOrden, color: activo ? 'var(--fg-1)' : 'inherit' }}
    >
      {children}
      <Icono size={12} strokeWidth={1.75} style={{ opacity: activo ? 1 : 0.45, flexShrink: 0 }} />
    </button>
  )
}

/** Encabezado `<th>` ordenable. `style` es el del `<th>` de la tabla que lo usa. */
export function ThOrden<K extends string>({
  campo, orden, onOrdenar, children, style,
}: {
  campo: K
  orden: Orden<K> | null
  onOrdenar: (campo: K) => void
  children: React.ReactNode
  style?: React.CSSProperties
}) {
  const activo = orden?.campo === campo
  return (
    <th
      style={style}
      aria-sort={activo ? (orden.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <BotonOrden campo={campo} orden={orden} onOrdenar={onOrdenar}>{children}</BotonOrden>
    </th>
  )
}

const botonOrden: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  background: 'none', border: 'none', padding: 0, margin: 0, cursor: 'pointer',
  font: 'inherit', letterSpacing: 'inherit', textTransform: 'inherit',
}
