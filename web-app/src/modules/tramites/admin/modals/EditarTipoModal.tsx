import { useState } from 'react'
import { Button, Input } from '../../../../ui'
import { useActualizarTipo } from '../hooks'
import { ModalShell, label, errorMsg, formRow } from './_modalShell'
import type { IniciadorTipo, TipoTramiteAdmin } from '../../types'

const INICIADORES: IniciadorTipo[] = ['ciudadano', 'empresa', 'area_interna']

export function EditarTipoModal({
  tipo, onCerrar,
}: {
  tipo: TipoTramiteAdmin
  onCerrar: () => void
}) {
  const [nombre, setNombre] = useState(tipo.nombre)
  const [prefijo, setPrefijo] = useState(tipo.prefijo)
  const [descripcion, setDescripcion] = useState(tipo.descripcion ?? '')
  const [iniciadores, setIniciadores] = useState<IniciadorTipo[]>(tipo.iniciadores_permitidos)
  const [permiteRep, setPermiteRep] = useState(tipo.permite_representante)
  const [error, setError] = useState('')

  const actualizar = useActualizarTipo(tipo.id_tipo_tramite)

  function toggleIni(i: IniciadorTipo) {
    setIniciadores((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i])
  }

  async function handleGuardar() {
    setError('')
    if (!nombre.trim()) { setError('Nombre obligatorio'); return }
    if (!prefijo.trim()) { setError('Prefijo obligatorio'); return }
    if (iniciadores.length === 0) { setError('Al menos un iniciador'); return }
    try {
      await actualizar.mutateAsync({
        nombre: nombre.trim(),
        prefijo: prefijo.trim(),
        descripcion: descripcion.trim() || null,
        iniciadores_permitidos: iniciadores,
        permite_representante: permiteRep,
      })
      onCerrar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  return (
    <ModalShell titulo={`Editar tipo · ${tipo.codigo}`} onCerrar={onCerrar} ancho={520}>
      <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--fg-2)' }}>
        Editás datos identitarios del tipo. El circuito (estados, transiciones) se modifica
        desde el editor de versión.
      </p>

      <div style={formRow}>
        <label style={label}>Código</label>
        <Input value={tipo.codigo} disabled style={{ fontFamily: 'var(--font-mono)' }} />
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
          El código no se puede cambiar.
        </p>
      </div>

      <div style={formRow}>
        <label style={label}>Nombre</label>
        <Input value={nombre} onChange={(e) => setNombre(e.target.value)} />
      </div>

      <div style={formRow}>
        <label style={label}>Prefijo numerador</label>
        <Input value={prefijo} onChange={(e) => setPrefijo(e.target.value.toUpperCase())} style={{ width: 200, fontFamily: 'var(--font-mono)' }} />
      </div>

      <div style={formRow}>
        <label style={label}>Iniciadores permitidos</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {INICIADORES.map((i) => (
            <label key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, cursor: 'pointer', padding: '6px 10px', background: iniciadores.includes(i) ? 'var(--zaris-orange)' : 'var(--surface-300)', color: iniciadores.includes(i) ? 'white' : 'var(--fg-2)', borderRadius: 4 }}>
              <input type="checkbox" checked={iniciadores.includes(i)} onChange={() => toggleIni(i)} style={{ display: 'none' }} />
              {i}
            </label>
          ))}
        </div>
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer', marginBottom: 12 }}>
        <input type="checkbox" checked={permiteRep} onChange={(e) => setPermiteRep(e.target.checked)} />
        Permitir representante
      </label>

      <div style={formRow}>
        <label style={label}>Descripción</label>
        <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={2} style={textarea} />
      </div>

      {error && <p style={errorMsg}>{error}</p>}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="accent" onClick={handleGuardar} disabled={actualizar.isPending}>
          {actualizar.isPending ? 'Guardando…' : 'Guardar'}
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
