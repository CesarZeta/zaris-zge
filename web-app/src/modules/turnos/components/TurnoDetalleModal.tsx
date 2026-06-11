import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { Button } from '../../../ui'
import { useAtencionesCiudadano } from '../hooks/useTurnos'
import { HistorialAtenciones, AtencionItem } from './HistorialAtenciones'
import type { EstadoTurno, Turno } from '../types/turno'

const ESTADO_LABEL: Record<EstadoTurno, string> = {
  reservado: 'Reservado',
  cumplido: 'Cumplido',
  cancelado: 'Cancelado',
}
const ESTADO_COLOR: Record<EstadoTurno, { bg: string; fg: string }> = {
  reservado: { bg: 'rgba(245,127,23,0.14)', fg: '#b35900' },
  cumplido: { bg: 'rgba(31,138,101,0.16)', fg: '#1f8a65' },
  cancelado: { bg: 'rgba(198,40,40,0.12)', fg: '#c62828' },
}

type Solapa = 'turno' | 'historia'

/**
 * Detalle de un turno (solo lectura). Se abre al clickear un turno en la lista,
 * la agenda o atendidos. Solapas: datos del turno (+ su atención registrada si
 * la tiene) e historia de atenciones del ciudadano (mig 86).
 */
export function TurnoDetalleModal({ turno, onClose }: { turno: Turno | null; onClose: () => void }) {
  const [solapa, setSolapa] = useState<Solapa>('turno')

  useEffect(() => {
    if (turno) setSolapa('turno')
  }, [turno])

  // La atención de ESTE turno se busca dentro de la historia del ciudadano
  // (mismo endpoint scopeado; sin backend extra).
  const atenciones = useAtencionesCiudadano(turno?.id_ciudadano ?? null)
  const atencionDelTurno = (atenciones.data ?? []).find((a) => a.id_turno === turno?.id_turno) ?? null

  if (!turno) return null
  const c = ESTADO_COLOR[turno.estado]

  return (
    <Modal
      open={turno != null}
      onClose={onClose}
      title={`Turno · ${turno.fecha} ${turno.hora_inicio.slice(0, 5)}`}
      width={640}
      footer={<Button variant="ghost" onClick={onClose}>Cerrar</Button>}
    >
      {/* Solapas */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
        <button onClick={() => setSolapa('turno')} style={tabBtn(solapa === 'turno')}>Turno</button>
        <button onClick={() => setSolapa('historia')} style={tabBtn(solapa === 'historia')}>
          Historia de atenciones{atenciones.data ? ` (${atenciones.data.length})` : ''}
        </button>
      </div>

      {solapa === 'turno' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={grid2}>
            <Dato label="Estado">
              <span style={{ background: c.bg, color: c.fg, fontSize: '0.74rem', fontWeight: 600, padding: '2px 10px', borderRadius: 999 }}>
                {ESTADO_LABEL[turno.estado]}
              </span>
            </Dato>
            <Dato label="Fecha y hora">
              <span style={mono}>{turno.fecha} · {turno.hora_inicio.slice(0, 5)}–{turno.hora_fin.slice(0, 5)}</span>
            </Dato>
            <Dato label="Ciudadano">
              {turno.ciudadano_nombre ?? '—'}
              {turno.ciudadano_dni && <span style={meta}> · DNI {turno.ciudadano_dni}</span>}
            </Dato>
            <Dato label="Atiende">
              {turno.recurso_nombre ?? turno.agente_nombre ?? '—'}
              <span style={meta}> · {turno.id_espacio != null ? 'Lugar de atención' : 'Agente'}</span>
            </Dato>
            <Dato label="Prestación">{turno.prestacion_nombre ?? '—'}</Dato>
            {turno.registra_atencion && (
              <Dato label="Tipo">
                <span style={{ background: 'rgba(245,78,0,0.12)', color: 'var(--zaris-orange)', fontSize: '0.74rem', fontWeight: 600, padding: '2px 10px', borderRadius: 999 }}>
                  Registra historia de atención
                </span>
              </Dato>
            )}
          </div>

          {turno.observaciones && (
            <Dato label="Observaciones">
              <span style={{ whiteSpace: 'pre-wrap', color: 'var(--fg-2)', fontSize: 13 }}>{turno.observaciones}</span>
            </Dato>
          )}

          {/* Atención registrada de este turno (si existe) */}
          {atencionDelTurno && (
            <div>
              <div style={seccionLbl}>Atención registrada en este turno</div>
              <AtencionItem a={atencionDelTurno} resaltada />
            </div>
          )}
          {!atencionDelTurno && turno.registra_atencion && turno.estado === 'cumplido' && !atenciones.isLoading && (
            <div style={{ ...meta, fontStyle: 'italic' }}>
              Este turno no tiene una atención registrada (o no está dentro de tu alcance de consulta).
            </div>
          )}
        </div>
      ) : (
        <HistorialAtenciones
          idCiudadano={turno.id_ciudadano}
          titulo={`Historia de atenciones de ${turno.ciudadano_nombre ?? 'ciudadano'}`}
          resaltarTurno={turno.id_turno}
          maxAlto={340}
        />
      )}
    </Modal>
  )
}

function Dato({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={seccionLbl}>{label}</div>
      <div style={{ fontSize: 13.5, color: 'var(--fg-1)' }}>{children}</div>
    </div>
  )
}

function tabBtn(active: boolean): React.CSSProperties {
  return {
    fontFamily: 'var(--font-display)', fontSize: 12.5, cursor: 'pointer',
    padding: '6px 14px', borderRadius: 8, fontWeight: active ? 600 : 400,
    border: '1px solid ' + (active ? 'var(--zaris-orange)' : 'var(--border-medium)'),
    background: active ? 'rgba(245,78,0,0.08)' : 'transparent',
    color: active ? 'var(--zaris-orange)' : 'var(--fg-2)',
  }
}

const grid2: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 16px',
}
const seccionLbl: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
  color: 'var(--fg-3)', marginBottom: 4,
}
const mono: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 12.5, color: 'var(--fg-1)' }
const meta: React.CSSProperties = { fontSize: 12, color: 'var(--fg-3)' }
