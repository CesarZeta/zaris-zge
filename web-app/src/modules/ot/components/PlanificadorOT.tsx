import { useEffect, useState } from 'react'
import { ClipboardList, Wand2 } from 'lucide-react'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAuthStore } from '../../../stores/auth'
import { useCrearOT } from '../hooks/useOT'
import { getAutoAsignarSugerencia } from '../api/otApi'
import type { MesaSupervisorRow, TipoRecursoOT } from '../types/ot'
import { BadgePrioridad } from '../lib/format'
// Reuso del RecursoPicker de Agenda (cross-module import OK: comparten
// el mismo recurso de backend, ver feedback_cross_module_imports_react).
// Necesario para no listar 84+ agentes en un <select> en prod.
import { RecursoPicker } from '../../agenda/components/RecursoPicker'

interface Props {
  reclamo: MesaSupervisorRow | null
  onDone?: () => void
}

/**
 * Panel de la vista Supervisor: crea la OT del reclamo seleccionado y la asigna
 * a un agente o equipo. Los reclamos NO se agendan (César 2026-10-21: «la agenda
 * solo es para turnos; los horarios no entran en la ecuación»): la OT se asigna
 * para hacerse, sin fecha ni horario. Hasta esa fecha el panel elegía un hueco
 * libre del recurso y creaba la ocupación en la Agenda (POST /ot/con-agenda).
 */
export function PlanificadorOT({ reclamo, onDone }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const user = useAuthStore((s) => s.user)
  // Fase 3 roles (modelo subárea compartida): el supervisor (nivel 2) solo ve
  // recursos de su subárea en el picker. El backend igual impone el scope en
  // los POST de OT; sesiones viejas sin id_subarea caen al listado completo.
  const subareaScope = user?.nivel_acceso === 2 ? (user.id_subarea ?? undefined) : undefined
  const crear = useCrearOT()

  const [modo, setModo] = useState<TipoRecursoOT>('agente')
  const [idRecurso, setIdRecurso] = useState<number | ''>('')
  const [obs, setObs] = useState('')
  const [autoBuscando, setAutoBuscando] = useState(false)

  // Reset al cambiar de reclamo.
  useEffect(() => {
    setModo('agente')
    setIdRecurso('')
    setObs('')
  }, [reclamo?.id_reclamo])

  if (!reclamo) {
    return (
      <div style={vacioStyle}>
        <ClipboardList size={28} strokeWidth={1.25} style={{ color: 'var(--fg-3)' }} />
        <div style={{ fontSize: '0.86rem', color: 'var(--fg-3)', marginTop: 8 }}>
          Selecciona un reclamo de la bandeja para crear su orden de trabajo.
        </div>
      </div>
    )
  }

  async function autoAsignar() {
    if (!reclamo) return
    setAutoBuscando(true)
    try {
      const r = await getAutoAsignarSugerencia(reclamo.id_reclamo)
      if (!r.sugerencia) {
        push({ kind: 'info', title: 'Sin a quién asignar',
          body: r.motivo ?? 'La gestión no tiene agentes ni cuadrillas que puedan recibir la OT.' })
        return
      }
      const s = r.sugerencia
      setModo(s.tipo_recurso)
      setIdRecurso(s.id_recurso)
      push({ kind: 'success',
        title: `Sugerido: ${s.tipo_recurso === 'equipo' ? 'equipo' : 'agente'} ${s.nombre}`,
        body: `Es el de menor carga de la gestión (${s.carga} ${s.carga === 1 ? 'OT abierta' : 'OTs abiertas'}). Revisá y confirmá.` })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo auto-asignar', body: (e as Error).message })
    } finally {
      setAutoBuscando(false)
    }
  }

  async function crearOT() {
    if (idRecurso === '' || !reclamo) return
    try {
      const r = await crear.mutateAsync({
        id_reclamo: reclamo.id_reclamo,
        id_agente: modo === 'agente' ? (idRecurso as number) : null,
        id_equipo: modo === 'equipo' ? (idRecurso as number) : null,
        observaciones: obs.trim() || undefined,
      })
      push({ kind: 'success', title: `${r.nro_ot} creada y asignada` })
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

      {/* Auto-asignar: el de menor carga de la gestión */}
      <button
        type="button"
        onClick={autoAsignar}
        disabled={autoBuscando || crear.isPending}
        style={btnAuto}
        title="Elige al agente o cuadrilla de la gestión con menos órdenes abiertas (y, si empatan, al que hace más tiempo que no recibe una) para que confirmes."
      >
        <Wand2 size={14} strokeWidth={1.75} />
        {autoBuscando ? 'Buscando…' : 'Auto-asignar al de menor carga'}
      </button>

      {/* Recurso */}
      <div style={{ display: 'flex', gap: 14 }}>
        <label style={radioLabel}>
          <input type="radio" checked={modo === 'agente'} onChange={() => { setModo('agente'); setIdRecurso('') }} /> Agente
        </label>
        <label style={radioLabel}>
          <input type="radio" checked={modo === 'equipo'} onChange={() => { setModo('equipo'); setIdRecurso('') }} /> Equipo
        </label>
      </div>

      <Field
        label={modo === 'agente' ? 'Agente' : 'Equipo'}
        hint={modo === 'equipo' ? 'Solo cuadrillas de trabajo (las mesas de trámites no atienden OT).' : undefined}
      >
        <RecursoPicker
          tipo={modo}
          value={idRecurso !== '' ? (idRecurso as number) : null}
          onChange={(id) => setIdRecurso(id ?? '')}
          soloCuadrillas
          idSubarea={subareaScope}
        />
      </Field>

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

      <button
        type="button"
        onClick={crearOT}
        disabled={crear.isPending || !recursoElegido}
        style={{ ...btnPrimary, ...(!recursoElegido ? { opacity: 0.5, cursor: 'not-allowed' } : {}) }}
      >
        {crear.isPending ? 'Creando…' : 'Crear OT'}
      </button>
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

const btnPrimary: React.CSSProperties = {
  padding: '9px 16px', background: 'var(--zaris-orange)', color: 'white',
  border: 'none', borderRadius: 8, marginTop: 4,
  fontFamily: 'var(--font-display)', fontSize: '0.86rem', fontWeight: 600, cursor: 'pointer',
}

const btnAuto: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  padding: '8px 12px', background: 'var(--surface-300)', color: 'var(--fg-1)',
  border: '1px dashed var(--zaris-orange)', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', fontWeight: 500, cursor: 'pointer',
}
