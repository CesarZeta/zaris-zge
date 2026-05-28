import { useState } from 'react'
import { ClipboardList, FileText, CalendarClock, ChevronRight } from 'lucide-react'
import { usePlantillas, usePlantillaDetalle } from '../hooks/useEncuestas'
import type { EncuestaPlantilla, EncuestaPregunta } from '../lib/types'

// Vista de solo-lectura del catálogo de plantillas (encuestas configuradas).
// Lista las plantillas activas (reclamos / turnos) y, al elegir una, muestra
// sus preguntas agrupadas por rama con las opciones de cada una. El contenido es
// la encuesta estándar ZARIS (no editable por municipio en v1, §42); por eso
// esto es informativo, no un editor.

const TIPO_META: Record<string, { label: string; icon: typeof FileText; color: string }> = {
  reclamos: { label: 'Reclamos', icon: FileText, color: '#b3380a' },
  turnos: { label: 'Turnos', icon: CalendarClock, color: '#1f8a65' },
  tramites: { label: 'Trámites', icon: FileText, color: '#6a1b9a' },
}

const RAMA_LABEL: Record<string, string> = {
  todos: 'Para todos',
  satisfechos: 'Si está satisfecho (4-5)',
  neutrales: 'Si es neutral (3)',
  insatisfechos: 'Si está insatisfecho (1-2)',
}
const RAMA_ORDEN = ['todos', 'insatisfechos', 'neutrales', 'satisfechos']

const TIPO_PREGUNTA_LABEL: Record<string, string> = {
  likert5: 'Escala 1 a 5',
  texto_libre: 'Texto libre',
  si_no: 'Sí / No',
  multiple: 'Opción múltiple',
}

export function PlantillasView() {
  const { data, isLoading, isError, error } = usePlantillas()
  const [selId, setSelId] = useState<number | null>(null)

  const plantillas = data ?? []
  // auto-seleccionar la primera si no hay nada elegido
  const activeId = selId ?? plantillas[0]?.id_encuesta_plantilla ?? null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ margin: 0, color: 'var(--fg-2)', fontSize: '0.88rem' }}>
        Encuestas configuradas en el sistema. Elegí una para ver sus preguntas. El contenido es la encuesta
        estándar ZARIS (no editable por municipio en esta versión).
      </p>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar las plantillas'}</div>}

      {isLoading ? (
        <p style={vacio}>Cargando…</p>
      ) : plantillas.length === 0 ? (
        <div style={emptyCard}>
          <ClipboardList size={26} strokeWidth={1.5} color="var(--fg-3)" />
          <p style={{ margin: '10px 0 0', fontWeight: 600, color: 'var(--fg-1)' }}>Sin plantillas activas</p>
        </div>
      ) : (
        <div style={layout}>
          <div style={listCol}>
            {plantillas.map((p) => (
              <PlantillaCard
                key={p.id_encuesta_plantilla}
                p={p}
                active={p.id_encuesta_plantilla === activeId}
                onClick={() => setSelId(p.id_encuesta_plantilla)}
              />
            ))}
          </div>
          <div style={detailCol}>
            {activeId != null && <PlantillaDetalle id={activeId} />}
          </div>
        </div>
      )}
    </div>
  )
}

function PlantillaCard({ p, active, onClick }: { p: EncuestaPlantilla; active: boolean; onClick: () => void }) {
  const meta = TIPO_META[p.tipo] ?? { label: p.tipo, icon: ClipboardList, color: 'var(--fg-2)' }
  const Icon = meta.icon
  return (
    <button
      onClick={onClick}
      style={{
        ...cardBtn,
        borderColor: active ? 'var(--zaris-orange)' : 'var(--border-primary)',
        background: active ? 'rgba(245,78,0,0.05)' : 'var(--surface-100)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <Icon size={18} strokeWidth={1.5} color={meta.color} />
        <div style={{ minWidth: 0, textAlign: 'left' }}>
          <div style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: '0.9rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {p.nombre}
          </div>
          <div style={{ fontSize: '0.74rem', color: meta.color, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
            {meta.label} · v{p.version}
          </div>
        </div>
      </div>
      <ChevronRight size={16} strokeWidth={1.5} color={active ? 'var(--zaris-orange)' : 'var(--fg-3)'} style={{ flexShrink: 0 }} />
    </button>
  )
}

function PlantillaDetalle({ id }: { id: number }) {
  const { data, isLoading } = usePlantillaDetalle(id)
  if (isLoading) return <p style={vacio}>Cargando preguntas…</p>
  if (!data) return <p style={{ color: 'var(--color-error)' }}>No se pudo cargar el detalle.</p>

  // agrupar por rama, ordenando ramas y preguntas dentro de cada una
  const porRama = new Map<string, EncuestaPregunta[]>()
  for (const q of data.preguntas) {
    if (!porRama.has(q.rama)) porRama.set(q.rama, [])
    porRama.get(q.rama)!.push(q)
  }
  const rank = (r: string) => {
    const i = RAMA_ORDEN.indexOf(r)
    return i === -1 ? RAMA_ORDEN.length : i
  }
  const ramas = [...porRama.keys()].sort((a, b) => rank(a) - rank(b))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.05rem', color: 'var(--fg-1)' }}>
          {data.nombre}
        </h3>
        {data.descripcion && (
          <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: 'var(--fg-3)' }}>{data.descripcion}</p>
        )}
      </div>

      {ramas.map((rama) => (
        <div key={rama}>
          <div style={ramaTitle}>{RAMA_LABEL[rama] ?? rama}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {porRama.get(rama)!
              .slice()
              .sort((a, b) => a.orden - b.orden)
              .map((q) => <PreguntaRow key={q.id_encuesta_pregunta} q={q} />)}
          </div>
        </div>
      ))}
    </div>
  )
}

function PreguntaRow({ q }: { q: EncuestaPregunta }) {
  return (
    <div style={qCard}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 500, color: 'var(--fg-1)', fontSize: '0.9rem' }}>{q.texto}</span>
        {q.obligatoria && <span style={obligTag}>obligatoria</span>}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6, alignItems: 'center' }}>
        <span style={tipoTag}>{TIPO_PREGUNTA_LABEL[q.tipo] ?? q.tipo}</span>
        {q.opciones.length > 0 && (
          <span style={{ fontSize: '0.8rem', color: 'var(--fg-3)' }}>
            {q.opciones
              .slice()
              .sort((a, b) => a.orden - b.orden)
              .map((o) => o.texto)
              .join(' · ')}
          </span>
        )}
      </div>
    </div>
  )
}

const layout: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'minmax(0, 300px) 1fr', gap: 18, alignItems: 'start' }
const listCol: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 8 }
const detailCol: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 18,
}
const cardBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
  border: '1px solid var(--border-primary)', borderRadius: 10, padding: '12px 14px',
  cursor: 'pointer', fontFamily: 'var(--font-display)', width: '100%',
}
const ramaTitle: React.CSSProperties = {
  fontSize: '0.74rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
  color: 'var(--fg-3)', marginBottom: 8, paddingBottom: 4, borderBottom: '1px solid var(--border-primary)',
}
const qCard: React.CSSProperties = {
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)', borderRadius: 8, padding: '10px 12px',
}
const tipoTag: React.CSSProperties = {
  fontSize: '0.72rem', fontWeight: 600, color: 'var(--fg-2)', background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)', borderRadius: 999, padding: '2px 8px',
}
const obligTag: React.CSSProperties = {
  fontSize: '0.68rem', fontWeight: 600, color: '#b3380a', background: 'rgba(245,78,0,0.1)',
  borderRadius: 999, padding: '1px 7px',
}
const emptyCard: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 36,
}
const vacio: React.CSSProperties = { color: 'var(--fg-3)', fontSize: 13, textAlign: 'center', padding: 20 }
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
