import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { StateStorage } from 'zustand/middleware'
import type { User } from '../lib/types'

interface AuthState {
  user: User | null
  accessToken: string | null
  login: (token: string, user: User) => void
  logout: () => void
  hasPermission: (minLevel: number) => boolean
}

// Storage custom que mantiene en `zaris_session` AMBAS shapes:
//   - { state: { accessToken, user }, version: 0 }   (formato zustand-persist)
//   - { access_token, user }                          (formato shell vanilla)
// Asi el mismo login alcanza para los modulos vanilla y para el shell React,
// sin importar quien guardo la sesion primero. Ver CLAUDE.md §29.
const dualShapeStorage: StateStorage = {
  getItem: (key) => localStorage.getItem(key),
  setItem: (key, value) => {
    try {
      const parsed = JSON.parse(value)
      const accessToken = parsed?.state?.accessToken ?? null
      const user = parsed?.state?.user ?? null
      // Reescribimos manteniendo las dos shapes en la misma clave.
      const merged = JSON.stringify({
        ...parsed,
        access_token: accessToken,
        user,
      })
      localStorage.setItem(key, merged)
    } catch {
      localStorage.setItem(key, value)
    }
  },
  removeItem: (key) => localStorage.removeItem(key),
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,

      login(token, user) {
        set({ accessToken: token, user })
      },

      logout() {
        set({ accessToken: null, user: null })
      },

      hasPermission(minLevel) {
        const level = get().user?.nivel_acceso
        return level !== undefined && level <= minLevel
      },
    }),
    {
      name: 'zaris_session',
      storage: createJSONStorage(() => dualShapeStorage),
      partialize: (s) => ({ accessToken: s.accessToken, user: s.user }),
    }
  )
)
