import { Database } from 'lucide-react'
import type { ModuleManifest } from '../../lib/types'
import { BiLayout } from './BiLayout'
import { DatosLanding } from './pages/DatosLanding'
import { ResumenView } from './views/ResumenView'
import { ResueltosView } from './views/ResueltosView'
import { PendientesView } from './views/PendientesView'
import { SubreclamosView } from './views/SubreclamosView'
import { useAuthStore } from '../../stores/auth'

// Módulo DATOS: landing con dos tableros analíticos sobre reclamos.
//   /bi               → landing (tarjetas Operativo / Ejecutivo)
//   /bi/operativo/*   → tablero Operativo (Resumen / Resueltos-SLA / Pendientes / Subreclamos)
//   /bi/ejecutivo     → (futuro) tablero Ejecutivo — placeholder en la landing por ahora
// Consume /api/v1/bi/* (router con guard JWT). moduloCodigo='bi' (catálogo
// `modulos`, mig 65, min_nivel_acceso=2). Gateamos la UI a nivel <= 2.

const MIN_NIVEL = 2

function useNivelOk() {
  return useAuthStore((s) => (s.user?.nivel_acceso ?? 99) <= MIN_NIVEL)
}

// Vistas operativas: envueltas en el BiLayout (con tabs).
const WrapOperativo = (Component: React.FC) => () => {
  const ok = useNivelOk()
  return <BiLayout>{ok ? <Component /> : <SinAcceso />}</BiLayout>
}

// Landing: sin el BiLayout (no tiene tabs operativas).
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
    { path: 'operativo', element: WrapOperativo(ResumenView), handle: { breadcrumb: 'Datos · Operativo' } },
    { path: 'operativo/resueltos', element: WrapOperativo(ResueltosView), handle: { breadcrumb: 'Datos · Operativo · Resueltos / SLA' } },
    { path: 'operativo/pendientes', element: WrapOperativo(PendientesView), handle: { breadcrumb: 'Datos · Operativo · Pendientes' } },
    { path: 'operativo/subreclamos', element: WrapOperativo(SubreclamosView), handle: { breadcrumb: 'Datos · Operativo · Subreclamos' } },
  ],
}
