import { useLocation, useNavigate } from 'react-router-dom'
import { Button } from '../ui'

/** Ruta interna inexistente del bundle React. Mismo mensaje que el 404.html de la raíz del sitio. */
export function NoEncontradaPage() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  return (
    <div style={{ minHeight: '100%', display: 'grid', placeItems: 'center', padding: 24, boxSizing: 'border-box' }}>
      <div style={{
        width: '100%', maxWidth: 460, boxSizing: 'border-box', padding: 32, background: 'var(--surface-100)',
        border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-xl)',
      }}>
        <p style={{ margin: '0 0 8px', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--zaris-orange)' }}>Error 404</p>
        <h1 style={{ margin: '0 0 12px', fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 500, color: 'var(--fg-1)' }}>
          No encontramos esta página
        </h1>
        <p style={{ margin: '0 0 16px', fontSize: 15, lineHeight: 1.5, color: 'var(--fg-2)' }}>
          La dirección puede estar mal escrita, o la página ya no existe.
        </p>
        <p style={{
          margin: '0 0 24px', padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-2)',
          background: 'var(--surface-400)', borderRadius: 'var(--radius-md)', overflowWrap: 'anywhere',
        }}>
          {pathname}
        </p>
        <Button variant="primary" type="button" onClick={() => navigate('/dashboard', { replace: true })}>Ir al inicio</Button>
      </div>
    </div>
  )
}
