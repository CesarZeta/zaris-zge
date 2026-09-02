import { Clock } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { TurnosLayout } from './TurnosLayout'
import { Overview } from './pages/Overview'
import { MisTurnos } from './pages/MisTurnos'
import { Atendidos } from './pages/Atendidos'
import { Consultas } from './pages/Consultas'
import { Prestaciones } from './pages/Prestaciones'
import { AgendaTurnos } from './pages/AgendaTurnos'
import { Ubicaciones } from './pages/Ubicaciones'
import { MesaUbicacion } from './pages/MesaUbicacion'

// Modulo Turnos (replanteado mig 71): los turnos cumplen PRESTACIONES. Una
// prestacion define el recurso fijo (un agente o un lugar de atencion), su
// duracion y su clase (atencion | reserva_espacio). El turno reserva un bloque
// de la disponibilidad efectiva de ese recurso (espejo en `ocupaciones` para la
// grilla de Agenda). Tab "Prestaciones" = ABM del catalogo (nivel <= 2).
// Backend: routes/turnos.py + turnos_publico.py. moduloCodigo='turnos' (mig 44).
const Wrap = (Component: React.FC) => () => (
  <TurnosLayout>
    <Component />
  </TurnosLayout>
)

export const turnosModule: ModuleManifest = {
  id:    'turnos',
  label: 'turnos',
  icon:  Clock,
  moduloCodigo: 'turnos',
  routes: [
    // F2 plan ATENCION (2026-09-01): el módulo se navega UBICACIÓN-primero.
    // index = landing de ubicaciones; 'mesa' = mesa del día de la ubicación
    // elegida; 'lista' = el listado histórico de turnos (scopeado por la
    // ubicación seleccionada, si hay).
    { index: true,           element: Wrap(Ubicaciones),     handle: { breadcrumb: 'turnos' } },
    { path: 'mesa',          element: Wrap(MesaUbicacion),   handle: { breadcrumb: 'turnos · mesa' } },
    { path: 'lista',         element: Wrap(Overview),        handle: { breadcrumb: 'turnos · lista' } },
    // "Mis turnos" = vista de gestión del agente (sidebar "Gestión de Turnos").
    // Reusa GET /turnos scopeado por nivel; no es una tab del layout, es ruta
    // directa enfocada en cumplir lo propio.
    { path: 'mis-turnos',    element: Wrap(MisTurnos),       handle: { breadcrumb: 'mis turnos' } },
    { path: 'agenda',        element: Wrap(AgendaTurnos),    handle: { breadcrumb: 'turnos · agenda' } },
    { path: 'atendidos',     element: Wrap(Atendidos),      handle: { breadcrumb: 'turnos · atendidos' } },
    { path: 'consultas',     element: Wrap(Consultas),      handle: { breadcrumb: 'turnos · consultas' } },
    { path: 'prestaciones',  element: Wrap(Prestaciones),    handle: { breadcrumb: 'turnos · prestaciones' } },
  ],
}
