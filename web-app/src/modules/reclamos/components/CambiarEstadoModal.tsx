import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAuthStore } from '../../../stores/auth'
import { useCambiarEstadoReclamo } from '../hooks/useReclamos'
import type { EstadoReclamo } from '../types/reclamo'

interface Props {
  open: boolean
  idReclamo: number
  estadoActual: EstadoReclamo
  onClose: () => void
  onSuccess?: () => void
}

// #3 — Grafo de transiciones permitidas. Espeja TRANSICIONES_PERMITIDAS del
// backend (reclamos.py). Cancelado se omite acá porque usa el endpoint dedicado
// /cancelar (motivo requerido + cascade OTs). El dropdown solo ofrece estados
// alcanzables desde el estado actual; el resto se deshabilita.
const TRANSICIONES_PERMITIDAS: Record<EstadoReclamo, EstadoReclamo[]> = {
  'Sin asignar':  ['En gestión'],
  'En gestión':   ['En espera', 'En auditoría', 'Resuelto'],
  'En espera':    ['En gestión', 'En auditoría'],
  'En auditoría': ['En gestión', 'Resuelto'],
  'Resuelto':     [],
  'Cancelado':    [],
}

export function CambiarEstadoModal({ open, idReclamo, estadoActual, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const esSupervisor = useAuthStore((s) => s.hasPermission(2))
  const mut = useCambiarEstadoReclamo(idReclamo)

  // Cierre directo sin OT (backend reclamos.py): un supervisor (nivel ≤ 2) de la
  // misma subárea del reclamo puede resolver un "Sin asignar" sin pasar por
  // gestión. El backend valida la subárea; acá solo ofrecemos la opción si el
  // usuario tiene nivel supervisor (sino ni la ve).
  const opcionesPara = (estado: EstadoReclamo): EstadoReclamo[] => {
    const base = TRANSICIONES_PERMITIDAS[estado] ?? []
    if (estado === 'Sin asignar' && esSupervisor && !base.includes('Resuelto')) {
      return [...base, 'Resuelto']
    }
    return base
  }

  const alcanzables = opcionesPara(estadoActual)
  // Preselecciona el primer estado alcanzable (no el actual, que no es opción).
  const [estadoNuevo, setEstadoNuevo] = useState<EstadoReclamo>(alcanzables[0] ?? estadoActual)
  const [nota, setNota] = useState('')
  // Pop-up de confirmación para el cierre directo (resolver sin OT).
  const [confirmandoCierre, setConfirmandoCierre] = useState(false)

  // Es cierre directo cuando se resuelve un reclamo todavía "Sin asignar".
  const esCierreDirecto = estadoActual === 'Sin asignar' && estadoNuevo === 'Resuelto'

  useEffect(() => {
    if (open) {
      const opciones = opcionesPara(estadoActual)
      setEstadoNuevo(opciones[0] ?? estadoActual)
      setNota('')
      setConfirmandoCierre(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, estadoActual])

  async function aplicar() {
    try {
      await mut.mutateAsync({ estado: estadoNuevo, nota: nota.trim() || undefined })
      push({ kind: 'success', title: `Estado actualizado a "${estadoNuevo}"` })
      onSuccess?.()
      onClose()
    } catch (err) {
      // Si el backend rechaza el cierre directo (subárea/nivel/OT), volvemos al
      // formulario para que el usuario lo vea y el mensaje del backend se muestra.
      setConfirmandoCierre(false)
      push({ kind: 'error', title: 'No se pudo cambiar el estado', body: (err as Error).message })
    }
  }

  function confirmar() {
    if (estadoNuevo === estadoActual) {
      push({ kind: 'info', title: 'El estado nuevo es igual al actual' })
      return
    }
    // Cierre directo: pedir confirmación explícita antes de ejecutar.
    if (esCierreDirecto && !confirmandoCierre) {
      setConfirmandoCierre(true)
      return
    }
    void aplicar()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cambiar estado del reclamo"
      width={480}
      footer={
        confirmandoCierre ? (
          <>
            <button onClick={() => setConfirmandoCierre(false)} disabled={mut.isPending} style={btnGhost}>
              Volver
            </button>
            <button onClick={() => void aplicar()} disabled={mut.isPending} style={btnDanger}>
              {mut.isPending ? 'Resolviendo...' : 'Sí, resolver sin OT'}
            </button>
          </>
        ) : (
          <>
            <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Cancelar</button>
            <button
              onClick={confirmar}
              disabled={mut.isPending || alcanzables.length === 0 || estadoNuevo === estadoActual}
              style={btnPrimary}
            >
              {mut.isPending ? 'Guardando...' : 'Aplicar cambio'}
            </button>
          </>
        )
      }
    >
      {confirmandoCierre ? (
        <div style={alertBox}>
          <div style={{ fontWeight: 600, color: 'var(--color-error)', marginBottom: 8, fontSize: 'var(--size-ui)' }}>
            ¿Resolver el reclamo sin generar OT?
          </div>
          <p style={{ margin: 0, color: 'var(--fg-2)', fontSize: 'var(--size-ui)', lineHeight: 1.55 }}>
            Vas a cerrar este reclamo (<strong>{estadoActual}</strong> → <strong>Resuelto</strong>) sin
            crear una orden de trabajo. Esta acción solo es válida para un supervisor de la misma
            subárea del reclamo, queda registrada en el historial y <strong>no se puede deshacer</strong>.
          </p>
          {nota.trim() && (
            <p style={{ margin: '10px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-caption)' }}>
              Nota: {nota.trim()}
            </p>
          )}
        </div>
      ) : (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Field label="Estado actual">
          <div style={readonlyField}>{estadoActual}</div>
        </Field>

        {alcanzables.length === 0 ? (
          <div style={{
            padding: '12px 14px', background: 'var(--surface-300)',
            border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
            color: 'var(--fg-2)', fontSize: 'var(--size-ui)', lineHeight: 1.5,
          }}>
            El reclamo está en estado <strong>{estadoActual}</strong> (final). No admite
            cambios de estado. {estadoActual === 'Resuelto'
              ? 'Para reabrirlo, generá una nueva OT o un subreclamo.'
              : ''}
          </div>
        ) : (
          <Field
            label="Nuevo estado"
            required
            hint={
              estadoActual === 'Sin asignar' && estadoNuevo === 'Resuelto'
                ? 'Resolución directa sin OT: solo válida para supervisores de la misma subárea del reclamo. El sistema lo verifica al guardar.'
                : 'Solo se muestran las transiciones válidas desde el estado actual.'
            }
          >
            <select
              value={estadoNuevo}
              onChange={(e) => setEstadoNuevo(e.target.value as EstadoReclamo)}
              style={inputStyle}
            >
              {alcanzables.map((e) => (
                <option key={e} value={e}>{e}</option>
              ))}
            </select>
          </Field>
        )}

        <Field label="Nota para el historial" hint="Opcional. Aparece en el timeline del reclamo y se concatena en observaciones.">
          <textarea
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder="Ej: contactado el reclamante, equipo asignado mañana 9hs."
            rows={3}
            maxLength={500}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>
      </div>
      )}
    </Modal>
  )
}

function Field({ label, required, hint, children }: {
  label: string; required?: boolean; hint?: string; children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
        {label}{required && <span style={{ color: 'var(--zaris-orange)', marginLeft: 4 }}>*</span>}
      </label>
      {children}
      {hint && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>{hint}</div>}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 12px',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  outline: 'none',
}

const readonlyField: React.CSSProperties = {
  padding: '9px 12px', background: 'var(--surface-300)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  color: 'var(--fg-2)', fontSize: 'var(--size-ui)',
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
  fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}

const btnDanger: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--color-error)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
  fontWeight: 500, cursor: 'pointer',
}

const alertBox: React.CSSProperties = {
  padding: '14px 16px',
  background: 'rgba(207,45,86,.07)',
  border: '1px solid var(--color-error)',
  borderRadius: 'var(--radius-lg)',
}
