import { useState } from 'react'
import { CalendarOff, UserX, Plus, Trash2 } from 'lucide-react'
import { RecursoPicker } from '../components/RecursoPicker'
import { ConfirmModal } from '../components/ConfirmModal'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useNovedades, useCrearNovedad, useEliminarNovedad,
  useFeriados, useCrearFeriado, useEliminarFeriado,
  type TipoNovedad, type AmbitoFeriado, type Novedad, type Feriado,
} from '../api/novedadesApi'

type Sub = 'feriados' | 'novedades'

const TIPO_LABEL: Record<TipoNovedad, string> = {
  inasistencia: 'Inasistencia', licencia: 'Licencia', vacaciones: 'Vacaciones',
  comision: 'Comisión', otro: 'Otro',
}

export function DisponibilidadView() {
  const [sub, setSub] = useState<Sub>('feriados')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ margin: 0, color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
        Feriados e inasistencias de agentes restan disponibilidad efectiva: no se ofrecen turnos
        ni slots en esos días/horarios mientras el switch global esté activo.
      </p>
      <div style={{ display: 'flex', gap: 6 }}>
        <SubTab active={sub === 'feriados'} onClick={() => setSub('feriados')} icon={CalendarOff} label="Feriados" />
        <SubTab active={sub === 'novedades'} onClick={() => setSub('novedades')} icon={UserX} label="Novedades de agentes" />
      </div>
      {sub === 'feriados' ? <Feriados /> : <Novedades />}
    </div>
  )
}

// ===========================================================================
// Feriados
// ===========================================================================
function Feriados() {
  const push = useNotificationsStore((s) => s.push)
  const anio = new Date().getFullYear()
  const { data, isLoading } = useFeriados({ anio })
  const crear = useCrearFeriado()
  const eliminar = useEliminarFeriado()
  const [fecha, setFecha] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [ambito, setAmbito] = useState<AmbitoFeriado>('MUNICIPAL')
  const [confirmDel, setConfirmDel] = useState<Feriado | null>(null)

  async function add() {
    if (!fecha || !descripcion.trim()) {
      push({ kind: 'error', title: 'Completá fecha y descripción' }); return
    }
    try {
      await crear.mutateAsync({ fecha, descripcion: descripcion.trim(), ambito })
      push({ kind: 'success', title: 'Feriado agregado' })
      setFecha(''); setDescripcion('')
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo agregar', body: (e as Error).message })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={panel}>
        <div style={{ ...field, minWidth: 150 }}>
          <label style={lbl}>Fecha</label>
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={inp} />
        </div>
        <div style={{ ...field, flex: 1, minWidth: 200 }}>
          <label style={lbl}>Descripción</label>
          <input type="text" value={descripcion} onChange={(e) => setDescripcion(e.target.value)}
            placeholder="Ej. Día del trabajador" style={inp} maxLength={200} />
        </div>
        <div style={{ ...field, minWidth: 150 }}>
          <label style={lbl}>Ámbito</label>
          <select value={ambito} onChange={(e) => setAmbito(e.target.value as AmbitoFeriado)} style={inp}>
            <option value="MUNICIPAL">Municipal</option>
            <option value="PROVINCIAL">Provincial</option>
            <option value="NACIONAL">Nacional</option>
          </select>
        </div>
        <button onClick={add} disabled={crear.isPending} style={btnPrimary}>
          <Plus size={14} strokeWidth={1.5} /> Agregar
        </button>
      </div>

      <div style={card}>
        <table style={table}>
          <thead><tr>
            <th style={th}>Fecha</th><th style={th}>Descripción</th>
            <th style={th}>Ámbito</th><th style={{ ...th, textAlign: 'right' }}>Acción</th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={4} style={empty}>Cargando…</td></tr>}
            {!isLoading && (data ?? []).length === 0 && (
              <tr><td colSpan={4} style={empty}>No hay feriados cargados para {anio}.</td></tr>
            )}
            {(data ?? []).map((f) => (
              <tr key={f.id_agenda_feriado}>
                <td style={{ ...td, ...mono }}>{f.fecha}</td>
                <td style={td}>{f.descripcion}</td>
                <td style={td}><span style={badge}>{f.ambito}</span></td>
                <td style={{ ...td, textAlign: 'right' }}>
                  <button onClick={() => setConfirmDel(f)} style={btnDangerSm}>
                    <Trash2 size={13} strokeWidth={1.5} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmModal
        open={confirmDel != null}
        title="Eliminar feriado"
        message={`Eliminar el feriado del ${confirmDel?.fecha} (${confirmDel?.descripcion})?`}
        confirmLabel="Eliminar" danger
        onConfirm={async () => {
          if (!confirmDel) return
          const f = confirmDel; setConfirmDel(null)
          try { await eliminar.mutateAsync(f.id_agenda_feriado); push({ kind: 'success', title: 'Feriado eliminado' }) }
          catch (e) { push({ kind: 'error', title: 'No se pudo eliminar', body: (e as Error).message }) }
        }}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  )
}

// ===========================================================================
// Novedades de agentes
// ===========================================================================
function Novedades() {
  const push = useNotificationsStore((s) => s.push)
  const hoy = new Date().toISOString().slice(0, 10)
  const { data, isLoading } = useNovedades({ desde: hoy })
  const crear = useCrearNovedad()
  const eliminar = useEliminarNovedad()

  const [idAgente, setIdAgente] = useState<number | null>(null)
  const [tipo, setTipo] = useState<TipoNovedad>('inasistencia')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [diaCompleto, setDiaCompleto] = useState(true)
  const [horaIni, setHoraIni] = useState('')
  const [horaFin, setHoraFin] = useState('')
  const [motivo, setMotivo] = useState('')
  const [confirmDel, setConfirmDel] = useState<Novedad | null>(null)

  async function add() {
    if (!idAgente) { push({ kind: 'error', title: 'Elegí un agente' }); return }
    if (!desde || !hasta) { push({ kind: 'error', title: 'Completá el rango de fechas' }); return }
    if (hasta < desde) { push({ kind: 'error', title: 'La fecha hasta debe ser igual o posterior a desde' }); return }
    if (!diaCompleto && (!horaIni || !horaFin)) { push({ kind: 'error', title: 'Completá el rango horario o marcá día completo' }); return }
    if (!diaCompleto && horaFin <= horaIni) { push({ kind: 'error', title: 'La hora fin debe ser mayor que la hora inicio' }); return }
    try {
      await crear.mutateAsync({
        id_agente: idAgente, tipo, fecha_desde: desde, fecha_hasta: hasta,
        hora_inicio: diaCompleto ? null : horaIni,
        hora_fin: diaCompleto ? null : horaFin,
        motivo: motivo.trim() || null,
      })
      push({ kind: 'success', title: 'Novedad registrada' })
      setDesde(''); setHasta(''); setHoraIni(''); setHoraFin(''); setMotivo('')
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo registrar', body: (e as Error).message })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ ...panel, flexDirection: 'column', alignItems: 'stretch', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ ...field, flex: 1, minWidth: 240 }}>
            <label style={lbl}>Agente</label>
            <RecursoPicker tipo="agente" value={idAgente} onChange={setIdAgente} placeholder="Buscar agente por nombre…" />
          </div>
          <div style={{ ...field, minWidth: 150 }}>
            <label style={lbl}>Tipo</label>
            <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoNovedad)} style={inp}>
              {Object.entries(TIPO_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ ...field, minWidth: 150 }}>
            <label style={lbl}>Desde</label>
            <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={inp} />
          </div>
          <div style={{ ...field, minWidth: 150 }}>
            <label style={lbl}>Hasta</label>
            <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={inp} />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--fg-2)', paddingBottom: 8 }}>
            <input type="checkbox" checked={diaCompleto} onChange={(e) => setDiaCompleto(e.target.checked)} />
            Día completo
          </label>
          {!diaCompleto && (
            <>
              <div style={{ ...field, minWidth: 110 }}>
                <label style={lbl}>Hora inicio</label>
                <input type="time" value={horaIni} onChange={(e) => setHoraIni(e.target.value)} style={inp} />
              </div>
              <div style={{ ...field, minWidth: 110 }}>
                <label style={lbl}>Hora fin</label>
                <input type="time" value={horaFin} onChange={(e) => setHoraFin(e.target.value)} style={inp} />
              </div>
            </>
          )}
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ ...field, flex: 1, minWidth: 240 }}>
            <label style={lbl}>Motivo (opcional)</label>
            <input type="text" value={motivo} onChange={(e) => setMotivo(e.target.value)} style={inp} maxLength={300} />
          </div>
          <button onClick={add} disabled={crear.isPending} style={btnPrimary}>
            <Plus size={14} strokeWidth={1.5} /> Registrar
          </button>
        </div>
      </div>

      <div style={card}>
        <table style={table}>
          <thead><tr>
            <th style={th}>Agente</th><th style={th}>Tipo</th><th style={th}>Rango</th>
            <th style={th}>Horario</th><th style={th}>Motivo</th>
            <th style={{ ...th, textAlign: 'right' }}>Acción</th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={empty}>Cargando…</td></tr>}
            {!isLoading && (data ?? []).length === 0 && (
              <tr><td colSpan={6} style={empty}>No hay novedades vigentes o futuras.</td></tr>
            )}
            {(data ?? []).map((n) => (
              <tr key={n.id_agente_novedad}>
                <td style={td}>{n.agente_nombre}</td>
                <td style={td}><span style={badge}>{TIPO_LABEL[n.tipo] ?? n.tipo}</span></td>
                <td style={{ ...td, ...mono }}>{n.fecha_desde === n.fecha_hasta ? n.fecha_desde : `${n.fecha_desde} → ${n.fecha_hasta}`}</td>
                <td style={{ ...td, ...mono }}>
                  {n.hora_inicio && n.hora_fin ? `${n.hora_inicio.slice(0, 5)}–${n.hora_fin.slice(0, 5)}` : 'Día completo'}
                </td>
                <td style={{ ...td, color: 'var(--fg-3)', maxWidth: 200 }}>{n.motivo ?? ''}</td>
                <td style={{ ...td, textAlign: 'right' }}>
                  <button onClick={() => setConfirmDel(n)} style={btnDangerSm}>
                    <Trash2 size={13} strokeWidth={1.5} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmModal
        open={confirmDel != null}
        title="Eliminar novedad"
        message={`Eliminar la novedad de ${confirmDel?.agente_nombre}? El agente vuelve a estar disponible en ese período.`}
        confirmLabel="Eliminar" danger
        onConfirm={async () => {
          if (!confirmDel) return
          const n = confirmDel; setConfirmDel(null)
          try { await eliminar.mutateAsync(n.id_agente_novedad); push({ kind: 'success', title: 'Novedad eliminada' }) }
          catch (e) { push({ kind: 'error', title: 'No se pudo eliminar', body: (e as Error).message }) }
        }}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  )
}

// ===========================================================================
function SubTab({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof CalendarOff; label: string }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px',
      borderRadius: 8, fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer',
      border: '1px solid ' + (active ? 'var(--zaris-orange)' : 'var(--border-medium)'),
      background: active ? 'var(--zaris-orange)' : 'transparent',
      color: active ? 'white' : 'var(--fg-2)', fontWeight: 500,
    }}>
      <Icon size={14} strokeWidth={1.5} /> {label}
    </button>
  )
}

const panel: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 14,
}
const field: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
const lbl: React.CSSProperties = { fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)' }
const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, padding: '7px 10px',
  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none', color: 'var(--fg-1)',
}
const btnPrimary: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer', borderRadius: 8,
  padding: '8px 14px', border: '1px solid var(--zaris-orange)', background: 'var(--zaris-orange)',
  color: 'white', fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 6, height: 36,
}
const btnDangerSm: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.76rem', cursor: 'pointer', borderRadius: 6,
  padding: '5px 8px', border: '1px solid var(--color-error)', background: 'transparent',
  color: 'var(--color-error)', display: 'inline-flex', alignItems: 'center',
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, overflowX: 'auto',
}
const table: React.CSSProperties = { width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.84rem', minWidth: 700 }
const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em',
  color: 'var(--fg-3)', padding: '9px 12px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-300)', whiteSpace: 'nowrap',
}
const td: React.CSSProperties = { padding: '10px 12px', borderBottom: '1px solid var(--border-primary)', verticalAlign: 'middle' }
const mono: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-2)', whiteSpace: 'nowrap' }
const empty: React.CSSProperties = { padding: 36, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem' }
const badge: React.CSSProperties = {
  background: 'var(--surface-300)', color: 'var(--fg-2)', fontSize: '0.72rem', fontWeight: 600,
  padding: '2px 9px', borderRadius: 999,
}
