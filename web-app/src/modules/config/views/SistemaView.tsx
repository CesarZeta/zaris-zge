import { Database, Landmark, Users } from 'lucide-react'
import { shellNavigate } from '../../../lib/shellNav'
import { ParametrosSistemaView } from './ParametrosSistemaView'

interface Atajo {
  icon: typeof Database
  titulo: string
  descripcion: string
  href: string
}

// Atajos a pantallas de catálogos/maestros que NO son ajustes booleanos del
// sistema (viven en admin_tablas vanilla o en la pantalla de usuarios).
const ATAJOS: Atajo[] = [
  {
    icon: Landmark,
    titulo: 'Municipios',
    descripcion: 'Datos del/los municipios donde opera el sistema.',
    href: 'frontend/admin_tablas.html?tabla=municipios',
  },
  {
    icon: Users,
    titulo: 'Usuarios del sistema',
    descripcion: 'Alta, baja y edición de cuentas de usuario.',
    href: 'frontend/usuarios.html',
  },
  {
    icon: Database,
    titulo: 'Todos los maestros',
    descripcion: 'Catálogos completos: áreas, subáreas, agentes, tipos de reclamo, etc.',
    href: 'frontend/admin_tablas.html?tabla=area',
  },
]

function irA(href: string, e: React.MouseEvent) {
  e.preventDefault()
  shellNavigate(href)
}

export function SistemaView() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {/* Ajustes reales del sistema, agrupados y con controles tipados. */}
      <ParametrosSistemaView />

      {/* Accesos a catálogos/maestros (secundario). */}
      <div>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.95rem',
          color: 'var(--fg-1)', marginBottom: 4,
        }}>
          Catálogos y maestros
        </div>
        <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', marginTop: 0, marginBottom: 14 }}>
          Abren el módulo Maestros o la gestión de usuarios.
        </p>

        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14,
        }}>
          {ATAJOS.map((a) => {
          const Icon = a.icon
          return (
            <a
              key={a.href}
              href={a.href}
              onClick={(e) => irA(a.href, e)}
              style={cardStyle}
              onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.background = 'var(--surface-400)' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.background = 'var(--surface-100)' }}
            >
              <div style={iconWrapStyle}>
                <Icon size={22} strokeWidth={1.5} color="var(--zaris-orange)" />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '1rem', color: 'var(--fg-1)' }}>
                  {a.titulo}
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)', marginTop: 4, lineHeight: 1.4 }}>
                  {a.descripcion}
                </div>
              </div>
            </a>
          )
        })}
        </div>
      </div>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 14,
  padding: 16,
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 12,
  textDecoration: 'none', color: 'var(--fg-1)',
  cursor: 'pointer',
  transition: 'background 150ms ease',
}

const iconWrapStyle: React.CSSProperties = {
  width: 40, height: 40,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: 'rgba(245, 78, 0, 0.08)', borderRadius: 8,
  flexShrink: 0,
}
