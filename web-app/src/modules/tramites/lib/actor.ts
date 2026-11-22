import type { IniciadorTipo } from '../types'

/** Quién hizo un movimiento o subió un documento (mig 139: puede ser el vecino desde el portal). */
export interface ConActor {
  actor_tipo?: 'agente' | 'ciudadano' | 'sistema'
  actor_nombre?: string | null
  agente_nombre?: string | null
}

/** Para intercalar en una frase: «el vecino Pérez, Ana» · «Gómez, Luis» · «el sistema». */
export function nombreActor(m: ConActor): string {
  if (m.actor_tipo === 'ciudadano') return `el vecino ${m.actor_nombre ?? ''}`.trim()
  if (m.actor_tipo === 'sistema') return 'el sistema'
  return m.agente_nombre ?? m.actor_nombre ?? 'un agente'
}

/** Para mostrar suelto, como autor de una fila: «Vecino · Pérez, Ana» · «Gómez, Luis» · «Sistema». */
export function autorActor(m: ConActor): string {
  if (m.actor_tipo === 'ciudadano') return `Vecino · ${m.actor_nombre ?? ''}`
  if (m.actor_tipo === 'sistema') return 'Sistema'
  return m.agente_nombre ?? m.actor_nombre ?? '—'
}

export const ETIQUETA_INICIADOR: Record<IniciadorTipo, string> = {
  ciudadano: 'Vecino',
  empresa: 'Empresa',
  area_interna: 'Área interna',
}
