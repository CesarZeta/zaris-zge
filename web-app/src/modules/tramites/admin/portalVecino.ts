import type { IniciadorTipo } from '../types'

/** Quitar «ciudadano» de los iniciadores apaga la oferta al vecino. */
export function ofrecerTrasCambioIniciadores(iniciadores: IniciadorTipo[], ofrecer: boolean): boolean {
  return iniciadores.includes('ciudadano') ? ofrecer : false
}
