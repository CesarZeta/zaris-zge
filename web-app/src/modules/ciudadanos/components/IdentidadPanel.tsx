import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../../../stores/auth'
import { useNotificationsStore } from '../../../stores/notifications'
import { revocarIdentidad, validarIdentidad } from '../api/ciudadanosApi'
import { useCuentasCiudadano } from '../hooks/useCiudadanos'

/**
 * Identidad validada en el municipio (mig 139): un agente vio el documento de la persona en
 * una ventanilla. Algunos trámites del portal la exigen. Valida Atención o superior con perfil
 * de agente; revoca Supervisor o Administrador (el backend es la fuente de verdad: 403/409).
 */
export function IdentidadPanel({ idCiudadano }: { idCiudadano: number }) {
  const cuentas = useCuentasCiudadano(idCiudadano)
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const push = useNotificationsStore((s) => s.push)
  const qc = useQueryClient()
  const [modal, setModal] = useState<'validar' | 'revocar' | null>(null)

  if (!cuentas.data) return null
  const validada = cuentas.data.identidad_validada ?? null

  function refrescar() {
    void qc.invalidateQueries({ queryKey: ['buc', 'ciudadanos', idCiudadano, 'cuentas'] })
  }

  function confirmar(valores: { texto: string; observacion: string }) {
    if (modal === 'validar') {
      validarIdentidad(idCiudadano, { documento_presentado: valores.texto, observacion: valores.observacion || undefined })
        .then(() => push({ kind: 'success', title: 'Identidad validada', body: 'Quedó registrada en la ficha' }))
        .catch((e: unknown) => push({ kind: 'error', title: 'No se pudo validar la identidad', body: e instanceof Error ? e.message : undefined }))
        .finally(refrescar)
    } else if (modal === 'revocar') {
      revocarIdentidad(idCiudadano, { motivo: valores.texto })
        .then(() => push({ kind: 'success', title: 'Validación revocada' }))
        .catch((e: unknown) => push({ kind: 'error', title: 'No se pudo revocar la validación', body: e instanceof Error ? e.message : undefined }))
        .finally(refrescar)
    }
    setModal(null)
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
      <span style={etiqueta}>Identidad</span>
      <span style={{ ...chip, ...(validada ? tonoOk : tonoNeutro) }}>
        {validada
          ? `Identidad validada el ${fecha(validada.fecha)}${validada.agente_nombre ? ` por ${validada.agente_nombre}` : ''}`
          : 'Identidad sin validar en el municipio'}
      </span>
      {!validada && hasPermission(3) && (
        <button type="button" style={linkBtn} onClick={() => setModal('validar')}>Validar identidad</button>
      )}
      {validada && hasPermission(2) && (
        <button type="button" style={linkBtn} onClick={() => setModal('revocar')}>Revocar validación</button>
      )}
      {modal && <ModalIdentidad modo={modal} onConfirmar={confirmar} onCerrar={() => setModal(null)} />}
    </div>
  )
}

function ModalIdentidad({
  modo, onConfirmar, onCerrar,
}: {
  modo: 'validar' | 'revocar'
  onConfirmar: (v: { texto: string; observacion: string }) => void
  onCerrar: () => void
}) {
  const [texto, setTexto] = useState(modo === 'validar' ? 'DNI' : '')
  const [observacion, setObservacion] = useState('')
  const t = texto.trim()
  const valido = modo === 'validar' ? t.length >= 2 && t.length <= 40 : t.length >= 5
  return (
    <div style={overlay} onClick={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div style={caja} role="dialog" aria-modal="true">
        <h2 style={titulo}>{modo === 'validar' ? 'Validar la identidad' : 'Revocar la validación de identidad'}</h2>
        {modo === 'validar' && (
          <p style={ayuda}>Validá solo con la persona y su documento delante.</p>
        )}
        <label style={label} htmlFor="ident-texto">{modo === 'validar' ? 'Documento que presentó' : 'Motivo'}</label>
        {modo === 'validar' ? (
          <input id="ident-texto" value={texto} maxLength={40} onChange={(e) => setTexto(e.target.value)} style={campo} />
        ) : (
          <textarea id="ident-texto" value={texto} maxLength={1000} rows={3} onChange={(e) => setTexto(e.target.value)} style={campo} />
        )}
        {modo === 'validar' && (
          <>
            <label style={label} htmlFor="ident-obs">Observación (opcional)</label>
            <textarea id="ident-obs" value={observacion} maxLength={500} rows={2}
              onChange={(e) => setObservacion(e.target.value)} style={campo} />
          </>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
          <button type="button" onClick={onCerrar} style={btnSec}>Volver</button>
          <button
            type="button"
            disabled={!valido}
            onClick={() => onConfirmar({ texto: t, observacion: observacion.trim() })}
            style={{ ...btnPrim, opacity: valido ? 1 : 0.45, cursor: valido ? 'pointer' : 'not-allowed' }}
          >
            {modo === 'validar' ? 'Validar identidad' : 'Revocar validación'}
          </button>
        </div>
      </div>
    </div>
  )
}

function fecha(iso: string): string {
  return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

const etiqueta: React.CSSProperties = {
  fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em',
}
const chip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', padding: '3px 10px', borderRadius: 'var(--radius-pill)',
  fontSize: 'var(--size-caption)', fontWeight: 600, fontFamily: 'var(--font-display)',
}
const tonoOk: React.CSSProperties = { background: 'rgba(31,138,101,.12)', color: 'var(--color-success)' }
const tonoNeutro: React.CSSProperties = { background: 'var(--surface-400)', color: 'var(--fg-2)' }
const linkBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', padding: '2px 4px', cursor: 'pointer', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--zaris-orange)', textDecoration: 'underline',
}
const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(38,37,30,.5)', display: 'flex', alignItems: 'center',
  justifyContent: 'center', zIndex: 1000,
}
const caja: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)', width: '100%', maxWidth: 440,
  boxShadow: 'var(--shadow-card)', padding: 20, display: 'flex', flexDirection: 'column', gap: 6,
}
const titulo: React.CSSProperties = { margin: '0 0 6px', fontSize: 16, fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }
const ayuda: React.CSSProperties = { margin: '0 0 6px', fontSize: 13, color: 'var(--fg-2)', fontFamily: 'var(--font-display)' }
const label: React.CSSProperties = {
  fontSize: 12, fontWeight: 500, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', textTransform: 'uppercase',
  letterSpacing: '0.04em', marginTop: 6,
}
const campo: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  background: 'transparent', fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', boxSizing: 'border-box',
}
const btnSec: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none', background: 'var(--surface-300)',
  color: 'var(--fg-2)', cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13,
}
const btnPrim: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none', background: 'var(--zaris-orange)',
  color: 'white', fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
}
