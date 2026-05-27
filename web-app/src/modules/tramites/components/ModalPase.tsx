import { useEffect, useRef, useState } from 'react'
import { listarDestinatariosPase, type DestinatariosPase } from '../lib/api'

type DestTipo = 'subarea' | 'equipo' | 'agente'

interface ModalPaseProps {
  numeroExpediente: string
  onConfirmar: (body: { destinatario_tipo: DestTipo; destinatario_id: number; comentario?: string }) => Promise<void>
  onCerrar: () => void
}

export function ModalPase({ numeroExpediente, onConfirmar, onCerrar }: ModalPaseProps) {
  const [tipo, setTipo] = useState<DestTipo>('agente')
  const [idDest, setIdDest] = useState<number | null>(null)
  const [comentario, setComentario] = useState('')
  const [loading, setLoading] = useState(false)

  // Buscador de destinatarios (agentes / equipos / subareas)
  const [q, setQ] = useState('')
  const [opciones, setOpciones] = useState<DestinatariosPase | null>(null)
  const [buscando, setBuscando] = useState(false)
  const skipNext = useRef(false)

  useEffect(() => {
    if (skipNext.current) { skipNext.current = false; return }
    let cancel = false
    setBuscando(true)
    const t = setTimeout(() => {
      listarDestinatariosPase(q.trim() || undefined)
        .then((d) => { if (!cancel) setOpciones(d) })
        .catch(() => { if (!cancel) setOpciones(null) })
        .finally(() => { if (!cancel) setBuscando(false) })
    }, 280)
    return () => { cancel = true; clearTimeout(t) }
  }, [q])

  const listaActual: { id: number; nombre: string; sub?: string | null }[] =
    tipo === 'agente'
      ? (opciones?.agentes ?? []).map((a) => ({ id: a.id, nombre: a.nombre, sub: a.subarea_nombre }))
      : tipo === 'equipo'
        ? (opciones?.equipos ?? []).map((e) => ({ id: e.id, nombre: e.nombre }))
        : (opciones?.subareas ?? []).map((s) => ({ id: s.id, nombre: s.nombre }))

  async function handleConfirmar() {
    if (loading || !idDest) return
    setLoading(true)
    try {
      await onConfirmar({
        destinatario_tipo: tipo,
        destinatario_id: idDest,
        comentario: comentario.trim() || undefined,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div style={modalStyle}>
        <div style={headerStyle}>
          <h2 style={titleStyle}>Pase — {numeroExpediente}</h2>
        </div>
        <div style={bodyStyle}>
          <div>
            <label style={labelStyle}>Tipo de destinatario</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['agente', 'equipo', 'subarea'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => { setTipo(t); setIdDest(null) }}
                  style={{
                    padding: '7px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
                    cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13,
                    background: tipo === t ? 'var(--zaris-orange)' : 'var(--surface-300)',
                    color: tipo === t ? 'white' : 'var(--fg-2)',
                    fontWeight: tipo === t ? 600 : 400,
                  }}
                >
                  {t === 'agente' ? 'Agente' : t === 'equipo' ? 'Mesa (equipo)' : 'Subárea'}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={labelStyle}>
              {tipo === 'agente' ? 'Agente destino' : tipo === 'equipo' ? 'Mesa destino' : 'Subárea destino'}{' '}
              <span style={{ color: 'var(--color-error)' }}>*</span>
            </label>
            <input
              type="text"
              value={q}
              onChange={(e) => { setQ(e.target.value); setIdDest(null) }}
              placeholder={`Buscar ${tipo === 'agente' ? 'agente' : tipo === 'equipo' ? 'mesa' : 'subárea'} por nombre...`}
              style={inputStyle}
            />
            <div style={listaStyle}>
              {buscando && listaActual.length === 0 && (
                <div style={emptyStyle}>Buscando...</div>
              )}
              {!buscando && listaActual.length === 0 && (
                <div style={emptyStyle}>Sin resultados</div>
              )}
              {listaActual.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  onClick={() => { skipNext.current = true; setIdDest(o.id); setQ(o.nombre) }}
                  style={{
                    ...itemStyle,
                    background: idDest === o.id ? 'var(--surface-400)' : 'transparent',
                    boxShadow: idDest === o.id ? 'inset 3px 0 0 var(--zaris-orange)' : 'none',
                  }}
                >
                  <span style={{ color: 'var(--fg-1)', fontWeight: idDest === o.id ? 600 : 400 }}>{o.nombre}</span>
                  {o.sub ? <span style={{ color: 'var(--fg-3)', fontSize: 12 }}>{o.sub}</span> : null}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={labelStyle}>Motivo del pase (opcional)</label>
            <textarea
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              rows={2}
              placeholder="Indicá el motivo o instrucciones para el área receptora..."
              style={textareaStyle}
            />
          </div>
        </div>

        <div style={footerStyle}>
          <button type="button" onClick={onCerrar} style={btnSecStyle}>Cancelar</button>
          <button
            type="button"
            onClick={() => { void handleConfirmar() }}
            disabled={loading || !idDest}
            style={{
              ...btnPrimStyle,
              opacity: loading || !idDest ? 0.45 : 1,
              cursor: loading || !idDest ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Enviando...' : 'Confirmar pase'}
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
  width: '100%', maxWidth: 460, boxShadow: 'var(--shadow-card)',
  display: 'flex', flexDirection: 'column', maxHeight: '90vh', overflow: 'hidden',
}
const headerStyle: React.CSSProperties = {
  padding: '16px 20px', borderBottom: '1px solid var(--border-primary)',
}
const titleStyle: React.CSSProperties = {
  margin: 0, fontSize: 16, fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)',
}
const bodyStyle: React.CSSProperties = {
  padding: '20px', display: 'flex', flexDirection: 'column', gap: 16,
  overflowY: 'auto', flex: 1, minHeight: 0,
}
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', background: 'transparent',
  fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', outline: 'none',
  boxSizing: 'border-box', marginBottom: 8,
}
const listaStyle: React.CSSProperties = {
  maxHeight: 180, overflowY: 'auto', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column',
}
const itemStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8,
  padding: '8px 12px', border: 'none', cursor: 'pointer', textAlign: 'left',
  fontFamily: 'var(--font-display)', fontSize: 13, width: '100%',
  borderBottom: '1px solid var(--border-primary)',
}
const emptyStyle: React.CSSProperties = {
  padding: '12px', color: 'var(--fg-3)', fontSize: 13, fontFamily: 'var(--font-display)',
}
const footerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 8,
  padding: '14px 20px', borderTop: '1px solid var(--border-primary)',
}
const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--fg-3)',
  marginBottom: 6, fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
}
const textareaStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', background: 'transparent', resize: 'vertical',
  fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', outline: 'none',
  boxSizing: 'border-box',
}
const btnSecStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
  background: 'var(--surface-300)', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const btnPrimStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
  background: 'var(--zaris-orange)', color: 'white', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
}
