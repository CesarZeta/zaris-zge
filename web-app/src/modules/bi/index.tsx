import { Database } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { BiLayout } from './BiLayout'
import { DatosLanding } from './pages/DatosLanding'
import { OperativoPage } from './pages/OperativoPage'
import { EjecutivoPage } from './pages/EjecutivoPage'
import { useAuthStore } from '../../stores/auth'

// Módulo DATOS: landing con dos tableros analíticos sobre reclamos.
//   /bi                        → landing (tarjetas Operativo / Ejecutivo)
//   /bi/operativo              → tablero Operativo en UNA página (2026-08-30):
//                                Resumen → Respuesta → Pendientes → Subreclamos
//   /bi/operativo/<seccion>    → misma página, desplazada a esa sección (compat
//                                con las rutas de los tabs viejos)
//   /bi/ejecutivo              → tablero Ejecutivo "Análisis de demanda ciudadana" (2026-08-30)
// Consume /api/v1/bi/* (router con guard JWT). moduloCodigo='bi' (catálogo
// `modulos`, mig 65, min_nivel_acceso=2). Gateamos la UI a nivel <= 2.

const MIN_NIVEL = 2

function useNivelOk() {
  return useAuthStore((s) => (s.user?.nivel_acceso ?? 99) <= MIN_NIVEL)
}

// Operativo: envuelto en el BiLayout (breadcrumb + título).
const WrapOperativo = (seccion?: string) => () => {
  const ok = useNivelOk()
  return <BiLayout>{ok ? <OperativoPage seccion={seccion} /> : <SinAcceso />}</BiLayout>
}

// Ejecutivo: página única con 5 secciones (2026-08-30).
function WrapEjecutivo() {
  const ok = useNivelOk()
  return (
    <BiLayout
      titulo="Análisis de datos Ejecutivo"
      subtitulo="Análisis de demanda ciudadana: score del período, evolución, histórico, mayores incidentes y satisfacción por subárea."
    >
      {ok ? <EjecutivoPage /> : <SinAcceso />}
    </BiLayout>
  )
}

// Landing: sin el BiLayout.
function WrapLanding() {
  const ok = useNivelOk()
  return ok ? <DatosLanding /> : <SinAcceso />
}

function SinAcceso() {
  return (
    <div style={{
      background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
      borderRadius: 12, padding: '36px 28px', textAlign: 'center',
      color: 'var(--fg-2)', maxWidth: 520, margin: '12px auto',
    }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.05rem', fontWeight: 600, color: 'var(--fg-1)', marginBottom: 8 }}>
        Acceso restringido
      </div>
      <p style={{ fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
        El análisis de datos es exclusivo de los perfiles <strong>Supervisor</strong> y <strong>Administrador</strong>.
      </p>
    </div>
  )
}

export const biModule: ModuleManifest = {
  id: 'bi',
  label: 'datos',
  icon: Database,
  moduloCodigo: 'bi',
  routes: [
    { index: true, element: WrapLanding, handle: { breadcrumb: 'Datos' } },
    { path: 'operativo', element: WrapOperativo(), handle: { breadcrumb: 'Datos · Operativo' } },
    { path: 'ejecutivo', element: WrapEjecutivo, handle: { breadcrumb: 'Datos · Ejecutivo' } },
    // Compat con las rutas de los tabs viejos: misma página, desplazada a la sección.
    { path: 'operativo/resueltos', element: WrapOperativo('respuesta'), handle: { breadcrumb: 'Datos · Operativo · Respuesta' } },
    { path: 'operativo/pendientes', element: WrapOperativo('pendientes'), handle: { breadcrumb: 'Datos · Operativo · Pendientes' } },
    { path: 'operativo/subreclamos', element: WrapOperativo('subreclamos'), handle: { breadcrumb: 'Datos · Operativo · Subreclamos' } },
  ],
}
