import type { ModuleManifest } from '../lib/types'
import { dashboardModule } from './dashboard'
import { emergenciasModule } from './emergencias'
import { reclamosModule } from './reclamos'
import { agendaModule } from './agenda'
import { turnosModule } from './turnos'
import { entradasModule } from './entradas'
import { otModule } from './ot'
import { contactosModule } from './contactos'
import { ciudadanosModule } from './ciudadanos'
import { empresasModule } from './empresas'
import { configModule } from './config'
import { tramitesModule } from './tramites'
import { encuestasModule } from './encuestas'
import { biModule } from './bi'
import { guiasModule } from './guias'

// Registrar módulos nuevos acá — el shell los lee automáticamente.
// El orden refleja el sidebar del shell vanilla (index.html). Ver §14 CLAUDE.md.
// Dashboard primero porque es HOME (no aparece en sidebar pero sirve de landing).
// Ciudadanos y Empresas viven bajo Contactos (no tienen item top-level propio
// en el sidebar; se llega via la landing de Contactos), pero siguen exportando
// sus rutas /ciudadanos y /empresas para deep-links del shell vanilla y links
// internos desde otros modulos.
// El orden y la agrupación espejan el sidebar reagrupado por rol del shell
// vanilla (index.html, secciones .nav-flat__section, CLAUDE.md §30):
//   Atención (nivel 3) · Supervisión (nivel 2) · Común · Administración (nivel 1)
export const modules: ModuleManifest[] = [
  dashboardModule,     // HOME — no aparece en sidebar
  // ── Atención (nivel 3) ──
  emergenciasModule,   // primero del sidebar (pedido del usuario 2026-06-10)
  reclamosModule,
  turnosModule,
  entradasModule,
  tramitesModule,
  // ── Supervisión (nivel 2) ──
  otModule,
  // ── Común (atención + supervisión) ──
  agendaModule,
  contactosModule,
  ciudadanosModule,    // detrás de Contactos (sin item top-level)
  empresasModule,      // detrás de Contactos (sin item top-level)
  // ── Administración (nivel 1) ──
  biModule,
  encuestasModule,
  configModule,
  guiasModule,
]
