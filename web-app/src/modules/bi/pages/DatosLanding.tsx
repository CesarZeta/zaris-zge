import { useNavigate } from 'react-router-dom'
import { Activity, Crown, Database } from 'lucide-react'
import { shellGoInicio } from '../../../lib/shellNav'
import s from './DatosLanding.module.css'

// Landing del módulo DATOS: dos tarjetas hacia los tableros analíticos.
//  - Operativo: tableros del día a día (el que ya está). Ruta /bi/operativo.
//  - Ejecutivo: "Análisis de demanda ciudadana" (2026-08-30) — réplica ZARIS de
//    los 5 tableros Power BI de referencia. Ruta /bi/ejecutivo.
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

        <button type="button" className={s.card} onClick={() => navigate('/bi/ejecutivo')}>
          <Crown className={s.icon} aria-hidden="true" />
          <span className={s.cardTitle}>Análisis de datos Ejecutivo</span>
          <span className={s.cardDesc}>
            Demanda ciudadana para la conducción: score de cierre, SLA y satisfacción, matriz por
            subárea, evolución de indicadores, históricos por canal y localidad, y mapas.
          </span>
        </button>
      </div>
    </div>
  )
}
