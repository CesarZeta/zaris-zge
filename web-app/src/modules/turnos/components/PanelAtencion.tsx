/**
 * Panel de atención de la mesa (colero, mig 105 — F3 plan ATENCION).
 *
 * La grilla horaria de la mesa sirve para VER el día; este panel es para
 * OPERARLO: la fila de turnos ordenada por hora con los botones del ciclo
 * Llamar → Re-llamar → Cumplir / Ausente y el número que ve el vecino.
 *
 * Consume `GET /turnos` filtrado por ubicación+fecha (no los datos de la mesa):
 * ese listado ya trae `numero_diario`, `cant_llamados` y `registra_atencion`,
 * que la grilla no necesita. El scope por nivel lo aplica el backend.
 */
import { useEffect, useState } from 'react'
import { Phone, RotateCw, Check, UserX, Monitor, Copy } from 'lucide-react'
import { useTurnos, useLlamarTurno, useMarcarAusente, useCumplirTurno } from '../hooks/useTurnos'
import { CumplirTurnoModal } from './CumplirTurnoModal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAuthStore } from '../../../stores/auth'
import type { CumplirTurnoBody, EstadoTurno, Turno } from '../types/turno'

/** El puesto se repite en cada llamado del mismo operador: lo recordamos para
 *  que no lo retipee en cada turno. Es una comodidad local, no estado de negocio. */
const LS_PUESTO = 'zaris_colero_puesto'

const ESTADO_CHIP: Record<EstadoTurno, { bg: string; color: string; label: string }> = {
  reservado: { bg: 'rgba(245,127,23,0.14)', color: '#b35900', label: 'En espera' },
  llamado: { bg: 'rgba(245,78,0,0.16)', color: '#f54e00', label: 'Llamado' },
  cumplido: { bg: 'rgba(31,138,101,0.16)', color: '#1f8a65', label: 'Atendido' },
  ausente: { bg: 'rgba(198,40,40,0.14)', color: '#c62828', label: 'Ausente' },
  cancelado: { bg: 'var(--surface-400)', color: 'var(--fg-3)', label: 'Cancelado' },
}

export function PanelAtencion({
  idEspacioUbicacion, fecha, tokenPantalla, onCambio,
}: {
  idEspacioUbicacion: number
  fecha: string
  /** Sólo llega a nivel <= 2 (el backend lo omite al resto). */
  tokenPantalla: string | null
  onCambio?: () => void
}) {
  const push = useNotificationsStore((s) => s.push)
  const nivel = useAuthStore((s) => s.user?.nivel_acceso ?? 9)
  const [puesto, setPuesto] = useState(() => {
    try { return localStorage.getItem(LS_PUESTO) ?? '' } catch { return '' }
  })
  const [aCumplir, setACumplir] = useState<Turno | null>(null)

  useEffect(() => {
    try { localStorage.setItem(LS_PUESTO, puesto) } catch { /* sin storage: seguimos igual */ }
  }, [puesto])

  // fecha_desde = fecha_hasta = el día de la mesa. El backend NO tiene un
  // filtro `fecha` suelto y FastAPI ignoraría el param en silencio: el panel
  // habría listado los turnos de TODOS los días.
  const { data: turnos, isLoading } = useTurnos({
    id_espacio_ubicacion: idEspacioUbicacion, fecha_desde: fecha, fecha_hasta: fecha,
  })
  const llamar = useLlamarTurno()
  const ausente = useMarcarAusente()
  const cumplir = useCumplirTurno()

  const lista = (turnos ?? [])
    .filter((t) => t.estado !== 'cancelado')
    .sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))

  async function accion(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn()
      push({ kind: 'success', title: ok })
      onCambio?.()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo completar la acción',
            body: e instanceof Error ? e.message : undefined })
    }
  }

  const urlPantalla = tokenPantalla
    ? `${window.location.origin}${window.location.pathname}#/pantalla/${tokenPantalla}`
    : null

  return (
    <div style={card}>
      <div style={cabecera}>
        <div>
          <h2 style={titulo}>Atención del día</h2>
          <p style={sub}>
            Llamá al vecino por su número. El llamado se ve al instante en la pantalla de la sala.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto', flexWrap: 'wrap' }}>
          <label style={labelPuesto}>
            Puesto
            <input
              value={puesto}
              onChange={(e) => setPuesto(e.target.value.slice(0, 40))}
              placeholder="Box 1"
              style={inputPuesto}
            />
          </label>
          {/* El link es público: sólo se lo ofrecemos a quien administra la mesa. */}
          {urlPantalla && nivel <= 2 && (
            <>
              <a href={urlPantalla} target="_blank" rel="noreferrer" style={btnGhost} title="Abrir la pantalla de sala en otra pestaña">
                <Monitor size={14} strokeWidth={1.5} /> Abrir pantalla
              </a>
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(urlPantalla)
                    .then(() => push({ kind: 'success', title: 'Link de la pantalla copiado' }))
                    .catch(() => push({ kind: 'error', title: 'No se pudo copiar el link' }))
                }}
                style={btnGhost}
                title="Copiar el link para proyectarlo en la TV de la sala"
              >
                <Copy size={14} strokeWidth={1.5} /> Copiar link
              </button>
            </>
          )}
        </div>
      </div>

      {isLoading ? (
        <p style={vacio}>Cargando turnos…</p>
      ) : lista.length === 0 ? (
        <p style={vacio}>No hay turnos para esta ubicación en la fecha elegida.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={tabla}>
            <thead>
              <tr>
                <th style={{ ...th, width: 70 }}>N°</th>
                <th style={{ ...th, width: 64 }}>Hora</th>
                <th style={th}>Vecino</th>
                <th style={th}>Prestación</th>
                <th style={{ ...th, width: 110 }}>Estado</th>
                <th style={{ ...th, width: 250, textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((t) => {
                const chip = ESTADO_CHIP[t.estado] ?? ESTADO_CHIP.reservado
                const abierto = t.estado === 'reservado' || t.estado === 'llamado'
                const yaLlamado = t.estado === 'llamado'
                return (
                  <tr key={t.id_turno} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                      {t.numero_diario ?? <span style={{ color: 'var(--fg-3)' }}>—</span>}
                    </td>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{t.hora_inicio?.slice(0, 5)}</td>
                    <td style={td}>{t.ciudadano_nombre ?? '—'}</td>
                    <td style={{ ...td, color: 'var(--fg-2)' }}>{t.prestacion_nombre ?? '—'}</td>
                    <td style={td}>
                      <span style={{ ...chipBase, background: chip.bg, color: chip.color }}>{chip.label}</span>
                      {t.cant_llamados > 1 && (
                        <span style={vecesLlamado} title={`Llamado ${t.cant_llamados} veces`}>
                          ×{t.cant_llamados}
                        </span>
                      )}
                    </td>
                    <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {abierto ? (
                        <>
                          <button
                            onClick={() => accion(
                              () => llamar.mutateAsync({ id_turno: t.id_turno, puesto }),
                              yaLlamado ? `Volviste a llamar al ${t.numero_diario}` : 'Turno llamado',
                            )}
                            style={yaLlamado ? btnSec : btnAccion}
                            title={yaLlamado ? 'Volver a llamar (queda registrado)' : 'Llamar y asignar número'}
                          >
                            {yaLlamado
                              ? <><RotateCw size={13} strokeWidth={1.5} /> Re-llamar</>
                              : <><Phone size={13} strokeWidth={1.5} /> Llamar</>}
                          </button>
                          <button onClick={() => setACumplir(t)} style={btnSec} title="Registrar la atención">
                            <Check size={13} strokeWidth={1.5} /> Atendido
                          </button>
                          <button
                            onClick={() => accion(
                              () => ausente.mutateAsync({ id_turno: t.id_turno }),
                              'Marcado como ausente',
                            )}
                            style={btnSec}
                            title="No se presentó"
                          >
                            <UserX size={13} strokeWidth={1.5} /> Ausente
                          </button>
                        </>
                      ) : (
                        <span style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Reusa el modal de cumplir: si la prestación registra historia clínica
          exige la intervención, igual que desde el listado de Turnos (mig 86). */}
      <CumplirTurnoModal
        turno={aCumplir}
        onCancel={() => setACumplir(null)}
        onConfirm={(body: CumplirTurnoBody) => {
          const id = aCumplir?.id_turno
          setACumplir(null)
          if (id != null) accion(() => cumplir.mutateAsync({ id_turno: id, ...body }), 'Turno cumplido')
        }}
      />
    </div>
  )
}

const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', gap: 12,
}
const cabecera: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap',
}
const titulo: React.CSSProperties = {
  margin: 0, fontSize: '1rem', fontWeight: 700, fontFamily: 'var(--font-display)',
}
const sub: React.CSSProperties = { margin: '2px 0 0', fontSize: '0.82rem', color: 'var(--fg-3)' }
const labelPuesto: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--fg-2)',
}
const inputPuesto: React.CSSProperties = {
  width: 92, padding: '5px 8px', fontSize: '0.85rem', fontFamily: 'inherit',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 6,
}
const tabla: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }
const th: React.CSSProperties = {
  textAlign: 'left', padding: '6px 8px', fontSize: '0.72rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', borderBottom: '1px solid var(--border-medium)',
}
const td: React.CSSProperties = { padding: '8px', color: 'var(--fg-1)', verticalAlign: 'middle' }
const chipBase: React.CSSProperties = {
  display: 'inline-block', padding: '2px 8px', borderRadius: 999,
  fontSize: '0.74rem', fontWeight: 600,
}
const vecesLlamado: React.CSSProperties = {
  marginLeft: 6, fontSize: '0.72rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)',
}
const btnBase: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px',
  fontSize: '0.8rem', fontFamily: 'inherit', fontWeight: 600, borderRadius: 6,
  cursor: 'pointer', marginLeft: 6,
}
const btnAccion: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: '#fff', border: '1px solid var(--zaris-orange)',
}
const btnSec: React.CSSProperties = {
  ...btnBase, background: 'var(--surface-100)', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)',
}
const btnGhost: React.CSSProperties = {
  ...btnBase, marginLeft: 0, background: 'var(--surface-300)', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', textDecoration: 'none',
}
const vacio: React.CSSProperties = {
  padding: '18px 8px', textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem', margin: 0,
}
