import { useState } from 'react'
import { Button, Input } from '../../../../ui'
import { useActualizarEstado, useCrearEstado, useSetEsperaIniciador } from '../hooks'
import { ModalShell, label, requiredMark, errorMsg, formRow } from './_modalShell'
import type { TipoTramiteEstado } from '../../types'

const COLORES_SUGERIDOS = ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#6b7280', '#9333ea']

export function EstadoModal({
  idVersion, estado, onCerrar,
}: {
  idVersion: number
  estado: TipoTramiteEstado | null
  onCerrar: () => void
}) {
  const esNuevo = estado === null
  const [codigo, setCodigo] = useState(estado?.codigo ?? '')
  const [etiqueta, setEtiqueta] = useState(estado?.etiqueta ?? '')
  const [descripcion, setDescripcion] = useState('')  // no viene en el detalle publico, solo en el admin
  const [color, setColor] = useState(estado?.color ?? '#6b7280')
  const [orden, setOrden] = useState(estado?.orden ?? 1)
  const [esInicial, setEsInicial] = useState(estado?.es_inicial ?? false)
  const [esFinal, setEsFinal] = useState(estado?.es_final ?? false)
  const [permiteAdjuntar, setPermiteAdjuntar] = useState(estado?.permite_adjuntar ?? true)
  const [permiteComentar, setPermiteComentar] = useState(estado?.permite_comentar ?? true)
  const [esperaIniciador, setEsperaIniciador] = useState(estado?.espera_iniciador ?? false)
  const [error, setError] = useState('')

  const crear = useCrearEstado()
  const actualizar = useActualizarEstado()
  const setEspera = useSetEsperaIniciador()

  async function handleGuardar() {
    setError('')
    if (esNuevo && !/^[a-z][a-z0-9_]{0,49}$/.test(codigo)) {
      setError('Código debe ser snake_case (a-z, 0-9, _)')
      return
    }
    if (!etiqueta.trim()) { setError('Etiqueta obligatoria'); return }
    try {
      if (esNuevo) {
        await crear.mutateAsync({
          idVersion,
          body: {
            codigo, etiqueta: etiqueta.trim(),
            descripcion: descripcion.trim() || null,
            color, orden,
            es_inicial: esInicial, es_final: esFinal,
            permite_adjuntar: permiteAdjuntar,
            permite_comentar: permiteComentar,
            espera_iniciador: esperaIniciador,
          },
        })
      } else {
        // mig 101: el flag "espera al iniciador" va por su PATCH propio, que NO
        // exige versión editable (es metadata). Así se puede marcar en circuitos
        // publicados con trámites en curso. El resto sigue por el PUT.
        if (esperaIniciador !== (estado!.espera_iniciador ?? false)) {
          await setEspera.mutateAsync({ idEstado: estado!.id_tipo_tramite_estado, espera: esperaIniciador })
        }
        const otrosCambios =
          etiqueta.trim() !== estado!.etiqueta ||
          color !== (estado!.color ?? '#6b7280') ||
          orden !== estado!.orden ||
          esInicial !== estado!.es_inicial ||
          esFinal !== estado!.es_final ||
          permiteAdjuntar !== estado!.permite_adjuntar ||
          permiteComentar !== estado!.permite_comentar ||
          descripcion.trim() !== ''
        if (otrosCambios) {
          await actualizar.mutateAsync({
            idEstado: estado!.id_tipo_tramite_estado,
            body: {
              etiqueta: etiqueta.trim(),
              descripcion: descripcion.trim() || null,
              color, orden,
              es_inicial: esInicial, es_final: esFinal,
              permite_adjuntar: permiteAdjuntar,
              permite_comentar: permiteComentar,
            },
          })
        }
      }
      onCerrar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  const pending = crear.isPending || actualizar.isPending || setEspera.isPending

  return (
    <ModalShell titulo={esNuevo ? 'Nuevo estado del circuito' : `Editar estado · ${estado!.codigo}`} onCerrar={onCerrar}>
      <div style={formRow}>
        <label style={label}>Código <span style={requiredMark}>*</span></label>
        <Input value={codigo} onChange={(e) => setCodigo(e.target.value.toLowerCase())} disabled={!esNuevo} placeholder="ingresado" style={{ fontFamily: 'var(--font-mono)' }} />
        {!esNuevo && (
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
            El código no se puede cambiar.
          </p>
        )}
      </div>

      <div style={formRow}>
        <label style={label}>Etiqueta visible <span style={requiredMark}>*</span></label>
        <Input value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)} placeholder="Ingresado" />
      </div>

      <div style={formRow}>
        <label style={label}>Descripción</label>
        <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={2} style={textarea} />
      </div>

      <div style={formRow}>
        <label style={label}>Color del badge</label>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Input type="color" value={color} onChange={(e) => setColor(e.target.value)} style={{ width: 60, padding: 2, height: 36 }} />
          <Input value={color} onChange={(e) => setColor(e.target.value)} style={{ width: 120, fontFamily: 'var(--font-mono)' }} />
          {COLORES_SUGERIDOS.map((c) => (
            <button key={c} onClick={() => setColor(c)} title={c} style={{ width: 24, height: 24, background: c, border: '1px solid var(--border-primary)', borderRadius: 4, cursor: 'pointer' }} />
          ))}
        </div>
      </div>

      <div style={{ width: 100, marginBottom: 12 }}>
        <label style={label}>Orden</label>
        <Input type="number" value={orden} onChange={(e) => setOrden(Number(e.target.value) || 0)} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={esInicial} onChange={(e) => setEsInicial(e.target.checked)} />
          Estado inicial (debe haber exactamente uno por versión)
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={esFinal} onChange={(e) => setEsFinal(e.target.checked)} />
          Estado final (puede haber varios)
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={permiteAdjuntar} onChange={(e) => setPermiteAdjuntar(e.target.checked)} />
          Permite adjuntar documentos
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={permiteComentar} onChange={(e) => setPermiteComentar(e.target.checked)} />
          Permite comentar
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={esperaIniciador} onChange={(e) => setEsperaIniciador(e.target.checked)} />
          Espera al iniciador (vecino) — corre el timer de desistimiento
        </label>
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '0 0 4px 22px' }}>
          Marcá los estados donde el expediente queda a la espera de documentación o respuesta del vecino.
          Vencido el SLA del tipo se le envían avisos (a los 30 y 60 días, y 72 h antes) y a los 90 días
          el trámite se da por desistido solo (plazos en Config → Sistema). Se puede cambiar aunque la
          versión esté publicada.
        </p>
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

const textarea: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-medium)', fontSize: 14,
  fontFamily: 'inherit', color: 'var(--fg-1)', background: 'var(--surface-100)',
  resize: 'vertical',
}
