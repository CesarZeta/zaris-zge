// Página pública de turnos (path /turnos-autoservicio). Hasta el 2026-11-23 reservaba con solo el DNI;
// desde entonces sacar un turno exige la cuenta del vecino y esta página lleva al portal.
// SIN AppShell, SIN JWT: el vecino llega por un link compartido.
import { IrAlPortal, layoutStyles as s, ZarisMark } from './shared'

export function TurnosPage() {
  return (
    <div style={s.page}>
      <div style={s.brand}><ZarisMark /></div>
      <div style={s.card}>
        <h1 style={s.h1}>Sacar un turno</h1>
        <IrAlPortal texto="Los turnos se sacan desde el portal del vecino, con tu cuenta. Si todavía no la tenés, registrate: solo hace falta una vez." />
      </div>
      <div style={s.footer}>ZARIS · Gestión Estado</div>
    </div>
  )
}
