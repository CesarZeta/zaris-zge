import { useState } from 'react'
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
  { v: 'seleccion', l: 'Selección única' },
  { v: 'seleccion_multiple', l: 'Selección múltiple' },
  { v: 'ciudadano', l: 'Buscador de ciudadano' },
  { v: 'empresa', l: 'Buscador de empresa' },
  { v: 'agente', l: 'Selector de agente' },
  { v: 'subarea', l: 'Selector de subárea' },
  { v: 'equipo', l: 'Selector de equipo' },
  { v: 'direccion', l: 'Dirección con buscador' },
  { v: 'archivo', l: 'Adjunto inline' },
]

const REQUIERE_OPCIONES: TipoDatoCampo[] = ['seleccion', 'seleccion_multiple']

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
  const [tipoDato, setTipoDato] = useState<TipoDatoCampo>(campo?.tipo_dato ?? 'texto')
  const [obligatorio, setObligatorio] = useState(campo?.obligatorio ?? false)
  const [ayuda, setAyuda] = useState(campo?.ayuda ?? '')
  const [orden, setOrden] = useState(campo?.orden ?? 1)
  const [visibleEnListado, setVisibleEnListado] = useState(campo?.visible_en_listado ?? false)
  const [opcionesTexto, setOpcionesTexto] = useState(
    campo?.opciones_jsonb
      ? (campo.opciones_jsonb as Array<{ valor: string; etiqueta: string }>).map((o) => `${o.valor}|${o.etiqueta}`).join('\n')
      : ''
  )
  const [error, setError] = useState('')

  const crear = useCrearCampo()
  const actualizar = useActualizarCampo()

  function parseOpciones(): Array<{ valor: string; etiqueta: string }> | null {
    const lineas = opcionesTexto.split('\n').map((l) => l.trim()).filter(Boolean)
    if (lineas.length === 0) return null
    return lineas.map((l) => {
      const [v, ...rest] = l.split('|')
      const et = rest.join('|').trim() || v.trim()
      return { valor: v.trim(), etiqueta: et }
    })
  }

  async function handleGuardar() {
    setError('')
    if (esNuevo && !/^[a-z][a-z0-9_]{0,49}$/.test(nombreInterno)) {
      setError('Nombre interno debe ser snake_case (a-z, 0-9, _), empezar con letra')
      return
    }
    if (!etiqueta.trim()) { setError('Etiqueta obligatoria'); return }

    const opciones = REQUIERE_OPCIONES.includes(tipoDato) ? parseOpciones() : null
    if (REQUIERE_OPCIONES.includes(tipoDato) && (!opciones || opciones.length === 0)) {
      setError('Este tipo requiere al menos 1 opción. Una por línea: "valor|Etiqueta"')
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
            opciones_jsonb: opciones,
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
            opciones_jsonb: opciones,
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
      <div style={formRow}>
        <label style={label}>Nombre interno <span style={requiredMark}>*</span></label>
        <Input value={nombreInterno} onChange={(e) => setNombreInterno(e.target.value.toLowerCase())} disabled={!esNuevo} placeholder="motivo" style={{ fontFamily: 'var(--font-mono)' }} />
        {esNuevo ? (
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
            snake_case. No se puede cambiar después.
          </p>
        ) : (
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
            El nombre interno no se puede cambiar.
          </p>
        )}
      </div>

      <div style={formRow}>
        <label style={label}>Etiqueta visible <span style={requiredMark}>*</span></label>
        <Input value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)} placeholder="Motivo de la solicitud" />
      </div>

      <div style={formRow}>
        <label style={label}>Tipo de dato</label>
        <select value={tipoDato} onChange={(e) => setTipoDato(e.target.value as TipoDatoCampo)} style={select}>
          {TIPOS_DATO.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
        </select>
      </div>

      {REQUIERE_OPCIONES.includes(tipoDato) && (
        <div style={formRow}>
          <label style={label}>Opciones (una por línea: <code>valor|Etiqueta</code>)</label>
          <textarea
            value={opcionesTexto}
            onChange={(e) => setOpcionesTexto(e.target.value)}
            rows={4}
            placeholder="alta|Alta&#10;media|Media&#10;baja|Baja"
            style={textarea}
          />
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
        <Button variant="accent" onClick={handleGuardar} disabled={pending}>
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
