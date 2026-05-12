import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { ClipboardList } from 'lucide-react'

function goInicio(e: React.MouseEvent) {
  e.preventDefault()
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) {
    w.shellNavigate('frontend/welcome.html')
  } else {
    window.location.href = '/'
  }
}

const VISTAS: Record<string, { label: string; title: string; subtitle: string }> = {
  supervisor: {
    label: 'Supervisor',
    title: 'Mesa del Supervisor',
    subtitle: 'Asigná o reasigná órdenes de trabajo sobre los reclamos activos.',
  },
  agente: {
    label: 'Agente',
    title: 'Mesa del Agente',
    subtitle: 'Tomá OTs disponibles para tu equipo o cerralas cuando termines el trabajo.',
  },
  auditoria: {
    label: 'Auditoría',
    title: 'Mesa de Auditoría',
    subtitle: 'Aprobá o rechazá OTs operativas cerradas pendientes de auditoría.',
  },
}

export function OTLayout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const partes = location.pathname.split('/').filter(Boolean) // ej ['ot','supervisor']
  const vista = partes[1] && VISTAS[partes[1]] ? VISTAS[partes[1]] : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav
        aria-label="Ruta de navegacion"
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontFamily: 'var(--font-display)', fontSize: '0.78rem',
        }}
      >
        <a
          href="#"
          onClick={goInicio}
          style={{
            color: 'var(--zaris-orange)', textDecoration: 'none',
            textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600,
          }}
        >
          INICIO
        </a>
        <span style={{ color: 'var(--fg-3)' }}>›</span>
        <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Órdenes de trabajo</span>
        {vista && (
          <>
            <span style={{ color: 'var(--fg-3)' }}>›</span>
            <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>{vista.label}</span>
          </>
        )}
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ClipboardList size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 style={{
            fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px',
            color: 'var(--fg-1)', lineHeight: 1.1, margin: 0,
          }}>
            {vista?.title ?? 'Órdenes de trabajo'}
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>
            {vista?.subtitle ?? 'Seleccioná una mesa desde el menú.'}
          </p>
        </div>
      </div>

      {children}
    </div>
  )
}
