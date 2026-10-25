import { useState } from 'react'
import { Landmark, Users } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { shellNavigate } from '../../../lib/shellNav'
import { useAuthStore } from '../../../stores/auth'
import { ParametrosGlobalesView } from './ParametrosGlobalesView'
import { ParametrosSistemaView } from './ParametrosSistemaView'

interface Atajo {
  icon: typeof Landmark
  titulo: string
  descripcion: string
  href: string
  /** Ruta interna del bundle React (react-router) en vez de página del shell. */
  interna?: boolean
  /** Solo para el super administrador (IT-01 F3). */
  soloSuper?: boolean
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
    // Desde IT-01 F3 los municipios los edita solo el super administrador, en su módulo.
    icon: Landmark,
    titulo: 'Municipios',
    descripcion: 'Datos de los municipios donde opera el sistema.',
    href: '/municipios',
    interna: true,
    soloSuper: true,
  },
]

export function SistemaView() {
  const navigate = useNavigate()
  const esSuper = useAuthStore((s) => s.user?.es_super_admin === true)
  const [solapa, setSolapa] = useState<'municipio' | 'globales'>('municipio')

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
          {ATAJOS.filter((a) => !a.soloSuper || esSuper).map((a) => {
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

      {/* Super administrador (IT-01 F3): los parámetros del municipio elegido en el selector y,
          en otra solapa, los globales. El resto ve solo los de su municipio. */}
      {esSuper && (
        <div role="tablist" aria-label="Parámetros" style={{ display: 'flex', gap: 8 }}>
          {([['municipio', 'Del municipio'], ['globales', 'Parámetros globales']] as const).map(([id, txt]) => (
            <button key={id} type="button" role="tab" aria-selected={solapa === id} onClick={() => setSolapa(id)}
                    style={{ ...solapaStyle, ...(solapa === id ? solapaActiva : {}) }}>
              {txt}
            </button>
          ))}
        </div>
      )}
      {/* Ajustes reales del sistema, agrupados y con controles tipados. */}
      {esSuper && solapa === 'globales' ? <ParametrosGlobalesView /> : <ParametrosSistemaView />}
    </div>
  )
}

const solapaStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 600, padding: '6px 14px',
  background: 'var(--surface-100)', color: 'var(--fg-2)', border: '1px solid var(--border-primary)',
  borderRadius: 999, cursor: 'pointer',
}
const solapaActiva: React.CSSProperties = {
  color: 'var(--zaris-orange)', borderColor: 'var(--zaris-orange)', background: 'var(--surface-300)',
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
