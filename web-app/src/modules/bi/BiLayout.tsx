import type { ReactNode } from 'react'
import { Activity } from 'lucide-react'
import { shellGoInicio } from '../../lib/shellNav'
import { shellNavigate } from '../../lib/shellNav'

// Layout compartido de los tableros (breadcrumb + título). Cada tablero pasa
// su título/subtítulo; el default es el Operativo, que desde 2026-08-30 es UNA
// página (Resumen → Respuesta → Pendientes → Subreclamos) sin tabs.
export function BiLayout({
  children,
  titulo = 'Análisis de datos Operativo',
  subtitulo = 'Tablero por área de servicio: resumen, tiempos de respuesta, pendientes y subreclamos, con exportación de los tickets filtrados.',
}: { children: ReactNode; titulo?: string; subtitulo?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 1400, margin: '0 auto', width: '100%', padding: '0 8px' }}>
      <nav
        aria-label="Ruta de navegación"
        style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-display)', fontSize: '0.78rem' }}
      >
        <a
          href="#"
          onClick={(e) => { e.preventDefault(); shellGoInicio() }}
          style={{ color: 'var(--zaris-orange)', textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}
        >
          INICIO
        </a>
        <span style={{ color: 'var(--fg-3)' }}>›</span>
        <a
          href="#"
          onClick={(e) => { e.preventDefault(); navDatos() }}
          style={{ color: 'var(--zaris-orange)', textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}
        >
          DATOS
        </a>
        <span style={{ color: 'var(--fg-3)' }}>›</span>
        <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>{titulo}</span>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Activity size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 style={{ fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px', color: 'var(--fg-1)', lineHeight: 1.1, margin: 0 }}>
            {titulo}
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>
            {subtitulo}
          </p>
        </div>
      </div>

      {children}
    </div>
  )
}

// Navega a la landing DATOS, respetando iframe (shell vanilla) vs standalone.
function navDatos() {
  if (typeof window !== 'undefined' && window.self !== window.top) {
    shellNavigate('web-app/dist/index.html#/bi')
  } else {
    window.location.hash = '#/bi'
  }
}
