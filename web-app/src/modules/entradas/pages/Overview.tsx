import s from './Overview.module.css'

// Landing minima del modulo Entradas (scaffold 2026-05-14). Pendiente: vista
// backoffice (staff gestiona entradas a eventos en espacios) + vista
// autoservicio (ciudadano reserva su entrada). Ver "Pendientes vigentes".
export function Overview() {
  return (
    <div className={s.page}>
      <div className={s.header}>
        <h1 className={s.title}>entradas</h1>
        <p className={s.subtitle}>
          gestión de entradas a eventos en espacios físicos
        </p>
      </div>
      <div className={s.placeholder}>
        <p>Módulo en construcción.</p>
        <p className={s.hint}>
          Una entrada es una reserva a un evento que ocupa la disponibilidad
          de un espacio físico. La disponibilidad del espacio se define en su
          registro y se visualiza en el módulo Agenda.
        </p>
      </div>
    </div>
  )
}
