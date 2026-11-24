import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useNotificationsStore } from '../../../stores/notifications'
import { useEmpresasVinculadas } from '../hooks/useCiudadanos'
import { type ModoFicha, useFichaCiudadano } from '../hooks/useFichaCiudadano'
import { CiudadanoForm } from '../components/CiudadanoForm'
import { CuentasChips } from '../components/CuentasChips'
import { IdentidadPanel } from '../components/IdentidadPanel'
import { EmpresaVinculadaPanel } from '../components/EmpresaVinculadaPanel'

export function FormView() {
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams<{ id?: string }>()
  const push = useNotificationsStore((s) => s.push)

  // Modo: derivado de la URL.
  // /ciudadanos/nuevo               → new
  // /ciudadanos/:id                 → view
  // /ciudadanos/:id/editar          → edit
  const modo: ModoFicha = useMemo(() => {
    if (location.pathname.endsWith('/nuevo')) return 'new'
    if (location.pathname.endsWith('/editar')) return 'edit'
    return 'view'
  }, [location.pathname])

  const id = params.id ? Number(params.id) : null
  const readonly = modo === 'view'

  const ficha = useFichaCiudadano({ modo, id })
  const { form, errores, detalle, handleChange, yaTieneZaris } = ficha
  const empresas = useEmpresasVinculadas(modo === 'new' ? null : id)

  const [empPanelOpen, setEmpPanelOpen] = useState(false)
  const [bloqueoEmpresaGuardar, setBloqueoEmpresaGuardar] = useState(false)

  useEffect(() => {
    if (modo === 'new') setEmpPanelOpen(false)
    else if (detalle.data?.emp_chk) setEmpPanelOpen(true)
  }, [modo, detalle.data])

  async function handleGuardar() {
    const r = await ficha.guardar()
    if (!r) return
    const { ciudadano: c, avisoZaris } = r
    const body = `${c.apellido}, ${c.nombre}.${avisoZaris}`
    const ttl = avisoZaris ? 8000 : undefined
    if (modo === 'new') {
      push({ kind: 'success', title: 'Ciudadano dado de alta', body, ttl })
      if (form.emp_chk) {
        // Quedarse en edicion del nuevo ciudadano y abrir panel empresa
        navigate(`/ciudadanos/${c.id_ciudadano}/editar`, { replace: true })
        setEmpPanelOpen(true)
      } else {
        navigate('/ciudadanos')
      }
    } else {
      push({ kind: 'success', title: 'Ciudadano actualizado', body, ttl })
      navigate('/ciudadanos')
    }
  }

  // ── Toggle emp_chk ──
  function handleEmpChk(checked: boolean) {
    handleChange('emp_chk', checked)
    if (!checked) {
      setEmpPanelOpen(false)
      return
    }
    if (modo === 'edit' && id) {
      setEmpPanelOpen(true)
    } else if (modo === 'new') {
      push({ kind: 'info', title: 'Guardá el ciudadano primero para vincular la empresa' })
    }
  }

  // Estado de UI superior
  const titulo = modo === 'new' ? 'Alta de ciudadano' : modo === 'edit' ? 'Modificar ciudadano' : 'Consulta de ciudadano'
  const estadoBadge = modo === 'new'
    ? { label: 'NUEVO', bg: 'rgba(31,138,101,.12)', fg: 'var(--color-success)' }
    : modo === 'edit'
      ? { label: 'EDICIÓN', bg: 'rgba(192,133,50,.14)', fg: 'var(--zaris-gold, #c08532)' }
      : { label: 'CONSULTA', bg: 'rgba(38,37,30,.08)', fg: 'var(--fg-2)' }

  if (modo !== 'new' && detalle.isLoading) {
    return <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando ciudadano...</div>
  }
  if (modo !== 'new' && detalle.isError) {
    return <div style={{ color: 'var(--color-error)', padding: 20 }}>Error: {(detalle.error as Error).message}</div>
  }

  return (
    <>
      <section style={cardStyle}>
        <header style={cardHeaderStyle}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-title-sm)', fontWeight: 500, color: 'var(--fg-1)' }}>
            {titulo}
          </h2>
          <span style={{
            display: 'inline-flex', alignItems: 'center', padding: '4px 12px',
            borderRadius: 'var(--radius-pill)', fontSize: 'var(--size-caption)',
            fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
            background: estadoBadge.bg, color: estadoBadge.fg,
          }}>
            {estadoBadge.label}
          </span>
        </header>

        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {modo !== 'new' && id ? <CuentasChips idCiudadano={id} /> : null}
          {modo !== 'new' && id ? <IdentidadPanel idCiudadano={id} /> : null}
          <CiudadanoForm
            form={form}
            errores={errores}
            readonly={readonly}
            esAlta={modo === 'new'}
            nacionalidades={ficha.nacionalidades}
            puedeMarcarFuncionario={ficha.esAdmin}
            yaTieneZaris={yaTieneZaris}
            mostrarCamposZaris={ficha.debeCrearCuentaZaris && !readonly}
            onChange={handleChange}
            onCuilBlur={ficha.handleCuilBlur}
            onEmpChkChange={handleEmpChk}
          />
        </div>

        <footer style={cardFooterStyle}>
          <button onClick={() => navigate('/ciudadanos')} style={btnGhost}>
            {readonly ? '← Volver' : 'Cancelar'}
          </button>
          {!readonly && (
            <button onClick={handleGuardar} disabled={ficha.guardando || bloqueoEmpresaGuardar} style={btnPrimary}>
              {ficha.guardando ? 'Guardando...' : 'Guardar ciudadano'}
            </button>
          )}
        </footer>
      </section>

      {/* Panel empresa vinculada */}
      {(empPanelOpen || (empresas.data && empresas.data.length > 0 && form.emp_chk)) && id && (
        <EmpresaVinculadaPanel
          idCiudadano={id}
          readonly={readonly}
          modoAlta={!empresas.data || empresas.data.length === 0}
          empresa={empresas.data?.[0]}
          onBusy={setBloqueoEmpresaGuardar}
        />
      )}
    </>
  )
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-xl)',
  boxShadow: 'var(--shadow-ambient)',
  overflow: 'hidden',
}

const cardHeaderStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 20px',
  borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}

const cardFooterStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 10,
  padding: '14px 20px',
  borderTop: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}

const btnPrimary: React.CSSProperties = {
  padding: '10px 18px',
  background: 'var(--zaris-dark)',
  color: 'var(--zaris-cream)',
  border: 'none',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  fontWeight: 500,
  cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '10px 18px',
  background: 'transparent',
  color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  cursor: 'pointer',
}
