import { useState } from 'react'
import { Button, Input } from '../../../../ui'
import { useCrearTipo } from '../hooks'
import { ModalShell, label, requiredMark, errorMsg, formRow } from './_modalShell'
import type { IniciadorTipo } from '../../types'

const INICIADORES: IniciadorTipo[] = ['ciudadano', 'empresa', 'area_interna']

export function NuevoTipoModal({
  onCerrar, onCreado,
}: {
  onCerrar: () => void
  onCreado: (idTipo: number) => void
}) {
  const [codigo, setCodigo] = useState('')
  const [nombre, setNombre] = useState('')
  const [prefijo, setPrefijo] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [iniciadores, setIniciadores] = useState<IniciadorTipo[]>(['ciudadano'])
  const [permiteRep, setPermiteRep] = useState(false)
  const [largoCorr, setLargoCorr] = useState(4)
  const [error, setError] = useState('')

  const crear = useCrearTipo()

  function toggleIni(i: IniciadorTipo) {
    setIniciadores((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i])
  }

  async function handleGuardar() {
    setError('')
    if (!codigo.trim()) { setError('Código obligatorio'); return }
    if (!/^[a-z][a-z0-9-]{0,49}$/.test(codigo.trim())) {
      setError('Código debe ser kebab-case (a-z, 0-9, guiones), empezar con letra')
      return
    }
    if (!nombre.trim()) { setError('Nombre obligatorio'); return }
    if (!prefijo.trim()) { setError('Prefijo obligatorio'); return }
    if (!/^[A-Z0-9]{1,20}$/.test(prefijo.trim())) {
      setError('Prefijo: MAYÚSCULAS y números, máx 20')
      return
    }
    if (iniciadores.length === 0) { setError('Al menos un iniciador'); return }
    try {
      const res = await crear.mutateAsync({
        codigo: codigo.trim(),
        nombre: nombre.trim(),
        prefijo: prefijo.trim(),
        descripcion: descripcion.trim() || null,
        iniciadores_permitidos: iniciadores,
        permite_representante: permiteRep,
        largo_correlativo: largoCorr,
      })
      onCreado(res.id_tipo_tramite)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al crear')
    }
  }

  return (
    <ModalShell titulo="Nuevo tipo de trámite" onCerrar={onCerrar} ancho={560}>
      <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--fg-2)' }}>
        Se creará el tipo con una versión <strong>v1 en borrador</strong>. Después podrás
        agregar estados, transiciones y campos antes de publicarla.
      </p>

      <div style={formRow}>
        <label style={label}>Código <span style={requiredMark}>*</span></label>
        <Input value={codigo} onChange={(e) => setCodigo(e.target.value.toLowerCase())} placeholder="poda-arbol" />
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
          Identificador único. Kebab-case (a-z, 0-9, guiones).
        </p>
      </div>

      <div style={formRow}>
        <label style={label}>Nombre <span style={requiredMark}>*</span></label>
        <Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Poda de árbol" />
      </div>

      <div style={formRow}>
        <label style={label}>Prefijo numerador <span style={requiredMark}>*</span></label>
        <Input value={prefijo} onChange={(e) => setPrefijo(e.target.value.toUpperCase())} placeholder="POD" style={{ width: 200, fontFamily: 'var(--font-mono)' }} />
        <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '4px 0 0' }}>
          Ej: POD → expedientes "POD-LPL-2026-0001"
        </p>
      </div>

      <div style={formRow}>
        <label style={label}>Iniciadores permitidos <span style={requiredMark}>*</span></label>
        <div style={{ display: 'flex', gap: 8 }}>
          {INICIADORES.map((i) => (
            <label key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, cursor: 'pointer', padding: '6px 10px', background: iniciadores.includes(i) ? 'var(--zaris-orange)' : 'var(--surface-300)', color: iniciadores.includes(i) ? 'white' : 'var(--fg-2)', borderRadius: 4 }}>
              <input type="checkbox" checked={iniciadores.includes(i)} onChange={() => toggleIni(i)} style={{ display: 'none' }} />
              {i}
            </label>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ width: 160 }}>
          <label style={label}>Largo correlativo</label>
          <Input type="number" min={1} max={8} value={largoCorr} onChange={(e) => setLargoCorr(Number(e.target.value) || 4)} />
        </div>
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer', marginBottom: 12 }}>
        <input type="checkbox" checked={permiteRep} onChange={(e) => setPermiteRep(e.target.checked)} />
        Permitir representante (ciudadano apoderado)
      </label>

      <div style={formRow}>
        <label style={label}>Descripción</label>
        <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={2} style={textarea} />
      </div>

      {error && <p style={errorMsg}>{error}</p>}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="accent" onClick={handleGuardar} disabled={crear.isPending}>
          {crear.isPending ? 'Creando…' : 'Crear tipo'}
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
