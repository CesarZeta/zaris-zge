import type { FormState } from '../views/FormView'
import { formatCuilInput } from '../lib/cuilUtils'
import type { Nacionalidad } from '../types/ciudadano'

interface Props {
  form: FormState
  errores: Record<string, string>
  readonly: boolean
  nacionalidades: Nacionalidad[]
  onChange: <K extends keyof FormState>(key: K, value: FormState[K]) => void
  onCuilBlur: () => void
  onEmpChkChange: (checked: boolean) => void
}

export function CiudadanoForm({ form, errores, readonly, nacionalidades, onChange, onCuilBlur, onEmpChkChange }: Props) {
  return (
    <form autoComplete="off" onSubmit={(e) => e.preventDefault()} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* ── Identificacion ── */}
      <Section title="Identificacion">
        <Row cols="1fr 1fr 1fr">
          <Field label="Tipo Documento" required error={errores.doc_tipo}>
            <select
              value={form.doc_tipo}
              onChange={(e) => onChange('doc_tipo', e.target.value as FormState['doc_tipo'])}
              disabled={readonly}
              style={inputStyle(readonly)}
            >
              <option value="">Seleccionar...</option>
              <option value="DNI">DNI</option>
              <option value="PASAPORTE">Pasaporte</option>
            </select>
          </Field>
          <Field label="Numero Documento" error={errores.doc_nro}>
            <input
              type="text"
              value={form.doc_nro}
              onChange={(e) => onChange('doc_nro', e.target.value.replace(/\D/g, '').slice(0, 10))}
              disabled={readonly}
              maxLength={10}
              placeholder="Ej: 30123456"
              style={inputStyle(readonly)}
            />
          </Field>
          <Field label="CUIL" error={errores.cuil}>
            <input
              type="text"
              value={form.cuil}
              onChange={(e) => onChange('cuil', formatCuilInput(e.target.value))}
              onBlur={onCuilBlur}
              disabled={readonly}
              maxLength={13}
              placeholder="XX-XXXXXXXX-X"
              style={inputStyle(readonly)}
            />
          </Field>
        </Row>
      </Section>

      {/* ── Datos personales ── */}
      <Section title="Datos personales">
        <Row cols="1fr 1fr">
          <Field label="Nombre" required error={errores.nombre}>
            <input
              type="text"
              value={form.nombre}
              onChange={(e) => onChange('nombre', e.target.value)}
              disabled={readonly}
              maxLength={100}
              placeholder="Nombre(s)"
              style={inputStyle(readonly)}
            />
          </Field>
          <Field label="Apellido" required error={errores.apellido}>
            <input
              type="text"
              value={form.apellido}
              onChange={(e) => onChange('apellido', e.target.value)}
              disabled={readonly}
              maxLength={100}
              placeholder="Apellido(s)"
              style={inputStyle(readonly)}
            />
          </Field>
        </Row>
        <Row cols="1fr 1fr 1fr">
          <Field label="Sexo" required error={errores.sexo}>
            <select
              value={form.sexo}
              onChange={(e) => onChange('sexo', e.target.value as FormState['sexo'])}
              disabled={readonly}
              style={inputStyle(readonly)}
            >
              <option value="">Seleccionar...</option>
              <option value="HOMBRE">Hombre</option>
              <option value="MUJER">Mujer</option>
              <option value="OTROS">Otros</option>
            </select>
          </Field>
          <Field label="Fecha de Nacimiento" required error={errores.fecha_nac}>
            <input
              type="date"
              value={form.fecha_nac}
              onChange={(e) => onChange('fecha_nac', e.target.value)}
              disabled={readonly}
              style={inputStyle(readonly)}
            />
          </Field>
          <Field label="Nacionalidad" required error={errores.id_nacionalidad}>
            <select
              value={form.id_nacionalidad}
              onChange={(e) => onChange('id_nacionalidad', e.target.value)}
              disabled={readonly}
              style={inputStyle(readonly)}
            >
              <option value="">Seleccionar...</option>
              {nacionalidades.map((n) => (
                <option key={n.id} value={n.id}>{n.pais} ({n.region})</option>
              ))}
            </select>
          </Field>
        </Row>
      </Section>

      {/* ── Domicilio ── */}
      <Section title="Domicilio">
        <Row cols="1fr 1fr">
          <Field label="Calle y Altura" required error={errores.calle}>
            <input
              type="text"
              value={form.calle}
              onChange={(e) => onChange('calle', e.target.value)}
              disabled={readonly}
              maxLength={200}
              placeholder="Ej: Av. San Martin 1234"
              style={inputStyle(readonly)}
            />
          </Field>
          <Field label="Localidad / Barrio" required error={errores.localidad}>
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
        <Field label="Estado / Provincia" required error={errores.provincia}>
          <input
            type="text"
            value={form.provincia}
            onChange={(e) => onChange('provincia', e.target.value)}
            disabled={readonly}
            maxLength={100}
            placeholder="Ej: Buenos Aires"
            style={inputStyle(readonly)}
          />
        </Field>
      </Section>

      {/* ── Contacto ── */}
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
              placeholder="ejemplo@correo.com"
              style={inputStyle(readonly)}
            />
          </Field>
        </Row>
      </Section>

      {/* ── Representacion empresarial ── */}
      <Section title="Representacion empresarial">
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: readonly ? 'default' : 'pointer', fontSize: 'var(--size-ui)', color: 'var(--fg-1)' }}>
          <input
            type="checkbox"
            checked={form.emp_chk}
            onChange={(e) => onEmpChkChange(e.target.checked)}
            disabled={readonly}
            style={{ width: 16, height: 16, accentColor: 'var(--zaris-orange)' }}
          />
          Este ciudadano es representante de una empresa
        </label>
      </Section>

      {/* ── Observaciones ── */}
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

// ── Componentes internos ──
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
  return (
    <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 12 }}>
      {children}
    </div>
  )
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
