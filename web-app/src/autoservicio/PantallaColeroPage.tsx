/**
 * Pantalla del colero (mig 105, F3 plan ATENCION) — la TV de la sala de espera.
 *
 * Es una vista PÚBLICA (sin JWT: el monitor no tiene sesión) que se abre con el
 * token de la ubicación. Diseñada para leerse de lejos y quedar proyectada horas:
 *
 *  - Tipografía enorme y contraste alto; el número es lo más grande de todo.
 *  - Fondo oscuro fijo (no sigue el tema del navegador): una pantalla de sala se
 *    ve de lejos y el oscuro cansa menos en un monitor siempre encendido.
 *  - Polling cada 5 s. Si una lectura falla NO se borra lo que está en pantalla
 *    (un corte de red momentáneo no debe dejar la sala sin información); recién
 *    tras varios fallos seguidos se avisa que la pantalla está desactualizada.
 *
 * Privacidad: el backend ya proyecta "Nombre I." y nunca manda apellido completo,
 * DNI, prestación ni id de turno — acá no hay nada que ocultar de más.
 */
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { pantallaColero } from '../modules/turnos/api/turnosApi'
import type { PantallaColero } from '../modules/turnos/types/turno'

const REFRESCO_MS = 5000
/** Fallos seguidos antes de avisar. Con 5 s de polling son ~15 s de silencio. */
const FALLOS_PARA_AVISAR = 3

export function PantallaColeroPage() {
  const { token } = useParams<{ token: string }>()
  const [data, setData] = useState<PantallaColero | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [desactualizada, setDesactualizada] = useState(false)
  const fallosRef = useRef(0)

  // El shell pinta el <body> de crema; esta vista ocupa la pantalla completa de
  // un monitor, así que también pintamos el body: sin esto se ve una franja
  // clara al hacer overscroll o si el contenido no llega a llenar el viewport.
  useEffect(() => {
    const previo = document.body.style.background
    document.body.style.background = '#141410'
    return () => { document.body.style.background = previo }
  }, [])

  useEffect(() => {
    if (!token) return
    let vivo = true

    async function tick() {
      try {
        const d = await pantallaColero(token as string)
        if (!vivo) return
        setData(d)
        setError(null)
        setDesactualizada(false)
        fallosRef.current = 0
      } catch (e) {
        if (!vivo) return
        fallosRef.current += 1
        // 404 = token equivocado: es definitivo, no tiene sentido esperar.
        const msg = e instanceof Error ? e.message : ''
        if (msg.includes('404')) {
          setError('Pantalla no encontrada. Verificá el enlace.')
          return
        }
        // Resto: mantener en pantalla lo último bueno y avisar recién si insiste.
        if (fallosRef.current >= FALLOS_PARA_AVISAR) setDesactualizada(true)
      }
    }

    tick()
    const id = window.setInterval(tick, REFRESCO_MS)
    return () => { vivo = false; window.clearInterval(id) }
  }, [token])

  const destacado = data?.llamando?.[0] ?? null
  const otrosLlamando = (data?.llamando ?? []).slice(1)

  return (
    <div style={styles.pantalla}>
      <header style={styles.header}>
        <div style={styles.ubicacion}>{data?.ubicacion_nombre ?? 'Cargando…'}</div>
        {desactualizada && (
          <div style={styles.avisoDesact}>Sin conexión — mostrando el último dato</div>
        )}
      </header>

      {error ? (
        <div style={styles.error}>{error}</div>
      ) : destacado ? (
        <main style={styles.main}>
          <div style={styles.etiqueta}>Llamando</div>
          <div style={styles.numero}>{destacado.numero ?? '—'}</div>
          <div style={styles.nombre}>{destacado.nombre_display}</div>
          {destacado.puesto && <div style={styles.puesto}>{destacado.puesto}</div>}
        </main>
      ) : (
        <main style={styles.main}>
          <div style={styles.espera}>Aguarde a ser llamado</div>
        </main>
      )}

      {otrosLlamando.length > 0 && (
        <section style={styles.tambien}>
          {otrosLlamando.map((l, i) => (
            <div key={i} style={styles.tambienItem}>
              <span style={styles.tambienNum}>{l.numero}</span>
              <span style={styles.tambienNom}>{l.nombre_display}</span>
              {l.puesto && <span style={styles.tambienPuesto}>{l.puesto}</span>}
            </div>
          ))}
        </section>
      )}

      {(data?.previos?.length ?? 0) > 0 && (
        <footer style={styles.previos}>
          <div style={styles.previosTitulo}>Anteriores</div>
          <div style={styles.previosLista}>
            {data!.previos.map((p, i) => (
              <span key={i} style={styles.previoItem}>
                <b style={{ fontWeight: 700 }}>{p.numero}</b> {p.nombre_display}
              </span>
            ))}
          </div>
        </footer>
      )}
    </div>
  )
}

/* Estilos inline y paleta fija a propósito: la pantalla no vive dentro del shell
   ni sigue el tema del viewer — es un monitor de sala. Usa los tokens de marca
   (naranja ZARIS) para el acento. */
const styles: Record<string, React.CSSProperties> = {
  pantalla: {
    minHeight: '100vh', width: '100%', boxSizing: 'border-box',
    background: '#141410', color: '#f7f7f4',
    fontFamily: "'Space Grotesk', system-ui, -apple-system, sans-serif",
    display: 'flex', flexDirection: 'column', padding: '3vh 4vw', gap: '2vh',
  },
  header: {
    display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
    gap: 16, borderBottom: '1px solid rgba(247,247,244,.15)', paddingBottom: '1.5vh',
  },
  ubicacion: {
    fontSize: 'clamp(20px, 3vw, 46px)', fontWeight: 700, letterSpacing: '.01em',
  },
  avisoDesact: {
    fontSize: 'clamp(12px, 1.2vw, 18px)', color: '#f5b300',
    border: '1px solid #f5b300', borderRadius: 6, padding: '4px 10px', whiteSpace: 'nowrap',
  },
  main: {
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', textAlign: 'center', gap: '1vh',
  },
  etiqueta: {
    fontSize: 'clamp(16px, 2vw, 32px)', textTransform: 'uppercase',
    letterSpacing: '.25em', color: '#f54e00', fontWeight: 600,
  },
  numero: {
    fontSize: 'clamp(90px, 26vw, 420px)', fontWeight: 700, lineHeight: 1,
    letterSpacing: '-.02em', fontVariantNumeric: 'tabular-nums',
  },
  nombre: { fontSize: 'clamp(28px, 6vw, 96px)', fontWeight: 500 },
  puesto: {
    fontSize: 'clamp(22px, 4vw, 64px)', fontWeight: 600, color: '#f54e00',
    marginTop: '1vh',
  },
  espera: {
    fontSize: 'clamp(28px, 5vw, 80px)', fontWeight: 500, color: 'rgba(247,247,244,.55)',
  },
  error: {
    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 'clamp(20px, 3vw, 40px)', color: '#ff6b6b', textAlign: 'center',
  },
  tambien: {
    display: 'flex', flexWrap: 'wrap', gap: '2vw', justifyContent: 'center',
    borderTop: '1px solid rgba(247,247,244,.15)', paddingTop: '1.5vh',
  },
  tambienItem: {
    display: 'flex', alignItems: 'baseline', gap: 12,
    fontSize: 'clamp(18px, 2.4vw, 40px)',
  },
  tambienNum: { fontWeight: 700, fontVariantNumeric: 'tabular-nums' },
  tambienNom: { color: 'rgba(247,247,244,.8)' },
  tambienPuesto: { color: '#f54e00', fontWeight: 600 },
  previos: { borderTop: '1px solid rgba(247,247,244,.15)', paddingTop: '1.5vh' },
  previosTitulo: {
    fontSize: 'clamp(11px, 1vw, 16px)', textTransform: 'uppercase',
    letterSpacing: '.2em', color: 'rgba(247,247,244,.45)', marginBottom: '.8vh',
  },
  previosLista: {
    display: 'flex', flexWrap: 'wrap', gap: '0 2.5vw',
    fontSize: 'clamp(14px, 1.6vw, 26px)', color: 'rgba(247,247,244,.6)',
    fontVariantNumeric: 'tabular-nums',
  },
  previoItem: { whiteSpace: 'nowrap' },
}
