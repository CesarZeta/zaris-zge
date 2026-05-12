import { useMemo, useState } from 'react'
import { useMesaAgente, useTomarOT } from '../hooks/useOT'
import { useNotificationsStore } from '../../../stores/notifications'
import type { EstadoOT, MesaAgenteRow } from '../types/ot'
import { BadgeEstadoOT, BadgePrioridad, SLACell, nombreCiudadano } from '../lib/format'
import { Field, StatsChips, Toolbar, inputStyle } from '../components/Toolbar'
import { CambiarEstadoOTModal } from '../components/CambiarEstadoOTModal'

type Tab = 'mias' | 'disponibles'

export function AgenteView() {
  const { data, isLoading, isError, error, refetch, isFetching } = useMesaAgente()
  const push = useNotificationsStore((s) => s.push)
  const mutTomar = useTomarOT()

  const idAgente = data?.id_agente ?? null
  const ots = data?.ots ?? []

  const [tab, setTab] = useState<Tab>('mias')
  const [fTexto, setFTexto] = useState('')
  const [fEstado, setFEstado] = useState<EstadoOT | ''>('')
  const [fPrioridad, setFPrioridad] = useState('')
  const [modalOT, setModalOT] = useState<MesaAgenteRow | null>(null)

  const counts = useMemo(() => ({
    mias: ots.filter((o) => o.scope === 'mia').length,
    disponibles: ots.filter((o) => o.scope === 'disponible_equipo').length,
  }), [ots])

  const porTab = useMemo(() => {
    if (tab === 'mias') return ots.filter((o) => o.scope === 'mia')
    return ots.filter((o) => o.scope === 'disponible_equipo')
  }, [tab, ots])

  const filtrados = useMemo(() => {
    const txt = fTexto.trim().toLowerCase()
    return porTab.filter((o) => {
      if (tab === 'mias' && fEstado && o.estado_nombre !== fEstado) return false
      if (fPrioridad && o.reclamo_prioridad !== fPrioridad) return false
      if (txt) {
        const hay = [
          o.nro_ot ?? '', o.nro_reclamo ?? '', o.tipo_nombre ?? '',
          o.reclamo_descripcion ?? '', o.subarea_nombre ?? '',
          o.equipo_nombre ?? '',
          `${o.ciudadano_apellido ?? ''} ${o.ciudadano_nombre ?? ''}`,
        ].join(' ').toLowerCase()
        if (!hay.includes(txt)) return false
      }
      return true
    })
  }, [porTab, tab, fTexto, fEstado, fPrioridad])

  const statsCounts = useMemo(() => {
    const c: Record<string, number> = {}
    porTab.forEach((o) => { c[o.estado_nombre] = (c[o.estado_nombre] ?? 0) + 1 })
    return c
  }, [porTab])

  async function tomarOT(o: MesaAgenteRow) {
    if (!idAgente) {
      push({ kind: 'error', title: 'No tenés un agente asociado a tu usuario' })
      return
    }
    try {
      await mutTomar.mutateAsync({ id_ot: o.id_ot, id_agente: idAgente })
      push({ kind: 'success', title: 'OT tomada: pasa a "Mis OTs"' })
    } catch (err) {
      push({ kind: 'error', title: 'Error al tomar OT', body: (err as Error).message })
    }
  }

  const subtitle = isLoading
    ? 'Cargando tus órdenes asignadas...'
    : isError
      ? 'No pudimos cargar tus OTs.'
      : idAgente
        ? `Trabajando como agente #${idAgente}. Tomá OTs disponibles o gestioná las tuyas.`
        : 'Tu usuario no tiene un agente asociado.'

  return (
    <div>
      <p style={{ fontSize: '0.86rem', color: 'var(--fg-3)', margin: '0 0 14px' }}>{subtitle}</p>

      {isError && (
        <div style={errorBanner}>
          {(error as Error)?.message ?? 'Error HTTP'}
        </div>
      )}

      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)', marginBottom: 14 }}>
        <TabButton active={tab === 'mias'} onClick={() => setTab('mias')}>
          Mis OTs <Count active={tab === 'mias'}>{counts.mias}</Count>
        </TabButton>
        <TabButton active={tab === 'disponibles'} onClick={() => setTab('disponibles')}>
          Disponibles para tomar <Count active={tab === 'disponibles'}>{counts.disponibles}</Count>
        </TabButton>
      </div>

      <Toolbar onRefresh={() => refetch()} refreshing={isFetching}>
        <Field label="Nº OT, reclamo o tipo" wide>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Ej: REC-2026-000001 o bache"
            autoComplete="off"
            style={inputStyle}
          />
        </Field>
        {tab === 'mias' && (
          <Field label="Estado OT">
            <select
              value={fEstado}
              onChange={(e) => setFEstado(e.target.value as EstadoOT | '')}
              style={inputStyle}
            >
              <option value="">Todos</option>
              <option value="En gestión">En gestión</option>
              <option value="En espera">En espera</option>
              <option value="Pendiente">Pendiente</option>
            </select>
          </Field>
        )}
        <Field label="Prioridad">
          <select value={fPrioridad} onChange={(e) => setFPrioridad(e.target.value)} style={inputStyle}>
            <option value="">Todas</option>
            <option value="Alta">Alta</option>
            <option value="Media">Media</option>
            <option value="Baja">Baja</option>
          </select>
        </Field>
      </Toolbar>

      <StatsChips counts={statsCounts} empty="Sin OTs en esta vista" />

      <div style={cardStyle}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>OT / Reclamo</th>
              <th style={thStyle}>{tab === 'mias' ? 'Estado' : 'Equipo'}</th>
              <th style={thStyle}>Prio.</th>
              <th style={{ ...thStyle, minWidth: 150 }}>SLA</th>
              <th style={thStyle}>Tipo</th>
              <th style={thStyle}>Subárea</th>
              <th style={thStyle}>Ciudadano</th>
              <th style={thStyle}>Descripción</th>
              <th style={{ ...thStyle, ...stickyTh }}>Acción</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={9} style={emptyStyle}>Cargando…</td></tr>
            )}
            {!isLoading && !isError && filtrados.length === 0 && (
              <tr><td colSpan={9} style={emptyStyle}>
                {tab === 'mias'
                  ? 'No tenés OTs asignadas. Mirá la pestaña "Disponibles" para tomar alguna.'
                  : 'No hay OTs disponibles en tus equipos por ahora.'}
              </td></tr>
            )}
            {filtrados.map((o) => (
              <tr key={o.id_ot}>
                <td style={tdStyle}>
                  <div style={monoStyle}>{o.nro_ot ?? '—'}</div>
                  <div style={{ ...monoStyle, fontSize: '0.72rem', color: 'var(--fg-3)' }}>{o.nro_reclamo ?? ''}</div>
                </td>
                {tab === 'mias' ? (
                  <td style={tdStyle}><BadgeEstadoOT estado={o.estado_nombre} /></td>
                ) : (
                  <td style={tdStyle}>
                    {o.equipo_nombre ?? '—'}
                    <div style={{ fontSize: '0.7rem', color: 'var(--fg-3)', marginTop: 2 }}>Sin agente asignado</div>
                  </td>
                )}
                <td style={tdStyle}><BadgePrioridad prioridad={o.reclamo_prioridad} /></td>
                <td style={tdStyle}>
                  <SLACell sla_vencimiento={o.sla_vencimiento} sla_dias={o.sla_dias} />
                </td>
                <td style={tdStyle}><Clamp2 title={o.tipo_nombre}>{o.tipo_nombre ?? '—'}</Clamp2></td>
                <td style={tdStyle}><Clamp2 title={o.subarea_nombre}>{o.subarea_nombre ?? '—'}</Clamp2></td>
                <td style={tdStyle}>{nombreCiudadano(o.ciudadano_apellido, o.ciudadano_nombre)}</td>
                <td style={tdStyle}><Clamp2 wide title={o.reclamo_descripcion}>{o.reclamo_descripcion ?? ''}</Clamp2></td>
                <td style={{ ...tdStyle, ...stickyTd }}>
                  {tab === 'mias' ? (
                    <button onClick={() => setModalOT(o)} style={btnPrimarySm}>Cambiar estado</button>
                  ) : (
                    <button onClick={() => tomarOT(o)} disabled={mutTomar.isPending} style={btnSuccessSm}>
                      Tomar OT
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <CambiarEstadoOTModal
        open={modalOT !== null}
        ot={modalOT}
        onClose={() => setModalOT(null)}
      />
    </div>
  )
}

// ── Locales ──

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'transparent', border: 'none', cursor: 'pointer',
        fontFamily: 'var(--font-display)', fontSize: '0.92rem', fontWeight: active ? 600 : 500,
        padding: '10px 18px',
        color: active ? 'var(--zaris-orange)' : 'var(--fg-3)',
        borderBottom: `2px solid ${active ? 'var(--zaris-orange)' : 'transparent'}`,
        marginBottom: -1,
      }}
    >
      {children}
    </button>
  )
}

function Count({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <span style={{
      background: active ? 'var(--zaris-orange)' : 'var(--surface-300)',
      color: active ? 'white' : 'var(--fg-2)',
      padding: '1px 8px', borderRadius: 999,
      fontSize: '0.72rem', fontWeight: 600, marginLeft: 6,
    }}>{children}</span>
  )
}

function Clamp2({ children, title, wide }: { children: React.ReactNode; title?: string | null; wide?: boolean }) {
  return (
    <div
      title={title ?? undefined}
      style={{
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
        maxWidth: wide ? 280 : 220,
        lineHeight: 1.25,
      }}
    >
      {children}
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, overflowX: 'auto', overflowY: 'hidden',
}

const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'separate', borderSpacing: 0,
  fontSize: '0.84rem', minWidth: 980,
}

const thStyle: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem',
  textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
  padding: '9px 12px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-300)', whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '10px 12px', borderBottom: '1px solid var(--border-primary)',
  verticalAlign: 'middle', background: 'var(--surface-100)',
}

const stickyTh: React.CSSProperties = {
  minWidth: 150, position: 'sticky', right: 0,
  boxShadow: '-6px 0 8px -6px rgba(0,0,0,0.12)', zIndex: 1,
}

const stickyTd: React.CSSProperties = {
  minWidth: 150, whiteSpace: 'nowrap',
  position: 'sticky', right: 0,
  boxShadow: '-6px 0 8px -6px rgba(0,0,0,0.12)', zIndex: 1,
}

const monoStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '0.78rem',
  color: 'var(--fg-2)', whiteSpace: 'nowrap',
}

const emptyStyle: React.CSSProperties = {
  padding: 36, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem',
}

const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2',
  borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '14px 18px', marginBottom: 16,
  color: '#c62828', fontSize: '0.88rem',
}

const btnBase: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.78rem',
  cursor: 'pointer', borderRadius: 8, padding: '5px 10px',
  border: '1px solid transparent', fontWeight: 500,
}

const btnPrimarySm: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: 'white',
  borderColor: 'var(--zaris-orange)',
}

const btnSuccessSm: React.CSSProperties = {
  ...btnBase, background: '#2e7d32', color: 'white', borderColor: '#2e7d32',
}
