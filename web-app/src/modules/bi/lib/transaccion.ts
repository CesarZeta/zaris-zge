import type { BiFiltros } from './types'

/** Cómo se nombra lo que cuenta el tablero según la transacción elegida (mig 141). */
export interface NombresTransaccion {
  singular: string
  Singular: string
  plural: string
  Plural: string
  subPlural: string
  SubPlural: string
  SubSingular: string
}

const RECLAMOS: NombresTransaccion = {
  singular: 'reclamo', Singular: 'Reclamo', plural: 'reclamos', Plural: 'Reclamos',
  subPlural: 'subreclamos', SubPlural: 'Subreclamos', SubSingular: 'Subreclamo',
}

const RELEVAMIENTOS: NombresTransaccion = {
  singular: 'relevamiento', Singular: 'Relevamiento', plural: 'relevamientos', Plural: 'Relevamientos',
  subPlural: 'subrelevamientos', SubPlural: 'Subrelevamientos', SubSingular: 'Subrelevamiento',
}

export function nombresTransaccion(f?: Pick<BiFiltros, 'clase'> | null): NombresTransaccion {
  return f?.clase === 'relevamientos' ? RELEVAMIENTOS : RECLAMOS
}
