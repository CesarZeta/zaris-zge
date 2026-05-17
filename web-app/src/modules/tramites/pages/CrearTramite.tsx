import React, { useState, createElement } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, icons as lucideIcons } from 'lucide-react'
import type { LucideProps } from 'lucide-react'
import { Button, Skeleton } from '../../../ui'
import { EntitySelect } from '../components/EntitySelect'
import { FormularioDinamico, validarDatos } from '../components/FormularioDinamico'
import { useTiposTramite, useTipoTramiteDetalle, useCrearTramite } from '../hooks/useTramites'
import { useNotificationsStore } from '../../../stores/notifications'
import type { IniciadorTipo, TipoTramite } from '../types'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

export function CrearTramite() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)

  const [idTipoSeleccionado, setIdTipoSeleccionado] = useState<number | null>(null)
  const [iniciadorTipo, setIniciadorTipo] = useState<IniciadorTipo | null>(null)
  const [idCiudadano, setIdCiudadano] = useState<number | null>(null)
  const [idEmpresa, setIdEmpresa] = useState<number | null>(null)
  const [idSubareaIniciadora, setIdSubareaIniciadora] = useState<number | null>(null)
  const [idRepresentante, setIdRepresentante] = useState<number | null>(null)
  const [asunto, setAsunto] = useState('')
  const [datos, setDatos] = useState<Record<string, unknown>>({})
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [confirmandoCambioTipo, setConfirmandoCambioTipo] = useState<number | null>(null)

  const tipos = useTiposTramite()
  const tipoDetalle = useTipoTramiteDetalle(idTipoSeleccionado)
  const crearMutation = useCrearTramite()

  function seleccionarTipo(tipo: TipoTramite) {
    if (idTipoSeleccionado === tipo.id_tipo_tramite) return
    if (Object.keys(datos).some((k) => datos[k] !== '' && datos[k] !== null)) {
      setConfirmandoCambioTipo(tipo.id_tipo_tramite)
      return
    }
    aplicarCambioTipo(tipo.id_tipo_tramite)
  }

  function aplicarCambioTipo(id: number) {
    setIdTipoSeleccionado(id)
    setIniciadorTipo(null)
    setIdCiudadano(null)
    setIdEmpresa(null)
    setIdSubareaIniciadora(null)
    setIdRepresentante(null)
    setDatos({})
    setErrores({})
    setConfirmandoCambioTipo(null)
  }

  function handleDato(nombre: string, valor: unknown) {
    setDatos((prev) => ({ ...prev, [nombre]: valor }))
    setErrores((prev) => { const next = { ...prev }; delete next[nombre]; return next })
  }

  async function handleCrear() {
    const tipo = tipoDetalle.data
    if (!tipo || !idTipoSeleccionado || !iniciadorTipo) {
      push({ kind: 'error', title: 'Faltan datos', body: 'Seleccioná un tipo de trámite y completá el iniciador.' })
      return
    }
    if (!asunto.trim()) {
      push({ kind: 'error', title: 'Asunto requerido', body: 'Ingresá el asunto del trámite.' })
      return
    }

    const campos = tipo.version.campos
    const errs = validarDatos(campos, datos)
    if (Object.keys(errs).length > 0) {
      setErrores(errs)
      push({ kind: 'error', title: 'Campos incompletos', body: 'Completá los campos obligatorios.' })
      return
    }

    if (iniciadorTipo === 'ciudadano' && !idCiudadano) {
      push({ kind: 'error', title: 'Iniciador requerido', body: 'Seleccioná el ciudadano.' }); return
    }
    if (iniciadorTipo === 'empresa' && !idEmpresa) {
      push({ kind: 'error', title: 'Iniciador requerido', body: 'Seleccioná la empresa.' }); return
    }
    if (iniciadorTipo === 'area_interna' && !idSubareaIniciadora) {
      push({ kind: 'error', title: 'Iniciador requerido', body: 'Seleccioná el área.' }); return
    }

    try {
      const result = await crearMutation.mutateAsync({
        id_tipo_tramite: idTipoSeleccionado,
        id_tipo_tramite_version: tipo.version.id_tipo_tramite_version,
        asunto: asunto.trim(),
        iniciador_tipo: iniciadorTipo,
        id_ciudadano_iniciador: iniciadorTipo === 'ciudadano' ? idCiudadano : null,
        id_empresa_iniciadora: iniciadorTipo === 'empresa' ? idEmpresa : null,
        id_subarea_iniciadora: iniciadorTipo === 'area_interna' ? idSubareaIniciadora : null,
        id_ciudadano_representante: idRepresentante ?? null,
        datos_jsonb: datos,
      })
      push({ kind: 'success', title: 'Trámite creado', body: result.numero_expediente })
      navigate(`/tramites/${result.numero_expediente}`)
    } catch (err) {
      push({ kind: 'error', title: 'Error al crear', body: (err as Error).message })
    }
  }

  const tiposItems = tipos.data?.items ?? []
  const camposOrdenados = tipoDetalle.data?.version.campos ?? []
  const tipoActual = tiposItems.find((t) => t.id_tipo_tramite === idTipoSeleccionado)
  const iniciadoresPermitidos = tipoActual?.iniciadores_permitidos ?? []
  const permiteRepresentante = tipoActual?.permite_representante ?? false

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 860 }}>
      <h1 style={h1Style}>Nuevo Trámite</h1>

      {/* Paso 1 — Tipo */}
      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>1. Tipo de trámite</h2>
        {tipos.isLoading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} height={90} />)}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
            {tiposItems.map((tipo) => (
              <TipoCard
                key={tipo.id_tipo_tramite}
                tipo={tipo}
                activo={idTipoSeleccionado === tipo.id_tipo_tramite}
                onClick={() => seleccionarTipo(tipo)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Confirmación de cambio de tipo */}
      {confirmandoCambioTipo != null && (
        <div style={alertStyle}>
          <p style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-display)' }}>
            Cambiar de tipo borrará los datos cargados. ¿Continuar?
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <Button variant="primary" onClick={() => aplicarCambioTipo(confirmandoCambioTipo)}>Sí, cambiar</Button>
            <Button variant="ghost" onClick={() => setConfirmandoCambioTipo(null)}>Cancelar</Button>
          </div>
        </div>
      )}

      {/* Paso 2 — Iniciador */}
      {idTipoSeleccionado && iniciadoresPermitidos.length > 0 && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>2. Iniciador</h2>

          {/* Radio de tipo */}
          {iniciadoresPermitidos.length > 1 && (
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 14 }}>
              {iniciadoresPermitidos.map((tipo) => (
                <label key={tipo} style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }}>
                  <input
                    type="radio"
                    name="iniciador_tipo"
                    value={tipo}
                    checked={iniciadorTipo === tipo}
                    onChange={() => {
                      setIniciadorTipo(tipo)
                      setIdCiudadano(null); setIdEmpresa(null); setIdSubareaIniciadora(null)
                    }}
                  />
                  {INICIADOR_LABELS[tipo]}
                </label>
              ))}
            </div>
          )}

          {/* Auto-selección si hay un único iniciador */}
          {iniciadoresPermitidos.length === 1 && iniciadorTipo !== iniciadoresPermitidos[0] && (
            <span style={{ display: 'none' }}>
              {/* side-effect: inicializa sin render de label */}
              {(() => { setTimeout(() => setIniciadorTipo(iniciadoresPermitidos[0]), 0); return null })()}
            </span>
          )}

          {/* Selector contextual */}
          {(iniciadorTipo === 'ciudadano' || (iniciadoresPermitidos.length === 1 && iniciadoresPermitidos[0] === 'ciudadano')) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={labelStyle}>Ciudadano</label>
              <EntitySelect
                endpoint={`${BASE}/api/v1/buc/ciudadanos/buscar`}
                idField="id_ciudadano"
                labelField="nombre_completo"
                value={idCiudadano}
                onChange={(id) => setIdCiudadano(id)}
                placeholder="Buscar ciudadano por nombre o DNI..."
              />
            </div>
          )}

          {(iniciadorTipo === 'empresa' || (iniciadoresPermitidos.length === 1 && iniciadoresPermitidos[0] === 'empresa')) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={labelStyle}>Empresa</label>
              <EntitySelect
                endpoint={`${BASE}/api/v1/buc/empresas/buscar`}
                idField="id_empresa"
                labelField="nombre"
                value={idEmpresa}
                onChange={(id) => setIdEmpresa(id)}
                placeholder="Buscar empresa por razón social o CUIT..."
              />
            </div>
          )}

          {(iniciadorTipo === 'area_interna' || (iniciadoresPermitidos.length === 1 && iniciadoresPermitidos[0] === 'area_interna')) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={labelStyle}>Área interna</label>
              <EntitySelect
                endpoint={`${BASE}/api/v1/admin/subareas`}
                idField="id_subarea"
                labelField="nombre"
                value={idSubareaIniciadora}
                onChange={(id) => setIdSubareaIniciadora(id)}
                placeholder="Buscar área o subárea..."
              />
            </div>
          )}

          {/* Representante (solo si empresa + permite_representante) */}
          {permiteRepresentante && iniciadorTipo === 'empresa' && idEmpresa && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 12 }}>
              <label style={labelStyle}>Representante (ciudadano)</label>
              <EntitySelect
                endpoint={`${BASE}/api/v1/buc/ciudadanos/buscar`}
                idField="id_ciudadano"
                labelField="nombre_completo"
                value={idRepresentante}
                onChange={(id) => setIdRepresentante(id)}
                placeholder="Buscar representante..."
              />
            </div>
          )}
        </section>
      )}

      {/* Paso 3 — Asunto */}
      {idTipoSeleccionado && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>3. Asunto</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={labelStyle}>
              Asunto <span style={{ color: 'var(--color-error)' }}>*</span>
            </label>
            <input
              value={asunto}
              onChange={(e) => setAsunto(e.target.value)}
              maxLength={500}
              placeholder="Describa brevemente el objeto del trámite..."
              style={inputStyle}
            />
            <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: 0, fontFamily: 'var(--font-display)' }}>
              {asunto.length}/500 caracteres
            </p>
          </div>
        </section>
      )}

      {/* Paso 4 — Formulario dinámico */}
      {idTipoSeleccionado && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>4. Datos del trámite</h2>
          {tipoDetalle.isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[1, 2, 3].map((i) => <Skeleton key={i} height={56} />)}
            </div>
          ) : camposOrdenados.filter((c) => c.tipo_dato !== 'archivo').length === 0 ? (
            <p style={{ fontSize: 13, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
              Este tipo de trámite no requiere datos adicionales.
            </p>
          ) : (
            <FormularioDinamico
              campos={camposOrdenados.filter((c) => c.tipo_dato !== 'archivo')}
              valores={datos}
              errores={errores}
              onChange={handleDato}
            />
          )}

          {/* Nota sobre archivos */}
          {camposOrdenados.some((c) => c.tipo_dato === 'archivo') && (
            <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(31,138,101,.08)', borderRadius: 'var(--radius-lg)', fontSize: 12, color: 'var(--fg-2)', fontFamily: 'var(--font-display)' }}>
              Los documentos requeridos se adjuntan una vez creado el trámite, desde la sección <strong>Documentos</strong>.
            </div>
          )}
        </section>
      )}

      {/* Acciones */}
      {idTipoSeleccionado && (
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingBottom: 40 }}>
          <Button variant="ghost" onClick={() => navigate('/tramites')}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            onClick={() => { void handleCrear() }}
            disabled={crearMutation.isPending}
            icon={<FileText size={15} strokeWidth={1.5} />}
          >
            {crearMutation.isPending ? 'Creando...' : 'Crear trámite'}
          </Button>
        </div>
      )}
    </div>
  )
}

function LucideIcono({ nombre }: { nombre: string | null | undefined }) {
  if (!nombre) return <span style={{ fontSize: 18 }}>📄</span>
  const key = nombre.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase()).replace(/^[a-z]/, (c) => c.toUpperCase()) as keyof typeof lucideIcons
  const Icon = lucideIcons[key] as React.FC<LucideProps> | undefined
  if (!Icon) return <span style={{ fontSize: 18 }}>📄</span>
  return createElement(Icon, { size: 20, strokeWidth: 1.5, color: 'var(--fg-2)' } as LucideProps)
}

function TipoCard({ tipo, activo, onClick }: { tipo: TipoTramite; activo: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '14px 16px',
        borderRadius: 'var(--radius-lg)',
        border: `2px solid ${activo ? 'var(--zaris-orange)' : 'var(--border-primary)'}`,
        background: activo ? 'rgba(245,78,0,.06)' : 'var(--surface-300)',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'all 150ms ease',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <LucideIcono nombre={tipo.icono} />
        <span style={{ fontSize: 10, background: 'var(--surface-400)', padding: '1px 6px', borderRadius: 'var(--radius-pill)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
          {tipo.prefijo}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }}>
        {tipo.nombre}
      </p>
      {tipo.descripcion && (
        <p style={{ margin: 0, fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', lineHeight: 1.4 }}>
          {tipo.descripcion.slice(0, 80)}{tipo.descripcion.length > 80 ? '…' : ''}
        </p>
      )}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {(tipo.iniciadores_permitidos ?? []).map((ini) => (
          <span key={ini} style={{ fontSize: 9, background: 'var(--surface-400)', padding: '1px 5px', borderRadius: 'var(--radius-pill)', color: 'var(--fg-3)', textTransform: 'capitalize' }}>
            {INICIADOR_LABELS[ini]}
          </span>
        ))}
      </div>
    </button>
  )
}

const INICIADOR_LABELS: Record<IniciadorTipo, string> = {
  ciudadano: 'Ciudadano',
  empresa: 'Empresa',
  area_interna: 'Área interna',
}

const h1Style: React.CSSProperties = { fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px', color: 'var(--fg-1)', margin: 0 }
const sectionStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 12, padding: '20px', background: 'var(--surface-300)', borderRadius: 'var(--radius-xl)', border: '1px solid var(--border-primary)' }
const sectionTitleStyle: React.CSSProperties = { margin: 0, fontSize: '1rem', fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }
const labelStyle: React.CSSProperties = { fontSize: 12, fontWeight: 500, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em' }
const inputStyle: React.CSSProperties = { fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', color: 'var(--fg-1)', background: 'transparent', padding: '9px 12px', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', outline: 'none', width: '100%', boxSizing: 'border-box' }
const alertStyle: React.CSSProperties = { padding: '14px 16px', background: 'rgba(245,127,23,.1)', border: '1px solid rgba(245,127,23,.3)', borderRadius: 'var(--radius-lg)' }
