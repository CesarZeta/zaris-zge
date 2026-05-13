import type { ModuleManifest } from '../lib/types'
import { dashboardModule } from './dashboard'
import { reclamosModule } from './reclamos'
import { agendaModule } from './agenda'
import { otModule } from './ot'
import { contactosModule } from './contactos'
import { ciudadanosModule } from './ciudadanos'
import { empresasModule } from './empresas'
import { configModule } from './config'

// Registrar módulos nuevos acá — el shell los lee automáticamente.
// El orden refleja el sidebar del shell vanilla (index.html). Ver §14 CLAUDE.md.
// Dashboard primero porque es HOME (no aparece en sidebar pero sirve de landing).
// Ciudadanos y Empresas viven bajo Contactos (no tienen item top-level propio
// en el sidebar; se llega via la landing de Contactos), pero siguen exportando
// sus rutas /ciudadanos y /empresas para deep-links del shell vanilla y links
// internos desde otros modulos.
export const modules: ModuleManifest[] = [
  dashboardModule,
  reclamosModule,
  agendaModule,
  otModule,
  contactosModule,
  ciudadanosModule,
  empresasModule,
  configModule,
]
