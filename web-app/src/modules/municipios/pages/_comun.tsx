// Piezas compartidas por las pantallas del módulo «Municipios».

export function Campo({ etiqueta, ayuda, error, children }: {
  etiqueta: string; ayuda?: string; error?: string; children: React.ReactNode
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={labelCampo}>{etiqueta}</span>
      {children}
      {error ? <span style={{ fontSize: 12, color: 'var(--color-error)' }}>{error}</span>
        : ayuda ? <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{ayuda}</span> : null}
    </label>
  )
}

export const titulo: React.CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--fg-1)' }
export const tabla: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: 13 }
export const th: React.CSSProperties = {
  textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border-medium)', color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em',
}
export const td: React.CSSProperties = { padding: '8px 10px', borderBottom: '1px solid var(--border-primary)', color: 'var(--fg-1)' }
export const grupo: React.CSSProperties = {
  padding: '12px 10px 6px', color: 'var(--fg-2)', fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600,
  borderBottom: '1px solid var(--border-medium)', background: 'var(--surface-300)',
}
export const labelCampo: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
}
export const input: React.CSSProperties = {
  fontFamily: 'inherit', fontSize: 13, color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-md)', padding: '7px 10px',
}
export const seccion: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 12, padding: 16, borderRadius: 12,
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
}
export const subtitulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--fg-1)',
}
