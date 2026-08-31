import type { LucideIcon } from 'lucide-react'
import type React from 'react'

export interface User {
  id_usuario: number
  nombre: string
  email: string
  nivel_acceso: 1 | 2 | 3 | 4 | 5
  modulos_permitidos?: string[]   // CLAUDE.md §30. Opcional para retro-compat con sesiones viejas.
  // Subárea del agente vinculado (Fase 3 roles): scopea pickers/bandejas del
  // supervisor. Opcionales: sesiones viejas no los traen (el backend igual impone).
  id_subarea?: number | null
  subarea_nombre?: string | null
  // Los trae login/me (§14); el shell dev los muestra en el topbar clonado de prod.
  cargo_nombre?: string | null
  foto_url?: string | null
}

export interface SubNavItem {
  label: string
  path: string
}

export interface ModuleRoute {
  index?: boolean
  path?: string
  element: React.FC
  handle?: Record<string, unknown>
}

export interface ModuleManifest {
  id: string
  label: string
  icon: LucideIcon
  routes: ModuleRoute[]
  navItems?: SubNavItem[]
  permissions?: string[]          // deprecado: usar moduloCodigo
  moduloCodigo?: string           // CLAUDE.md §30: si esta seteado y el usuario no lo tiene en modulos_permitidos, el modulo se oculta del sidebar.
  hideFromSidebar?: boolean       // El modulo se registra (rutas activas, deep-links del shell vanilla) pero NO aparece en el sidebar del shell React standalone. Util para modulos accesibles solo desde una landing (ej: ciudadanos / empresas viven bajo contactos).
}

export interface Notification {
  id: string
  kind: 'info' | 'success' | 'error'
  title: string
  body?: string
  ttl?: number
}

export interface Notification {
  id: string
  kind: 'info' | 'success' | 'error'
  title: string
  body?: string
  ttl?: number // ms, default 4000
}
