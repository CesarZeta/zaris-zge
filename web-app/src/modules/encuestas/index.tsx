import { BarChart3 } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { EncuestasLayout } from './EncuestasLayout'
import { ResumenView } from './views/ResumenView'
import { ContactoView } from './views/ContactoView'
import { EnviosView } from './views/EnviosView'
import { useAuthStore } from '../../stores/auth'

// Módulo Encuestas (CSAT): resultados de las encuestas de satisfacción que se
// envían al cerrar reclamos (CLAUDE.md §42). Consume los dashboards del backend
// (/api/v1/admin/encuestas/*), que ya existían. moduloCodigo='encuestas' (catálogo
// `modulos`). El backend exige nivel <= 2 (_require_supervisor) en los dashboards;
// gateamos la UI igual para que el operador no vea pantalla vacía ni errores 403.

const MIN_NIVEL = 2

const Wrap = (Component: React.FC) => () => {
  const ok = useAuthStore((s) => (s.user?.nivel_acceso ?? 99) <= MIN_NIVEL)
  return (
    <EncuestasLayout>
      {ok ? <Component /> : <SinAcceso />}
    </EncuestasLayout>
  )
}

function SinAcceso() {
  return (
    <div style={{
      background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
      borderRadius: 12, padding: '36px 28px', textAlign: 'center',
      color: 'var(--fg-2)', maxWidth: 520, margin: '12px auto',
    }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.05rem', fontWeight: 600, color: 'var(--fg-1)', marginBottom: 8 }}>
        Acceso restringido
      </div>
      <p style={{ fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
        Los resultados de encuestas son exclusivos de los perfiles <strong>Supervisor</strong> y <strong>Administrador</strong>.
      </p>
    </div>
  )
}

export const encuestasModule: ModuleManifest = {
  id: 'encuestas',
  label: 'encuestas',
  icon: BarChart3,
  moduloCodigo: 'encuestas',
  routes: [
    { index: true,        element: Wrap(ResumenView),  handle: { breadcrumb: 'Encuestas' } },
    { path: 'contacto',   element: Wrap(ContactoView),  handle: { breadcrumb: 'Encuestas · Contacto' } },
    { path: 'envios',     element: Wrap(EnviosView),    handle: { breadcrumb: 'Encuestas · Envíos' } },
  ],
}
