import { useState } from 'react'
import { Button, Input } from '../../../../ui'
import { useActualizarTransicion, useCrearTransicion } from '../hooks'
import { ModalShell, label, requiredMark, errorMsg, formRow } from './_modalShell'
import type { TipoTramiteEstado, TipoTramiteTransicion, TipoAccionTransicion } from '../../types'

// BUG-04: cada transición tiene una semántica. El color guía al agente.
const TIPOS_ACCION: { v: TipoAccionTransicion; l: string; color: string }[] = [
  { v: 'aprobar', l: 'Aprobar', color: 'var(--color-success)' },
  { v: 'rechazar', l: 'Rechazar', color: 'var(--color-error)' },
  { v: 'derivar', l: 'Derivar', color: '#6a1b9a' },
  { v: 'avanzar', l: 'Avanzar', color: 'var(--fg-2)' },
  { v: 'otro', l: 'Otro', color: 'var(--fg-3)' },
]

export function TransicionModal({
  idVersion, transicion, estados, onCerrar,
}: {
  idVersion: number
  transicion: TipoTramiteTransicion | null
  estados: TipoTramiteEstado[]
  onCerrar: () => void
}) {
  const esNuevo = transicion === null
  const [origenId, setOrigenId] = useState<number>(transicion?.id_estado_origen ?? estados[0]?.id_tipo_tramite_estado ?? 0)
  const [destinoId, setDestinoId] = useState<number>(transicion?.id_estado_destino ?? estados[1]?.id_tipo_tramite_estado ?? estados[0]?.id_tipo_tramite_estado ?? 0)
  const [etiqueta, setEtiqueta] = useState(transicion?.etiqueta_accion ?? '')
  const [tipoAccion, setTipoAccion] = useState<TipoAccionTransicion>(transicion?.tipo_accion ?? 'avanzar')
  const [orden, setOrden] = useState(transicion?.orden ?? 1)
  const [requiereComentario, setRequiereComentario] = useState(transicion?.requiere_comentario ?? false)
  const [requiereAdjunto, setRequiereAdjunto] = useState(transicion?.requiere_adjunto ?? false)
  const [notificaIniciador, setNotificaIniciador] = useState(transicion?.notifica_iniciador ?? true)
  const [mensajeIniciador, setMensajeIniciador] = useState(transicion?.mensaje_iniciador ?? '')
  const [error, setError] = useState('')

  const crear = useCrearTransicion()
  const actualizar = useActualizarTransicion()

  async function handleGuardar() {
    setError('')
    if (!etiqueta.trim()) { setError('Etiqueta de acción obligatoria'); return }
    if (origenId === destinoId) { setError('Origen y destino no pueden ser el mismo estado'); return }
    try {
      const bodyComun = {
        id_estado_origen: origenId,
        id_estado_destino: destinoId,
        etiqueta_accion: etiqueta.trim(),
        tipo_accion: tipoAccion,
        orden,
        requiere_comentario: requiereComentario,
        requiere_adjunto: requiereAdjunto,
        notifica_iniciador: notificaIniciador,
        mensaje_iniciador: mensajeIniciador.trim() || null,
      }
      if (esNuevo) {
        await crear.mutateAsync({ idVersion, body: bodyComun })
      } else {
        await actualizar.mutateAsync({
          idTrans: transicion!.id_tipo_tramite_transicion,
          body: bodyComun,
        })
      }
      onCerrar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  const pending = crear.isPending || actualizar.isPending

  if (estados.length < 2) {
    return (
      <ModalShell titulo="Nueva transición" onCerrar={onCerrar}>
        <p style={{ color: 'var(--color-error)' }}>
          Necesitás al menos 2 estados para crear transiciones.
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
          <Button onClick={onCerrar}>Cerrar</Button>
        </div>
      </ModalShell>
    )
  }

  return (
    <ModalShell titulo={esNuevo ? 'Nueva transición del FSM' : `Editar transición · ${transicion!.etiqueta_accion}`} onCerrar={onCerrar}>
      <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--fg-2)' }}>
        Las transiciones son los "botones" disponibles en cada estado para pasar al siguiente.
      </p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <label style={label}>Estado origen <span style={requiredMark}>*</span></label>
          <select value={origenId} onChange={(e) => setOrigenId(Number(e.target.value))} style={select}>
            {estados.map((e) => <option key={e.id_tipo_tramite_estado} value={e.id_tipo_tramite_estado}>{e.etiqueta}</option>)}
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={label}>Estado destino <span style={requiredMark}>*</span></label>
          <select value={destinoId} onChange={(e) => setDestinoId(Number(e.target.value))} style={select}>
            {estados.map((e) => <option key={e.id_tipo_tramite_estado} value={e.id_tipo_tramite_estado}>{e.etiqueta}</option>)}
          </select>
        </div>
      </div>

      <div style={formRow}>
        <label style={label}>Tipo de acción <span style={requiredMark}>*</span></label>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TIPOS_ACCION.map((ta) => {
            const activo = tipoAccion === ta.v
            return (
              <button
                key={ta.v}
                type="button"
                onClick={() => setTipoAccion(ta.v)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '5px 12px', borderRadius: 'var(--radius-pill)',
                  border: `1.5px solid ${activo ? ta.color : 'var(--border-medium)'}`,
                  background: activo ? ta.color : 'transparent',
                  color: activo ? 'white' : 'var(--fg-2)',
                  cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-display)',
                  fontWeight: activo ? 600 : 400,
                }}
              >
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: activo ? 'white' : ta.color }} />
                {ta.l}
              </button>
            )
          })}
        </div>
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '6px 0 0' }}>
          Una sola intención por transición. El botón del agente se colorea según esto (verde aprobar, rojo rechazar).
        </p>
      </div>

      <div style={formRow}>
        <label style={label}>Etiqueta del botón <span style={requiredMark}>*</span></label>
        <Input value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)} placeholder="Aprobar" />
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
          Lo que ve el agente: "Aprobar", "Rechazar", "Pasar a revisión"…
        </p>
      </div>

      <div style={{ width: 100, marginBottom: 12 }}>
        <label style={label}>Orden</label>
        <Input type="number" value={orden} onChange={(e) => setOrden(Number(e.target.value) || 0)} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={requiereComentario} onChange={(e) => setRequiereComentario(e.target.checked)} />
          Requiere comentario obligatorio
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={requiereAdjunto} onChange={(e) => setRequiereAdjunto(e.target.checked)} />
          Requiere al menos un adjunto nuevo
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={notificaIniciador} onChange={(e) => setNotificaIniciador(e.target.checked)} />
          Notifica al iniciador (cuando se ejecute)
        </label>
      </div>

      {notificaIniciador && (
        <div style={{ ...formRow, marginTop: 12 }}>
          <label style={label}>Mensaje al iniciador</label>
          <textarea
            value={mensajeIniciador}
            onChange={(e) => setMensajeIniciador(e.target.value)}
            rows={2}
            placeholder="Ej: Tu trámite fue aprobado. Podés retirar la documentación en la oficina."
            style={textareaMensaje}
          />
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
            Texto que recibe el vecino (o el área iniciadora) cuando se ejecuta esta transición. Si lo dejás vacío, se envía un mensaje genérico.
          </p>
        </div>
      )}

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
const textareaMensaje: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-medium)', fontSize: 14,
  fontFamily: 'inherit', color: 'var(--fg-1)', background: 'var(--surface-100)',
  resize: 'vertical',
}
