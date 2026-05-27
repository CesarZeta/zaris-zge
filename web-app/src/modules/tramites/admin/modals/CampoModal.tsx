import { useRef, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button, Input } from '../../../../ui'
import { useActualizarCampo, useCrearCampo } from '../hooks'
import { ModalShell, label, requiredMark, errorMsg, formRow } from './_modalShell'
import type { TipoTramiteCampo, TipoDatoCampo } from '../../types'

const TIPOS_DATO: Array<{ v: TipoDatoCampo; l: string }> = [
  { v: 'texto', l: 'Texto corto' },
  { v: 'texto_largo', l: 'Texto largo' },
  { v: 'numero', l: 'Número entero' },
  { v: 'decimal', l: 'Decimal' },
  { v: 'moneda', l: 'Monto monetario' },
  { v: 'fecha', l: 'Fecha' },
  { v: 'fecha_hora', l: 'Fecha + hora' },
  { v: 'booleano', l: 'Sí/No' },
  { v: 'seleccion', l: 'Lista de opciones (elegir una)' },
  { v: 'seleccion_multiple', l: 'Lista de opciones (elegir varias)' },
  { v: 'ciudadano', l: 'Buscador de ciudadano' },
  { v: 'empresa', l: 'Buscador de empresa' },
  { v: 'agente', l: 'Selector de agente' },
  { v: 'subarea', l: 'Selector de subárea' },
  { v: 'equipo', l: 'Selector de equipo' },
  { v: 'direccion', l: 'Dirección con buscador' },
  { v: 'archivo', l: 'Adjunto inline' },
]

const REQUIERE_OPCIONES: TipoDatoCampo[] = ['seleccion', 'seleccion_multiple']

const NOMBRE_INTERNO_RE = /^[a-z][a-z0-9_]{0,49}$/

/**
 * Convierte una etiqueta visible a snake_case (BUG-07): saca tildes, baja a
 * minúsculas, reemplaza todo lo no [a-z0-9] por "_", colapsa y recorta. Si
 * arranca con dígito, le antepone "_". "Tipo de obra" → "tipo_de_obra".
 */
function aSnakeCase(texto: string): string {
  const base = texto
    .normalize('NFD').replace(/\p{Diacritic}/gu, '') // saca tildes (diacríticos combinantes)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 50)
  return /^[0-9]/.test(base) ? `_${base}`.slice(0, 50) : base
}

export function CampoModal({
  idVersion, campo, onCerrar,
}: {
  idVersion: number
  campo: TipoTramiteCampo | null
  onCerrar: () => void
}) {
  const esNuevo = campo === null
  const [nombreInterno, setNombreInterno] = useState(campo?.nombre_interno ?? '')
  const [etiqueta, setEtiqueta] = useState(campo?.etiqueta ?? '')
  // BUG-07: mientras el usuario no toque el nombre interno a mano, se autocompleta
  // desde la etiqueta. Una vez que lo edita manualmente, se respeta lo suyo.
  const nombreEditadoAMano = useRef(false)
  const [tipoDato, setTipoDato] = useState<TipoDatoCampo>(campo?.tipo_dato ?? 'texto')
  const [obligatorio, setObligatorio] = useState(campo?.obligatorio ?? false)
  const [ayuda, setAyuda] = useState(campo?.ayuda ?? '')
  const [orden, setOrden] = useState(campo?.orden ?? 1)
  const [visibleEnListado, setVisibleEnListado] = useState(campo?.visible_en_listado ?? false)
  // BUG-04: las opciones se editan como filas {valor, etiqueta} en vez de un
  // textarea con formato pipe. El valor (interno) se autocompleta desde la
  // etiqueta visible, igual que el nombre interno del campo.
  const [opciones, setOpciones] = useState<Array<{ valor: string; etiqueta: string }>>(
    campo?.opciones_jsonb
      ? (campo.opciones_jsonb as Array<{ valor: string; etiqueta: string }>).map((o) => ({ valor: o.valor, etiqueta: o.etiqueta }))
      : []
  )
  const [error, setError] = useState('')

  const crear = useCrearCampo()
  const actualizar = useActualizarCampo()

  function agregarOpcion() {
    setOpciones((prev) => [...prev, { valor: '', etiqueta: '' }])
  }
  function quitarOpcion(idx: number) {
    setOpciones((prev) => prev.filter((_, i) => i !== idx))
  }
  function setEtiquetaOpcion(idx: number, et: string) {
    setOpciones((prev) => prev.map((o, i) => {
      if (i !== idx) return o
      // si el valor estaba vacío o seguía al slug de la etiqueta anterior, lo re-derivamos
      const valorAuto = aSnakeCase(o.etiqueta) === o.valor || o.valor === ''
      return { etiqueta: et, valor: valorAuto ? aSnakeCase(et) : o.valor }
    }))
  }
  function setValorOpcion(idx: number, v: string) {
    setOpciones((prev) => prev.map((o, i) => (i === idx ? { ...o, valor: aSnakeCase(v) } : o)))
  }

  /** Opciones limpias para enviar (sin filas vacías). null si no aplica/ninguna. */
  function opcionesValidas(): Array<{ valor: string; etiqueta: string }> | null {
    const limpias = opciones
      .map((o) => ({ valor: o.valor.trim(), etiqueta: o.etiqueta.trim() || o.valor.trim() }))
      .filter((o) => o.valor)
    return limpias.length ? limpias : null
  }

  // Validez del nombre interno (BUG-03): en alta debe ser snake_case; en edición
  // es inmutable, así que no se valida.
  const nombreValido = !esNuevo || NOMBRE_INTERNO_RE.test(nombreInterno)
  const mostrarEstadoNombre = esNuevo && nombreInterno.length > 0

  async function handleGuardar() {
    setError('')
    if (esNuevo && !NOMBRE_INTERNO_RE.test(nombreInterno)) {
      setError('Nombre interno debe ser snake_case (a-z, 0-9, _), empezar con letra')
      return
    }
    if (!etiqueta.trim()) { setError('Etiqueta obligatoria'); return }

    const opcs = REQUIERE_OPCIONES.includes(tipoDato) ? opcionesValidas() : null
    if (REQUIERE_OPCIONES.includes(tipoDato) && (!opcs || opcs.length === 0)) {
      setError('Este tipo requiere al menos 1 opción. Agregá al menos una con el botón "+ Agregar opción".')
      return
    }

    try {
      if (esNuevo) {
        await crear.mutateAsync({
          idVersion,
          body: {
            nombre_interno: nombreInterno,
            etiqueta: etiqueta.trim(),
            tipo_dato: tipoDato,
            obligatorio,
            orden,
            ayuda: ayuda.trim() || null,
            visible_en_listado: visibleEnListado,
            opciones_jsonb: opcs,
          },
        })
      } else {
        await actualizar.mutateAsync({
          idCampo: campo!.id_tipo_tramite_campo,
          body: {
            etiqueta: etiqueta.trim(),
            tipo_dato: tipoDato,
            obligatorio,
            orden,
            ayuda: ayuda.trim() || null,
            visible_en_listado: visibleEnListado,
            opciones_jsonb: opcs,
          },
        })
      }
      onCerrar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  const pending = crear.isPending || actualizar.isPending

  return (
    <ModalShell titulo={esNuevo ? 'Nuevo campo del formulario' : `Editar campo · ${campo!.nombre_interno}`} onCerrar={onCerrar} ancho={560}>
      {/* Etiqueta primero: es lo que el usuario piensa naturalmente, y de acá
          se autocompleta el nombre interno (BUG-07). */}
      <div style={formRow}>
        <label style={label}>Etiqueta visible <span style={requiredMark}>*</span></label>
        <Input
          value={etiqueta}
          onChange={(e) => {
            const val = e.target.value
            setEtiqueta(val)
            if (esNuevo && !nombreEditadoAMano.current) setNombreInterno(aSnakeCase(val))
          }}
          placeholder="Motivo de la solicitud"
        />
      </div>

      <div style={formRow}>
        <label style={label}>Nombre interno <span style={requiredMark}>*</span></label>
        <div style={{ position: 'relative' }}>
          <Input
            value={nombreInterno}
            onChange={(e) => {
              if (esNuevo) nombreEditadoAMano.current = true
              setNombreInterno(aSnakeCase(e.target.value))
            }}
            disabled={!esNuevo}
            placeholder="motivo"
            style={{
              fontFamily: 'var(--font-mono)',
              paddingRight: mostrarEstadoNombre ? 30 : undefined,
              borderColor: mostrarEstadoNombre
                ? (nombreValido ? 'var(--color-success)' : 'var(--color-error)')
                : undefined,
            }}
          />
          {mostrarEstadoNombre && (
            <span style={{
              position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
              color: nombreValido ? 'var(--color-success)' : 'var(--color-error)',
              fontSize: 15, fontWeight: 700, pointerEvents: 'none',
            }}>
              {nombreValido ? '✓' : '✕'}
            </span>
          )}
        </div>
        {esNuevo ? (
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
            Identificador técnico: solo minúsculas, números y guión bajo, sin espacios
            (se completa solo desde la etiqueta). No se puede cambiar después.
          </p>
        ) : (
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
            El nombre interno no se puede cambiar.
          </p>
        )}
      </div>

      <div style={formRow}>
        <label style={label}>Tipo de dato</label>
        <select value={tipoDato} onChange={(e) => setTipoDato(e.target.value as TipoDatoCampo)} style={select}>
          {TIPOS_DATO.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
        </select>
      </div>

      {REQUIERE_OPCIONES.includes(tipoDato) && (
        <div style={formRow}>
          <label style={label}>Opciones de la lista</label>
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '0 0 8px' }}>
            Escribí lo que verá el usuario en la "Etiqueta". El valor interno se
            completa solo (podés ajustarlo si lo necesitás).
          </p>
          {opciones.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
                <span style={{ flex: 1 }}>Etiqueta visible</span>
                <span style={{ flex: 1 }}>Valor interno</span>
                <span style={{ width: 28 }} />
              </div>
              {opciones.map((o, idx) => (
                <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Input
                    value={o.etiqueta}
                    onChange={(e) => setEtiquetaOpcion(idx, e.target.value)}
                    placeholder="Alta"
                    style={{ flex: 1 }}
                  />
                  <Input
                    value={o.valor}
                    onChange={(e) => setValorOpcion(idx, e.target.value)}
                    placeholder="alta"
                    style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 13 }}
                  />
                  <button
                    type="button"
                    onClick={() => quitarOpcion(idx)}
                    title="Quitar opción"
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-3)', padding: 4, borderRadius: 4, width: 28 }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <button
            type="button"
            onClick={agregarOpcion}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 8,
              background: 'transparent', border: '1px dashed var(--border-medium)',
              borderRadius: 'var(--radius-md)', padding: '6px 12px', cursor: 'pointer',
              color: 'var(--fg-2)', fontFamily: 'var(--font-display)', fontSize: 13,
            }}
          >
            <Plus size={14} /> Agregar opción
          </button>
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ width: 100 }}>
          <label style={label}>Orden</label>
          <Input type="number" value={orden} onChange={(e) => setOrden(Number(e.target.value) || 0)} />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={obligatorio} onChange={(e) => setObligatorio(e.target.checked)} />
          Obligatorio
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={visibleEnListado} onChange={(e) => setVisibleEnListado(e.target.checked)} />
          Visible en bandeja
        </label>
      </div>

      <div style={{ ...formRow, marginTop: 12 }}>
        <label style={label}>Ayuda (tooltip)</label>
        <textarea value={ayuda} onChange={(e) => setAyuda(e.target.value)} rows={2} style={textarea} />
      </div>

      {error && <p style={errorMsg}>{error}</p>}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="accent" onClick={handleGuardar} disabled={pending || !nombreValido || !etiqueta.trim()}>
          {pending ? 'Guardando…' : 'Guardar'}
        </Button>
      </div>
    </ModalShell>
  )
}

const select: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-medium)', fontSize: 14,
  fontFamily: 'inherit', color: 'var(--fg-1)', background: 'var(--surface-100)',
}
const textarea: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-medium)', fontSize: 14,
  fontFamily: 'inherit', color: 'var(--fg-1)', background: 'var(--surface-100)',
  resize: 'vertical',
}
