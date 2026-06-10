import { Siren } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { EmergenciasLayout } from './EmergenciasLayout'
import { Dispatcher } from './pages/Dispatcher'
import { Recepcion } from './pages/Recepcion'
import { DetalleEvento } from './pages/DetalleEvento'

// Modulo Emergencias (COM - Centro de Operaciones Municipales). Atencion de
// eventos de emergencia: recepcion del llamado (triage + denunciante BUC /
// contacto eventual / anonimo), tablero del dispatcher con polling 30s y
// detalle con FSM de estados + historial append-only.
// Backend: routes/emergencias.py (migs 81-83). moduloCodigo='emergencias'
// (mig 84, min_nivel_acceso=3 — espeja el guard nivel<=3 del backend).
const Wrap = (Component: React.FC) => () => (
  <EmergenciasLayout>
    <Component />
  </EmergenciasLayout>
)

export const emergenciasModule: ModuleManifest = {
  id:    'emergencias',
  label: 'emergencias',
  icon:  Siren,
  moduloCodigo: 'emergencias',
  routes: [
    { index: true,         element: Wrap(Dispatcher),    handle: { breadcrumb: 'emergencias' } },
    { path: 'recepcion',   element: Wrap(Recepcion),     handle: { breadcrumb: 'emergencias · recepción' } },
    { path: 'evento/:id',  element: Wrap(DetalleEvento), handle: { breadcrumb: 'emergencias · detalle' } },
  ],
}
