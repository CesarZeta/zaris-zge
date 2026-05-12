import { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import { Copy, Check } from 'lucide-react'

interface Props {
  value: string
  size?: number
  showText?: boolean
  copiable?: boolean
}

/**
 * Render del codigo QR sobre un <canvas>. Acepta cualquier string.
 * Devuelve un bloque con el QR + texto monoespaciado debajo (opcional)
 * y boton de copiar (opcional).
 */
export function QRDisplay({ value, size = 160, showText = true, copiable = true }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!canvasRef.current || !value) return
    QRCode.toCanvas(canvasRef.current, value, {
      width: size,
      margin: 1,
      errorCorrectionLevel: 'M',
      color: { dark: '#26251e', light: '#ffffff' },
    }).catch((e) => {
      console.warn('QRCode render error:', e)
    })
  }, [value, size])

  function onCopy() {
    if (!navigator.clipboard) return
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div style={{
      display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: 6,
      padding: 10, background: 'var(--surface-100)', borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-primary)',
    }}>
      <canvas ref={canvasRef} style={{ display: 'block', borderRadius: 4 }} />
      {showText && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)',
          maxWidth: size + 20,
        }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>
          {copiable && (
            <button
              onClick={onCopy}
              aria-label={copied ? 'Copiado' : 'Copiar codigo'}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: copied ? 'var(--color-success)' : 'var(--fg-3)',
                padding: 0, display: 'inline-flex', alignItems: 'center',
              }}
            >
              {copied ? <Check size={12} strokeWidth={1.5} /> : <Copy size={12} strokeWidth={1.5} />}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
