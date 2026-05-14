import s from './Overview.module.css'

// Landing minima del modulo Turnos (scaffold 2026-05-14). Pendiente: vista
// backoffice (staff gestiona turnos sobre agenda de agentes) + vista
// autoservicio (ciudadano saca su propio turno). Ver "Pendientes vigentes".
export function Overview() {
  return (
    <div className={s.page}>
      <div className={s.header}>
        <h1 className={s.title}>turnos</h1>
        <p className={s.subtitle}>
          gestión de turnos sobre la disponibilidad de agentes
        </p>
      </div>
      <div className={s.placeholder}>
        <p>Módulo en construcción.</p>
        <p className={s.hint}>
          Un turno ocupa un bloque de disponibilidad de un agente. La
          disponibilidad se define en el registro del agente y se visualiza
          en el módulo Agenda.
        </p>
      </div>
    </div>
  )
}
