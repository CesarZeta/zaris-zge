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
 *
 * Sonido (decisión de César 2026-09-06): el chime al llamar se ACTIVA CON UN
 * BOTÓN. Los navegadores (y las TVs con browser) bloquean el audio hasta que
 * hay un gesto del usuario, así que quien enciende la pantalla toca "Activar
 * sonido" una vez; a partir de ahí cada llamado nuevo suena. El chime se
 * sintetiza con Web Audio (dos tonos), sin archivo de audio que cargar.
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
  // Sonido: estado para el botón + ref para leerlo dentro del tick (closure).
  const [sonido, setSonido] = useState(false)
  const sonidoRef = useRef(false)
  const audioRef = useRef<AudioContext | null>(null)
  // Último llamado visto (ISO): un llamado_en mayor = llamado nuevo => chime.
  const ultimoLlamadoRef = useRef<string | null>(null)

  function chime() {
    const ctx = audioRef.current
    if (!ctx) return
    const t0 = ctx.currentTime
    // "Din-don": dos tonos cortos con envolvente para que no haga clic.
    for (const [freq, ini, dur] of [[880, 0, 0.35], [660, 0.32, 0.55]] as const) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, t0 + ini)
      gain.gain.exponentialRampToValueAtTime(0.5, t0 + ini + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + ini + dur)
      osc.connect(gain).connect(ctx.destination)
      osc.start(t0 + ini)
      osc.stop(t0 + ini + dur + 0.05)
    }
  }

  async function toggleSonido() {
    if (sonido) {
      sonidoRef.current = false
      setSonido(false)
      return
    }
    // Crear/resumir el AudioContext DENTRO del gesto del usuario: es lo que
    // destraba el autoplay. Suena una vez de confirmación.
    try {
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!Ctx) return
      if (!audioRef.current) audioRef.current = new Ctx()
      await audioRef.current.resume()
      sonidoRef.current = true
      setSonido(true)
      chime()
    } catch {
      sonidoRef.current = false
      setSonido(false)
    }
  }

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
        // Detectar llamado nuevo por el llamado_en más reciente. La primera
        // lectura solo fija la marca (no suena al encender la pantalla).
        const masReciente = d.llamando.reduce<string | null>(
          (acc, l) => (acc == null || l.llamado_en > acc ? l.llamado_en : acc), null,
        )
        if (masReciente != null) {
          const previo = ultimoLlamadoRef.current
          if (previo != null && masReciente > previo && sonidoRef.current) chime()
          ultimoLlamadoRef.current = masReciente
        }
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
        <div style={styles.headerDerecha}>
          {desactualizada && (
            <div style={styles.avisoDesact}>Sin conexión — mostrando el último dato</div>
          )}
          <button
            type="button"
            onClick={toggleSonido}
            style={{ ...styles.btnSonido, ...(sonido ? styles.btnSonidoOn : {}) }}
            title={sonido ? 'El chime suena en cada llamado. Clic para silenciar.' : 'Activar el chime de llamado (los navegadores exigen un clic para habilitar audio)'}
          >
            {sonido ? 'Sonido activado' : 'Activar sonido'}
          </button>
        </div>
      </header>

      {error ? (
        <div style={styles.error}>{error}</div>
      ) : destacado ? (
        <main style={styles.main}>
          <div style={styles.etiqueta}>Llamando</div>
          <div style={{ ...styles.numero, fontSize: tamanoNumero(destacado.numero) }}>{destacado.numero ?? '—'}</div>
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

/** Tamaño del número destacado según su largo: "014" entra a 26vw, pero con
 *  prefijo ("ODO-014", 7 caracteres) a ese tamaño se partía en dos líneas.
 *  Ancho aproximado de un glifo ≈ 0.62em → se busca que el número ocupe ~85vw
 *  como máximo, con tope en 26vw. */
function tamanoNumero(n: string | null): string {
  const largo = Math.max(3, (n ?? '').length)
  const vw = Math.min(26, 85 / (0.62 * largo))
  return `clamp(80px, ${vw.toFixed(1)}vw, 420px)`
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
  headerDerecha: { display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', justifyContent: 'flex-end' },
  avisoDesact: {
    fontSize: 'clamp(12px, 1.2vw, 18px)', color: '#f5b300',
    border: '1px solid #f5b300', borderRadius: 6, padding: '4px 10px', whiteSpace: 'nowrap',
  },
  btnSonido: {
    fontFamily: 'inherit', fontSize: 'clamp(12px, 1.2vw, 18px)', cursor: 'pointer',
    background: 'transparent', color: 'rgba(247,247,244,.75)',
    border: '1px solid rgba(247,247,244,.35)', borderRadius: 6, padding: '4px 12px', whiteSpace: 'nowrap',
  },
  btnSonidoOn: { color: '#f54e00', borderColor: '#f54e00' },
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
    letterSpacing: '-.02em', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
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
