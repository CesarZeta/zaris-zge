import { useEffect, useMemo, useState } from 'react'
import { Search, X } from 'lucide-react'
import { useMesaSupervisor } from '../hooks/useOT'
import type { MesaSupervisorFiltros } from '../api/otApi'
import type { MesaSupervisorRow } from '../types/ot'
import { BadgeEstadoReclamo, BadgePrioridad, SLACell } from '../lib/format'
import { Field, StatsChips, Toolbar, inputStyle } from '../components/Toolbar'
import { AsignarModal } from '../components/AsignarModal'
import { ReasignarModal } from '../components/ReasignarModal'
import { OTDetalleDrawer } from '../components/OTDetalleDrawer'
import { PlanificadorOT } from '../components/PlanificadorOT'
import { useAuthStore } from '../../../stores/auth'
import { AvisoBuscar, useBusquedaDiferida } from '../../../ui/busqueda'
import { BotonOrden, ThOrden, ordenarFilas, useOrden } from '../../../ui/orden'

type Tab = 'asignar' | 'reasignar'

// La mesa trae TODOS los reclamos activos (sin tope): el orden se resuelve en
// pantalla sobre lo cargado (ui/orden.tsx).
type CampoOrden = 'nro' | 'tipo' | 'fecha' | 'subarea' | 'prioridad' | 'sla' | 'estado' | 'asignado'
const PESO_PRIORIDAD: Record<string, number> = { Alta: 1, Media: 2, Baja: 3 }
const VALORES_ORDEN: Record<CampoOrden, (r: MesaSupervisorRow) => string | number | null> = {
  nro: (r) => r.id_reclamo,
  tipo: (r) => r.tipo_nombre,
  fecha: (r) => (r.fecha_alta ? new Date(r.fecha_alta).getTime() : null),
  subarea: (r) => r.subarea_nombre,
  prioridad: (r) => (r.prioridad ? PESO_PRIORIDAD[r.prioridad] ?? 9 : null),
  sla: (r) => (r.sla_vencimiento ? new Date(r.sla_vencimiento).getTime() : null),
  estado: (r) => r.estado,
  asignado: (r) => r.ot_agente_nombre ?? r.ot_equipo_nombre ?? null,
}

// Filtros que viajan al backend (borrador de la búsqueda diferida, §23).
type BorradorServer = { nroDesde: string; nroHasta: string; fechaDesde: string; fechaHasta: string }

export function SupervisorView() {
  const user = useAuthStore((s) => s.user)
  const puedeGestionarAdjuntos = user != null && user.nivel_acceso <= 2
  // Fase 3 roles: para nivel 2 el backend fuerza la subárea del supervisor;
  // acá solo lo comunicamos en la UI.
  const esScopeado = user?.nivel_acceso === 2

  const [tab, setTab] = useState<Tab>('asignar')
  const [fTexto, setFTexto] = useState('')
  const [fEstado, setFEstado] = useState('')
  const [fPrioridad, setFPrioridad] = useState('')
  // Búsqueda server-side por rango de número y de fechas (Fase 3), diferida
  // (§23): los cuatro inputs son el borrador y el request sale recién al
  // presionar Buscar (o Enter en el form). Texto/estado/prioridad son
  // client-side y siguen filtrando en vivo sobre lo cargado.
  const busqueda = useBusquedaDiferida<BorradorServer>({ nroDesde: '', nroHasta: '', fechaDesde: '', fechaHasta: '' })
  const { nroDesde: fNroDesde, nroHasta: fNroHasta, fechaDesde: fFechaDesde, fechaHasta: fFechaHasta } = busqueda.borrador
  const setBorrador = (patch: Partial<BorradorServer>) => busqueda.setBorrador({ ...busqueda.borrador, ...patch })
  const filtrosServer = useMemo<MesaSupervisorFiltros>(() => {
    const a = busqueda.aplicado
    if (!a) return {}
    return {
      nro_desde: a.nroDesde !== '' ? Number(a.nroDesde) : undefined,
      nro_hasta: a.nroHasta !== '' ? Number(a.nroHasta) : undefined,
      fecha_desde: a.fechaDesde || undefined,
      fecha_hasta: a.fechaHasta || undefined,
    }
  }, [busqueda.aplicado])

  const { data, isLoading, isError, error, refetch, isFetching } = useMesaSupervisor(
    filtrosServer,
    { enabled: busqueda.buscado, version: busqueda.version },
  )
  const reclamos = data ?? []
  const [seleccionados, setSeleccionados] = useState<Set<number>>(new Set())

  const [modalAsignarReclamos, setModalAsignarReclamos] = useState<MesaSupervisorRow[]>([])
  const [modalReasignReclamo, setModalReasignReclamo] = useState<MesaSupervisorRow | null>(null)
  const [drawerRow, setDrawerRow] = useState<MesaSupervisorRow | null>(null)
  // Reclamo elegido para el panel de planificacion (tab Asignar).
  const [reclamoPlanificar, setReclamoPlanificar] = useState<MesaSupervisorRow | null>(null)

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

  // Sin orden elegido queda el del backend (prioridad, SLA, antigüedad).
  const { orden, alternar } = useOrden<CampoOrden>()
  const ordenados = useMemo(() => ordenarFilas(filtrados, orden, VALORES_ORDEN), [filtrados, orden])

  // Stats por estado dentro del tab actual
  const stats = useMemo(() => {
    const counts: Record<string, number> = {}
    porTab.forEach((r) => { counts[r.estado] = (counts[r.estado] ?? 0) + 1 })
    return counts
  }, [porTab])

  // Limpiar selección al cambiar tab o al cambiar dataset
  useEffect(() => {
    if (tab === 'reasignar') { setSeleccionados(new Set()); setReclamoPlanificar(null) }
  }, [tab])

  useEffect(() => {
    const vivos = new Set(reclamos.map((r) => r.id_reclamo))
    setSeleccionados((prev) => {
      // Bail si no cambio: evita loop cuando `reclamos` es un array
      // nuevo en cada render (data ?? []) pero las ids no cambiaron.
      let allHere = true
      prev.forEach((id) => { if (!vivos.has(id)) allHere = false })
      if (allHere) return prev
      const next = new Set<number>()
      prev.forEach((id) => { if (vivos.has(id)) next.add(id) })
      return next
    })
    // Si el reclamo planificado ya no esta en el dataset (ej: se le creo OT y
    // paso a En gestion -> sale del tab Asignar), limpiar el panel.
    setReclamoPlanificar((prev) => (prev && !vivos.has(prev.id_reclamo) ? null : prev))
  }, [reclamos])

  // Escape cierra el panel de planificación.
  useEffect(() => {
    if (!reclamoPlanificar) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setReclamoPlanificar(null) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [reclamoPlanificar])

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
          Asignar {busqueda.buscado && <Count active={tab === 'asignar'}>{nAsignar}</Count>}
        </TabButton>
        <TabButton active={tab === 'reasignar'} onClick={() => setTab('reasignar')}>
          Reasignar {busqueda.buscado && <Count active={tab === 'reasignar'}>{nReasignar}</Count>}
        </TabButton>
      </div>

      {esScopeado && (
        <div style={scopeChipStyle}>
          Bandeja de tu subárea:{' '}
          <strong>{user?.subarea_nombre ?? 'la asignada a tu perfil de agente'}</strong>
        </div>
      )}

      {/* Form: Enter en cualquier filtro = Buscar. Refrescar es type="button" y no dispara el submit. */}
      <form onSubmit={(e) => { e.preventDefault(); busqueda.buscar() }}>
      <Toolbar onRefresh={() => refetch()} refreshing={isFetching} refreshDisabled={!busqueda.buscado}>
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
        <Field label="Nº desde">
          <input
            type="number"
            min={1}
            value={fNroDesde}
            onChange={(e) => setBorrador({ nroDesde: e.target.value })}
            placeholder="Ej: 40"
            style={inputStyle}
          />
        </Field>
        <Field label="Nº hasta">
          <input
            type="number"
            min={1}
            value={fNroHasta}
            onChange={(e) => setBorrador({ nroHasta: e.target.value })}
            placeholder="Ej: 60"
            style={inputStyle}
          />
        </Field>
        <Field label="Fecha desde">
          <input type="date" value={fFechaDesde} onChange={(e) => setBorrador({ fechaDesde: e.target.value })} style={inputStyle} />
        </Field>
        <Field label="Fecha hasta">
          <input type="date" value={fFechaHasta} onChange={(e) => setBorrador({ fechaHasta: e.target.value })} style={inputStyle} />
        </Field>
        {tab === 'reasignar' && (
          <Field label="Estado">
            <select value={fEstado} onChange={(e) => setFEstado(e.target.value)} style={inputStyle}>
              <option value="">Todos</option>
              <option value="En gestión">En gestión</option>
              <option value="En espera">En espera</option>
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
        <button type="submit" style={btnBuscar} title="Traer la mesa con el rango de números y fechas elegido">
          <Search size={14} strokeWidth={1.5} /> Buscar
        </button>
      </Toolbar>
      </form>

      {busqueda.buscado && <StatsChips counts={stats} empty="Sin reclamos en esta vista" />}

      {/* Barra de selección SIEMPRE visible en Asignar (2026-10-20): tildar y
          «Asignar» tiene que descubrirse sin haber tildado nada antes. */}
      {tab === 'asignar' && busqueda.buscado && (
        <div style={seleccionados.size > 0 ? selbarStyle : selbarVacioStyle}>
          <div style={{ fontSize: '0.84rem' }}>
            {seleccionados.size > 0
              ? <><strong style={{ color: 'var(--zaris-orange)' }}>{seleccionados.size}</strong> {seleccionados.size === 1 ? 'reclamo seleccionado' : 'reclamos seleccionados'}</>
              : 'Tildá los reclamos que quieras asignar juntos, o tocá una fila para planificar uno.'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {seleccionados.size > 0 && (
              <button type="button" onClick={() => setSeleccionados(new Set())} style={selbarBtnGhost}>Limpiar</button>
            )}
            <button
              type="button"
              onClick={abrirAsignarLote}
              disabled={seleccionados.size === 0}
              style={{ ...selbarBtnPrimary, ...(seleccionados.size === 0 ? { opacity: 0.45, cursor: 'not-allowed' } : {}) }}
            >
              Asignar{seleccionados.size > 0 ? ` (${seleccionados.size})` : ''}
            </button>
          </div>
        </div>
      )}

      {/* La tabla usa todo el ancho; planificar abre un panel lateral que se
          superpone (antes ocupaba una columna fija de 340 px aunque no hubiera
          nada elegido y la tabla quedaba con scroll horizontal). */}
      {!busqueda.buscado ? (
        <AvisoBuscar texto="Elegí rango de números o fechas (o dejá todo vacío para ver toda la mesa) y presioná Buscar." />
      ) : (
        <div style={cardStyle}>
          <table style={tableStyle}>
            <thead>
              <tr>
                {tab === 'asignar' && (
                  <th style={{ ...thStyle, width: 32, paddingRight: 0 }}>
                    <input
                      type="checkbox"
                      checked={allVisiblesSelected}
                      onChange={(e) => toggleSelAll(e.target.checked)}
                      style={checkboxStyle}
                      title="Tildar todos los visibles"
                    />
                  </th>
                )}
                <th style={thStyle} aria-sort={orden?.campo === 'nro' || orden?.campo === 'tipo' ? (orden.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  <BotonOrden campo="nro" orden={orden} onOrdenar={alternar}>N°</BotonOrden>
                  <span style={{ margin: '0 4px', opacity: 0.5 }}>·</span>
                  <BotonOrden campo="tipo" orden={orden} onOrdenar={alternar}>Tipo</BotonOrden>
                </th>
                {tab === 'reasignar' && <ThOrden campo="estado" orden={orden} onOrdenar={alternar} style={thStyle}>Estado</ThOrden>}
                {/* Fecha de ingreso en lugar del ciudadano (César 2026-10-21): al
                    supervisor le sirve cuándo entró; el vecino está en «Ver». */}
                <ThOrden campo="fecha" orden={orden} onOrdenar={alternar} style={thStyle}>Fecha</ThOrden>
                <ThOrden campo="subarea" orden={orden} onOrdenar={alternar} style={thStyle}>Subárea</ThOrden>
                <ThOrden campo="prioridad" orden={orden} onOrdenar={alternar} style={thStyle}>Prio.</ThOrden>
                <ThOrden campo="sla" orden={orden} onOrdenar={alternar} style={thStyle}>SLA</ThOrden>
                {tab === 'reasignar' && <ThOrden campo="asignado" orden={orden} onOrdenar={alternar} style={thStyle}>Asignado a</ThOrden>}
                <th style={{ ...thStyle, textAlign: 'right' }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={9} style={emptyStyle}>Cargando…</td></tr>
              )}
              {isError && (
                <tr><td colSpan={9} style={emptyStyle}>Error: {(error as Error)?.message ?? 'desconocido'}</td></tr>
              )}
              {!isLoading && !isError && ordenados.length === 0 && (
                <tr><td colSpan={9} style={emptyStyle}>Sin reclamos en esta vista</td></tr>
              )}
              {ordenados.map((r) => {
                const isSel = seleccionados.has(r.id_reclamo)
                const isPlan = tab === 'asignar' && reclamoPlanificar?.id_reclamo === r.id_reclamo
                return (
                  <tr
                    key={r.id_reclamo}
                    onClick={tab === 'asignar' ? () => setReclamoPlanificar(r) : undefined}
                    style={{
                      cursor: tab === 'asignar' ? 'pointer' : undefined,
                      background: isPlan ? '#ffe6da' : isSel ? '#fff1ea' : undefined,
                    }}
                  >
                    {tab === 'asignar' && (
                      <td style={{ ...tdStyle, width: 32, paddingRight: 0 }} onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSel}
                          onChange={(e) => toggleSel(r.id_reclamo, e.target.checked)}
                          style={checkboxStyle}
                        />
                      </td>
                    )}
                    <td style={tdStyle}>
                      <div style={monoStyle}>{r.nro_reclamo ?? '—'}</div>
                      <Clamp2 title={r.tipo_nombre}>{r.tipo_nombre ?? '—'}</Clamp2>
                    </td>
                    {tab === 'reasignar' && <td style={tdStyle}><BadgeEstadoReclamo estado={r.estado} /></td>}
                    <td style={tdStyle}><FechaIngreso iso={r.fecha_alta} /></td>
                    <td style={tdStyle}><Clamp2 title={r.subarea_nombre}>{r.subarea_nombre ?? '—'}</Clamp2></td>
                    <td style={tdStyle}><BadgePrioridad prioridad={r.prioridad} /></td>
                    <td style={tdStyle}>
                      <SLACell sla_vencimiento={r.sla_vencimiento} sla_dias={r.sla_dias} compacto />
                    </td>
                    {tab === 'reasignar' && <td style={tdStyle}><AsignadoCell row={r} /></td>}
                    <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
                      <button type="button" onClick={() => setDrawerRow(r)} style={btnGhostSm}>Ver</button>
                      {tab === 'asignar'
                        ? <button type="button" onClick={() => setReclamoPlanificar(r)} style={{ ...btnPrimarySm, marginLeft: 4 }}>Planificar</button>
                        : <button type="button" onClick={() => abrirReasignar(r)} style={{ ...btnWarnSm, marginLeft: 4 }}>Reasignar</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Panel lateral de planificación: aparece solo con un reclamo elegido. */}
      {tab === 'asignar' && reclamoPlanificar && (
        <>
          <div style={drawerFondoStyle} onClick={() => setReclamoPlanificar(null)} aria-hidden="true" />
          <aside style={drawerStyle} role="dialog" aria-label="Planificar orden de trabajo">
            <div style={drawerHeadStyle}>
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.95rem' }}>Planificar OT</span>
              <button type="button" onClick={() => setReclamoPlanificar(null)} style={drawerCerrarStyle} aria-label="Cerrar">
                <X size={18} strokeWidth={1.5} />
              </button>
            </div>
            <PlanificadorOT
              reclamo={reclamoPlanificar}
              onDone={() => setReclamoPlanificar(null)}
            />
          </aside>
        </>
      )}

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
      <OTDetalleDrawer
        open={drawerRow !== null}
        idReclamo={drawerRow?.id_reclamo ?? null}
        idOTResaltada={drawerRow?.ot_activa_id ?? null}
        puedeGestionarAdjuntos={puedeGestionarAdjuntos}
        onClose={() => setDrawerRow(null)}
        onPlanificar={tab === 'asignar' && drawerRow?.estado === 'Sin asignar'
          ? () => { setReclamoPlanificar(drawerRow); setDrawerRow(null) }
          : undefined}
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

function FechaIngreso({ iso }: { iso: string | null }) {
  const d = iso ? new Date(iso) : null
  if (!d || Number.isNaN(d.getTime())) return <span style={{ color: 'var(--fg-3)' }}>—</span>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2, whiteSpace: 'nowrap' }}>
      <span style={monoStyle}>{d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })}</span>
      <span style={{ ...monoStyle, color: 'var(--fg-3)' }}>{d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}</span>
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
  minWidth: 0,
}

// Sin minWidth: las celdas parten en dos líneas (Clamp2) en vez de forzar
// scroll horizontal; con pantallas muy angostas el card igual scrollea.
const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'separate', borderSpacing: 0,
  fontSize: '0.84rem', minWidth: 640,
}

// Panel lateral de planificación (se superpone a la tabla). z por encima del
// topbar del shell dev (2000) para que el encabezado del panel no quede tapado.
const drawerFondoStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.18)', zIndex: 2100,
}
const drawerStyle: React.CSSProperties = {
  position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(400px, 100vw)',
  background: 'var(--zaris-cream)', borderLeft: '1px solid var(--border-primary)',
  boxShadow: '-8px 0 32px rgba(0,0,0,0.18)', zIndex: 2101,
  overflowY: 'auto', padding: '12px 14px 24px',
  display: 'flex', flexDirection: 'column', gap: 10,
}
const drawerHeadStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
}
const drawerCerrarStyle: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-2)',
  padding: 4, borderRadius: 6, display: 'flex',
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

// Chip informativo del scope del supervisor (Fase 3 roles).
const scopeChipStyle: React.CSSProperties = {
  display: 'inline-block', marginBottom: 10,
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)',
  borderRadius: 999, padding: '4px 14px',
  fontSize: '0.78rem', color: 'var(--fg-2)',
}

const selbarStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
  background: 'var(--fg-1)', color: 'var(--surface-100)',
  borderRadius: 10, padding: '9px 16px', marginBottom: 10,
}

// Misma barra sin selección: tono suave, con la ayuda de cómo usarla.
const selbarVacioStyle: React.CSSProperties = {
  ...selbarStyle,
  background: 'var(--surface-300)', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)',
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

const btnGhostSm: React.CSSProperties = {
  ...btnBase, background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-medium)',
}

// Botón Buscar del toolbar (submit del form de búsqueda diferida, §23).
// Misma geometría que el Refrescar del Toolbar para que alineen en la fila.
const btnBuscar: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', cursor: 'pointer',
  borderRadius: 8, padding: '7px 14px', border: '1px solid var(--zaris-orange)',
  background: 'var(--zaris-orange)', color: 'white', fontWeight: 500,
  display: 'inline-flex', alignItems: 'center', gap: 6,
}

const selbarBtnPrimary: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: 'white', borderColor: 'var(--zaris-orange)',
}

const selbarBtnGhost: React.CSSProperties = {
  ...btnBase, background: 'transparent', color: 'var(--surface-100)',
  border: '1px solid var(--surface-100)',
}
