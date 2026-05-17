interface EstadoBadgeProps {
  etiqueta: string
  color?: string | null
  esFinal?: boolean
}

export function EstadoBadge({ etiqueta, color, esFinal }: EstadoBadgeProps) {
  const bg = color ? `${color}22` : 'var(--surface-400)'
  const fg = color ?? 'var(--fg-2)'
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontFamily: 'var(--font-display)',
        fontSize: 12,
        fontWeight: 500,
        padding: '3px 10px',
        borderRadius: 'var(--radius-pill)',
        background: bg,
        color: fg,
        opacity: esFinal ? 0.8 : 1,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: fg,
          flexShrink: 0,
        }}
      />
      {etiqueta}
    </span>
  )
}
