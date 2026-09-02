import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Ubicación de atención seleccionada en el módulo Turnos (F2 plan ATENCION,
// 2026-09-01). El módulo se navega ubicación-primero: la selección persiste
// entre sesiones (localStorage) y scopea Mesa, Turnos, Agenda y Atendidos.

export interface UbicacionSeleccionada {
  id_espacio: number
  nombre: string
}

interface UbicacionTurnosState {
  ubicacion: UbicacionSeleccionada | null
  setUbicacion: (u: UbicacionSeleccionada | null) => void
}

export const useUbicacionTurnosStore = create<UbicacionTurnosState>()(
  persist(
    (set) => ({
      ubicacion: null,
      setUbicacion: (u) => set({ ubicacion: u }),
    }),
    { name: 'zaris_turnos_ubicacion' },
  ),
)
