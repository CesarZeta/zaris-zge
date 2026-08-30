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
  const [nuncaDepurar, setNuncaDepurar] = useState(tipo.retencion_nunca_depurar ?? false)
  const [slaDias, setSlaDias] = useState(tipo.sla_dias ?? 0)
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
        retencion_nunca_depurar: nuncaDepurar,
        sla_dias: slaDias,  // 0 = el backend vuelve al default global
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

      <label style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 14, cursor: 'pointer', marginBottom: 4 }}>
        <input type="checkbox" checked={nuncaDepurar} onChange={(e) => setNuncaDepurar(e.target.checked)} style={{ marginTop: 3 }} />
        Nunca depurar adjuntos de este tipo
      </label>
      <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '0 0 12px 24px' }}>
        Si está marcado, los archivos de los expedientes de este tipo se conservan indefinidamente
        (excepción a la política de retención por antigüedad). Útil para Habilitaciones u otros
        trámites con valor permanente.
      </p>

      <div style={{ width: 220, marginBottom: 12 }}>
        <label style={label}>SLA del trámite (días)</label>
        <Input type="number" min={0} value={slaDias} onChange={(e) => setSlaDias(Math.max(0, Number(e.target.value) || 0))} />
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
          Plazo esperado de resolución. 0 = usa el valor global (Config → Sistema). Vencido el SLA,
          en los estados que esperan al vecino arrancan los avisos de desistimiento.
        </p>
      </div>

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
