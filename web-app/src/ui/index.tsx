import React from 'react'

/* ── Button ───────────────────────────────────────────────── */
type ButtonVariant = 'default' | 'primary' | 'accent' | 'ghost'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  icon?: React.ReactNode
}

export function Button({ variant = 'default', icon, children, style, ...rest }: ButtonProps) {
  const base: React.CSSProperties = {
    fontFamily: 'var(--font-display)',
    fontSize: 'var(--size-btn)',
    fontWeight: 400,
    lineHeight: 1,
    padding: '10px 14px',
    borderRadius: 'var(--radius-lg)',
    border: 'none',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    transition: 'color 150ms ease, background 150ms ease, box-shadow 200ms ease',
  }
  const variants: Record<ButtonVariant, React.CSSProperties> = {
    default: { background: 'var(--surface-300)', color: 'var(--fg-1)', boxShadow: 'var(--ring-border)' },
    primary: { background: 'var(--zaris-dark)', color: 'var(--zaris-cream)' },
    accent:  { background: 'var(--zaris-orange)', color: 'var(--zaris-cream)' },
    ghost:   { background: 'rgba(38,37,30,.06)', color: 'var(--fg-3)', padding: '6px 12px' },
  }

  const [hovered, setHovered] = React.useState(false)
  const hoverColor = variant === 'primary' || variant === 'accent' ? undefined : 'var(--color-error)'

  return (
    <button
      {...rest}
      style={{ ...base, ...variants[variant], ...(hovered && hoverColor ? { color: hoverColor } : {}), ...style }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {icon}{children}
    </button>
  )
}

/* ── IconButton ───────────────────────────────────────────── */
interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
}

export function IconButton({ label, children, style, ...rest }: IconButtonProps) {
  const [hovered, setHovered] = React.useState(false)
  return (
    <button
      aria-label={label}
      title={label}
      {...rest}
      style={{
        background: 'transparent',
        border: 'none',
        borderRadius: 'var(--radius-lg)',
        padding: 6,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: hovered ? 'var(--color-error)' : 'var(--fg-3)',
        transition: 'color 150ms ease',
        cursor: 'pointer',
        ...style,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {children}
    </button>
  )
}

/* ── Pill ─────────────────────────────────────────────────── */
interface PillProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean
}

export function Pill({ active, children, ...rest }: PillProps) {
  return (
    <button
      {...rest}
      style={{
        fontFamily: 'var(--font-display)',
        fontSize: 13,
        padding: '4px 10px',
        borderRadius: 'var(--radius-pill)',
        border: 'none',
        cursor: 'pointer',
        background: active ? 'var(--surface-500)' : 'var(--surface-400)',
        color: active ? 'var(--fg-2)' : 'var(--fg-3)',
        transition: 'color 150ms ease',
      }}
    >
      {children}
    </button>
  )
}

/* ── Badge ────────────────────────────────────────────────── */
type BadgeKind = 'neutral' | 'success' | 'error' | 'warn'

interface BadgeProps {
  kind?: BadgeKind
  dot?: boolean
  children: React.ReactNode
}

const BADGE_COLORS: Record<BadgeKind, { bg: string; fg: string }> = {
  neutral: { bg: 'var(--surface-400)',           fg: 'var(--fg-2)' },
  success: { bg: 'rgba(31,138,101,.14)',         fg: '#1f8a65' },
  error:   { bg: 'rgba(207,45,86,.14)',          fg: 'var(--color-error)' },
  warn:    { bg: 'rgba(192,133,50,.18)',         fg: 'var(--zaris-gold)' },
}

export function Badge({ kind = 'neutral', dot, children }: BadgeProps) {
  const { bg, fg } = BADGE_COLORS[kind]
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 500,
      padding: '3px 10px', borderRadius: 'var(--radius-pill)',
      background: bg, color: fg,
    }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: '50%', background: fg }} />}
      {children}
    </span>
  )
}

/* ── Input ────────────────────────────────────────────────── */
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode
}

export function Input({ icon, style, ...rest }: InputProps) {
  const [focused, setFocused] = React.useState(false)
  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {icon && (
        <span style={{
          position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
          color: 'var(--fg-3)', pointerEvents: 'none', display: 'flex',
        }}>
          {icon}
        </span>
      )}
      <input
        {...rest}
        onFocus={(e) => { setFocused(true); rest.onFocus?.(e) }}
        onBlur={(e)  => { setFocused(false); rest.onBlur?.(e) }}
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--size-ui)',
          color: 'var(--fg-1)',
          background: 'transparent',
          padding: icon ? '9px 12px 9px 34px' : '9px 12px',
          border: `1px solid ${focused ? 'var(--border-medium)' : 'var(--border-primary)'}`,
          borderRadius: 'var(--radius-lg)',
          outline: 'none',
          width: '100%',
          boxShadow: focused ? 'var(--shadow-focus)' : 'none',
          transition: 'border-color 150ms ease, box-shadow 200ms ease',
          ...style,
        }}
      />
    </div>
  )
}

/* ── Card ─────────────────────────────────────────────────── */
type CardVariant = 'default' | 'elevated' | 'ambient' | 'featured'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant
}

const CARD_SHADOWS: Record<CardVariant, string> = {
  default:  'var(--ring-border)',
  elevated: 'var(--shadow-card)',
  ambient:  'var(--shadow-ambient), var(--ring-border)',
  featured: 'var(--shadow-card)',
}

export function Card({ variant = 'default', children, style, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      style={{
        background: 'var(--surface-400)',
        borderRadius: variant === 'featured' ? 'var(--radius-xl)' : 'var(--radius-lg)',
        padding: 16,
        boxShadow: CARD_SHADOWS[variant],
        ...style,
      }}
    >
      {children}
    </div>
  )
}

/* ── EmptyState ───────────────────────────────────────────── */
interface EmptyStateProps {
  title: string
  description?: string
  action?: React.ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: 48, textAlign: 'center', gap: 12,
    }}>
      <p style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', color: 'var(--fg-1)', fontWeight: 500 }}>
        {title}
      </p>
      {description && (
        <p style={{ fontSize: 'var(--size-btn)', color: 'var(--fg-3)', maxWidth: 340 }}>{description}</p>
      )}
      {action}
    </div>
  )
}

/* ── Skeleton ─────────────────────────────────────────────── */
export function Skeleton({ width = '100%', height = 16, style }: { width?: number | string; height?: number | string; style?: React.CSSProperties }) {
  return (
    <div style={{
      width, height,
      background: 'linear-gradient(90deg, var(--surface-400) 25%, var(--surface-300) 50%, var(--surface-400) 75%)',
      backgroundSize: '200% 100%',
      borderRadius: 'var(--radius-md)',
      animation: 'skeleton-shimmer 1.4s ease infinite',
      ...style,
    }} />
  )
}

/* ── Table ────────────────────────────────────────────────── */
interface Column<T> {
  key: keyof T | string
  header: string
  render?: (row: T) => React.ReactNode
  width?: number | string
}

interface TableProps<T> {
  columns: Column<T>[]
  rows: T[]
  keyField: keyof T
}

export function Table<T extends object>({ columns, rows, keyField }: TableProps<T>) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--size-btn)', fontFamily: 'var(--font-display)' }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={String(col.key)} style={{
                padding: '8px 12px', textAlign: 'left', fontWeight: 500,
                color: 'var(--fg-3)', borderBottom: '1px solid var(--border-primary)',
                width: col.width,
              }}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String((row as Record<string, unknown>)[keyField as string])} style={{ borderBottom: '1px solid var(--border-primary)' }}>
              {columns.map((col) => (
                <td key={String(col.key)} style={{ padding: '10px 12px', color: 'var(--fg-1)' }}>
                  {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key as string] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
