import { ClipboardList } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import type { ModuleManifest } from '../../lib/types'
import { OTLayout } from './OTLayout'
import { SupervisorView } from './views/SupervisorView'
import { AgenteView } from './views/AgenteView'
import { AuditoriaView } from './views/AuditoriaView'
import { useAuthStore } from '../../stores/auth'

const Wrap = (Component: React.FC) => () => (
  <OTLayout>
    <Component />
  </OTLayout>
)

// #2 — Gate de rol en el bundle: Mesa Supervisor y Auditoría exigen nivel <= 2
// (Admin/Supervisor). El backend ya rechaza con 403 los endpoints, pero gateamos
// también acá para que el operador no vea la pantalla ni los botones (defensa en
// profundidad + UX clara). El sidebar vanilla ya oculta el ítem por data-modulo,
// pero un operador con ot_agente comparte el mismo bundle y puede deep-linkear.
const WrapNivel = (Component: React.FC, minNivel: number, mesa: string) => () => {
  const ok = useAuthStore((s) => (s.user?.nivel_acceso ?? 99) <= minNivel)
  return (
    <OTLayout>
      {ok ? <Component /> : <SinAcceso mesa={mesa} />}
    </OTLayout>
  )
}

function SinAcceso({ mesa }: { mesa: string }) {
  return (
    <div
      style={{
        background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
        borderRadius: 12, padding: '36px 28px', textAlign: 'center',
        color: 'var(--fg-2)', maxWidth: 520, margin: '12px auto',
      }}
    >
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.05rem', fontWeight: 600, color: 'var(--fg-1)', marginBottom: 8 }}>
        Acceso restringido
      </div>
      <p style={{ fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
        La {mesa} es exclusiva de los perfiles <strong>Supervisor</strong> y <strong>Administrador</strong>.
        Tu perfil no tiene permiso para esta sección.
      </p>
    </div>
  )
}

// /ot sin sub-ruta → supervisor para Admin/Supervisor (nivel <=2),
// agente para Operador/Consultor (no tienen Mesa Supervisor).
const RedirectDefault = () => {
  const esSupervisor = useAuthStore((s) => (s.user?.nivel_acceso ?? 99) <= 2)
  return <Navigate to={esSupervisor ? '/ot/supervisor' : '/ot/agente'} replace />
}

export const otModule: ModuleManifest = {
  id: 'ot',
  label: 'OT',
  icon: ClipboardList,
  // NO seteamos moduloCodigo a nivel manifest porque las 3 mesas tienen
  // moduloCodigo distinto (ot_supervisor / ot_agente / ot_auditoria).
  // El filtrado de permisos se hace por link en el sidebar vanilla
  // (data-modulo) y a nivel endpoint backend cuando corresponda.
  routes: [
    { index: true,           element: RedirectDefault, handle: { breadcrumb: 'OT' } },
    { path: 'supervisor',    element: WrapNivel(SupervisorView, 2, 'Mesa del Supervisor'), handle: { breadcrumb: 'OT · Supervisor' } },
    { path: 'agente',        element: Wrap(AgenteView),     handle: { breadcrumb: 'OT · Agente' } },
    { path: 'auditoria',     element: WrapNivel(AuditoriaView, 2, 'Mesa de Auditoría'),  handle: { breadcrumb: 'OT · Auditoría' } },
  ],
}
