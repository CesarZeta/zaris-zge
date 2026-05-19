import { useState } from 'react'
import { Button, Input } from '../../../../ui'
import { useActualizarDocReq, useCrearDocReq } from '../hooks'
import { ModalShell, label, requiredMark, errorMsg, formRow } from './_modalShell'
import type { TipoTramiteEstado, TipoTramiteDocRequerido } from '../../types'

const APORTA = [
  { v: 'iniciador', l: 'El iniciador' },
  { v: 'oficina_actual', l: 'La oficina actual' },
  { v: 'cualquiera', l: 'Cualquiera' },
]

const FORMATOS_COMUNES = ['pdf', 'jpg', 'jpeg', 'png', 'webp', 'heic', 'doc', 'docx', 'xls', 'xlsx']

export function DocReqModal({
  idVersion, doc, estados, onCerrar,
}: {
  idVersion: number
  doc: TipoTramiteDocRequerido | null
  estados: TipoTramiteEstado[]
  onCerrar: () => void
}) {
  const esNuevo = doc === null
  const [nombre, setNombre] = useState(doc?.nombre ?? '')
  const [descripcion, setDescripcion] = useState(doc?.descripcion ?? '')
  const [idEstado, setIdEstado] = useState<number | null>(
    // El detalle público no expone id_tipo_tramite_estado, pero el endpoint admin sí.
    // Para edición usamos el dato del endpoint admin si vino:
    (doc as unknown as { id_tipo_tramite_estado?: number | null })?.id_tipo_tramite_estado ?? null
  )
  const [obligatorio, setObligatorio] = useState(doc?.obligatorio ?? true)
  const [formatos, setFormatos] = useState<string[]>(doc?.formatos_permitidos ?? ['pdf', 'jpg', 'png'])
  const [tamanoMax, setTamanoMax] = useState(doc?.tamano_max_mb ?? 10)
  const [requiereFirma, setRequiereFirma] = useState(doc?.requiere_firma ?? false)
  const [aporta, setAporta] = useState(doc?.quien_debe_adjuntar ?? 'iniciador')
  const [orden, setOrden] = useState(1)
  const [error, setError] = useState('')

  const crear = useCrearDocReq()
  const actualizar = useActualizarDocReq()

  function toggleFormato(f: string) {
    setFormatos((prev) => prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f])
  }

  async function handleGuardar() {
    setError('')
    if (!nombre.trim()) { setError('Nombre obligatorio'); return }
    if (formatos.length === 0) { setError('Elegí al menos un formato permitido'); return }
    try {
      if (esNuevo) {
        await crear.mutateAsync({
          idVersion,
          body: {
            nombre: nombre.trim(),
            descripcion: descripcion.trim() || null,
            id_tipo_tramite_estado: idEstado,
            obligatorio,
            formatos_permitidos: formatos,
            tamano_max_mb: tamanoMax,
            requiere_firma: requiereFirma,
            aporta_quien: aporta,
            orden,
          },
        })
      } else {
        await actualizar.mutateAsync({
          idDoc: doc!.id_tipo_tramite_documento_requerido,
          body: {
            nombre: nombre.trim(),
            descripcion: descripcion.trim() || null,
            id_tipo_tramite_estado: idEstado,
            obligatorio,
            formatos_permitidos: formatos,
            tamano_max_mb: tamanoMax,
            requiere_firma: requiereFirma,
            aporta_quien: aporta,
            orden,
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
    <ModalShell titulo={esNuevo ? 'Nuevo documento requerido' : `Editar documento · ${doc!.nombre}`} onCerrar={onCerrar}>
      <div style={formRow}>
        <label style={label}>Nombre <span style={requiredMark}>*</span></label>
        <Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="DNI del solicitante" />
      </div>

      <div style={formRow}>
        <label style={label}>Descripción</label>
        <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={2} style={textarea} />
      </div>

      <div style={formRow}>
        <label style={label}>Vincular al estado</label>
        <select value={idEstado ?? ''} onChange={(e) => setIdEstado(e.target.value ? Number(e.target.value) : null)} style={select}>
          <option value="">(al iniciar el trámite)</option>
          {estados.map((es) => <option key={es.id_tipo_tramite_estado} value={es.id_tipo_tramite_estado}>{es.etiqueta}</option>)}
        </select>
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
          Si no elegís estado, será un documento exigible al inicio.
        </p>
      </div>

      <div style={formRow}>
        <label style={label}>Aporta</label>
        <select value={aporta} onChange={(e) => setAporta(e.target.value)} style={select}>
          {APORTA.map((a) => <option key={a.v} value={a.v}>{a.l}</option>)}
        </select>
      </div>

      <div style={formRow}>
        <label style={label}>Formatos permitidos</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {FORMATOS_COMUNES.map((f) => (
            <label key={f} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, cursor: 'pointer', padding: '4px 8px', background: formatos.includes(f) ? 'var(--zaris-orange)' : 'var(--surface-300)', color: formatos.includes(f) ? 'white' : 'var(--fg-2)', borderRadius: 4 }}>
              <input type="checkbox" checked={formatos.includes(f)} onChange={() => toggleFormato(f)} style={{ display: 'none' }} />
              {f}
            </label>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <label style={label}>Tamaño máx (MB)</label>
          <Input type="number" value={tamanoMax} onChange={(e) => setTamanoMax(Number(e.target.value) || 10)} style={{ width: 100 }} />
        </div>
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
          <input type="checkbox" checked={requiereFirma} onChange={(e) => setRequiereFirma(e.target.checked)} />
          Requiere firma digital
        </label>
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
const select: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-medium)', fontSize: 14,
  fontFamily: 'inherit', color: 'var(--fg-1)', background: 'var(--surface-100)',
}
