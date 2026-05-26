import { useEffect, useState } from 'react'
import {
  BellRing, Check, ClipboardCheck, Loader2, Palette, Settings2,
} from 'lucide-react'
import { useConfigGeneral, useActualizarConfigParam } from '../hooks/useConfig'
import type { ConfigParam } from '../api/configApi'

// =============================================================================
// Catálogo de presentación: agrupa las claves crudas de configuracion_general
// en secciones con etiquetas legibles, ayuda y control apropiado. Cualquier
// clave no listada cae en la sección "Otros parámetros" con editor genérico
// (futuro-proof: una clave nueva no rompe la pantalla).
// =============================================================================

type Control = 'toggle' | 'number' | 'text' | 'color'

interface ParamMeta {
  clave: string
  label: string
  ayuda: string
  control: Control
  /** Texto on/off para toggles, opcional. */
  onLabel?: string
  offLabel?: string
  /** Sufijo para números (ej. "días"). */
  sufijo?: string
}

interface Seccion {
  id: string
  titulo: string
  descripcion: string
  icon: typeof Settings2
  claves: ParamMeta[]
}

const SECCIONES: Seccion[] = [
  {
    id: 'encuestas',
    titulo: 'Encuestas de satisfacción',
    descripcion: 'Controlan el envío de encuestas (CSAT) al cierre de reclamos.',
    icon: BellRing,
    claves: [
      {
        clave: 'encuestas_activas',
        label: 'Enviar encuestas al cerrar reclamos',
        ayuda: 'Si está activo, cada reclamo resuelto dispara una encuesta de satisfacción al ciudadano. Desactivarlo detiene el envío en todo el municipio.',
        control: 'toggle',
      },
      {
        clave: 'encuestas_antifatiga_activo',
        label: 'Control anti-fatiga (no repetir antes de 30 días)',
        ayuda: 'Si está activo, no se reenvía una encuesta al mismo ciudadano de la misma subárea dentro de los 30 días. Desactivarlo permite encuestar en cada cierre.',
        control: 'toggle',
      },
    ],
  },
  {
    id: 'reclamos_ot',
    titulo: 'Reclamos y Órdenes de Trabajo',
    descripcion: 'Reglas operativas del circuito de reclamos y auditoría.',
    icon: ClipboardCheck,
    claves: [
      {
        clave: 'auditor_misma_subarea_permitido',
        label: 'Permitir que el auditor sea de la misma subárea',
        ayuda: 'Si está desactivado, un auditor no puede auditar reclamos de su propia subárea (separación de funciones).',
        control: 'toggle',
      },
      {
        clave: 'ot_pendiente_dias_vencimiento',
        label: 'Vencimiento de OT pendiente',
        ayuda: 'Días máximos que una orden de trabajo en estado Pendiente puede quedar sin reasignarse.',
        control: 'number',
        sufijo: 'días',
      },
    ],
  },
  {
    id: 'app_vecinos',
    titulo: 'App Vecinos (PWA)',
    descripcion: 'Marca y textos que ven los vecinos en la app pública.',
    icon: Palette,
    claves: [
      {
        clave: 'municipio_descripcion',
        label: 'Texto de bienvenida (login App Vecinos)',
        ayuda: 'Frase corta que aparece en la pantalla de inicio de sesión de la PWA. Ej: "Servicio oficial de atención al vecino".',
        control: 'text',
      },
      {
        clave: 'municipio_color_primary',
        label: 'Color primario',
        ayuda: 'Color principal de la App Vecinos (botones y énfasis). Formato hex #RRGGBB.',
        control: 'color',
      },
      {
        clave: 'municipio_color_accent',
        label: 'Color de acento',
        ayuda: 'Color secundario opcional (badges y links) de la App Vecinos. Formato hex #RRGGBB.',
        control: 'color',
      },
    ],
  },
]

// Claves que se gestionan en OTRAS pantallas y no deben aparecer acá para no
// duplicar edición (nombre/logo del municipio viven en la pestaña Identidad).
const CLAVES_OCULTAS = new Set(['municipio_nombre', 'municipio_logo_url'])

const CLAVES_CONOCIDAS = new Set(
  SECCIONES.flatMap((s) => s.claves.map((c) => c.clave)),
)

export function ParametrosSistemaView() {
  const { data: params, isLoading, isError } = useConfigGeneral()

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-3)', padding: 24 }}>
        <Loader2 size={16} className="spin" /> Cargando parámetros…
      </div>
    )
  }
  if (isError || !params) {
    return (
      <div style={{ color: 'var(--color-error)', padding: 16 }}>
        No se pudieron cargar los parámetros del sistema.
      </div>
    )
  }

  const porClave = new Map(params.map((p) => [p.clave, p]))

  // Claves presentes en DB que no están en ninguna sección ni ocultas.
  const otras = params.filter(
    (p) => !CLAVES_CONOCIDAS.has(p.clave) && !CLAVES_OCULTAS.has(p.clave),
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <p style={{ fontSize: '0.86rem', color: 'var(--fg-3)', margin: 0 }}>
        Ajustes generales del sistema. Cada cambio se guarda por separado y toma efecto de inmediato.
      </p>

      {SECCIONES.map((sec) => {
        const filas = sec.claves
          .map((meta) => ({ meta, param: porClave.get(meta.clave) }))
          .filter((f): f is { meta: ParamMeta; param: ConfigParam } => !!f.param)
        if (filas.length === 0) return null
        return (
          <SeccionCard key={sec.id} seccion={sec}>
            {filas.map(({ meta, param }) => (
              <ParamRow key={meta.clave} meta={meta} param={param} />
            ))}
          </SeccionCard>
        )
      })}

      {otras.length > 0 && (
        <SeccionCard
          seccion={{
            id: 'otros',
            titulo: 'Otros parámetros',
            descripcion: 'Claves de sistema no clasificadas. Editar con cuidado.',
            icon: Settings2,
            claves: [],
          }}
        >
          {otras.map((param) => (
            <ParamRow
              key={param.clave}
              meta={{
                clave: param.clave,
                label: param.clave,
                ayuda: param.descripcion || '',
                control: param.tipo === 'boolean' ? 'toggle' : param.tipo === 'integer' ? 'number' : 'text',
              }}
              param={param}
            />
          ))}
        </SeccionCard>
      )}
    </div>
  )
}

function SeccionCard({ seccion, children }: { seccion: Seccion; children: React.ReactNode }) {
  const Icon = seccion.icon
  return (
    <section style={{
      background: 'var(--surface-100)',
      border: '1px solid var(--border-primary)',
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      <header style={{
        display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '14px 16px',
        borderBottom: '1px solid var(--border-primary)',
        background: 'var(--surface-200)',
      }}>
        <div style={{
          width: 34, height: 34, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(245, 78, 0, 0.08)', borderRadius: 8,
        }}>
          <Icon size={18} strokeWidth={1.5} color="var(--zaris-orange)" />
        </div>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.98rem', color: 'var(--fg-1)' }}>
            {seccion.titulo}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--fg-3)', marginTop: 2 }}>
            {seccion.descripcion}
          </div>
        </div>
      </header>
      <div>{children}</div>
    </section>
  )
}

function ParamRow({ meta, param }: { meta: ParamMeta; param: ConfigParam }) {
  const mut = useActualizarConfigParam()
  const [valor, setValor] = useState(param.valor)
  const [savedFlash, setSavedFlash] = useState(false)

  // Si el dato remoto cambia (otra edición / refetch), re-sincronizar salvo que
  // el usuario tenga cambios sin guardar.
  useEffect(() => {
    setValor(param.valor)
  }, [param.valor])

  const dirty = valor !== param.valor
  const esBool = meta.control === 'toggle'
  const boolOn = String(param.valor).trim().toLowerCase() === 'true'

  const guardar = (nuevo: string) => {
    mut.mutate(
      { id_config: param.id_config, valor: nuevo },
      { onSuccess: () => { setSavedFlash(true); setTimeout(() => setSavedFlash(false), 1500) } },
    )
  }

  const guardarTexto = () => { if (dirty) guardar(valor.trim()) }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 16,
      padding: '13px 16px',
      borderTop: '1px solid var(--border-primary)',
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--fg-1)' }}>{meta.label}</div>
        <div style={{ fontSize: '0.78rem', color: 'var(--fg-3)', marginTop: 3, lineHeight: 1.45 }}>{meta.ayuda}</div>
        <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--fg-3)', opacity: 0.7 }}>
          {param.clave}
        </code>
      </div>

      <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
        {savedFlash && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-success)', fontSize: '0.76rem' }}>
            <Check size={14} /> Guardado
          </span>
        )}
        {mut.isPending && <Loader2 size={14} className="spin" color="var(--fg-3)" />}

        {esBool ? (
          <Toggle
            on={boolOn}
            disabled={mut.isPending}
            onChange={(next) => guardar(next ? 'true' : 'false')}
          />
        ) : meta.control === 'color' ? (
          <ColorField
            value={valor}
            onChange={setValor}
            onCommit={guardarTexto}
            disabled={mut.isPending}
            dirty={dirty}
          />
        ) : meta.control === 'number' ? (
          <NumberField
            value={valor}
            sufijo={meta.sufijo}
            onChange={setValor}
            onCommit={guardarTexto}
            disabled={mut.isPending}
            dirty={dirty}
          />
        ) : (
          <TextField
            value={valor}
            onChange={setValor}
            onCommit={guardarTexto}
            disabled={mut.isPending}
            dirty={dirty}
          />
        )}
      </div>
    </div>
  )
}

function Toggle({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={() => onChange(!on)}
      style={{
        position: 'relative', width: 46, height: 26, borderRadius: 13,
        border: 'none', cursor: disabled ? 'default' : 'pointer',
        background: on ? 'var(--zaris-orange)' : 'var(--border-medium)',
        transition: 'background 150ms ease', flexShrink: 0,
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span style={{
        position: 'absolute', top: 3, left: on ? 23 : 3,
        width: 20, height: 20, borderRadius: '50%', background: '#fff',
        transition: 'left 150ms ease', boxShadow: '0 1px 3px rgba(0,0,0,.25)',
      }} />
    </button>
  )
}

const inputBase: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.86rem',
  padding: '7px 10px', borderRadius: 8,
  border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
  color: 'var(--fg-1)', outline: 'none',
}

function commitKeys(e: React.KeyboardEvent) {
  if (e.key === 'Enter') { (e.target as HTMLInputElement).blur() }
}

function TextField({ value, onChange, onCommit, disabled, dirty }: {
  value: string; onChange: (v: string) => void; onCommit: () => void; disabled?: boolean; dirty: boolean
}) {
  return (
    <input
      value={value}
      disabled={disabled}
      placeholder="—"
      onChange={(e) => onChange(e.target.value)}
      onBlur={onCommit}
      onKeyDown={(e) => commitKeys(e)}
      style={{ ...inputBase, width: 220, borderColor: dirty ? 'var(--zaris-orange)' : 'var(--border-primary)' }}
    />
  )
}

function NumberField({ value, sufijo, onChange, onCommit, disabled, dirty }: {
  value: string; sufijo?: string; onChange: (v: string) => void; onCommit: () => void; disabled?: boolean; dirty: boolean
}) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <input
        type="number"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onCommit}
        onKeyDown={(e) => commitKeys(e)}
        style={{ ...inputBase, width: 90, borderColor: dirty ? 'var(--zaris-orange)' : 'var(--border-primary)' }}
      />
      {sufijo && <span style={{ fontSize: '0.8rem', color: 'var(--fg-3)' }}>{sufijo}</span>}
    </span>
  )
}

function ColorField({ value, onChange, onCommit, disabled, dirty }: {
  value: string; onChange: (v: string) => void; onCommit: () => void; disabled?: boolean; dirty: boolean
}) {
  const hexValido = /^#[0-9a-fA-F]{6}$/.test(value)
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <input
        type="color"
        value={hexValido ? value : '#000000'}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onCommit}
        style={{
          width: 34, height: 30, padding: 0, border: '1px solid var(--border-primary)',
          borderRadius: 6, background: 'transparent', cursor: disabled ? 'default' : 'pointer',
        }}
        title={value || 'Sin color'}
      />
      <input
        value={value}
        disabled={disabled}
        placeholder="#RRGGBB"
        onChange={(e) => onChange(e.target.value)}
        onBlur={onCommit}
        onKeyDown={(e) => commitKeys(e)}
        style={{ ...inputBase, width: 110, fontFamily: 'var(--font-mono)', fontSize: '0.8rem',
          borderColor: dirty ? 'var(--zaris-orange)' : 'var(--border-primary)' }}
      />
    </span>
  )
}
