import { useEffect, useState } from 'react'
import { Button, Input } from '../../../../ui'
import { useActualizarAprobReq, useCrearAprobReq } from '../hooks'
import { ModalShell, label, requiredMark, errorMsg, formRow } from './_modalShell'
import type { TipoTramiteEstado } from '../../types'
import type { TipoTramiteAprobReq } from '../api'
import { listarDestinatariosPase, type DestinatariosPase } from '../../lib/api'

type AprobTipo = 'subarea' | 'equipo' | 'agente'

export function AprobReqModal({
  idVersion, aprob, estados, onCerrar,
}: {
  idVersion: number
  aprob: TipoTramiteAprobReq | null
  estados: TipoTramiteEstado[]
  onCerrar: () => void
}) {
  const esNuevo = aprob === null
  const [idEstado, setIdEstado] = useState<number | null>(aprob?.id_tipo_tramite_estado ?? null)
  const [etiqueta, setEtiqueta] = useState(aprob?.etiqueta ?? '')
  const [bloqueante, setBloqueante] = useState(aprob?.bloqueante ?? true)
  const [aprobTipo, setAprobTipo] = useState<AprobTipo>((aprob?.aprobador_tipo as AprobTipo) ?? 'subarea')
  const [idAprobador, setIdAprobador] = useState<number | null>(
    aprob?.id_subarea_aprobadora ?? aprob?.id_equipo_aprobador ?? aprob?.id_agente_aprobador ?? null
  )
  const [orden, setOrden] = useState(aprob?.orden ?? 1)
  const [error, setError] = useState('')

  const [opciones, setOpciones] = useState<DestinatariosPase | null>(null)

  const crear = useCrearAprobReq()
  const actualizar = useActualizarAprobReq()

  useEffect(() => {
    listarDestinatariosPase().then(setOpciones).catch(() => setOpciones(null))
  }, [])

  const lista: { id: number; nombre: string }[] =
    aprobTipo === 'subarea'
      ? (opciones?.subareas ?? [])
      : aprobTipo === 'equipo'
        ? (opciones?.equipos ?? [])
        : (opciones?.agentes ?? []).map((a) => ({ id: a.id, nombre: a.nombre }))

  function cambiarTipo(t: AprobTipo) {
    setAprobTipo(t)
    setIdAprobador(null)
  }

  async function handleGuardar() {
    setError('')
    if (idEstado === null) { setError('Elegí la etapa donde se exige la aprobación'); return }
    if (!etiqueta.trim()) { setError('La etiqueta es obligatoria'); return }
    if (idAprobador === null) { setError('Elegí quién debe aprobar'); return }
    const body = {
      id_tipo_tramite_estado: idEstado,
      aprobador_tipo: aprobTipo,
      id_subarea_aprobadora: aprobTipo === 'subarea' ? idAprobador : null,
      id_equipo_aprobador: aprobTipo === 'equipo' ? idAprobador : null,
      id_agente_aprobador: aprobTipo === 'agente' ? idAprobador : null,
      etiqueta: etiqueta.trim(),
      bloqueante,
      orden,
    }
    try {
      if (esNuevo) await crear.mutateAsync({ idVersion, body })
      else await actualizar.mutateAsync({ idAprob: aprob!.id_tipo_tramite_aprobacion_requerida, body })
      onCerrar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  const pending = crear.isPending || actualizar.isPending

  return (
    <ModalShell titulo={esNuevo ? 'Nueva aprobación por etapa' : `Editar aprobación · ${aprob!.etiqueta}`} onCerrar={onCerrar}>
      <div style={formRow}>
        <label style={label}>Etapa donde se exige <span style={requiredMark}>*</span></label>
        <select value={idEstado ?? ''} onChange={(e) => setIdEstado(e.target.value ? Number(e.target.value) : null)} style={select}>
          <option value="">— Elegir etapa —</option>
          {estados.map((es) => <option key={es.id_tipo_tramite_estado} value={es.id_tipo_tramite_estado}>{es.etiqueta}</option>)}
        </select>
      </div>

      <div style={formRow}>
        <label style={label}>Etiqueta (qué se aprueba) <span style={requiredMark}>*</span></label>
        <Input value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)} placeholder="Visto bueno de Legales" />
      </div>

      <div style={formRow}>
        <label style={label}>Quién debe aprobar <span style={requiredMark}>*</span></label>
        <select value={aprobTipo} onChange={(e) => cambiarTipo(e.target.value as AprobTipo)} style={select}>
          <option value="subarea">Subárea</option>
          <option value="equipo">Mesa / Equipo</option>
          <option value="agente">Agente (persona)</option>
        </select>
      </div>

      <div style={formRow}>
        <label style={label}>{aprobTipo === 'subarea' ? 'Subárea' : aprobTipo === 'equipo' ? 'Mesa / Equipo' : 'Agente'} aprobador <span style={requiredMark}>*</span></label>
        <select value={idAprobador ?? ''} onChange={(e) => setIdAprobador(e.target.value ? Number(e.target.value) : null)} style={select}>
          <option value="">{opciones ? '— Elegir —' : 'Cargando…'}</option>
          {lista.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
        </select>
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 12, alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, cursor: 'pointer' }}>
          <input type="checkbox" checked={bloqueante} onChange={(e) => setBloqueante(e.target.checked)} />
          Bloquea el avance hasta estar aprobada
        </label>
        <div style={{ marginLeft: 'auto', width: 90 }}>
          <label style={label}>Orden</label>
          <Input type="number" value={orden} onChange={(e) => setOrden(Number(e.target.value) || 0)} />
        </div>
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
