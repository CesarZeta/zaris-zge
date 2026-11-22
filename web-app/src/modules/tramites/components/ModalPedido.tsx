import { useState } from 'react'

/**
 * Pedir algo al vecino iniciador, o cancelar el pedido abierto (mig 139).
 * Se cierra AL CONFIRMAR (CLAUDE.md §23): el resultado llega por toast desde quien lo abre.
 */
type Props =
  | { modo: 'pedir'; abierto: boolean; onConfirmar: (b: { texto: string; pide_archivo: boolean }) => void; onCerrar: () => void }
  | { modo: 'cancelar'; abierto: boolean; onConfirmar: (b: { motivo: string }) => void; onCerrar: () => void }

const MIN = 5

export function ModalPedido(props: Props) {
  // El contenido se monta en cada apertura: los campos arrancan vacíos (§29, sin texto residual).
  if (!props.abierto) return null
  return <Contenido {...props} />
}

function Contenido(props: Props) {
  const [texto, setTexto] = useState('')
  const [pideArchivo, setPideArchivo] = useState(false)
  const max = props.modo === 'pedir' ? 2000 : 1000

  const largo = texto.trim().length
  const valido = largo >= MIN && largo <= max

  function confirmar() {
    if (!valido) return
    if (props.modo === 'pedir') props.onConfirmar({ texto: texto.trim(), pide_archivo: pideArchivo })
    else props.onConfirmar({ motivo: texto.trim() })
    props.onCerrar()
  }

  return (
    <div
      style={overlayStyle}
      onMouseDown={(e) => { if (e.target === e.currentTarget) (e.currentTarget as HTMLElement).dataset.down = '1' }}
      onMouseUp={(e) => {
        const el = e.currentTarget as HTMLElement
        if (e.target === el && el.dataset.down === '1') props.onCerrar()
        delete el.dataset.down
      }}
    >
      <div style={modalStyle} role="dialog" aria-modal="true">
        <div style={headerStyle}>
          <h2 style={titleStyle}>{props.modo === 'pedir' ? 'Pedir al vecino' : 'Cancelar el pedido al vecino'}</h2>
        </div>
        <div style={bodyStyle}>
          <div>
            <label style={labelStyle} htmlFor="pedido-texto">
              {props.modo === 'pedir' ? '¿Qué le pedís al vecino?' : 'Motivo'}
            </label>
            <textarea
              id="pedido-texto"
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              rows={props.modo === 'pedir' ? 5 : 3}
              maxLength={max}
              style={textareaStyle}
              placeholder={props.modo === 'pedir'
                ? 'Por ejemplo: adjuntá una foto del árbol desde la vereda.'
                : 'Por ejemplo: ya lo trajo en persona a la ventanilla.'}
            />
            <p style={{ ...hintStyle, color: largo > 0 && !valido ? 'var(--color-error)' : 'var(--fg-3)' }}>
              {largo}/{max} · mínimo {MIN} caracteres
            </p>
          </div>

          {props.modo === 'pedir' && (
            <>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', fontFamily: 'var(--font-display)' }}>
                <input type="checkbox" checked={pideArchivo} onChange={(e) => setPideArchivo(e.target.checked)} />
                Tiene que adjuntar al menos un archivo
              </label>
              <p style={{ ...hintStyle, margin: 0 }}>
                Le llega un aviso en la app y un correo. Si no contesta, el trámite queda desistido
                en el mismo plazo que los demás avisos.
              </p>
            </>
          )}
        </div>
        <div style={footerStyle}>
          <button type="button" onClick={props.onCerrar} style={btnSecStyle}>Volver</button>
          <button
            type="button"
            onClick={confirmar}
            disabled={!valido}
            style={{ ...btnPrimStyle, opacity: valido ? 1 : 0.45, cursor: valido ? 'pointer' : 'not-allowed' }}
          >
            {props.modo === 'pedir' ? 'Enviar pedido' : 'Cancelar pedido'}
          </button>
        </div>
      </div>
    </div>
  )
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(38,37,30,.5)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}
const modalStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)',
  width: '100%', maxWidth: 480, boxShadow: 'var(--shadow-card)',
  display: 'flex', flexDirection: 'column',
}
const headerStyle: React.CSSProperties = { padding: '16px 20px', borderBottom: '1px solid var(--border-primary)' }
const titleStyle: React.CSSProperties = {
  margin: 0, fontSize: 16, fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)',
}
const bodyStyle: React.CSSProperties = { padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }
const footerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '14px 20px', borderTop: '1px solid var(--border-primary)',
}
const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--fg-3)', marginBottom: 4,
  fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
}
const textareaStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  background: 'transparent', resize: 'vertical', fontFamily: 'var(--font-display)', fontSize: 13,
  color: 'var(--fg-1)', outline: 'none', boxSizing: 'border-box',
}
const hintStyle: React.CSSProperties = { margin: '4px 0 0', fontSize: 11, fontFamily: 'var(--font-display)' }
const btnSecStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none', background: 'var(--surface-300)',
  color: 'var(--fg-2)', cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13,
}
const btnPrimStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none', background: 'var(--zaris-orange)',
  color: 'white', fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
}
