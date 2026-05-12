import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useNotificationsStore } from '../../../stores/notifications'
import { CiudadanoSearch } from '../../agenda/components/CiudadanoSearch'
import type { CiudadanoMinimo } from '../../agenda/types/agenda'
import { TipoReclamoPicker } from '../components/TipoReclamoPicker'
import {
  useCrearReclamo,
  useEditarReclamo,
  useReclamoDetalle,
} from '../hooks/useReclamos'
import type {
  CanalOrigen,
  Prioridad,
  ReclamoCreate,
  ReclamoUpdate,
  TipoCatalogo,
} from '../types/reclamo'

type Modo = 'new' | 'edit'

interface FormState {
  // Identidad
  ciudadano: CiudadanoMinimo | null
  id_ciudadano: number | null
  // Tipo
  tipo: TipoCatalogo | null
  id_tipo_reclamo: number | null
  // Atributos
  prioridad: Prioridad
  canal_origen: CanalOrigen | ''
  direccion: string
  descripcion: string
  observaciones: string
  // Modo edit: nota libre para historial (solo si no estamos en Sin asignar)
  nota_historial: string
}

const emptyForm: FormState = {
  ciudadano: null, id_ciudadano: null,
  tipo: null, id_tipo_reclamo: null,
  prioridad: 'Media', canal_origen: '',
  direccion: '', descripcion: '',
  observaciones: '', nota_historial: '',
}

const PRIORIDADES: Prioridad[] = ['Baja', 'Media', 'Alta', 'Crítica']
const CANALES: { value: CanalOrigen; label: string }[] = [
  { value: 'web', label: 'Web' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'telefono', label: 'Teléfono' },
  { value: 'presencial', label: 'Presencial' },
  { value: 'oficio', label: 'Oficio' },
  { value: 'app_movil', label: 'App móvil' },
  { value: 'otro', label: 'Otro' },
]

export function FormView() {
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams<{ id?: string }>()
  const push = useNotificationsStore((s) => s.push)

  const modo: Modo = useMemo(() => {
    if (location.pathname.endsWith('/nuevo')) return 'new'
    return 'edit'
  }, [location.pathname])

  const id = params.id ? Number(params.id) : null
  const detalle = useReclamoDetalle(modo === 'edit' ? id : null)
  const crear = useCrearReclamo()
  const editar = useEditarReclamo(id)

  const [form, setForm] = useState<FormState>(emptyForm)
  const [errores, setErrores] = useState<Record<string, string>>({})

  // Solo en Sin asignar se puede editar todo. En otros estados vivos, sólo observaciones.
  const estadoActual = detalle.data?.estado ?? null
  const fullEdit = modo === 'new' || estadoActual === 'Sin asignar'
  const sloObservaciones = modo === 'edit' && !fullEdit

  // Hidratar form desde detalle al cargar
  useEffect(() => {
    if (modo === 'new') {
      setForm(emptyForm)
      return
    }
    if (!detalle.data) return
    const r = detalle.data
    setForm({
      ciudadano: r.id_ciudadano ? {
        id_ciudadano: r.id_ciudadano,
        apellido: r.ciudadano_apellido,
        nombre: r.ciudadano_nombre,
        doc_nro: r.doc_nro,
        cuil: r.cuil,
        telefono: r.telefono,
        email: r.ciudadano_email,
      } : null,
      id_ciudadano: r.id_ciudadano,
      tipo: r.id_tipo_reclamo ? {
        id_tipo_reclamo: r.id_tipo_reclamo,
        nombre: r.tipo_nombre ?? '',
        sla_dias: r.sla_dias,
        audit: r.tipo_audit ?? false,
        id_area: r.id_area,
        area_nombre: r.area_nombre,
        id_subarea: null,
        subarea_nombre: null,
      } : null,
      id_tipo_reclamo: r.id_tipo_reclamo,
      prioridad: r.prioridad ?? 'Media',
      canal_origen: (r.canal_origen as CanalOrigen | null) ?? '',
      direccion: r.direccion ?? r.domicilio_reclamo ?? '',
      descripcion: r.descripcion ?? '',
      observaciones: r.observaciones ?? '',
      nota_historial: '',
    })
  }, [modo, detalle.data])

  function setField<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((prev) => ({ ...prev, [k]: v }))
    if (errores[k as string]) {
      setErrores((prev) => { const n = { ...prev }; delete n[k as string]; return n })
    }
  }

  function validarAlta(): { ok: boolean; data?: ReclamoCreate } {
    const errs: Record<string, string> = {}
    if (!form.id_ciudadano) errs.ciudadano = 'Seleccioná un ciudadano'
    if (!form.descripcion.trim()) errs.descripcion = 'La descripción es requerida'
    if (form.descripcion.trim().length < 5) errs.descripcion = 'La descripción debe tener al menos 5 caracteres'

    setErrores(errs)
    if (Object.keys(errs).length > 0) return { ok: false }

    const data: ReclamoCreate = {
      id_ciudadano: form.id_ciudadano!,
      descripcion: form.descripcion.trim(),
      id_tipo_reclamo: form.id_tipo_reclamo ?? null,
      prioridad: form.prioridad,
      direccion: form.direccion.trim() || null,
      observaciones: form.observaciones.trim() || null,
      canal_origen: form.canal_origen || null,
    }
    return { ok: true, data }
  }

  function validarEdicion(): { ok: boolean; data?: ReclamoUpdate } {
    const errs: Record<string, string> = {}

    if (sloObservaciones) {
      // Solo observaciones editable; debe haber al menos algo o nota_historial
      if (!form.observaciones.trim() && !form.nota_historial.trim()) {
        errs.observaciones = 'Ingresá observaciones o una nota para el historial'
      }
    } else {
      if (!form.descripcion.trim()) errs.descripcion = 'Requerido'
      if (form.descripcion.trim().length < 5) errs.descripcion = 'Mínimo 5 caracteres'
    }

    setErrores(errs)
    if (Object.keys(errs).length > 0) return { ok: false }

    if (sloObservaciones) {
      const data: ReclamoUpdate = {
        observaciones: form.observaciones.trim() || null,
      }
      if (form.nota_historial.trim()) data.nota_historial = form.nota_historial.trim()
      return { ok: true, data }
    }

    // Edicion full (estado Sin asignar)
    const data: ReclamoUpdate = {
      descripcion: form.descripcion.trim(),
      id_tipo_reclamo: form.id_tipo_reclamo ?? null,
      prioridad: form.prioridad,
      direccion: form.direccion.trim() || null,
      observaciones: form.observaciones.trim() || null,
      canal_origen: form.canal_origen || null,
    }
    return { ok: true, data }
  }

  async function handleGuardar() {
    if (modo === 'new') {
      const v = validarAlta()
      if (!v.ok || !v.data) {
        push({ kind: 'error', title: 'Revisá los campos marcados' })
        return
      }
      try {
        const r = await crear.mutateAsync(v.data)
        push({
          kind: 'success',
          title: 'Reclamo ingresado',
          body: `${r.nro_reclamo ?? `#${r.id_reclamo}`}`,
        })
        navigate(`/reclamos/${r.id_reclamo}`)
      } catch (err) {
        push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
      }
    } else {
      const v = validarEdicion()
      if (!v.ok || !v.data) {
        push({ kind: 'error', title: 'Revisá los campos' })
        return
      }
      try {
        await editar.mutateAsync(v.data)
        push({ kind: 'success', title: 'Reclamo actualizado' })
        navigate(`/reclamos/${id}`)
      } catch (err) {
        push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
      }
    }
  }

  // Loading / error
  if (modo === 'edit' && detalle.isLoading) {
    return <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando reclamo...</div>
  }
  if (modo === 'edit' && detalle.isError) {
    return <div style={{ color: 'var(--color-error)', padding: 20 }}>Error: {(detalle.error as Error).message}</div>
  }
  if (modo === 'edit' && (estadoActual === 'Resuelto' || estadoActual === 'Cancelado')) {
    return (
      <div style={cardStyle}>
        <div style={cardHeader}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Reclamo cerrado</h2>
        </div>
        <div style={{ padding: 20 }}>
          <p style={{ margin: 0, color: 'var(--fg-2)' }}>
            Este reclamo está en estado <strong>{estadoActual}</strong> y no se puede editar.
          </p>
          <div style={{ marginTop: 16 }}>
            <button onClick={() => navigate(`/reclamos/${id}`)} style={btnGhost}>← Volver al detalle</button>
          </div>
        </div>
      </div>
    )
  }

  const titulo = modo === 'new' ? 'Alta de reclamo' : 'Modificar reclamo'
  const subtitulo = modo === 'edit'
    ? sloObservaciones
      ? `Reclamo en estado "${estadoActual}": solo podés editar observaciones / nota operativa.`
      : `Reclamo en estado "${estadoActual}": editás todos los campos.`
    : 'Registrar un nuevo reclamo en el sistema'

  return (
    <section style={cardStyle}>
      <header style={cardHeader}>
        <div>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.15rem', fontWeight: 600, color: 'var(--fg-1)' }}>
            {titulo}
          </h2>
          <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: 'var(--fg-3)' }}>
            {subtitulo}
          </p>
        </div>
        <span style={badgeNew}>
          {modo === 'new' ? '● NUEVO' : '✏ EDICION'}
        </span>
      </header>

      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>

        {/* Ciudadano */}
        <Section title="Ciudadano">
          {modo === 'new' ? (
            <>
              {form.ciudadano ? (
                <div style={cardCiudadano}>
                  <div>
                    <strong style={{ color: 'var(--fg-1)' }}>
                      {form.ciudadano.apellido}, {form.ciudadano.nombre}
                    </strong>
                    <div style={{ fontSize: '0.78rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                      DNI {form.ciudadano.doc_nro ?? '—'} · CUIL {form.ciudadano.cuil ?? '—'} · {form.ciudadano.telefono ?? '—'}
                    </div>
                  </div>
                  <button onClick={() => { setForm((p) => ({ ...p, ciudadano: null, id_ciudadano: null })) }} style={btnXsGhost}>Cambiar</button>
                </div>
              ) : (
                <Field label="Buscar ciudadano" required error={errores.ciudadano}>
                  <CiudadanoSearch
                    placeholder="DNI, CUIL, teléfono o nombre..."
                    onSelect={(c) => { setForm((p) => ({ ...p, ciudadano: c, id_ciudadano: c.id_ciudadano })); if (errores.ciudadano) setErrores((p) => { const n = {...p}; delete n.ciudadano; return n }) }}
                  />
                </Field>
              )}
            </>
          ) : (
            // En edit el ciudadano viene fijo (no se cambia desde la UI en Fase B)
            <div style={cardCiudadano}>
              <div>
                <strong style={{ color: 'var(--fg-1)' }}>
                  {form.ciudadano?.apellido ?? '—'}, {form.ciudadano?.nombre ?? '—'}
                </strong>
                <div style={{ fontSize: '0.78rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                  DNI {form.ciudadano?.doc_nro ?? '—'} · CUIL {form.ciudadano?.cuil ?? '—'}
                </div>
              </div>
              <span style={{ fontSize: '0.78rem', color: 'var(--fg-3)' }}>(no editable en esta vista)</span>
            </div>
          )}
        </Section>

        {/* Tipo + clasificacion (solo si fullEdit) */}
        {fullEdit && (
          <Section title="Tipo y clasificación">
            <Row cols="2fr 1fr 1fr">
              <Field label="Tipo de reclamo">
                <TipoReclamoPicker
                  value={form.id_tipo_reclamo}
                  onChange={(id, tipo) => setForm((p) => ({ ...p, id_tipo_reclamo: id, tipo }))}
                />
              </Field>
              <Field label="Prioridad">
                <select
                  value={form.prioridad}
                  onChange={(e) => setField('prioridad', e.target.value as Prioridad)}
                  style={inputStyle(false)}
                >
                  {PRIORIDADES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </Field>
              <Field label="Canal">
                <select
                  value={form.canal_origen}
                  onChange={(e) => setField('canal_origen', e.target.value as CanalOrigen | '')}
                  style={inputStyle(false)}
                >
                  <option value="">— sin definir —</option>
                  {CANALES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </Field>
            </Row>
          </Section>
        )}

        {/* Ubicacion minima (B1 sin mapa/geo, solo texto) */}
        {fullEdit && (
          <Section title="Ubicación (texto)">
            <Field label="Dirección" hint="En Fase C agregaremos el mapa con pin y geocoding OSM.">
              <input
                value={form.direccion}
                onChange={(e) => setField('direccion', e.target.value)}
                placeholder="Calle y altura, referencia..."
                maxLength={300}
                style={inputStyle(false)}
              />
            </Field>
          </Section>
        )}

        {/* Descripcion */}
        {fullEdit && (
          <Section title="Descripción">
            <Field label="Detalle del reclamo" required error={errores.descripcion}>
              <textarea
                value={form.descripcion}
                onChange={(e) => setField('descripcion', e.target.value)}
                placeholder="Describí el reclamo con suficiente detalle para que pueda ser atendido."
                rows={4}
                maxLength={2000}
                style={{ ...inputStyle(false), resize: 'vertical', fontFamily: 'var(--font-display)' }}
              />
            </Field>
          </Section>
        )}

        {/* Observaciones - SIEMPRE editable */}
        <Section title="Observaciones operativas">
          <Field
            label="Notas internas"
            hint={sloObservaciones
              ? 'Disponible siempre. El campo principal del reclamo no se puede editar en este estado.'
              : `${form.observaciones.length}/500 caracteres`}
            error={errores.observaciones}
          >
            <textarea
              value={form.observaciones}
              onChange={(e) => setField('observaciones', e.target.value)}
              placeholder="Anotaciones que vea el equipo de gestión..."
              rows={3}
              maxLength={500}
              style={{ ...inputStyle(false), resize: 'vertical', fontFamily: 'var(--font-display)' }}
            />
          </Field>
          {sloObservaciones && (
            <Field label="Nota para el historial" hint="Texto libre que aparece en el timeline del reclamo (no pisa observaciones).">
              <input
                value={form.nota_historial}
                onChange={(e) => setField('nota_historial', e.target.value)}
                placeholder="Ej: contactado el reclamante, se reagenda visita"
                maxLength={300}
                style={inputStyle(false)}
              />
            </Field>
          )}
        </Section>

      </div>

      <footer style={cardFooter}>
        <button
          onClick={() => navigate(modo === 'new' ? '/reclamos' : `/reclamos/${id}`)}
          style={btnGhost}
        >
          Cancelar
        </button>
        <button
          onClick={handleGuardar}
          disabled={crear.isPending || editar.isPending}
          style={btnPrimary}
        >
          {(crear.isPending || editar.isPending)
            ? 'Guardando...'
            : (modo === 'new' ? 'Guardar reclamo' : 'Aplicar cambios')}
        </button>
      </footer>
    </section>
  )
}

// ── Primitives ──

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <h3 style={{
        margin: 0, fontFamily: 'var(--font-display)',
        fontSize: 'var(--size-caption)', fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.07em',
        color: 'var(--fg-3)', borderBottom: '1px solid var(--border-primary)',
        paddingBottom: 4,
      }}>{title}</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>{children}</div>
    </div>
  )
}

function Row({ cols, children }: { cols: string; children: React.ReactNode }) {
  return <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 12 }}>{children}</div>
}

function Field({ label, required, error, hint, children }: {
  label: string
  required?: boolean
  error?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
        {label}{required && <span style={{ color: 'var(--zaris-orange)', marginLeft: 4 }}>*</span>}
      </label>
      {children}
      {error && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--color-error)' }}>{error}</div>}
      {hint && !error && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>{hint}</div>}
    </div>
  )
}

function inputStyle(disabled: boolean): React.CSSProperties {
  return {
    width: '100%',
    padding: '9px 12px',
    fontFamily: 'var(--font-display)',
    fontSize: 'var(--size-ui)',
    color: disabled ? 'var(--fg-2)' : 'var(--fg-1)',
    background: disabled ? 'var(--surface-300)' : 'var(--surface-100)',
    border: '1px solid var(--border-primary)',
    borderRadius: 'var(--radius-lg)',
    outline: 'none',
    cursor: disabled ? 'not-allowed' : 'text',
  }
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-xl)',
  boxShadow: 'var(--shadow-ambient)',
  overflow: 'hidden',
}

const cardHeader: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 20px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}

const cardFooter: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 10,
  padding: '14px 20px', borderTop: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}

const cardCiudadano: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '10px 14px',
  background: 'var(--surface-200)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
}

const badgeNew: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center',
  padding: '4px 12px', borderRadius: 'var(--radius-pill)',
  fontSize: 'var(--size-caption)', fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.04em',
  background: 'rgba(31,138,101,.12)', color: 'var(--color-success)',
}

const btnPrimary: React.CSSProperties = {
  padding: '10px 18px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '10px 18px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}

const btnXsGhost: React.CSSProperties = {
  padding: '5px 10px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)', fontSize: '0.75rem', cursor: 'pointer',
}
