import { useNavigate } from 'react-router-dom'
import { Users, Building2 } from 'lucide-react'
import s from './Overview.module.css'

export function Overview() {
  const navigate = useNavigate()
  return (
    <div className={s.page}>
      <div className={s.header}>
        <h1 className={s.title}>contactos</h1>
        <p className={s.subtitle}>padrones de personas y empresas</p>
      </div>
      <div className={s.grid}>
        <button
          type="button"
          className={s.card}
          onClick={() => navigate('/ciudadanos')}
        >
          <Users className={s.icon} aria-hidden="true" />
          <span className={s.cardTitle}>ciudadanos</span>
          <span className={s.cardDesc}>buscar, alta y edición de personas físicas</span>
        </button>
        <button
          type="button"
          className={s.card}
          onClick={() => navigate('/empresas')}
        >
          <Building2 className={s.icon} aria-hidden="true" />
          <span className={s.cardTitle}>empresas</span>
          <span className={s.cardDesc}>buscar, alta y edición de personas jurídicas</span>
        </button>
      </div>
    </div>
  )
}
