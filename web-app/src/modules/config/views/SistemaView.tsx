import { Landmark, Users } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { shellNavigate } from '../../../lib/shellNav'
import { ParametrosSistemaView } from './ParametrosSistemaView'

interface Atajo {
  icon: typeof Landmark
  titulo: string
  descripcion: string
  href: string
  /** Ruta interna del bundle React (react-router) en vez de página del shell. */
  interna?: boolean
}

// Atajos a pantallas de catálogos/maestros que NO son ajustes booleanos del
// sistema. Usuarios es un módulo React propio desde 2026-07-16 (tiene ítem
// en el sidebar); el atajo queda como acceso alternativo.
const ATAJOS: Atajo[] = [
  {
    icon: Users,
    titulo: 'Usuarios del sistema',
    descripcion: 'Alta, baja y edición de cuentas, permisos y catálogo de módulos.',
    href: '/usuarios/maestro',
    interna: true,
  },
  {
    icon: Landmark,
    titulo: 'Municipios',
    descripcion: 'Datos del/los municipios donde opera el sistema.',
    href: 'frontend/admin_tablas.html?tabla=municipios',
  },
]

export function SistemaView() {
  const navigate = useNavigate()

  function irA(a: Atajo, e: React.MouseEvent) {
    e.preventDefault()
    if (a.interna) navigate(a.href)
    else shellNavigate(a.href)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {/* Accesos a catálogos/maestros — primero, para que Usuarios sea
          alcanzable sin scrollear (es su único acceso desde el menú). */}
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
              onClick={(e) => irA(a, e)}
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

      {/* Ajustes reales del sistema, agrupados y con controles tipados. */}
      <ParametrosSistemaView />
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
