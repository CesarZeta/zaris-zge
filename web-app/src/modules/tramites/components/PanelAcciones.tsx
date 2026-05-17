import { useState } from 'react'
import { Lock, Unlock, ChevronRight, MessageSquare, Paperclip, ArrowRight, Link, AlertCircle } from 'lucide-react'
import type { TramiteDetalle, TransicionPermitida, TramiteDocumento } from '../types'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  tomarTramite, liberarTramite, transicionarTramite,
  pasarTramite, comentarTramite, relacionarTramite
} from '../lib/api'
import { ModalTransicion } from './ModalTransicion'
import { ModalPase } from './ModalPase'
import { ModalRelacionar } from './ModalRelacionar'

interface PanelAccionesProps {
  tramite: TramiteDetalle
  transicionesPermitidas: TransicionPermitida[]
  documentosDesdeEstado: TramiteDocumento[]
  idUsuarioActual?: number
  onActualizar: () => void
}

export function PanelAcciones({ tramite, transicionesPermitidas, documentosDesdeEstado, idUsuarioActual, onActualizar }: PanelAccionesProps) {
  const push = useNotificationsStore((s) => s.push)
  const [cargandoToma, setCargandoToma] = useState(false)
  const [comentario, setComentario] = useState('')
  const [enviandoComent, setEnviandoComent] = useState(false)
  const [transicionActiva, setTransicionActiva] = useState<TransicionPermitida | null>(null)
  const [showPase, setShowPase] = useState(false)
  const [showRelacionar, setShowRelacionar] = useState(false)

  // estado_actual.es_final no viene en la API plana — inferimos por código
  const esFinal = ['resuelto', 'cancelado', 'archivado'].includes(tramite.estado_codigo)
  const tomado = tramite.tomado_por_nombre != null
  const tomadoPorMi = tomado && idUsuarioActual != null  // aproximación: no tenemos id del tomador
  const tomadoPorOtro = tomado && !tomadoPorMi

  async function handleTomar() {
    setCargandoToma(true)
    try {
      await tomarTramite(tramite.numero_expediente)
      push({ kind: 'success', title: 'Trámite tomado' })
      onActualizar()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo tomar', body: e instanceof Error ? e.message : undefined })
    } finally {
      setCargandoToma(false)
    }
  }

  async function handleLiberar() {
    setCargandoToma(true)
    try {
      await liberarTramite(tramite.numero_expediente)
      push({ kind: 'success', title: 'Trámite liberado' })
      onActualizar()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo liberar', body: e instanceof Error ? e.message : undefined })
    } finally {
      setCargandoToma(false)
    }
  }

  async function handleTransicion(body: { id_tipo_tramite_transicion: number; comentario?: string }) {
    await transicionarTramite(tramite.numero_expediente, body)
    push({ kind: 'success', title: 'Transición ejecutada' })
    setTransicionActiva(null)
    onActualizar()
  }

  async function handlePase(body: { destinatario_tipo: 'subarea' | 'equipo'; destinatario_id: number; comentario?: string }) {
    await pasarTramite(tramite.numero_expediente, body)
    push({ kind: 'success', title: 'Pase registrado' })
    setShowPase(false)
    onActualizar()
  }

  async function handleRelacionar(body: { id_tramite_b: number; comentario?: string }) {
    await relacionarTramite(tramite.numero_expediente, body)
    push({ kind: 'success', title: 'Trámites relacionados' })
    setShowRelacionar(false)
    onActualizar()
  }

  async function handleComentar() {
    if (!comentario.trim()) return
    setEnviandoComent(true)
    try {
      await comentarTramite(tramite.numero_expediente, comentario.trim())
      push({ kind: 'success', title: 'Comentario registrado' })
      setComentario('')
      onActualizar()
    } catch (e) {
      push({ kind: 'error', title: 'Error al comentar', body: e instanceof Error ? e.message : undefined })
    } finally {
      setEnviandoComent(false)
    }
  }

  if (esFinal) {
    return (
      <div style={panelStyle}>
        <div style={{ padding: '14px 16px', background: 'var(--surface-300)', borderRadius: 'var(--radius-lg)', textAlign: 'center' }}>
          <p style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-3)' }}>
            Este trámite está en estado final — no hay acciones disponibles.
          </p>
        </div>
      </div>
    )
  }

  return (
    <>
      <div style={panelStyle}>
        {/* Toma */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Toma del trámite</h3>
          {tomadoPorOtro && (
            <div style={alertBoxStyle}>
              <AlertCircle size={14} strokeWidth={1.5} />
              <span style={{ fontSize: 12, fontFamily: 'var(--font-display)' }}>
                Tomado por {tramite.tomado_por_nombre ?? 'otro agente'}
              </span>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            {!tomado && (
              <button type="button" onClick={() => { void handleTomar() }} disabled={cargandoToma} style={btnAccentStyle}>
                <Lock size={14} strokeWidth={1.5} />
                {cargandoToma ? 'Tomando...' : 'Tomar'}
              </button>
            )}
            {tomadoPorMi && (
              <button type="button" onClick={() => { void handleLiberar() }} disabled={cargandoToma} style={btnGhostStyle}>
                <Unlock size={14} strokeWidth={1.5} />
                {cargandoToma ? 'Liberando...' : 'Liberar'}
              </button>
            )}
            {!tomado && (
              <p style={{ margin: 0, fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', alignSelf: 'center' }}>
                Sin tomar
              </p>
            )}
          </div>
        </section>

        {/* Transiciones */}
        {transicionesPermitidas.length > 0 && (
          <section style={sectionStyle}>
            <h3 style={sectionTitleStyle}>Acciones disponibles</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {transicionesPermitidas.map((t) => (
                <button
                  key={t.id_tipo_tramite_transicion}
                  type="button"
                  onClick={() => t.disponible && setTransicionActiva(t)}
                  title={!t.disponible ? (t.motivo_no_disponible ?? 'No disponible') : undefined}
                  style={{
                    ...transicionBtnStyle,
                    opacity: t.disponible ? 1 : 0.45,
                    cursor: t.disponible ? 'pointer' : 'not-allowed',
                  }}
                >
                  <span style={{ flex: 1, textAlign: 'left' }}>
                    <span style={{ display: 'block', fontWeight: 600, fontSize: 13 }}>{t.etiqueta_accion}</span>
                    <span style={{ display: 'block', fontSize: 11, color: 'var(--fg-3)' }}>
                      → {t.etiqueta_destino}
                    </span>
                  </span>
                  <ChevronRight size={14} strokeWidth={1.5} color="var(--fg-3)" />
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Acciones secundarias */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Otras acciones</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button type="button" onClick={() => setShowPase(true)} style={btnSecundarioStyle}>
              <ArrowRight size={14} strokeWidth={1.5} />
              Pase manual a área/equipo
            </button>
            <button type="button" onClick={() => setShowRelacionar(true)} style={btnSecundarioStyle}>
              <Link size={14} strokeWidth={1.5} />
              Relacionar con otro expediente
            </button>
          </div>
        </section>

        {/* Comentar */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Agregar comentario</h3>
          <textarea
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            rows={3}
            placeholder="Observación o nota interna..."
            style={textareaStyle}
          />
          <button
            type="button"
            onClick={() => { void handleComentar() }}
            disabled={enviandoComent || !comentario.trim()}
            style={{
              ...btnGhostSmStyle,
              opacity: enviandoComent || !comentario.trim() ? 0.45 : 1,
              cursor: enviandoComent || !comentario.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            <MessageSquare size={13} strokeWidth={1.5} />
            {enviandoComent ? 'Enviando...' : 'Agregar nota'}
          </button>
        </section>

        {/* Info estado */}
        <section style={{ ...sectionStyle, borderBottom: 'none', paddingBottom: 0 }}>
          <h3 style={sectionTitleStyle}>Estado actual</h3>
          <p style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-1)', fontWeight: 500 }}>
            {tramite.estado_etiqueta}
          </p>
          {tramite.destinatario_actual_nombre && (
            <p style={{ margin: '4px 0 0', fontSize: 12, fontFamily: 'var(--font-display)', color: 'var(--fg-3)' }}>
              Ubicación: {tramite.destinatario_actual_nombre}
            </p>
          )}
          <p style={{ margin: '4px 0 0', fontSize: 12, fontFamily: 'var(--font-display)', color: 'var(--fg-3)' }}>
            <Paperclip size={11} strokeWidth={1.5} style={{ verticalAlign: 'middle' }} />
            {' '}{tramite.cant_documentos} documento{tramite.cant_documentos !== 1 ? 's' : ''} adjunto{tramite.cant_documentos !== 1 ? 's' : ''}
          </p>
        </section>
      </div>

      {transicionActiva && (
        <ModalTransicion
          transicion={transicionActiva}
          documentosDesdeEstado={documentosDesdeEstado}
          onConfirmar={handleTransicion}
          onCerrar={() => setTransicionActiva(null)}
        />
      )}
      {showPase && (
        <ModalPase
          numeroExpediente={tramite.numero_expediente}
          onConfirmar={handlePase}
          onCerrar={() => setShowPase(false)}
        />
      )}
      {showRelacionar && (
        <ModalRelacionar
          numeroExpediente={tramite.numero_expediente}
          onConfirmar={handleRelacionar}
          onCerrar={() => setShowRelacionar(false)}
        />
      )}
    </>
  )
}


const panelStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)',
  border: '1px solid var(--border-primary)', display: 'flex', flexDirection: 'column',
  overflow: 'hidden',
}
const sectionStyle: React.CSSProperties = {
  padding: '16px', borderBottom: '1px solid var(--border-primary)',
  display: 'flex', flexDirection: 'column', gap: 8,
}
const sectionTitleStyle: React.CSSProperties = {
  margin: 0, fontSize: 11, fontWeight: 600, color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
}
const alertBoxStyle: React.CSSProperties = {
  display: 'flex', gap: 6, alignItems: 'center',
  padding: '8px 10px', background: 'rgba(207,45,86,.08)',
  border: '1px solid rgba(207,45,86,.25)', borderRadius: 'var(--radius-lg)',
  color: 'var(--color-error)',
}
const btnAccentStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '7px 14px', borderRadius: 'var(--radius-lg)', border: 'none',
  background: 'var(--zaris-orange)', color: 'white', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
}
const btnGhostStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '7px 14px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)',
  background: 'transparent', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const transicionBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '10px 12px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)',
  background: 'var(--surface-300)', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', width: '100%',
  transition: 'background 120ms ease',
}
const btnSecundarioStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '8px 12px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)',
  background: 'transparent', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13, width: '100%',
}
const textareaStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', background: 'transparent', resize: 'vertical',
  fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', outline: 'none',
  boxSizing: 'border-box',
}
const btnGhostSmStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '6px 12px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)',
  background: 'transparent', color: 'var(--fg-2)',
  fontFamily: 'var(--font-display)', fontSize: 12, alignSelf: 'flex-start',
}
