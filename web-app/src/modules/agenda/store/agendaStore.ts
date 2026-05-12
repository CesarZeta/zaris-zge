import { create } from 'zustand'
import { hoy, toIsoDate } from '../../../lib/dates'

export type VistaAgenda = 'timeline' | 'mensual' | 'eventos' | 'conflictos'
export type FiltroRecurso = 'todos' | 'agente' | 'equipo'

interface AgendaState {
  fechaActiva: string           // YYYY-MM-DD
  idMunicipio: number
  filtroRecurso: FiltroRecurso
  filtroSubarea: number | null
  vista: VistaAgenda
  setFechaActiva: (f: string) => void
  setIdMunicipio: (n: number) => void
  setFiltroRecurso: (r: FiltroRecurso) => void
  setFiltroSubarea: (id: number | null) => void
  setVista: (v: VistaAgenda) => void
  irAHoy: () => void
}

export const useAgendaStore = create<AgendaState>()((set) => ({
  fechaActiva: toIsoDate(hoy()),
  idMunicipio: 1,
  filtroRecurso: 'todos',
  filtroSubarea: null,
  vista: 'timeline',
  setFechaActiva:    (f) => set({ fechaActiva: f }),
  setIdMunicipio:    (n) => set({ idMunicipio: n }),
  setFiltroRecurso:  (r) => set({ filtroRecurso: r }),
  setFiltroSubarea:  (id) => set({ filtroSubarea: id }),
  setVista:          (v) => set({ vista: v }),
  irAHoy:            () => set({ fechaActiva: toIsoDate(hoy()) }),
}))
