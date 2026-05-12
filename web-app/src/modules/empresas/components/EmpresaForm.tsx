import { useMemo, useState } from 'react'
import type { EmpresaFormState } from '../views/FormView'
import { formatCuitInput } from '../lib/cuitUtils'
import type { Actividad } from '../types/empresa'

interface Props {
  form: EmpresaFormState
  errores: Record<string, string>
  readonly: boolean
  actividades: Actividad[]
  onChange: <K extends keyof EmpresaFormState>(key: K, value: EmpresaFormState[K]) => void
}

const CATEGORY_COLORS: Record<string, { bg: string; color: string }> = {
  comercio: { bg: '#E3F2FD', color: '#1565C0' },
  servicios: { bg: '#E8F5E9', color: '#2E7D32' },
  industria: { bg: '#FFF8E1', color: '#F57F17' },
}

export function EmpresaForm({ form, errores, readonly, actividades, onChange }: Props) {
  const [filtroClae, setFiltroClae] = useState('')

  // Actividades filtradas + agrupadas por categoria
  const grupos = useMemo(() => {
    const f = filtroClae.toLowerCase().trim()
    const filtradas = actividades.filter((a) => {
      if (!f) return true
      return a.descripcion.toLowerCase().includes(f) || String(a.codigo_clae).includes(f)
    })
    const out: Record<string, Actividad[]> = {}
    filtradas.forEach((a) => {
      const cat = a.categoria_tasa || 'otros'
      if (!out[cat]) out[cat] = []
      out[cat].push(a)
    })
    return out
  }, [actividades, filtroClae])

  // Categoria de la actividad seleccionada (para el badge)
  const categoriaActual = useMemo(() => {
    if (!form.id_actividad) return null
    const a = actividades.find((x) => String(x.id) === form.id_actividad)
    return a?.categoria_tasa || null
  }, [actividades, form.id_actividad])

  const badgeColor = categoriaActual ? (CATEGORY_COLORS[categoriaActual] || { bg: '#F5F5F5', color: '#333' }) : null

  return (
    <form autoComplete="off" onSubmit={(e) => e.preventDefault()} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Identificacion */}
      <Section title="Identificacion">
        <Row cols="1fr 2fr">
          <Field label="CUIT" required error={errores.cuit}>
            <input
              type="text"
              value={form.cuit}
              onChange={(e) => onChange('cuit', formatCuitInput(e.target.value))}
              disabled={readonly}
              maxLength={13}
              placeholder="XX-XXXXXXXX-X"
              style={inputStyle(readonly)}
            />
          </Field>
          <Field label="Nombre de empresa" required error={errores.nombre}>
            <input
              type="text"
              value={form.nombre}
              onChange={(e) => onChange('nombre', e.target.value)}
              disabled={readonly}
              maxLength={100}
              placeholder="Razon social"
              style={inputStyle(readonly)}
            />
          </Field>
        </Row>

        <Row cols="2fr 1fr">
          <Field label="Actividad economica (CLAE)" required error={errores.id_actividad}>
            <input
              type="text"
              placeholder="Filtrar actividades..."
              value={filtroClae}
              onChange={(e) => setFiltroClae(e.target.value)}
              disabled={readonly}
              style={{ ...inputStyle(readonly), marginBottom: 4 }}
            />
            <select
              value={form.id_actividad}
              onChange={(e) => onChange('id_actividad', e.target.value)}
              disabled={readonly}
              style={inputStyle(readonly)}
            >
              <option value="">Seleccionar actividad...</option>
              {Object.entries(grupos).map(([cat, acts]) => (
                <optgroup key={cat} label={cat.charAt(0).toUpperCase() + cat.slice(1)}>
                  {acts.map((a) => (
                    <option key={a.id} value={a.id}>{a.codigo_clae} — {a.descripcion}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </Field>
          <Field label="">
            {categoriaActual && badgeColor && (
              <span style={{
                display: 'inline-flex', alignItems: 'center',
                padding: '6px 12px', borderRadius: 'var(--radius-pill)',
                fontSize: 'var(--size-caption)', fontWeight: 600,
                textTransform: 'uppercase', letterSpacing: '0.04em',
                background: badgeColor.bg, color: badgeColor.color,
                alignSelf: 'flex-start',
              }}>
                Categoria: {categoriaActual}
              </span>
            )}
          </Field>
        </Row>
      </Section>

      {/* Domicilio */}
      <Section title="Domicilio">
        <Row cols="1fr 1fr">
          <Field label="Calle y altura" required error={errores.calle}>
            <input
              type="text"
              value={form.calle}
              onChange={(e) => onChange('calle', e.target.value)}
              disabled={readonly}
              maxLength={200}
              placeholder="Direccion de la empresa"
              style={inputStyle(readonly)}
            />
          </Field>
          <Field label="Localidad / barrio" required error={errores.localidad}>
            <input
              type="text"
              value={form.localidad}
              onChange={(e) => onChange('localidad', e.target.value)}
              disabled={readonly}
              maxLength={100}
              style={inputStyle(readonly)}
            />
          </Field>
        </Row>
        <Field label="Provincia / estado" required error={errores.provincia}>
          <input
            type="text"
            value={form.provincia}
            onChange={(e) => onChange('provincia', e.target.value)}
            disabled={readonly}
            maxLength={100}
            style={inputStyle(readonly)}
          />
        </Field>
      </Section>

      {/* Contacto */}
      <Section title="Contacto">
        <Row cols="1fr 1fr">
          <Field label="Telefono" required error={errores.telefono} hint="Sin el 0 del codigo de area. Ej: 1155667788">
            <input
              type="text"
              value={form.telefono}
              onChange={(e) => onChange('telefono', e.target.value.replace(/\D/g, '').slice(0, 10))}
              disabled={readonly}
              maxLength={10}
              placeholder="Cod. area + numero (10 digitos)"
              style={inputStyle(readonly)}
            />
          </Field>
          <Field label="Email" required error={errores.email}>
            <input
              type="email"
              value={form.email}
              onChange={(e) => onChange('email', e.target.value)}
              disabled={readonly}
              maxLength={150}
              placeholder="empresa@correo.com"
              style={inputStyle(readonly)}
            />
          </Field>
        </Row>
      </Section>

      {/* Observaciones */}
      <Section title="Observaciones">
        <Field label="" hint={`${form.observaciones.length}/500 caracteres`}>
          <textarea
            value={form.observaciones}
            onChange={(e) => onChange('observaciones', e.target.value)}
            disabled={readonly}
            maxLength={500}
            rows={3}
            placeholder="Notas adicionales (max. 500 caracteres)"
            style={{ ...inputStyle(readonly), resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>
      </Section>
    </form>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h3 style={{
        margin: 0, fontFamily: 'var(--font-display)',
        fontSize: 'var(--size-caption)', fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.07em',
        color: 'var(--fg-3)', borderBottom: '1px solid var(--border-primary)',
        paddingBottom: 4,
      }}>{title}</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>{children}</div>
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
      {label && (
        <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
          {label}{required && <span style={{ color: 'var(--zaris-orange)', marginLeft: 4 }}>*</span>}
        </label>
      )}
      {children}
      {error && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--color-error)' }}>{error}</div>}
      {hint && !error && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>{hint}</div>}
    </div>
  )
}

function inputStyle(readonly: boolean): React.CSSProperties {
  return {
    width: '100%',
    padding: '9px 12px',
    fontFamily: 'var(--font-display)',
    fontSize: 'var(--size-ui)',
    color: readonly ? 'var(--fg-2)' : 'var(--fg-1)',
    background: readonly ? 'var(--surface-300)' : 'var(--surface-100)',
    border: '1px solid var(--border-primary)',
    borderRadius: 'var(--radius-lg)',
    outline: 'none',
    cursor: readonly ? 'not-allowed' : 'text',
  }
}
