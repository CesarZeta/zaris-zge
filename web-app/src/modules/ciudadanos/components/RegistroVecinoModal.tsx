import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { estadoCuentasCiudadano } from '../api/ciudadanosApi'
import { useEmpresasVinculadas } from '../hooks/useCiudadanos'
import { useFichaCiudadano } from '../hooks/useFichaCiudadano'
import type { Ciudadano } from '../types/ciudadano'
import { CiudadanoForm } from './CiudadanoForm'
import { EmpresaVinculadaPanel } from './EmpresaVinculadaPanel'

interface Props {
  /** null = persona nueva; con id, se completa su ficha para que tenga cuenta. */
  idCiudadano: number | null
  /** Documento tipeado en el buscador (solo alta). */
  docInicial?: string
  onListo: (c: Ciudadano) => void
  onCerrar: () => void
}

/**
 * Registro del vecino sin salir de lo que se está cargando (PLAN_REGISTRO_PREVIO.md, F2).
 *
 * Va en un portal sobre `document.body` y con su propio overlay: se abre desde formularios que
 * ya son un `Modal` de Agenda, y dos `Modal` apilados se cierran juntos con Escape. No se cierra
 * con clic afuera ni con Escape: es una carga larga y se perdería lo escrito.
 */
export function RegistroVecinoModal({ idCiudadano, docInicial, onListo, onCerrar }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const esAlta = idCiudadano == null
  const ficha = useFichaCiudadano({ modo: esAlta ? 'new' : 'edit', id: idCiudadano, docInicial })
  const [guardado, setGuardado] = useState<Ciudadano | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const empresas = useEmpresasVinculadas(guardado?.id_ciudadano ?? idCiudadano)

  // Escape no llega al modal de abajo (se registra en captura, antes que el suyo).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') e.stopImmediatePropagation() }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [])

  const esFichaDemo = !!ficha.cuentas.data?.vecino.ficha_demo
  const cargandoFicha = !esAlta && (ficha.detalle.isLoading || ficha.cuentas.isLoading)
  const errorFicha = !esAlta && ficha.detalle.isError

  async function handleGuardar() {
    if (ocupado) return
    setOcupado(true)
    setAviso(null)
    try {
      const r = await ficha.guardar()
      if (!r) return
      // El guardado puede salir bien y la cuenta no crearse (DNI de prueba, o un correo que ya
      // es de la cuenta de otra persona): sin cuenta no se sigue, y se dice por qué.
      const cuentas = await estadoCuentasCiudadano(r.ciudadano.id_ciudadano).catch(() => null)
      if (cuentas && cuentas.vecino.estado === 'sin_cuenta') {
        setAviso(cuentas.vecino.ficha_demo
          ? 'La ficha se guardó, pero el DNI sigue siendo de prueba (rango 99.000.000) y no se le crea la cuenta. Cargá el DNI real y volvé a guardar.'
          : 'La ficha se guardó, pero la cuenta no se creó: el correo ya es de la cuenta de otra persona. Cambialo y volvé a guardar.')
        return
      }
      push({
        kind: 'success',
        title: esAlta ? 'Vecino registrado' : 'Ficha completada',
        body: `${r.ciudadano.apellido}, ${r.ciudadano.nombre}. Se le envió el correo de activación.${r.avisoZaris}`,
      })
      if (ficha.form.emp_chk && (empresas.data ?? []).length === 0) setGuardado(r.ciudadano)
      else onListo(r.ciudadano)
    } finally {
      setOcupado(false)
    }
  }

  const yaVinculada = (empresas.data ?? [])[0]

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Registro del vecino"
      // El portal burbujea por el árbol de React: nada de lo que pasa acá llega al formulario de abajo.
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      onSubmit={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
      style={overlay}
    >
      <div style={caja}>
        <header style={cabecera}>
          <h2 style={titulo}>
            {guardado ? 'Empresa que representa' : esAlta ? 'Registrar un vecino' : 'Completar el registro del vecino'}
          </h2>
          <button type="button" aria-label="Cerrar" onClick={() => (guardado ? onListo(guardado) : onCerrar())} style={cerrar}>
            <X size={18} strokeWidth={1.5} />
          </button>
        </header>

        <div style={{ overflowY: 'auto', flex: 1, padding: '16px 20px' }}>
          {guardado ? (
            <>
              <p style={nota}>
                {yaVinculada
                  ? `La empresa quedó vinculada a ${guardado.apellido}, ${guardado.nombre}.`
                  : `${guardado.apellido}, ${guardado.nombre} ya está registrado. Podés cargar ahora la empresa que representa, o seguir sin ella.`}
              </p>
              <EmpresaVinculadaPanel
                idCiudadano={guardado.id_ciudadano}
                readonly={false}
                modoAlta={!yaVinculada}
                empresa={yaVinculada}
                onBusy={setOcupado}
              />
            </>
          ) : cargandoFicha ? (
            <p style={nota}>Cargando la ficha…</p>
          ) : errorFicha ? (
            <p style={{ ...nota, color: 'var(--color-error)' }}>No se pudo cargar la ficha: {(ficha.detalle.error as Error).message}</p>
          ) : (
            <>
              <p style={nota}>
                {esAlta
                  ? 'Lo que estabas cargando queda como está: al guardar volvés ahí con el vecino elegido.'
                  : esFichaDemo
                    ? 'Este vecino no tiene cuenta en el portal porque su ficha tiene un DNI de prueba. Cargá el DNI real y los datos que falten: al guardar se crea la cuenta y volvés a lo que estabas cargando.'
                    : 'Este vecino todavía no tiene cuenta en el portal, y sin ella no se puede cargar nada a su nombre. Revisá sus datos y guardá: se crea la cuenta, le llega el correo de activación y volvés a lo que estabas cargando.'}
              </p>
              <CiudadanoForm
                form={ficha.form}
                errores={ficha.errores}
                readonly={false}
                esAlta={esAlta}
                nacionalidades={ficha.nacionalidades}
                puedeMarcarFuncionario={ficha.esAdmin}
                yaTieneZaris={ficha.yaTieneZaris}
                mostrarCamposZaris={ficha.debeCrearCuentaZaris}
                ocultarFuncionario={!ficha.debeCrearCuentaZaris}
                onChange={ficha.handleChange}
                onCuilBlur={ficha.handleCuilBlur}
                onEmpChkChange={(v) => ficha.handleChange('emp_chk', v)}
              />
            </>
          )}
        </div>

        <footer style={pie}>
          {aviso && <div role="alert" style={{ flex: 1, fontSize: 13, color: 'var(--color-error)' }}>{aviso}</div>}
          {guardado ? (
            <Button variant="accent" disabled={ocupado} onClick={() => onListo(guardado)}>Seguir con este vecino</Button>
          ) : (
            <>
              <Button variant="ghost" disabled={ocupado} onClick={onCerrar}>Cancelar</Button>
              <Button
                variant="accent"
                disabled={ocupado || ficha.guardando || cargandoFicha || errorFicha}
                onClick={() => { void handleGuardar() }}
              >
                {ocupado || ficha.guardando ? 'Guardando…' : 'Guardar y seguir'}
              </Button>
            </>
          )}
        </footer>
      </div>
    </div>,
    document.body,
  )
}

const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(38,37,30,.45)', zIndex: 1200,
  display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '32px 24px 24px',
}
const caja: React.CSSProperties = {
  width: 860, maxWidth: '100%', maxHeight: 'calc(100vh - 56px)', background: 'var(--surface-100)',
  borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-card)', display: 'flex', flexDirection: 'column',
}
const cabecera: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 20px', borderBottom: '1px solid var(--border-primary)',
}
const titulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-title-sm)', fontWeight: 500, color: 'var(--fg-1)',
}
const cerrar: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-3)', padding: 4, display: 'inline-flex',
}
const nota: React.CSSProperties = { margin: '0 0 16px', fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.5 }
const pie: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10,
  padding: '12px 20px', borderTop: '1px solid var(--border-primary)',
}
