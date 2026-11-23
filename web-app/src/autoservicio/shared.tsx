// Estilos y assets compartidos por las paginas publicas de autoservicio.
// No importar nada de stores ni de hooks del backoffice.

import { useEffect, useState, type CSSProperties } from 'react'
import { raizDelSitio } from '../lib/shellNav'
import { getIdentidadPublica, type IdentidadPublica } from './api'

export const layoutStyles = {
  page: {
    minHeight: '100vh',
    background: 'var(--zaris-cream)',
    color: 'var(--fg-1)',
    fontFamily: 'var(--font-display)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '32px 16px',
  } satisfies CSSProperties,
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 18,
    color: 'var(--zaris-orange)',
  } satisfies CSSProperties,
  card: {
    width: '100%',
    maxWidth: 560,
    background: 'var(--surface-100)',
    border: '1px solid var(--border-primary)',
    borderRadius: 'var(--radius-lg)',
    padding: '28px 28px 32px',
    boxShadow: '0 8px 24px rgba(38,37,30,.06)',
  } satisfies CSSProperties,
  footer: {
    marginTop: 24,
    fontSize: 12,
    color: 'var(--fg-3)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '.06em',
  } satisfies CSSProperties,
  h1: {
    margin: '0 0 6px',
    fontSize: 26,
    fontFamily: 'var(--font-display)',
    color: 'var(--fg-1)',
    lineHeight: 1.2,
  } satisfies CSSProperties,
  h2: {
    margin: '0 0 8px',
    fontSize: 16,
    fontFamily: 'var(--font-display)',
    color: 'var(--fg-1)',
  } satisfies CSSProperties,
  desc: {
    color: 'var(--fg-2)',
    fontSize: 14,
    marginTop: 0,
    marginBottom: 18,
  } satisfies CSSProperties,
  metaRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
    gap: 10,
    padding: 14,
    background: 'var(--surface-200)',
    borderRadius: 'var(--radius-md)',
  } satisfies CSSProperties,
  metaCell: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  } satisfies CSSProperties,
  metaLabel: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'uppercase',
    letterSpacing: '.06em',
  } satisfies CSSProperties,
  metaValue: {
    fontSize: 14,
    color: 'var(--fg-1)',
    fontWeight: 500,
  } satisfies CSSProperties,
  formGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 14,
  } satisfies CSSProperties,
  fieldLabel: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'uppercase',
    letterSpacing: '.04em',
    fontFamily: 'var(--font-display)',
  } satisfies CSSProperties,
  input: {
    width: '100%',
    fontFamily: 'var(--font-display)',
    fontSize: 14,
    color: 'var(--fg-1)',
    padding: '10px 12px',
    border: '1px solid var(--border-primary)',
    borderRadius: 'var(--radius-md)',
    background: 'var(--surface-100)',
    outline: 'none',
    boxSizing: 'border-box',
  } satisfies CSSProperties,
  submit: {
    marginTop: 22,
    width: '100%',
    padding: '12px 16px',
    background: 'var(--zaris-orange)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: 15,
    fontFamily: 'var(--font-display)',
    fontWeight: 600,
    letterSpacing: '.02em',
    cursor: 'pointer',
  } satisfies CSSProperties,
  err: {
    marginTop: 14,
    padding: '10px 12px',
    background: 'rgba(207,45,86,.08)',
    color: 'var(--color-error)',
    border: '1px solid rgba(207,45,86,.2)',
    borderRadius: 'var(--radius-md)',
    fontSize: 13,
  } satisfies CSSProperties,
  warn: {
    marginTop: 20,
    padding: '12px 14px',
    background: 'var(--surface-300)',
    color: 'var(--fg-2)',
    borderRadius: 'var(--radius-md)',
    fontSize: 14,
  } satisfies CSSProperties,
  center: {
    textAlign: 'center' as const,
    color: 'var(--fg-2)',
    padding: '24px 8px',
  } satisfies CSSProperties,
} as const

// Logo oficial ZARIS. Espeja zaris-mark-flat.svg (stroke=currentColor) inline
// para heredar el color del contenedor. Fuente del path:
// design-system/assets/zaris-mark-flat.svg (mantener en sync).
export function ZarisMark() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--zaris-orange)' }}>
      <svg width={36} height={36} viewBox="0 0 500 500" aria-hidden>
        <g fill="none" stroke="currentColor" strokeWidth={34} strokeLinecap="round" strokeLinejoin="round">
          <path d="M 110 78 L 388 78" />
          <path d="M 388 78 L 110 430" />
          <path d="M 388 220 L 222 430" />
          <path d="M 388 362 L 334 430" />
        </g>
      </svg>
      <span style={{
        fontWeight: 600, color: 'var(--fg-1)', letterSpacing: '.04em',
        fontFamily: 'var(--font-display)', fontSize: 18,
      }}>ZARIS</span>
    </div>
  )
}

// Toda transacción empieza por el registro de la persona (César, 2026-11-23): estas páginas no
// reservan; mandan al portal del vecino a ingresar o a crear la cuenta.
export function IrAlPortal({ texto }: { texto: string }) {
  const [id, setId] = useState<IdentidadPublica | null>(null)
  const [fallo, setFallo] = useState(false)
  useEffect(() => {
    let cancel = false
    getIdentidadPublica()
      .then((d) => { if (!cancel) setId(d) })
      .catch(() => { if (!cancel) setFallo(true) })
    return () => { cancel = true }
  }, [])

  const alta = id?.municipio_slug
    ? `${raizDelSitio(window.location.pathname)}frontend/alta-vecino.html?m=${encodeURIComponent(id.municipio_slug)}`
    : null
  const boton: CSSProperties = { ...layoutStyles.submit, display: 'block', textAlign: 'center', textDecoration: 'none', boxSizing: 'border-box' }

  return (
    <div style={{ marginTop: 20 }}>
      <p style={{ ...layoutStyles.desc, marginBottom: 0 }}>{texto}</p>
      {id?.app_vecinos_url && (
        <a style={boton} href={id.app_vecinos_url}>Ingresar al portal del vecino</a>
      )}
      {alta && (
        <a
          style={{ ...boton, marginTop: 10, background: 'transparent', color: 'var(--zaris-orange)', border: '1px solid var(--zaris-orange)' }}
          href={alta}
        >
          Todavía no tengo cuenta
        </a>
      )}
      {(fallo || (id && !id.app_vecinos_url && !alta)) && (
        <div style={layoutStyles.warn}>En este momento no podemos mostrarte el portal. Acercate al municipio o probá más tarde.</div>
      )}
    </div>
  )
}
