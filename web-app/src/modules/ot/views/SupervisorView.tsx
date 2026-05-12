import { useEffect, useMemo, useState } from 'react'
import { useMesaSupervisor } from '../hooks/useOT'
import type { MesaSupervisorRow } from '../types/ot'
import { BadgeEstadoReclamo, BadgePrioridad, SLACell, nombreCiudadano } from '../lib/format'
import { Field, StatsChips, Toolbar, inputStyle } from '../components/Toolbar'
import { AsignarModal } from '../components/AsignarModal'
import { ReasignarModal } from '../components/ReasignarModal'

type Tab = 'asignar' | 'reasignar'

export function SupervisorView() {
  const { data, isLoading, isError, error, refetch, isFetching } = useMesaSupervisor()
  const reclamos = data ?? []

  const [tab, setTab] = useState<Tab>('asignar')
  const [fTexto, setFTexto] = useState('')
  const [fEstado, setFEstado] = useState('')
  const [fPrioridad, setFPrioridad] = useState('')
  const [seleccionados, setSeleccionados] = useState<Set<number>>(new Set())

  const [modalAsignarReclamos, setModalAsignarReclamos] = useState<MesaSupervisorRow[]>([])
  const [modalReasignReclamo, setModalReasignReclamo] = useState<MesaSupervisorRow | null>(null)

  // Counts globales (no filtrados, por tab) — para badges en pestañas
  const nAsignar = useMemo(
    () => reclamos.filter((r) => r.estado === 'Sin asignar').length,
    [reclamos],
  )
  const nReasignar = useMemo(
    () => reclamos.filter((r) => (r.cant_ots ?? 0) > 0 && r.ot_activa_id !== null).length,
    [reclamos],
  )

  // Filtro principal por tab
  const porTab = useMemo(() => {
    if (tab === 'asignar') return reclamos.filter((r) => r.estado === 'Sin asignar')
    return reclamos.filter((r) => (r.cant_ots ?? 0) > 0 && r.ot_activa_id !== null)
  }, [tab, reclamos])

  // Filtrado por toolbar
  const filtrados = useMemo(() => {
    const txt = fTexto.trim().toLowerCase()
    return porTab.filter((r) => {
      if (tab === 'reasignar' && fEstado && r.estado !== fEstado) return false
      if (fPrioridad && r.prioridad !== fPrioridad) return false
      if (txt) {
        const hay = [
          r.nro_reclamo ?? '', r.tipo_nombre ?? '', r.descripcion ?? '',
          r.subarea_nombre ?? '',
          `${r.ciudadano_apellido ?? ''} ${r.ciudadano_nombre ?? ''}`,
          r.ot_agente_nombre ?? '', r.ot_equipo_nombre ?? '', r.ot_activa_nro ?? '',
        ].join(' ').toLowerCase()
        if (!hay.includes(txt)) return false
      }
      return true
    })
  }, [porTab, fTexto, fEstado, fPrioridad, tab])

  // Stats por estado dentro del tab actual
  const stats = useMemo(() => {
    const counts: Record<string, number> = {}
    porTab.forEach((r) => { counts[r.estado] = (counts[r.estado] ?? 0) + 1 })
    return counts
  }, [porTab])

  // Limpiar selección al cambiar tab o al cambiar dataset
  useEffect(() => {
    if (tab === 'reasignar') setSeleccionados(new Set())
  }, [tab])

  useEffect(() => {
    const vivos = new Set(reclamos.map((r) => r.id_reclamo))
    setSeleccionados((prev) => {
      const next = new Set<number>()
      prev.forEach((id) => { if (vivos.has(id)) next.add(id) })
      return next
    })
  }, [reclamos])

  function toggleSel(id: number, on: boolean) {
    setSeleccionados((prev) => {
      const next = new Set(prev)
      if (on) next.add(id); else next.delete(id)
      return next
    })
  }

  function toggleSelAll(on: boolean) {
    if (on) {
      setSeleccionados(new Set([...seleccionados, ...filtrados.map((r) => r.id_reclamo)]))
    } else {
      const visibles = new Set(filtrados.map((r) => r.id_reclamo))
      setSeleccionados((prev) => {
        const next = new Set<number>()
        prev.forEach((id) => { if (!visibles.has(id)) next.add(id) })
        return next
      })
    }
  }

  const allVisiblesSelected =
    filtrados.length > 0 && filtrados.every((r) => seleccionados.has(r.id_reclamo))

  function abrirAsignarUno(r: MesaSupervisorRow) {
    setModalAsignarReclamos([r])
  }

  function abrirAsignarLote() {
    const rows = filtrados.filter((r) => seleccionados.has(r.id_reclamo))
    if (rows.length) setModalAsignarReclamos(rows)
  }

  function abrirReasignar(r: MesaSupervisorRow) {
    if (!r.ot_activa_id) return
    setModalReasignReclamo(r)
  }

  return (
    <div>
      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)', marginBottom: 14 }}>
        <TabButton active={tab === 'asignar'} onClick={() => setTab('asignar')}>
          Asignar <Count active={tab === 'asignar'}>{nAsignar}</Count>
        </TabButton>
        <TabButton active={tab === 'reasignar'} onClick={() => setTab('reasignar')}>
          Reasignar <Count active={tab === 'reasignar'}>{nReasignar}</Count>
        </TabButton>
      </div>

      <Toolbar onRefresh={() => refetch()} refreshing={isFetching}>
        <Field label="Nº reclamo o tipo" wide>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Ej: REC-2026-000001 o bache"
            autoComplete="off"
            style={inputStyle}
          />
        </Field>
        {tab === 'reasignar' && (
          <Field label="Estado">
            <select value={fEstado} onChange={(e) => setFEstado(e.target.value)} style={inputStyle}>
              <option value="">Todos</option>
              <option value="En gestión">En gestión</option>
              <option value="En espera">En espera</option>
              <option value="En auditoría">En auditoría</option>
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

      <StatsChips counts={stats} empty="Sin reclamos en esta vista" />

      {tab === 'asignar' && seleccionados.size > 0 && (
        <div style={selbarStyle}>
          <div style={{ fontSize: '0.84rem' }}>
            <strong style={{ color: 'var(--zaris-orange)' }}>{seleccionados.size}</strong> reclamos seleccionados
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setSeleccionados(new Set())} style={selbarBtnGhost}>Limpiar</button>
            <button onClick={abrirAsignarLote} style={selbarBtnPrimary}>Asignar OT en lote</button>
          </div>
        </div>
      )}

      <div style={cardStyle}>
        <table style={tableStyle}>
          <thead>
            {tab === 'asignar' ? (
              <tr>
                <th style={{ ...thStyle, width: 32, paddingTop: 9, paddingBottom: 9, paddingLeft: 12, paddingRight: 0 }}>
                  <input
                    type="checkbox"
                    checked={allVisiblesSelected}
                    onChange={(e) => toggleSelAll(e.target.checked)}
                    style={checkboxStyle}
                  />
                </th>
                <th style={thStyle}>N° reclamo</th>
                <th style={thStyle}>Prio.</th>
                <th style={{ ...thStyle, minWidth: 150 }}>SLA</th>
                <th style={thStyle}>Tipo</th>
                <th style={thStyle}>Subárea</th>
                <th style={thStyle}>Ciudadano</th>
                <th style={thStyle}>Descripción</th>
                <th style={{ ...thStyle, ...stickyTh }}>Acción</th>
              </tr>
            ) : (
              <tr>
                <th style={thStyle}>N° reclamo</th>
                <th style={thStyle}>Estado</th>
                <th style={thStyle}>Prio.</th>
                <th style={{ ...thStyle, minWidth: 150 }}>SLA</th>
                <th style={thStyle}>Tipo</th>
                <th style={thStyle}>Subárea</th>
                <th style={thStyle}>Ciudadano</th>
                <th style={thStyle}>Asignado a</th>
                <th style={{ ...thStyle, ...stickyTh }}>Acción</th>
              </tr>
            )}
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={tab === 'asignar' ? 9 : 9} style={emptyStyle}>Cargando…</td></tr>
            )}
            {isError && (
              <tr><td colSpan={9} style={emptyStyle}>Error: {(error as Error)?.message ?? 'desconocido'}</td></tr>
            )}
            {!isLoading && !isError && filtrados.length === 0 && (
              <tr><td colSpan={9} style={emptyStyle}>Sin reclamos en esta vista</td></tr>
            )}
            {filtrados.map((r) => {
              const isSel = seleccionados.has(r.id_reclamo)
              if (tab === 'asignar') {
                return (
                  <tr key={r.id_reclamo} style={isSel ? { background: '#fff1ea' } : undefined}>
                    <td style={{ ...tdStyle, width: 32, paddingTop: 10, paddingBottom: 10, paddingLeft: 12, paddingRight: 0 }}>
                      <input
                        type="checkbox"
                        checked={isSel}
                        onChange={(e) => toggleSel(r.id_reclamo, e.target.checked)}
                        style={checkboxStyle}
                      />
                    </td>
                    <td style={{ ...tdStyle, ...monoStyle }}>{r.nro_reclamo ?? '—'}</td>
                    <td style={tdStyle}><BadgePrioridad prioridad={r.prioridad} /></td>
                    <td style={tdStyle}>
                      <SLACell sla_vencimiento={r.sla_vencimiento} sla_dias={r.sla_dias} />
                    </td>
                    <td style={tdStyle}><Clamp2 title={r.tipo_nombre}>{r.tipo_nombre ?? '—'}</Clamp2></td>
                    <td style={tdStyle}><Clamp2 title={r.subarea_nombre}>{r.subarea_nombre ?? '—'}</Clamp2></td>
                    <td style={tdStyle}>{nombreCiudadano(r.ciudadano_apellido, r.ciudadano_nombre)}</td>
                    <td style={tdStyle}><Clamp2 wide title={r.descripcion}>{r.descripcion ?? ''}</Clamp2></td>
                    <td style={{ ...tdStyle, ...stickyTd }}>
                      <button onClick={() => abrirAsignarUno(r)} style={btnPrimarySm}>Asignar OT</button>
                    </td>
                  </tr>
                )
              }
              return (
                <tr key={r.id_reclamo}>
                  <td style={{ ...tdStyle, ...monoStyle }}>{r.nro_reclamo ?? '—'}</td>
                  <td style={tdStyle}><BadgeEstadoReclamo estado={r.estado} /></td>
                  <td style={tdStyle}><BadgePrioridad prioridad={r.prioridad} /></td>
                  <td style={tdStyle}>
                    <SLACell sla_vencimiento={r.sla_vencimiento} sla_dias={r.sla_dias} />
                  </td>
                  <td style={tdStyle}><Clamp2 title={r.tipo_nombre}>{r.tipo_nombre ?? '—'}</Clamp2></td>
                  <td style={tdStyle}><Clamp2 title={r.subarea_nombre}>{r.subarea_nombre ?? '—'}</Clamp2></td>
                  <td style={tdStyle}>{nombreCiudadano(r.ciudadano_apellido, r.ciudadano_nombre)}</td>
                  <td style={tdStyle}><AsignadoCell row={r} /></td>
                  <td style={{ ...tdStyle, ...stickyTd }}>
                    <button onClick={() => abrirReasignar(r)} style={btnWarnSm}>Reasignar</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <AsignarModal
        open={modalAsignarReclamos.length > 0}
        reclamos={modalAsignarReclamos}
        onClose={() => setModalAsignarReclamos([])}
        onSuccess={() => setSeleccionados(new Set())}
      />
      <ReasignarModal
        open={modalReasignReclamo !== null}
        reclamo={modalReasignReclamo}
        onClose={() => setModalReasignReclamo(null)}
      />
    </div>
  )
}

// ── Sub componentes locales ──

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
        transition: '0.15s',
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

function AsignadoCell({ row }: { row: MesaSupervisorRow }) {
  if (row.ot_agente_nombre) {
    return (
      <div style={asignCellStyle}>
        <span style={asignCellNro}>{row.ot_activa_nro ?? ''}</span>
        <span style={{ fontSize: '0.82rem' }}>{row.ot_agente_nombre}</span>
        <span style={asignCellKind}>Agente</span>
      </div>
    )
  }
  if (row.ot_equipo_nombre) {
    return (
      <div style={asignCellStyle}>
        <span style={asignCellNro}>{row.ot_activa_nro ?? ''}</span>
        <span style={{ fontSize: '0.82rem' }}>{row.ot_equipo_nombre}</span>
        <span style={asignCellKind}>Equipo</span>
      </div>
    )
  }
  return <span style={{ color: 'var(--fg-3)', fontSize: '0.78rem' }}>—</span>
}

const asignCellStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 1 }
const asignCellNro: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: '0.74rem', color: 'var(--fg-3)' }
const asignCellKind: React.CSSProperties = {
  fontSize: '0.68rem', color: 'var(--fg-3)',
  textTransform: 'uppercase', letterSpacing: '0.04em',
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
  minWidth: 120, position: 'sticky', right: 0,
  boxShadow: '-6px 0 8px -6px rgba(0,0,0,0.12)', zIndex: 1,
}

const stickyTd: React.CSSProperties = {
  minWidth: 120, whiteSpace: 'nowrap',
  position: 'sticky', right: 0,
  boxShadow: '-6px 0 8px -6px rgba(0,0,0,0.12)', zIndex: 1,
}

const monoStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '0.78rem',
  color: 'var(--fg-2)', whiteSpace: 'nowrap',
}

const checkboxStyle: React.CSSProperties = {
  width: 16, height: 16, cursor: 'pointer', accentColor: 'var(--zaris-orange)',
}

const emptyStyle: React.CSSProperties = {
  padding: 36, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem',
}

const selbarStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  background: 'var(--fg-1)', color: 'var(--surface-100)',
  borderRadius: 10, padding: '9px 16px', marginBottom: 10,
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

const btnWarnSm: React.CSSProperties = {
  ...btnBase, background: '#ef6c00', color: 'white', borderColor: '#ef6c00',
}

const selbarBtnPrimary: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: 'white', borderColor: 'var(--zaris-orange)',
}

const selbarBtnGhost: React.CSSProperties = {
  ...btnBase, background: 'transparent', color: 'var(--surface-100)',
  border: '1px solid var(--surface-100)',
}
