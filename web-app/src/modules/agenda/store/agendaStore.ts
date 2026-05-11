import { create } from 'zustand'
import { hoy, toIsoDate } from '../../../lib/dates'

export type VistaAgenda = 'timeline' | 'mensual' | 'eventos' | 'conflictos'
export type FiltroRecurso = 'todos' | 'agente' | 'equipo'

interface AgendaState {
  fechaActiva: string           // YYYY-MM-DD
  idMunicipio: number
  filtroRecurso: FiltroRecurso
  vista: VistaAgenda
  setFechaActiva: (f: string) => void
  setIdMunicipio: (n: number) => void
  setFiltroRecurso: (r: FiltroRecurso) => void
  setVista: (v: VistaAgenda) => void
  irAHoy: () => void
}

export const useAgendaStore = create<AgendaState>()((set) => ({
  fechaActiva: toIsoDate(hoy()),
  idMunicipio: 1,
  filtroRecurso: 'todos',
  vista: 'timeline',
  setFechaActiva:    (f) => set({ fechaActiva: f }),
  setIdMunicipio:    (n) => set({ idMunicipio: n }),
  setFiltroRecurso:  (r) => set({ filtroRecurso: r }),
  setVista:          (v) => set({ vista: v }),
  irAHoy:            () => set({ fechaActiva: toIsoDate(hoy()) }),
}))
