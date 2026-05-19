import { FileText, ClipboardList, Settings, ExternalLink } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface Guia {
  titulo: string
  descripcion: string
  icon: LucideIcon
  htmlName: string  // nombre del archivo en /docs/
  audiencia: string
  tags: string[]
}

const GUIAS: Guia[] = [
  {
    titulo: 'RECLAMOS',
    descripcion: 'Cómo gestionar reclamos ciudadanos: alta, seguimiento, cambio de estado, adjuntos, subreclamos y cierre.',
    icon: FileText,
    htmlName: 'manual_reclamos.html',
    audiencia: 'Operador o superior',
    tags: ['Operativo', '10 capturas', '11 secciones'],
  },
  {
    titulo: 'ÓRDENES DE TRABAJO',
    descripcion: 'Las 3 mesas del módulo OT: Supervisor (asignar), Agente (ejecutar) y Auditoría (validar). Ciclo de vida completo.',
    icon: ClipboardList,
    htmlName: 'manual_ot.html',
    audiencia: 'Supervisor / Agente / Auditor',
    tags: ['Operativo', '9 capturas', '11 secciones'],
  },
  {
    titulo: 'TRÁMITES (CREACIÓN)',
    descripcion: 'Cómo el administrador configura tipos de trámite custom: estados, transiciones, campos, documentos requeridos y versionado.',
    icon: Settings,
    htmlName: 'manual_admin_tramites.html',
    audiencia: 'Admin o Supervisor',
    tags: ['Configuración', '11 capturas', '11 secciones'],
  },
]

function urlDocs(htmlName: string): string {
  // En prod (shell vanilla en /), el HTML vive en /docs/X.html.
  // En dev (localhost:5173 standalone), el archivo no está disponible (porque vite no sirve /docs).
  // En ese caso usamos el dev del shell vanilla en http://localhost:8080/docs/...
  if (typeof window === 'undefined') return `/docs/${htmlName}`

  // Caso 1: estamos dentro del iframe del shell vanilla (prod o local 8080).
  // El parent location nos da el root del shell (con su pathname).
  if (window.self !== window.top) {
    try {
      const parentLoc = window.parent.location
      const base = parentLoc.pathname.replace(/[^/]*$/, '')  // strip "index.html"
      return `${parentLoc.origin}${base}docs/${htmlName}`
    } catch {
      // cross-origin (no debería pasar en prod): fallback al origin actual
    }
  }

  // Caso 2: standalone en dev (localhost:5173). El docs/ no está disponible acá;
  // apuntamos al shell vanilla local en 8080.
  if (window.location.hostname === 'localhost' && window.location.port === '5173') {
    return `http://localhost:8080/docs/${htmlName}`
  }

  // Caso 3: standalone en prod (no debería pasar, hay un redirect en el bundle).
  return `${window.location.origin}/docs/${htmlName}`
}

export function GuiasIndex() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <header>
        <h1 style={titleStyle}>Guías de uso</h1>
        <p style={subStyle}>
          Manuales operativos con capturas reales. Click en una tarjeta abre la guía en una pestaña nueva.
        </p>
      </header>

      <div style={gridStyle}>
        {GUIAS.map((g) => (
          <a
            key={g.htmlName}
            href={urlDocs(g.htmlName)}
            target="_blank"
            rel="noopener noreferrer"
            style={cardStyle}
            onMouseEnter={(e) => {
              ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--zaris-orange)'
              ;(e.currentTarget as HTMLElement).style.boxShadow = '0 4px 16px rgba(245,78,0,.12)'
            }}
            onMouseLeave={(e) => {
              ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--border-primary)'
              ;(e.currentTarget as HTMLElement).style.boxShadow = '0 1px 3px rgba(38,37,30,.05)'
            }}
          >
            <div style={cardHeaderStyle}>
              <g.icon size={20} strokeWidth={1.5} color="var(--zaris-orange)" />
              <h2 style={cardTitleStyle}>{g.titulo}</h2>
              <ExternalLink size={14} color="var(--fg-3)" />
            </div>
            <p style={cardDescStyle}>{g.descripcion}</p>
            <div style={cardMetaStyle}>
              <span style={audienciaStyle}>{g.audiencia}</span>
              <div style={tagsRow}>
                {g.tags.map((t) => (
                  <span key={t} style={tagStyle}>{t}</span>
                ))}
              </div>
            </div>
          </a>
        ))}
      </div>

      <footer style={footerStyle}>
        Más guías próximamente para Agenda, Turnos, Entradas, Padrones y Trámites (uso operativo).
      </footer>
    </div>
  )
}

const titleStyle: React.CSSProperties = {
  margin: 0, fontSize: '1.6rem', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', fontWeight: 700, letterSpacing: '-0.01em',
}
const subStyle: React.CSSProperties = {
  margin: '6px 0 0', color: 'var(--fg-2)', fontSize: 14,
}
const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
  gap: 16,
  marginTop: 12,
}
const cardStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
  padding: '20px 22px',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg, 12px)',
  textDecoration: 'none',
  color: 'var(--fg-1)',
  transition: 'border-color 150ms ease, box-shadow 150ms ease',
  cursor: 'pointer',
  boxShadow: '0 1px 3px rgba(38,37,30,.05)',
}
const cardHeaderStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10,
}
const cardTitleStyle: React.CSSProperties = {
  flex: 1,
  margin: 0,
  fontSize: '0.95rem',
  fontFamily: 'var(--font-display)',
  fontWeight: 700,
  color: 'var(--fg-1)',
  letterSpacing: '0.02em',
}
const cardDescStyle: React.CSSProperties = {
  margin: 0,
  color: 'var(--fg-2)',
  fontSize: 13,
  lineHeight: 1.5,
}
const cardMetaStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 10,
  marginTop: 4,
  paddingTop: 10,
  borderTop: '1px solid var(--border-primary)',
}
const audienciaStyle: React.CSSProperties = {
  fontSize: 11,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--fg-3)',
  fontWeight: 600,
}
const tagsRow: React.CSSProperties = {
  display: 'flex', gap: 4, flexWrap: 'wrap',
}
const tagStyle: React.CSSProperties = {
  fontSize: 10,
  padding: '2px 6px',
  background: 'var(--surface-300)',
  color: 'var(--fg-3)',
  borderRadius: 4,
  fontFamily: 'var(--font-mono, monospace)',
}
const footerStyle: React.CSSProperties = {
  marginTop: 16, padding: '12px 0',
  color: 'var(--fg-3)', fontSize: 12, textAlign: 'center',
  borderTop: '1px solid var(--border-primary)',
}
