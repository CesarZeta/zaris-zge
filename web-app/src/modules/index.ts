import type { ModuleManifest } from '../lib/types'
import { dashboardModule } from './dashboard'
import { agendaModule } from './agenda'

// Registrar módulos nuevos acá — el shell los lee automáticamente.
export const modules: ModuleManifest[] = [
  dashboardModule,
  agendaModule,
]
