import React, { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  width?: number | string
  footer?: React.ReactNode
}

export function Modal({ open, onClose, title, children, width = 560, footer }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    // Focus trap basico: focus en el modal al abrir
    setTimeout(() => contentRef.current?.focus(), 0)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(38,37,30,.45)',
        zIndex: 1000, display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        padding: '60px 24px 24px',
      }}
    >
      <div
        ref={contentRef}
        tabIndex={-1}
        style={{
          width, maxWidth: '100%', background: 'var(--surface-100)',
          borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-card)',
          padding: 20, outline: 'none',
          maxHeight: 'calc(100vh - 96px)', display: 'flex', flexDirection: 'column',
        }}
      >
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--size-title-sm)', fontWeight: 500, color: 'var(--fg-1)' }}>{title}</h2>
          <button
            aria-label="Cerrar"
            onClick={onClose}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: 'var(--fg-3)', padding: 4, display: 'inline-flex', borderRadius: 'var(--radius-md)',
            }}
          >
            <X size={18} strokeWidth={1.5} />
          </button>
        </header>
        <div style={{ overflowY: 'auto', flex: 1 }}>{children}</div>
        {footer && (
          <footer style={{ marginTop: 16, display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            {footer}
          </footer>
        )}
      </div>
    </div>
  )
}
