import { useMemo, useState } from 'react'
import { useMesaAuditoria } from '../hooks/useOT'
import type { MesaAuditoriaRow } from '../types/ot'
import { BadgePrioridad, SLACell, nombreAgente, nombreCiudadano } from '../lib/format'
import { Field, Toolbar, inputStyle } from '../components/Toolbar'
import { AuditarModal } from '../components/AuditarModal'
import { OTDetalleDrawer } from '../components/OTDetalleDrawer'

type Kind = 'aprobar' | 'rechazar'

export function AuditoriaView() {
  const { data, isLoading, isError, error, refetch, isFetching } = useMesaAuditoria()
  const idAgente = data?.id_agente ?? null
  const ots = data?.ots ?? []

  const [fTexto, setFTexto] = useState('')
  const [fPrioridad, setFPrioridad] = useState('')
  const [modal, setModal] = useState<{ kind: Kind; ot: MesaAuditoriaRow } | null>(null)
  const [drawerOT, setDrawerOT] = useState<MesaAuditoriaRow | null>(null)

  const filtrados = useMemo(() => {
    const txt = fTexto.trim().toLowerCase()
    return ots.filter((o) => {
      if (fPrioridad && o.reclamo_prioridad !== fPrioridad) return false
      if (txt) {
        const hay = [
          o.nro_ot ?? '', o.nro_reclamo ?? '', o.tipo_nombre ?? '',
          o.reclamo_descripcion ?? '', o.subarea_nombre ?? '',
          o.ot_origen_nro ?? '',
          `${o.ot_origen_agente_apellido ?? ''} ${o.ot_origen_agente_nombre ?? ''}`,
          `${o.ciudadano_apellido ?? ''} ${o.ciudadano_nombre ?? ''}`,
        ].join(' ').toLowerCase()
        if (!hay.includes(txt)) return false
      }
      return true
    })
  }, [ots, fTexto, fPrioridad])

  const subtitle = isLoading
    ? 'Cargando OTs pendientes de auditoría...'
    : isError
      ? 'Acceso denegado o sin agente auditor vinculado.'
      : idAgente
        ? `Auditando como agente #${idAgente}. Aprobá o rechazá las OTs operativas cerradas.`
        : 'Tu usuario no tiene un agente con permiso de auditoría.'

  return (
    <div>
      <p style={{ fontSize: '0.86rem', color: 'var(--fg-3)', margin: '0 0 14px' }}>{subtitle}</p>

      {isError && (
        <div style={errorBanner}>
          {(error as Error)?.message ?? 'Error HTTP'}
        </div>
      )}

      <Toolbar onRefresh={() => refetch()} refreshing={isFetching}>
        <Field label="Nº OT, reclamo o tipo" wide>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Ej: OT-2026-000001 o bache"
            autoComplete="off"
            style={inputStyle}
          />
        </Field>
        <Field label="Prioridad">
          <select value={fPrioridad} onChange={(e) => setFPrioridad(e.target.value)} style={inputStyle}>
            <option value="">Todas</option>
            <option value="Alta">Alta</option>
            <option value="Media">Media</option>
            <option value="Baja">Baja</option>
          </select>
        </Field>
      </Toolbar>

      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={chipStyle}><strong style={{ color: 'var(--fg-1)', marginRight: 4 }}>{ots.length}</strong> OTs en auditoría</span>
        {filtrados.length !== ots.length && (
          <span style={chipStyle}><strong style={{ color: 'var(--fg-1)', marginRight: 4 }}>{filtrados.length}</strong> visibles tras filtros</span>
        )}
      </div>

      <div style={cardStyle}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>OT auditoría</th>
              <th style={thStyle}>Prio.</th>
              <th style={{ ...thStyle, minWidth: 150 }}>SLA reclamo</th>
              <th style={thStyle}>Tipo</th>
              <th style={thStyle}>Subárea</th>
              <th style={thStyle}>Ciudadano</th>
              <th style={thStyle}>OT operativa origen</th>
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
                No hay OTs pendientes de auditoría{ots.length ? ' que coincidan con los filtros' : ''}
              </td></tr>
            )}
            {filtrados.map((o) => (
              <tr key={o.id_ot}>
                <td style={tdStyle}>
                  <div style={monoStyle}>{o.nro_ot ?? '—'}</div>
                  <div style={{ ...monoStyle, fontSize: '0.7rem', color: 'var(--fg-3)' }}>{o.nro_reclamo ?? ''}</div>
                </td>
                <td style={tdStyle}><BadgePrioridad prioridad={o.reclamo_prioridad} /></td>
                <td style={tdStyle}>
                  <SLACell sla_vencimiento={o.sla_vencimiento} sla_dias={o.sla_dias} />
                </td>
                <td style={tdStyle}><Clamp2 title={o.tipo_nombre}>{o.tipo_nombre ?? '—'}</Clamp2></td>
                <td style={tdStyle}><Clamp2 title={o.subarea_nombre}>{o.subarea_nombre ?? '—'}</Clamp2></td>
                <td style={tdStyle}>{nombreCiudadano(o.ciudadano_apellido, o.ciudadano_nombre)}</td>
                <td style={tdStyle}>
                  <div style={{ ...monoStyle, fontSize: '0.72rem', color: 'var(--fg-3)' }}>{o.ot_origen_nro ?? '—'}</div>
                  <div style={{ fontSize: '0.8rem' }}>
                    Agente: {nombreAgente(o.ot_origen_agente_apellido, o.ot_origen_agente_nombre)}
                  </div>
                </td>
                <td style={tdStyle}><Clamp2 wide title={o.reclamo_descripcion}>{o.reclamo_descripcion ?? ''}</Clamp2></td>
                <td style={{ ...tdStyle, ...stickyTd }}>
                  <button onClick={() => setDrawerOT(o)} style={{ ...btnGhostSm, marginRight: 4 }}>Ver</button>
                  <button onClick={() => setModal({ kind: 'aprobar', ot: o })} style={{ ...btnSuccessSm, marginRight: 4 }}>
                    Aprobar
                  </button>
                  <button onClick={() => setModal({ kind: 'rechazar', ot: o })} style={btnDangerSm}>
                    Rechazar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AuditarModal
        open={modal !== null}
        kind={modal?.kind ?? null}
        ot={modal?.ot ?? null}
        onClose={() => setModal(null)}
      />
      <OTDetalleDrawer
        open={drawerOT !== null}
        idReclamo={drawerOT?.id_reclamo ?? null}
        idOTResaltada={drawerOT?.id_ot ?? null}
        onClose={() => setDrawerOT(null)}
      />
    </div>
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
        maxWidth: wide ? 260 : 200,
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
  minWidth: 200, position: 'sticky', right: 0,
  boxShadow: '-6px 0 8px -6px rgba(0,0,0,0.12)', zIndex: 1,
}

const stickyTd: React.CSSProperties = {
  minWidth: 200, whiteSpace: 'nowrap',
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

const chipStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 999, padding: '4px 11px',
  fontSize: '0.76rem', color: 'var(--fg-2)',
}

const btnBase: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.78rem',
  cursor: 'pointer', borderRadius: 8, padding: '5px 10px',
  border: '1px solid transparent', fontWeight: 500,
}

const btnSuccessSm: React.CSSProperties = {
  ...btnBase, background: '#2e7d32', color: 'white', borderColor: '#2e7d32',
}

const btnDangerSm: React.CSSProperties = {
  ...btnBase, background: 'var(--color-error)', color: 'white', borderColor: 'var(--color-error)',
}

const btnGhostSm: React.CSSProperties = {
  ...btnBase, background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-medium)',
}
