import { useState } from 'react'
import { Eye } from 'lucide-react'
import { FormularioDinamico, validarDatos } from '../../components/FormularioDinamico'
import type { TipoTramiteCampo } from '../../types'

interface PreviewFormularioProps {
  campos: TipoTramiteCampo[]
  /** Nombre del tipo de trámite, para encabezar la ficha simulada. */
  nombreTipo: string
}

/**
 * Vista previa en vivo del formulario de inicio que verá el iniciador.
 * Reusa el mismo `FormularioDinamico` que la pantalla real de alta (CrearTramite),
 * así lo que se ve acá es exactamente lo que el operador/ciudadano va a completar.
 *
 * Es interactivo (se puede tipear/seleccionar) pero NO guarda nada — sirve para que
 * el admin compruebe cómo queda el form mientras edita campos. Al editar un campo,
 * react-query invalida la versión y este componente recibe los `campos` nuevos.
 */
export function PreviewFormulario({ campos, nombreTipo }: PreviewFormularioProps) {
  const [valores, setValores] = useState<Record<string, unknown>>({})
  const [validar, setValidar] = useState(false)

  const ordenados = [...campos].sort((a, b) => a.orden - b.orden)
  const errores = validar ? validarDatos(ordenados, valores) : {}

  function handleChange(nombre: string, valor: unknown) {
    setValores((prev) => ({ ...prev, [nombre]: valor }))
  }

  if (ordenados.length === 0) {
    return (
      <div style={vacioStyle}>
        <Eye size={28} strokeWidth={1.5} color="var(--fg-3)" />
        <p style={{ margin: '8px 0 0', color: 'var(--fg-2)', fontSize: 14 }}>
          Todavía no hay campos. Agregá campos en el modo «Editar» y van a aparecer acá
          tal como los verá el iniciador al crear el trámite.
        </p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={notaStyle}>
        <Eye size={16} strokeWidth={1.5} color="var(--zaris-orange)" />
        <span>
          Así verá el iniciador el formulario de inicio. Es interactivo para probarlo,
          pero <strong>no guarda nada</strong>.
        </span>
      </div>

      {/* Ficha simulada — espeja el contenedor de la pantalla de alta real */}
      <div style={fichaStyle}>
        <h3 style={fichaTituloStyle}>Nuevo trámite · {nombreTipo}</h3>
        <p style={fichaSubtituloStyle}>Datos de inicio</p>

        <div style={{ marginTop: 16 }}>
          <FormularioDinamico
            campos={ordenados}
            valores={valores}
            errores={errores}
            onChange={handleChange}
          />
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
          <button
            type="button"
            onClick={() => setValidar(true)}
            style={btnValidarStyle}
          >
            Probar validación
          </button>
          <button
            type="button"
            onClick={() => { setValores({}); setValidar(false) }}
            style={btnLimpiarStyle}
          >
            Limpiar
          </button>
        </div>
        {validar && Object.keys(errores).length === 0 && (
          <p style={{ margin: '10px 0 0', fontSize: 12, color: 'var(--color-success)', fontFamily: 'var(--font-display)' }}>
            Todos los campos obligatorios están completos.
          </p>
        )}
      </div>
    </div>
  )
}

const vacioStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
  padding: '40px 24px', maxWidth: 440, margin: '0 auto',
}

const notaStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10,
  padding: '10px 14px', borderRadius: 'var(--radius-lg, 12px)',
  background: 'rgba(245,78,0,.07)', border: '1px solid rgba(245,78,0,.25)',
  fontSize: 13, color: 'var(--fg-2)', fontFamily: 'var(--font-display)',
}

const fichaStyle: React.CSSProperties = {
  maxWidth: 560,
  padding: '24px 28px',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-xl, 16px)',
  boxShadow: 'var(--shadow-card)',
}

const fichaTituloStyle: React.CSSProperties = {
  margin: 0, fontSize: '1.15rem', color: 'var(--fg-1)', fontFamily: 'var(--font-display)',
}

const fichaSubtituloStyle: React.CSSProperties = {
  margin: '4px 0 0', fontSize: 12, color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
}

const btnValidarStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)',
  border: 'none', cursor: 'pointer',
  background: 'var(--zaris-orange)', color: '#fff',
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
}

const btnLimpiarStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-medium)', cursor: 'pointer',
  background: 'transparent', color: 'var(--fg-2)',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
