import type { EstadoTurno, OrdenTurnos, Turno } from '../types/turno'

/** Orden del ciclo de vida (espejo del CASE de `_ORDEN_TURNOS` en turnos.py). */
const RANGO_ESTADO: Record<EstadoTurno, number> = {
  reservado: 1, llamado: 2, cumplido: 3, ausente: 4, cancelado: 5,
}

/** Valores para `ordenarFilas` en las pantallas que ordenan lo cargado (Mis
 *  turnos, Consultas). Mismas columnas y criterio que el orden del backend. */
export const VALORES_ORDEN_TURNOS: Record<OrdenTurnos, (t: Turno) => string | number | null> = {
  fecha: (t) => `${t.fecha} ${t.hora_inicio}`,
  ciudadano: (t) => t.ciudadano_nombre,
  atiende: (t) => t.recurso_nombre ?? t.agente_nombre,
  prestacion: (t) => t.prestacion_nombre,
  estado: (t) => RANGO_ESTADO[t.estado],
}
