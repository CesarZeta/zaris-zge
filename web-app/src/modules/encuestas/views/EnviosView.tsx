import { useState } from 'react'
import { RefreshCw, X } from 'lucide-react'
import { useEnvios, useEnvioDetalle } from '../hooks/useEncuestas'
import { colorCsat } from '../components/charts'
import type { EstadoEnvio } from '../lib/types'

const ESTADO_COLOR: Record<string, { bg: string; fg: string }> = {
  pendiente:  { bg: 'var(--surface-400)',         fg: 'var(--fg-2)' },
  enviada:    { bg: 'rgba(245,127,23,0.14)',      fg: '#b35900' },
  abierta:    { bg: 'rgba(106,27,154,0.12)',      fg: '#6a1b9a' },
  completada: { bg: 'rgba(31,138,101,0.16)',      fg: '#1f8a65' },
  expirada:   { bg: 'rgba(38,37,30,0.08)',        fg: 'var(--fg-3)' },
}

const ESTADOS: EstadoEnvio[] = ['pendiente', 'enviada', 'abierta', 'completada', 'expirada']

function fmt(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function EnviosView() {
  const [estado, setEstado] = useState<string>('')
  const [detalleId, setDetalleId] = useState<number | null>(null)
  const { data, isLoading, isError, error, refetch, isFetching } = useEnvios({
    estado: estado || undefined,
    limit: 200,
  })

  const envios = data ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={toolbar}>
        <div style={field}>
          <label style={lbl}>Estado</label>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} style={inp}>
            <option value="">Todos</option>
            {ESTADOS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <button onClick={() => refetch()} style={{ ...btnGhost, marginLeft: 'auto', alignSelf: 'flex-end' }} title="Refrescar">
          <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
        </button>
      </div>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar envíos'}</div>}

      <div style={card}>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Envío</th>
              <th style={th}>Reclamo</th>
              <th style={th}>Email destino</th>
              <th style={th}>Estado</th>
              <th style={th}>Enviada</th>
              <th style={th}>Completada</th>
              <th style={th}>Vence</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} style={empty}>Cargando…</td></tr>}
            {!isLoading && envios.length === 0 && (
              <tr><td colSpan={7} style={empty}>No hay envíos para el filtro seleccionado.</td></tr>
            )}
            {envios.map((e) => {
              const c = ESTADO_COLOR[e.estado] ?? ESTADO_COLOR.pendiente
              return (
                <tr key={e.id_encuesta_envio} style={{ cursor: 'pointer' }} onClick={() => setDetalleId(e.id_encuesta_envio)}>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>#{e.id_encuesta_envio}</td>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)', color: 'var(--fg-2)' }}>{e.id_reclamo}</td>
                  <td style={{ ...td, color: 'var(--fg-2)' }}>{e.email_destino_snapshot}</td>
                  <td style={td}>
                    <span style={{ background: c.bg, color: c.fg, fontSize: '0.72rem', fontWeight: 600, padding: '2px 9px', borderRadius: 999 }}>
                      {e.estado}
                    </span>
                  </td>
                  <td style={{ ...td, color: 'var(--fg-3)' }}>{fmt(e.fecha_envio)}</td>
                  <td style={{ ...td, color: 'var(--fg-3)' }}>{fmt(e.fecha_completada)}</td>
                  <td style={{ ...td, color: 'var(--fg-3)' }}>{fmt(e.fecha_expiracion)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {detalleId != null && <DetalleEnvio id={detalleId} onClose={() => setDetalleId(null)} />}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function DetalleEnvio({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, isLoading } = useEnvioDetalle(id)
  return (
    <div style={overlay} onClick={onClose}>
      <div style={drawer} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.05rem', color: 'var(--fg-1)' }}>
            Envío #{id}
          </h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-3)' }} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>

        {isLoading ? <p style={{ color: 'var(--fg-3)' }}>Cargando…</p> : data ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.86rem' }}>
            <Row k="Estado" v={data.estado} />
            <Row k="Reclamo" v={`#${data.id_reclamo}`} />
            <Row k="Email destino" v={data.email_destino_snapshot} />
            <Row k="Enviada" v={fmt(data.fecha_envio)} />
            <Row k="Abierta" v={fmt(data.fecha_apertura)} />
            <Row k="Completada" v={fmt(data.fecha_completada)} />
            <Row k="Vence" v={fmt(data.fecha_expiracion)} />
            {data.intentos_envio > 0 && <Row k="Intentos de envío" v={String(data.intentos_envio)} />}
            {data.ultimo_error_envio && <Row k="Último error" v={data.ultimo_error_envio} />}

            {data.respuesta ? (
              <div style={{ marginTop: 8, paddingTop: 12, borderTop: '1px solid var(--border-primary)' }}>
                <h4 style={{ margin: '0 0 8px', fontSize: '0.84rem', color: 'var(--fg-2)' }}>Respuesta del vecino</h4>
                <Row k="Puntaje inicial" v={
                  <span style={{ fontWeight: 700, color: colorCsat(data.respuesta.clasificacion_inicial) }}>
                    {data.respuesta.clasificacion_inicial} / 5
                  </span>
                } />
                <Row k="Rama seguida" v={data.respuesta.rama_seguida} />
                <Row k="Pidió contacto" v={data.respuesta.solicita_contacto ? 'Sí' : 'No'} />
                {data.respuesta.tiempo_completado_seg != null &&
                  <Row k="Tiempo" v={`${data.respuesta.tiempo_completado_seg}s`} />}
                <Row k="Atendida" v={data.respuesta.atendida ? 'Sí' : 'No'} />
              </div>
            ) : (
              <p style={{ marginTop: 8, paddingTop: 12, borderTop: '1px solid var(--border-primary)', color: 'var(--fg-3)' }}>
                El vecino todavía no respondió esta encuesta.
              </p>
            )}
          </div>
        ) : <p style={{ color: 'var(--color-error)' }}>No se pudo cargar el detalle.</p>}
      </div>
    </div>
  )
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
      <span style={{ color: 'var(--fg-3)' }}>{k}</span>
      <span style={{ color: 'var(--fg-1)', textAlign: 'right', wordBreak: 'break-word' }}>{v}</span>
    </div>
  )
}

const toolbar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 14,
}
const field: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
const lbl: React.CSSProperties = { fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)' }
const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, padding: '6px 10px',
  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)', background: 'var(--surface-100)', outline: 'none',
}
const btnGhost: React.CSSProperties = {
  fontFamily: 'var(--font-display)', cursor: 'pointer', borderRadius: 8, padding: '6px 9px',
  background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
  display: 'inline-flex', alignItems: 'center',
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, overflowX: 'auto',
}
const table: React.CSSProperties = { width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.84rem', minWidth: 760 }
const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em',
  color: 'var(--fg-3)', padding: '9px 12px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-300)', whiteSpace: 'nowrap',
}
const td: React.CSSProperties = { padding: '10px 12px', borderBottom: '1px solid var(--border-primary)', color: 'var(--fg-1)' }
const empty: React.CSSProperties = { padding: 36, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem' }
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 1000,
  display: 'flex', justifyContent: 'flex-end',
}
const drawer: React.CSSProperties = {
  width: 420, maxWidth: '90vw', height: '100%', background: 'var(--surface-100)',
  boxShadow: '-4px 0 24px rgba(0,0,0,0.15)', padding: 20, overflowY: 'auto',
}
