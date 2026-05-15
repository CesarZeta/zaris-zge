import { useEffect, useState } from 'react'
import { ClipboardList, CalendarClock } from 'lucide-react'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useSlotsRecurso,
  useCrearOT, useCrearOTConAgenda,
} from '../hooks/useOT'
import type { MesaSupervisorRow, SlotLibre, TipoRecursoOT } from '../types/ot'
import { BadgePrioridad } from '../lib/format'
// Reuso del RecursoPicker de Agenda (cross-module import OK: comparten
// el mismo recurso de backend, ver feedback_cross_module_imports_react).
// Necesario para no listar 84+ agentes en un <select> en prod.
import { RecursoPicker } from '../../agenda/components/RecursoPicker'

interface Props {
  reclamo: MesaSupervisorRow | null
  onDone?: () => void
}

const DURACION_MIN = 60

/**
 * Panel derecho de la vista Supervisor: planifica una OT para el reclamo
 * seleccionado. Elige agente/equipo + fecha -> muestra slots libres ->
 * crea OT + ocupacion en una pasada (POST /ot/con-agenda). Tambien permite
 * crear la OT sin agendar (POST /ot normal).
 */
export function PlanificadorOT({ reclamo, onDone }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const crearConAgenda = useCrearOTConAgenda()
  const crearSimple = useCrearOT()

  const [modo, setModo] = useState<TipoRecursoOT>('agente')
  const [idRecurso, setIdRecurso] = useState<number | ''>('')
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10))
  const [slotSel, setSlotSel] = useState<SlotLibre | null>(null)
  const [obs, setObs] = useState('')

  // Reset al cambiar de reclamo.
  useEffect(() => {
    setModo('agente')
    setIdRecurso('')
    setFecha(new Date().toISOString().slice(0, 10))
    setSlotSel(null)
    setObs('')
  }, [reclamo?.id_reclamo])

  // Al cambiar recurso o fecha, el slot elegido deja de ser valido.
  useEffect(() => { setSlotSel(null) }, [modo, idRecurso, fecha])

  const slotsQ = useSlotsRecurso(
    idRecurso !== '' ? modo : null,
    idRecurso !== '' ? (idRecurso as number) : null,
    idRecurso !== '' ? fecha : null,
    DURACION_MIN,
  )
  const slots = slotsQ.data?.slots ?? []

  const pendiente = crearConAgenda.isPending || crearSimple.isPending

  if (!reclamo) {
    return (
      <div style={vacioStyle}>
        <ClipboardList size={28} strokeWidth={1.25} style={{ color: 'var(--fg-3)' }} />
        <div style={{ fontSize: '0.86rem', color: 'var(--fg-3)', marginTop: 8 }}>
          Selecciona un reclamo de la bandeja para planificar su orden de trabajo.
        </div>
      </div>
    )
  }

  async function crearAgendado() {
    if (idRecurso === '' || !slotSel || !reclamo) return
    try {
      const r = await crearConAgenda.mutateAsync({
        id_reclamo: reclamo.id_reclamo,
        tipo_recurso: modo,
        id_recurso: idRecurso as number,
        fecha,
        hora_inicio: slotSel.hora_inicio.slice(0, 5),
        hora_fin: slotSel.hora_fin.slice(0, 5),
        observaciones: obs.trim() || undefined,
      })
      const conConflicto = r.conflictos.length > 0
      push({
        kind: conConflicto ? 'error' : 'success',
        title: conConflicto
          ? `${r.nro_ot} creada con conflicto de agenda`
          : `${r.nro_ot} creada y agendada`,
        body: conConflicto ? `${r.conflictos.length} solapamiento(s) en el recurso.` : undefined,
        ttl: conConflicto ? 7000 : 4000,
      })
      onDone?.()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo crear la OT', body: (e as Error).message })
    }
  }

  async function crearSinAgendar() {
    if (idRecurso === '' || !reclamo) return
    try {
      const r = await crearSimple.mutateAsync({
        id_reclamo: reclamo.id_reclamo,
        id_agente: modo === 'agente' ? (idRecurso as number) : null,
        id_equipo: modo === 'equipo' ? (idRecurso as number) : null,
        observaciones: obs.trim() || undefined,
      })
      push({ kind: 'success', title: `${r.nro_ot} creada (sin agendar)` })
      onDone?.()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo crear la OT', body: (e as Error).message })
    }
  }

  const recursoElegido = idRecurso !== ''

  return (
    <div style={panelStyle}>
      {/* Contexto: el reclamo */}
      <div style={reclamoBoxStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.76rem', color: 'var(--fg-3)' }}>
            {reclamo.nro_reclamo ?? '—'}
          </span>
          {reclamo.prioridad && <BadgePrioridad prioridad={reclamo.prioridad} />}
        </div>
        <div style={{ fontSize: '0.84rem', color: 'var(--fg-1)', fontWeight: 500 }}>
          {reclamo.tipo_nombre ?? '—'}
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--fg-3)' }}>
          {reclamo.subarea_nombre ?? '—'}
        </div>
        {reclamo.descripcion && (
          <div style={{ fontSize: '0.8rem', color: 'var(--fg-2)', marginTop: 4, lineHeight: 1.35 }}>
            {reclamo.descripcion}
          </div>
        )}
      </div>

      {/* Recurso */}
      <div style={{ display: 'flex', gap: 14 }}>
        <label style={radioLabel}>
          <input type="radio" checked={modo === 'agente'} onChange={() => { setModo('agente'); setIdRecurso('') }} /> Agente
        </label>
        <label style={radioLabel}>
          <input type="radio" checked={modo === 'equipo'} onChange={() => { setModo('equipo'); setIdRecurso('') }} /> Equipo
        </label>
      </div>

      <Field label={modo === 'agente' ? 'Agente' : 'Equipo'}>
        <RecursoPicker
          tipo={modo}
          value={idRecurso !== '' ? (idRecurso as number) : null}
          onChange={(id) => setIdRecurso(id ?? '')}
        />
      </Field>

      <Field label="Fecha">
        <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={inputStyle} />
      </Field>

      {/* Slots libres */}
      {recursoElegido && (
        <div>
          <div style={{ fontSize: '0.78rem', color: 'var(--fg-2)', fontWeight: 500, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
            <CalendarClock size={13} strokeWidth={1.5} /> Slots libres
          </div>
          {slotsQ.isLoading && <div style={hintStyle}>Buscando huecos…</div>}
          {slotsQ.isError && <div style={{ ...hintStyle, color: 'var(--color-error)' }}>Error al cargar slots.</div>}
          {!slotsQ.isLoading && !slotsQ.isError && slots.length === 0 && (
            <div style={hintStyle}>
              {modo === 'equipo'
                ? 'Este equipo no tiene agentes con agenda disponible ese día.'
                : 'Este agente no tiene horario disponible ese día (sin disponibilidad o todo ocupado).'}
            </div>
          )}
          {slots.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {slots.map((s) => {
                const sel = slotSel?.hora_inicio === s.hora_inicio
                return (
                  <button
                    key={s.hora_inicio}
                    onClick={() => setSlotSel(sel ? null : s)}
                    style={sel ? slotChipSel : slotChip}
                  >
                    {s.hora_inicio.slice(0, 5)}–{s.hora_fin.slice(0, 5)}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      <Field label="Observaciones" hint="Opcional. Notas para el agente o equipo.">
        <textarea
          value={obs}
          onChange={(e) => setObs(e.target.value)}
          placeholder="Notas…"
          rows={2}
          maxLength={500}
          style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-display)' }}
        />
      </Field>

      {/* Acciones */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
        <button
          onClick={crearAgendado}
          disabled={pendiente || !recursoElegido || !slotSel}
          style={btnPrimary}
        >
          {crearConAgenda.isPending ? 'Creando…' : 'Crear OT y agendar'}
        </button>
        <button
          onClick={crearSinAgendar}
          disabled={pendiente || !recursoElegido}
          style={btnGhostLink}
          title="La OT se crea sin ocupación en la agenda. Queda registrada con tu usuario como supervisor."
        >
          {crearSimple.isPending ? 'Creando…' : 'Crear OT sin agendar'}
        </button>
      </div>
    </div>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: '0.78rem', color: 'var(--fg-2)', fontWeight: 500 }}>{label}</label>
      {children}
      {hint && <div style={hintStyle}>{hint}</div>}
    </div>
  )
}

const panelStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 12,
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 16,
  position: 'sticky', top: 12,
}

const vacioStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
  textAlign: 'center', padding: '40px 20px',
  background: 'var(--surface-100)', border: '1px dashed var(--border-medium)',
  borderRadius: 12, position: 'sticky', top: 12,
}

const reclamoBoxStyle: React.CSSProperties = {
  background: 'var(--surface-300)', borderRadius: 8, padding: '10px 12px',
  display: 'flex', flexDirection: 'column', gap: 2,
}

const radioLabel: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.84rem', cursor: 'pointer',
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 11px',
  fontFamily: 'var(--font-display)', fontSize: '0.86rem',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, outline: 'none',
}

const hintStyle: React.CSSProperties = {
  fontSize: '0.74rem', color: 'var(--fg-3)', lineHeight: 1.35,
}

const slotChip: React.CSSProperties = {
  padding: '5px 10px', fontFamily: 'var(--font-mono)', fontSize: '0.76rem',
  background: 'var(--surface-300)', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', borderRadius: 999, cursor: 'pointer',
}

const slotChipSel: React.CSSProperties = {
  ...slotChip,
  background: 'var(--zaris-orange)', color: 'white', borderColor: 'var(--zaris-orange)',
}

const btnPrimary: React.CSSProperties = {
  padding: '9px 16px', background: 'var(--zaris-orange)', color: 'white',
  border: 'none', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.86rem', fontWeight: 600, cursor: 'pointer',
}

const btnGhostLink: React.CSSProperties = {
  padding: '6px 12px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', cursor: 'pointer',
}
