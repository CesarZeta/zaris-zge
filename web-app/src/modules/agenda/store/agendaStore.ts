import { create } from 'zustand'
import { hoy, toIsoDate } from '../../../lib/dates'
import type { FiltroRecursoUI, TipoRecurso, VistaGrilla } from '../types/agenda'

export type VistaAgenda = 'vistas' | 'eventos' | 'conflictos' | 'config'

interface AgendaState {
  fechaActiva: string           // YYYY-MM-DD
  idMunicipio: number
  // Sub-fase B2: 4 valores (agentes / equipos / espacios_atendidos / espacios_desatendidos).
  filtroRecurso: FiltroRecursoUI
  filtroSubarea: number | null
  vista: VistaAgenda
  vistaGrilla: VistaGrilla       // sub-toggle dentro de 'vistas'
  setFechaActiva: (f: string) => void
  setIdMunicipio: (n: number) => void
  setFiltroRecurso: (r: FiltroRecursoUI) => void
  setFiltroSubarea: (id: number | null) => void
  setVista: (v: VistaAgenda) => void
  setVistaGrilla: (v: VistaGrilla) => void
  irAHoy: () => void
}

export const useAgendaStore = create<AgendaState>()((set) => ({
  fechaActiva: toIsoDate(hoy()),
  idMunicipio: 1,
  filtroRecurso: 'agentes',
  filtroSubarea: null,
  vista: 'vistas',
  vistaGrilla: 'dia',
  setFechaActiva:    (f) => set({ fechaActiva: f }),
  setIdMunicipio:    (n) => set({ idMunicipio: n }),
  setFiltroRecurso:  (r) => set({ filtroRecurso: r }),
  setFiltroSubarea:  (id) => set({ filtroSubarea: id }),
  setVista:          (v) => set({ vista: v }),
  setVistaGrilla:    (v) => set({ vistaGrilla: v }),
  irAHoy:            () => set({ fechaActiva: toIsoDate(hoy()) }),
}))

/**
 * Traduce el filtro UI a los params que entiende el backend:
 *   - tipo_recurso: 'agente' | 'equipo' | 'espacio'
 *   - atendido: solo aplica a tipo_recurso='espacio'
 *   - scopeSubareaPropia: la vista "equipos" sirve a la asignacion de OT y
 *     se scopea a la subarea del supervisor logueado (ver §33 CLAUDE.md).
 *     Backend hace fail-open si no puede resolver la subarea del usuario.
 */
export function filtroUIaBackend(f: FiltroRecursoUI): {
  tipo_recurso: TipoRecurso
  atendido: boolean | null
  scopeSubareaPropia: boolean
} {
  switch (f) {
    case 'agentes':               return { tipo_recurso: 'agente',  atendido: null,  scopeSubareaPropia: false }
    case 'equipos':               return { tipo_recurso: 'equipo',  atendido: null,  scopeSubareaPropia: true }
    case 'espacios_atendidos':    return { tipo_recurso: 'espacio', atendido: true,  scopeSubareaPropia: false }
    case 'espacios_desatendidos': return { tipo_recurso: 'espacio', atendido: false, scopeSubareaPropia: false }
  }
}
