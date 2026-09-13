/**
 * Historia clínica mínima viable (F5 plan ATENCION, migs 107 + 107b).
 *
 * Timeline unificado por ciudadano: atenciones por turno (turno_atencion, mig 86)
 * + atenciones en la Guardia (emergencia_atencion atendida|ausente, mig 106),
 * servido por `GET /turnos/atenciones/historia`. Dato sensible: el permiso lo
 * decide SOLO el backend (`/permiso`, misma función que el guard) y cada
 * lectura queda registrada — por eso todo acá es lazy (monta recién cuando la
 * solapa / el details / el modal están visibles) y sin refetch por foco.
 *
 * Tres piezas:
 *  - `HistoriaClinicaPanel`: el timeline embebible (solapas, `<details>`, modal).
 *  - `HistoriaClinicaModal`: Panel dentro del `Modal` de Agenda. REGLA: se abre
 *    SOLO desde nivel de página (tablas de PanelGuardia / PanelAtencion), NUNCA
 *    encima de otro `Modal` de Agenda (comparten el listener de ESC y se
 *    cerrarían juntos). Dentro de otros modales se embebe el Panel.
 *  - `BotonHistoriaClinica`: botón gateado por `/permiso` (fail-closed visual).
 *
 * Estilos: SOLO tokens del DS (dark mode sale gratis) + Badge/EmptyState/Skeleton/
 * Button compartidos de `ui/`. Sin hex/rgba/color-mix nuevos.
 */
import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Stethoscope } from 'lucide-react'
import { Modal } from '../../agenda/components/Modal'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { httpStatus } from '../../../lib/api'
import { useHistoriaClinica, useHistoriaClinicaPermiso, usePuedeHistoriaClinica } from '../hooks/useTurnos'
import type { HistoriaClinicaContexto, HistoriaClinicaItem } from '../types/turno'

const LIMITE_PAGINA = 100
const TOPE_BACKEND = 200

/* ── Panel ─────────────────────────────────────────────────────────────── */

export function HistoriaClinicaPanel({ idCiudadano, contexto, maxAlto = 360, compacto = false }: {
  idCiudadano: number
  contexto: HistoriaClinicaContexto
  /** Alto máximo del timeline; el <ol> scrollea. */
  maxAlto?: number
  /** Sin encabezado grande (dentro de <details>). */
  compacto?: boolean
}) {
  const qc = useQueryClient()
  const [limit, setLimit] = useState(LIMITE_PAGINA)
  // Cambio de paciente sin remontar (defensa extra al `key` del Modal): volver a la 1ª página.
  useEffect(() => { setLimit(LIMITE_PAGINA) }, [idCiudadano])

  const q = useHistoriaClinica(idCiudadano, contexto, true, limit)
  const permiso = useHistoriaClinicaPermiso()
  const status = httpStatus(q.error)

  // Un 403 acá = el permiso cambió desde que se cacheó: que el botón desaparezca.
  useEffect(() => {
    if (status === 403) qc.invalidateQueries({ queryKey: ['turnos', 'historia', 'permiso'] })
  }, [status, qc])

  if (q.isLoading) {
    return (
      <div aria-busy="true" aria-label="Cargando historia clínica" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Skeleton height={56} />
        <Skeleton height={56} />
        <Skeleton height={56} />
      </div>
    )
  }

  if (q.isError) {
    if (status === 403) {
      return <EmptyState title="Sin permiso para ver la historia clínica" description={q.error.message} />
    }
    if (status === 404) {
      return <EmptyState title="Ciudadano no encontrado" />
    }
    if (status === 429) {
      return <EmptyState title="Demasiadas consultas seguidas" description="Esperá un minuto y volvé a intentar" />
    }
    return (
      <div role="alert" style={bannerError}>
        <span style={{ flex: 1 }}>{q.error.message}</span>
        {/* react-query v5: tras un error, isLoading queda false durante el refetch → usar isFetching */}
        <Button variant="ghost" type="button" disabled={q.isFetching} onClick={() => q.refetch()}>
          {q.isFetching ? 'Reintentando…' : 'Reintentar'}
        </Button>
      </div>
    )
  }

  const data = q.data
  if (!data) return null
  // Nunca pintar la historia de otro id (cache / carrera de keys).
  if (data.ciudadano.id_ciudadano !== idCiudadano) return null

  const c = data.ciudadano
  const { items, total } = data
  const restantes = total - items.length
  const puedeVerMas = restantes > 0 && limit < TOPE_BACKEND
  const topeAlcanzado = total > TOPE_BACKEND && limit >= TOPE_BACKEND

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {!compacto && (
        <header style={encabezado}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={nombrePaciente}>{nombreCompleto(c.apellido, c.nombre)}</span>
            <Badge kind="neutral">{total} {total === 1 ? 'registro' : 'registros'}</Badge>
            {!c.activo && <Badge kind="warn">Dado de baja en la BUC</Badge>}
          </div>
          <div style={lineaDoc}>{lineaIdentidad(c.doc_tipo, c.doc_nro, c.edad, c.fecha_nac)}</div>
          <div style={microLabel}>Confidencial · acceso registrado</div>
          {permiso.data?.motivo === 'admin_sin_config' && (
            <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 4 }}>
              Falta configurar la gestión Salud (id_area_salud, Config → Sistema): hoy solo los administradores ven la historia clínica.
            </div>
          )}
        </header>
      )}

      {total === 0 ? (
        <EmptyState
          title="Sin atenciones registradas"
          description="Este ciudadano no tiene atenciones registradas por turno ni en la Guardia."
        />
      ) : (
        <>
          {/* El scroll va en el wrapper (no en el <ol>): con overflow en el <ol> el punto
              del riel, que cuelga a la izquierda del borde, quedaría recortado. */}
          <div style={{ maxHeight: maxAlto, overflowY: 'auto', paddingRight: 2 }}>
            <ol role="list" aria-label="Historia clínica" style={riel}>
              {items.map((it, i) => {
                const anio = new Date(it.fecha_hora).getFullYear()
                const anioPrev = i > 0 ? new Date(items[i - 1].fecha_hora).getFullYear() : null
                return (
                  <li key={`${it.origen}-${it.id}`} style={{ position: 'relative', listStyle: 'none', marginBottom: 10 }}>
                    {anio !== anioPrev && <div style={rotuloAnio}>{anio}</div>}
                    <ItemHistoria it={it} />
                  </li>
                )
              })}
            </ol>
          </div>
          {puedeVerMas && (
            <div>
              <Button variant="ghost" type="button" onClick={() => setLimit((l) => Math.min(TOPE_BACKEND, l + LIMITE_PAGINA))}>
                Ver más ({restantes} {restantes === 1 ? 'restante' : 'restantes'})
              </Button>
            </div>
          )}
          {topeAlcanzado && (
            <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              Se muestran los {TOPE_BACKEND} más recientes de {total}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function ItemHistoria({ it }: { it: HistoriaClinicaItem }) {
  const esTurno = it.origen === 'turno'
  const ausente = it.estado === 'ausente'
  const colorPunto = ausente ? 'var(--color-error)' : esTurno ? 'var(--color-success)' : 'var(--zaris-gold)'
  const meta = [it.gestion_nombre, it.ubicacion_nombre, it.profesional_nombre].filter((s): s is string => !!s)

  return (
    <article style={{ ...cardItem, opacity: ausente ? 0.8 : 1 }}>
      <span aria-hidden="true" style={{ ...punto, borderColor: colorPunto }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <time dateTime={it.fecha_hora} style={fechaMono}>{formatearFechaHora(it.fecha_hora)}</time>
        {esTurno ? <Badge kind="success">Turno</Badge> : <Badge kind="warn">Guardia</Badge>}
        {ausente && <Badge kind="error">No se presentó</Badge>}
        <span style={tituloItem}>{it.titulo}</span>
      </div>
      {(meta.length > 0 || it.numero_operativo) && (
        <div style={lineaMeta}>
          {meta.join(' · ')}
          {it.numero_operativo && (
            <span style={{ fontFamily: 'var(--font-mono)', marginLeft: meta.length > 0 ? 8 : 0 }}>{it.numero_operativo}</span>
          )}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
        {it.motivo_derivacion && <Campo label="Motivo de derivación" texto={it.motivo_derivacion} />}
        {it.intervencion ? (
          <Campo label="Intervención" texto={it.intervencion} />
        ) : ausente ? (
          <div>
            <div style={labelCampo}>Intervención</div>
            <div style={{ fontSize: 13, color: 'var(--fg-3)', fontStyle: 'italic' }}>Sin atención registrada (no se presentó)</div>
          </div>
        ) : null}
        {it.recomendaciones && <Campo label="Recomendaciones" texto={it.recomendaciones} />}
      </div>
    </article>
  )
}

function Campo({ label, texto }: { label: string; texto: string }) {
  return (
    <div>
      <div style={labelCampo}>{label}</div>
      <div style={{ fontSize: 13, color: 'var(--fg-1)', whiteSpace: 'pre-wrap', lineHeight: 1.45 }}>{texto}</div>
    </div>
  )
}

/* ── Modal (nivel de página únicamente) ────────────────────────────────── */

export function HistoriaClinicaModal({ idCiudadano, nombre, contexto, onClose }: {
  /** null = cerrado. */
  idCiudadano: number | null
  nombre?: string | null
  contexto: HistoriaClinicaContexto
  onClose: () => void
}) {
  return (
    <Modal
      open={idCiudadano != null}
      onClose={onClose}
      title={nombre ? `Historia clínica · ${nombre}` : 'Historia clínica'}
      width={760}
      footer={<Button variant="ghost" type="button" onClick={onClose}>Cerrar</Button>}
    >
      {/* `key` remonta al cambiar de paciente: cero estado residual (§23/§29). */}
      {idCiudadano != null && (
        <HistoriaClinicaPanel key={idCiudadano} idCiudadano={idCiudadano} contexto={contexto} maxAlto={480} />
      )}
    </Modal>
  )
}

/* ── Botón gateado por /permiso ────────────────────────────────────────── */

export function BotonHistoriaClinica({ idCiudadano, nombre, onAbrir, style }: {
  idCiudadano: number | null
  nombre?: string | null
  onAbrir: (idCiudadano: number, nombre?: string | null) => void
  /** Reusar el `btnSec` del host. */
  style?: React.CSSProperties
}) {
  // Fail-closed visual: mientras carga o si /permiso falla, no se muestra.
  const puede = usePuedeHistoriaClinica()
  if (idCiudadano == null || !puede) return null
  return (
    <button
      type="button"
      onClick={() => onAbrir(idCiudadano, nombre)}
      style={style}
      title="Ver historia clínica (queda registrado)"
      aria-haspopup="dialog"
    >
      <Stethoscope size={13} strokeWidth={1.5} /> Historia clínica
    </button>
  )
}

/* ── Helpers ───────────────────────────────────────────────────────────── */

function nombreCompleto(apellido: string | null, nombre: string | null): string {
  if (apellido && nombre) return `${apellido}, ${nombre}`
  return apellido ?? nombre ?? 'Ciudadano'
}

function lineaIdentidad(docTipo: string | null, docNro: string | null, edad: number | null, fechaNac: string | null): string {
  const partes: string[] = []
  if (docNro) partes.push(`${docTipo ?? 'DNI'} ${docNro}`)
  if (edad != null) partes.push(`${edad} ${edad === 1 ? 'año' : 'años'}`)
  if (fechaNac) partes.push(`nac. ${formatearFecha(fechaNac)}`)
  return partes.join(' · ')
}

/** 'YYYY-MM-DD' → 'DD/MM/YYYY' sin pasar por Date (evita el corrimiento por zona). */
function formatearFecha(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso
}

function formatearFechaHora(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
}

/* ── Estilos (solo tokens) ─────────────────────────────────────────────── */

const encabezado: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', padding: 12, display: 'flex', flexDirection: 'column', gap: 4,
}
const nombrePaciente: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 600, color: 'var(--fg-1)',
}
const lineaDoc: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-2)' }
const microLabel: React.CSSProperties = {
  fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-4)',
  fontFamily: 'var(--font-display)',
}
const riel: React.CSSProperties = {
  margin: 0, marginLeft: 8, padding: 0, paddingLeft: 18, paddingTop: 2,
  borderLeft: '2px solid var(--border-medium)',
}
const rotuloAnio: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em',
  color: 'var(--fg-3)', margin: '2px 0 6px',
}
const cardItem: React.CSSProperties = {
  position: 'relative', background: 'var(--surface-300)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)', padding: '10px 12px',
}
const punto: React.CSSProperties = {
  position: 'absolute', left: -24, top: 14, width: 10, height: 10, borderRadius: '50%',
  background: 'var(--surface-100)', border: '2px solid var(--border-medium)', boxSizing: 'border-box',
}
const fechaMono: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-2)' }
const tituloItem: React.CSSProperties = { fontSize: 13.5, fontWeight: 600, color: 'var(--fg-1)' }
const lineaMeta: React.CSSProperties = { fontSize: 12, color: 'var(--fg-3)', marginTop: 4 }
const labelCampo: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)', marginBottom: 2,
}
const bannerError: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
  background: 'var(--surface-300)', borderLeft: '3px solid var(--color-error)',
  borderRadius: 'var(--radius-md)', padding: '10px 12px', fontSize: 13, color: 'var(--fg-1)',
}
