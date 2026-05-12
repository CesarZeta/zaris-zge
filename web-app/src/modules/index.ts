import type { ModuleManifest } from '../lib/types'
import { dashboardModule } from './dashboard'
import { agendaModule } from './agenda'
import { ciudadanosModule } from './ciudadanos'
import { empresasModule } from './empresas'

// Registrar módulos nuevos acá — el shell los lee automáticamente.
export const modules: ModuleManifest[] = [
  dashboardModule,
  agendaModule,
  ciudadanosModule,
  empresasModule,
]
