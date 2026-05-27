import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, Search, Inbox, ArrowRightLeft, Hand } from 'lucide-react'
import { Input, Skeleton, EmptyState } from '../../../ui'
import { useMiBandeja } from '../hooks/useTramites'
import { tomarTramite, pasarTramite } from '../lib/api'
import { useNotificationsStore } from '../../../stores/notifications'
import { EstadoBadge } from '../components/EstadoBadge'
import { ModalPase } from '../components/ModalPase'
import type { TramiteBandejaItem } from '../types'

const LIMIT = 50

/**
 * Mi bandeja: los tramites que me corresponden (mi subarea, mis mesas/equipos,
 * o asignados a mi directamente, o ya tomados por mi). Desde aca puedo tomar y
 * hacer pases (a agente, mesa o subarea) sin entrar al detalle.
 */
export function MiBandeja() {
  const navigate = useNavigate()
  const notify = useNotificationsStore((s) => s.push)

  const [q, setQ] = useState('')
  const [qDebounced, setQDebounced] = useState('')
  const [soloSinTomar, setSoloSinTomar] = useState(false)
  const [pasando, setPasando] = useState<TramiteBandejaItem | null>(null)
  const [accionId, setAccionId] = useState<number | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setQDebounced(q.trim()), 350)
    return () => clearTimeout(t)
  }, [q])

  const { data, isLoading, error, refetch } = useMiBandeja({
    limit: LIMIT,
    ...(qDebounced ? { q: qDebounced } : {}),
    ...(soloSinTomar ? { sin_tomar: true } : {}),
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  async function handleTomar(item: TramiteBandejaItem) {
    setAccionId(item.id_tramite)
    try {
      await tomarTramite(item.numero_expediente)
      notify({ kind: 'success', title: `Tomaste ${item.numero_expediente}` })
      await refetch()
    } catch (e) {
      notify({ kind: 'error', title: 'No se pudo tomar', body: (e as Error).message })
    } finally {
      setAccionId(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Inbox size={20} strokeWidth={1.5} color="var(--zaris-orange)" />
        <h1 style={h1Style}>Mi bandeja</h1>
      </div>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
        Trámites asignados a vos, a tus mesas o a tu subárea. Tomalos y hacé pases desde acá.
      </p>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ flex: '1 1 240px', minWidth: 180 }}>
          <Input
            icon={<Search size={14} />}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por asunto o número..."
          />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-2)', cursor: 'pointer' }}>
          <input type="checkbox" checked={soloSinTomar} onChange={(e) => setSoloSinTomar(e.target.checked)} />
          Solo sin tomar
        </label>
        <button type="button" onClick={() => { void refetch() }} title="Actualizar" style={iconBtnStyle}>
          <RefreshCw size={15} strokeWidth={1.5} />
        </button>
      </div>

      {error ? (
        <div style={{ color: 'var(--color-error)', fontFamily: 'var(--font-display)', fontSize: 13 }}>
          Error al cargar: {(error as Error).message}
        </div>
      ) : isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height={40} />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="Tu bandeja está vacía"
          description="No tenés trámites asignados a vos, a tus mesas ni a tu subárea con los filtros actuales."
        />
      ) : (
        <>
          <p style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', margin: 0 }}>
            {total} trámite{total !== 1 ? 's' : ''} en tu bandeja
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {['N° Expediente', 'Tipo', 'Estado', 'Ubicación actual', 'Tomado por', 'Días', 'Acciones'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const cargando = accionId === item.id_tramite
                  return (
                    <tr key={item.id_tramite} style={trStyle}>
                      <td
                        style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--zaris-orange)', fontWeight: 600, cursor: 'pointer' }}
                        onClick={() => navigate(`/tramites/${item.numero_expediente}`)}
                      >
                        {item.numero_expediente}
                      </td>
                      <td style={tdStyle}>
                        <span style={tipoPill}>{item.tipo_nombre}</span>
                      </td>
                      <td style={tdStyle}><EstadoBadge etiqueta={item.estado_etiqueta} color={item.estado_color} /></td>
                      <td style={{ ...tdStyle, fontSize: 12, color: 'var(--fg-2)', fontFamily: 'var(--font-display)' }}>
                        {item.destinatario_actual_tipo === 'agente'
                          ? <span title="Asignado directo a un agente">👤 {item.destinatario_actual_nombre}</span>
                          : item.destinatario_actual_tipo === 'equipo'
                            ? <span title="Mesa (equipo)">{item.destinatario_actual_nombre} · mesa</span>
                            : (item.destinatario_actual_nombre ?? '—')}
                      </td>
                      <td style={{ ...tdStyle, fontSize: 12, color: item.tomado_por_nombre ? 'var(--fg-2)' : 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
                        {item.tomado_por_nombre ?? 'Sin tomar'}
                      </td>
                      <td style={{ ...tdStyle, fontSize: 13, fontWeight: item.dias_en_estado_actual > 7 ? 600 : 400, color: item.dias_en_estado_actual > 7 ? 'var(--color-error)' : 'var(--fg-2)', fontFamily: 'var(--font-display)' }}>
                        {item.dias_en_estado_actual}d
                      </td>
                      <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {!item.tomado_por_nombre && (
                            <button
                              type="button"
                              onClick={() => { void handleTomar(item) }}
                              disabled={cargando}
                              style={accionBtn}
                              title="Tomar trámite"
                            >
                              <Hand size={13} strokeWidth={1.5} /> {cargando ? '...' : 'Tomar'}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setPasando(item)}
                            style={accionBtn}
                            title="Pasar a otro destinatario"
                          >
                            <ArrowRightLeft size={13} strokeWidth={1.5} /> Pasar
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {pasando && (
        <ModalPase
          numeroExpediente={pasando.numero_expediente}
          onCerrar={() => setPasando(null)}
          onConfirmar={async (body) => {
            try {
              await pasarTramite(pasando.numero_expediente, body)
              notify({ kind: 'success', title: `${pasando.numero_expediente} pasado correctamente` })
              setPasando(null)
              await refetch()
            } catch (e) {
              notify({ kind: 'error', title: 'No se pudo pasar', body: (e as Error).message })
            }
          }}
        />
      )}
    </div>
  )
}

const h1Style: React.CSSProperties = {
  fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px', color: 'var(--fg-1)', margin: 0,
}
const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse', fontSize: 'var(--size-btn)', fontFamily: 'var(--font-display)',
}
const thStyle: React.CSSProperties = {
  padding: '8px 12px', textAlign: 'left', fontWeight: 500, color: 'var(--fg-3)',
  borderBottom: '1px solid var(--border-primary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em',
}
const tdStyle: React.CSSProperties = { padding: '10px 12px', color: 'var(--fg-1)', fontSize: 13 }
const trStyle: React.CSSProperties = { borderBottom: '1px solid var(--border-primary)' }
const tipoPill: React.CSSProperties = {
  fontSize: 12, padding: '2px 8px', borderRadius: 'var(--radius-pill)', background: 'var(--surface-400)',
  fontFamily: 'var(--font-display)', color: 'var(--fg-2)',
}
const iconBtnStyle: React.CSSProperties = {
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  padding: '9px 10px', color: 'var(--fg-3)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center',
}
const accionBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px',
  borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', color: 'var(--fg-1)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 12,
}
