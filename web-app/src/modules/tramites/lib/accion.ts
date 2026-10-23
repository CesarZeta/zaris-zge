// Color de una transición según su tipo de acción (BUG-04). Lo usan el editor de
// circuitos y los botones del agente en el detalle del trámite.
export function colorAccion(tipo?: string): string {
  switch (tipo) {
    case 'aprobar': return 'var(--color-success)'
    case 'rechazar': return 'var(--color-error)'
    case 'derivar': return '#6a1b9a'
    case 'otro': return 'var(--fg-3)'
    default: return 'var(--fg-2)' // avanzar / sin definir
  }
}

// En el botón del agente solo llevan acento las acciones con intención propia;
// avanzar/otro quedan neutros.
export function accionDestacada(tipo?: string): boolean {
  return tipo === 'aprobar' || tipo === 'rechazar' || tipo === 'derivar'
}
