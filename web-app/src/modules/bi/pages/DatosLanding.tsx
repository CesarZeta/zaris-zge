import { useNavigate } from 'react-router-dom'
import { Activity, Crown, Database } from 'lucide-react'
import { shellGoInicio } from '../../../lib/shellNav'
import s from './DatosLanding.module.css'

// Landing del módulo DATOS: dos tarjetas hacia los tableros analíticos.
//  - Operativo: tableros del día a día (el que ya está). Ruta /bi/operativo.
//  - Ejecutivo: vista estratégica de alto nivel. Placeholder por ahora (las
//    visualizaciones las define el usuario en una fase siguiente).
export function DatosLanding() {
  const navigate = useNavigate()

  return (
    <div className={s.page}>
      <nav className={s.breadcrumb} aria-label="Ruta de navegación">
        <a href="#" onClick={(e) => { e.preventDefault(); shellGoInicio() }}>INICIO</a>
        <span className={s.sep}>›</span>
        <span className={s.current}>Datos</span>
      </nav>

      <div className={s.header}>
        <Database size={32} strokeWidth={1.5} color="var(--zaris-orange)" />
        <div>
          <h1 className={s.title}>Datos</h1>
          <p className={s.subtitle}>Análisis y tableros de gestión sobre los reclamos del municipio.</p>
        </div>
      </div>

      <div className={s.grid}>
        <button type="button" className={s.card} onClick={() => navigate('/bi/operativo')}>
          <Activity className={s.icon} aria-hidden="true" />
          <span className={s.cardTitle}>Análisis de datos Operativo</span>
          <span className={s.cardDesc}>
            Tableros del día a día: volumen y composición de reclamos, tiempos de respuesta y SLA,
            pendientes con geoposicionamiento, y subreclamos.
          </span>
        </button>

        <button type="button" className={`${s.card} ${s.cardDisabled}`} disabled aria-disabled="true">
          <Crown className={s.icon} aria-hidden="true" />
          <span className={s.cardTitle}>Análisis de datos Ejecutivo</span>
          <span className={s.cardDesc}>
            Vista estratégica de alto nivel para la conducción: indicadores agregados, tendencias y
            comparativos por área.
          </span>
          <span className={s.badge}>Próximamente</span>
        </button>
      </div>
    </div>
  )
}
