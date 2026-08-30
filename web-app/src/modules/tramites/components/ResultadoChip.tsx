import { useState } from 'react'
import { CheckCircle2, XCircle, CircleDashed, ChevronDown, Ban } from 'lucide-react'
import type { TramiteResultado } from '../types'
import { useAuthStore } from '../../../stores/auth'
import { useMarcarResultado } from '../hooks/useTramites'
import { useNotificationsStore } from '../../../stores/notifications'

interface ResultadoChipProps {
  numero: string
  resultado: TramiteResultado
}

const META: Record<TramiteResultado, { label: string; color: string; bg: string; icon: typeof CheckCircle2 }> = {
  pendiente: { label: 'Sin resolver', color: 'var(--fg-2)', bg: 'var(--surface-400)', icon: CircleDashed },
  aprobado: { label: 'Aprobado', color: '#1f8a65', bg: 'rgba(31,138,101,0.12)', icon: CheckCircle2 },
  rechazado: { label: 'Rechazado', color: 'var(--color-error)', bg: 'rgba(207,45,86,0.12)', icon: XCircle },
  // mig 101: desistido = el iniciador no respondió (automático por timer o manual).
  desistido: { label: 'Desistido', color: '#78909c', bg: 'rgba(120,144,156,0.18)', icon: Ban },
}

const OPCIONES: TramiteResultado[] = ['aprobado', 'rechazado', 'desistido', 'pendiente']

/**
 * Chip que muestra el resultado del tramite (aprobado/rechazado/sin resolver),
 * marca paralela al estado FSM (mig 74). Supervisor/admin (nivel <= 2) puede
 * cambiarlo desde un dropdown; el backend es la fuente de verdad (403 al resto).
 */
export function ResultadoChip({ numero, resultado }: ResultadoChipProps) {
  const puedeMarcar = useAuthStore((s) => s.hasPermission(2))
  const push = useNotificationsStore((s) => s.push)
  const marcar = useMarcarResultado(numero)
  const [abierto, setAbierto] = useState(false)

  const meta = META[resultado]
  const Icon = meta.icon

  async function elegir(nuevo: TramiteResultado) {
    setAbierto(false)
    if (nuevo === resultado) return
    try {
      await marcar.mutateAsync({ resultado: nuevo })
      push({ kind: 'success', title: `Resultado: ${META[nuevo].label}` })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo marcar', body: (e as Error).message })
    }
  }

  const chip = (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        padding: '3px 9px', borderRadius: 'var(--radius-lg)',
        fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600,
        color: meta.color, background: meta.bg,
      }}
    >
      <Icon size={13} strokeWidth={2} />
      {meta.label}
      {puedeMarcar && <ChevronDown size={12} strokeWidth={2} style={{ opacity: 0.7 }} />}
    </span>
  )

  if (!puedeMarcar) return chip

  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        disabled={marcar.isPending}
        title="Marcar resultado del trámite"
        style={{ border: 'none', background: 'none', padding: 0, cursor: marcar.isPending ? 'wait' : 'pointer' }}
      >
        {chip}
      </button>
      {abierto && (
        <>
          <div
            onClick={() => setAbierto(false)}
            style={{ position: 'fixed', inset: 0, zIndex: 40 }}
          />
          <div
            style={{
              position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 50,
              background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-card)',
              minWidth: 160, overflow: 'hidden',
            }}
          >
            {OPCIONES.map((op) => {
              const m = META[op]
              const OpIcon = m.icon
              return (
                <button
                  key={op}
                  type="button"
                  onClick={() => { void elegir(op) }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                    padding: '8px 12px', border: 'none', background: op === resultado ? 'var(--surface-300)' : 'transparent',
                    cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13,
                    color: m.color, textAlign: 'left',
                  }}
                >
                  <OpIcon size={14} strokeWidth={2} />
                  {m.label}
                </button>
              )
            })}
          </div>
        </>
      )}
    </span>
  )
}
