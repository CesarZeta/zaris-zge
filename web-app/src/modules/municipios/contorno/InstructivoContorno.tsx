import { useEffect } from 'react'
import { Modal } from '../../agenda/components/Modal'
import type { PasoInstructivo } from './api'
import abrir from './instructivo/geojsonio-01-abrir.png'
import buscar from './instructivo/geojsonio-02-buscar.png'
import poligono from './instructivo/geojsonio-03-poligono.png'
import puntos from './instructivo/geojsonio-04-puntos.png'
import terminado from './instructivo/geojsonio-05-terminado.png'
import exportar from './instructivo/geojsonio-06-exportar.png'

// Instructivo para armar el archivo del contorno (PLAN_CONTORNO_MUNICIPIO_DISENO.md §4.7). Es ayuda
// dentro de la pantalla, no un docs/manual_* (CLAUDE.md §36). Las capturas de geojson.io se tomaron
// el 2026-10-28 con la versión de entonces (en inglés, con Mapbox). Los nombres de QGIS se verificaron
// contra la documentación oficial de QGIS 3.44 en español (docs.qgis.org/latest/es), el 2026-10-28:
// «Creando nuevas capas desde una capa existente» (managing_data_source/create_layers.html), «Abrir datos»
// (managing_data_source/opening_data.html) y «Geometría vectorial» (processing_algs/qgis/vectorgeometry.html).

const EJEMPLO = `${import.meta.env.BASE_URL}ejemplos/contorno_ejemplo.geojson`

const h3: React.CSSProperties = { margin: '18px 0 8px', fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--fg-1)' }
const p: React.CSSProperties = { margin: '0 0 8px', fontSize: 13, lineHeight: 1.55, color: 'var(--fg-1)' }
const ol: React.CSSProperties = { margin: '0 0 8px', paddingLeft: 20, fontSize: 13, lineHeight: 1.6, color: 'var(--fg-1)' }
const menu: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 12, background: 'var(--surface-300)',
  padding: '1px 5px', borderRadius: 4 }
const td: React.CSSProperties = { padding: '6px 8px', borderBottom: '1px solid var(--border-primary)', fontSize: 13, verticalAlign: 'top' }

function Captura({ src, alt }: { src: string; alt: string }) {
  return (
    <img src={src} alt={alt} loading="lazy"
         style={{ display: 'block', width: '100%', maxWidth: 560, margin: '6px 0 12px',
                  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)' }} />
  )
}

const M = ({ children }: { children: React.ReactNode }) => <span style={menu}>{children}</span>

function Seccion({ id, titulo, resaltada, children }: {
  id: PasoInstructivo | 'antes' | 'formato-ok'; titulo: string; resaltada?: boolean; children: React.ReactNode
}) {
  return (
    <section id={`instructivo-${id}`} data-instructivo-seccion={id}
             style={resaltada ? { borderLeft: '3px solid var(--zaris-orange)', paddingLeft: 12 } : undefined}>
      <h3 style={h3}>{titulo}</h3>
      {children}
    </section>
  )
}

/** Cada rechazo del backend (ContornoInvalido.paso) con su causa y su arreglo. */
const ERRORES: { paso: PasoInstructivo; titulo: string; causa: string; arreglo: React.ReactNode }[] = [
  { paso: 'formato', titulo: '«El archivo no es GeoJSON válido»',
    causa: 'Se subió otro formato (un shapefile en .zip, un KML, una planilla) o un archivo dañado.',
    arreglo: <>Abrilo en QGIS y exportalo como GeoJSON (camino B), o dibujalo en geojson.io (camino A).</> },
  { paso: 'metros', titulo: '«El archivo está en metros»',
    causa: 'La capa está en un sistema de coordenadas en metros (Gauss-Krüger, POSGAR, UTM).',
    arreglo: <>En QGIS, al exportar, elegí en <M>CRS</M> el sistema <M>EPSG:4326 - WGS 84</M> (paso 5 del camino B).</> },
  { paso: 'invertido', titulo: '«La latitud y la longitud están invertidas»',
    causa: 'Cada punto tiene que ir como [longitud, latitud], y el archivo los trae al revés.',
    arreglo: <>Exportalo de nuevo desde QGIS con <M>EPSG:4326 - WGS 84</M>; no lo armes a mano.</> },
  { paso: 'tipo', titulo: '«Hace falta un polígono cerrado»',
    causa: 'El archivo trae puntos o líneas, no trae ninguna figura, o el polígono se corta a sí mismo.',
    arreglo: <>Dibujá el contorno con la herramienta de polígono y cerralo sobre el primer punto. Si el polígono se
      corta a sí mismo, en QGIS abrí la Caja de herramientas de procesamiento (menú <M>Procesamiento</M>), buscá
      «Corregir geometrías», y exportá el resultado.</> },
  { paso: 'pais', titulo: '«El contorno cae fuera del país»',
    causa: 'El archivo es de otro lugar, o las coordenadas no corresponden al municipio.',
    arreglo: <>Revisá que sea el archivo correcto. Si lo dibujaste, buscá el municipio antes de empezar (paso 2 del camino A).</> },
  { paso: 'tamano', titulo: '«El archivo pesa más de 5 MB» o «demasiado detallado»',
    causa: 'El contorno tiene demasiados vértices (suele pasar con capas catastrales muy precisas).',
    arreglo: <>En QGIS usá <M>Vectorial ► Herramientas de geometría ► Simplificar</M> con una tolerancia chica y exportá el
      resultado. ZARIS igual simplifica a unos 5 metros, que alcanza para los mapas.</> },
]

export function InstructivoContorno({ abierto, paso, onCerrar }: {
  abierto: boolean; paso?: PasoInstructivo; onCerrar: () => void
}) {
  // Desde un error, el instructivo abre en la sección que lo explica.
  useEffect(() => {
    if (!abierto || !paso) return
    const t = setTimeout(() => document.getElementById(`instructivo-${paso}`)?.scrollIntoView({ block: 'start' }), 50)
    return () => clearTimeout(t)
  }, [abierto, paso])

  return (
    <Modal open={abierto} onClose={onCerrar} title="¿Cómo armo el archivo del contorno?" width={760}>
      <div data-instructivo data-paso={paso ?? ''} style={{ maxHeight: '70vh', overflowY: 'auto', paddingRight: 6 }}>
        <Seccion id="antes" titulo="Antes que nada">
          <p style={p}>
            Si el botón <strong>Traer contorno oficial (IGN)</strong> funcionó, no hace falta ningún archivo: es el límite oficial
            del Instituto Geográfico Nacional. El archivo sirve cuando el IGN no tiene el contorno del municipio, o cuando el
            límite oficial no es el que corresponde (por ejemplo, un ejido distinto del que figura en el catastro).
          </p>
        </Seccion>

        <Seccion id="formato-ok" titulo="Qué archivo sirve">
          <table style={{ borderCollapse: 'collapse', width: '100%', marginBottom: 8 }}>
            <tbody>
              <tr><td style={td}><strong>Sí</strong></td><td style={td}>
                Un archivo <strong>GeoJSON</strong> (.geojson o .json) con <strong>un polígono cerrado</strong> en
                latitud/longitud (<M>EPSG:4326 - WGS 84</M>). Si el municipio tiene varias partes (islas), puede traer varios
                polígonos.
              </td></tr>
              <tr><td style={td}><strong>ZARIS se encarga</strong></td><td style={td}>
                De redondear las coordenadas, simplificar el contorno (unos 5 metros) y juntar las partes en una sola figura.
                Antes de guardar lo vas a ver en el mapa.
              </td></tr>
              <tr><td style={td}><strong>No</strong></td><td style={td}>
                Coordenadas en metros, puntos o líneas sueltas, otros formatos (shapefile, KML, planillas) o un contorno de
                otro país.
              </td></tr>
            </tbody>
          </table>
          <p style={p}><a href={EJEMPLO} download="contorno_ejemplo.geojson" data-instructivo-ejemplo>Descargar un archivo de ejemplo</a> para
            comparar el formato.</p>
        </Seccion>

        <Seccion id="geojsonio" titulo="Camino A — sin instalar nada: geojson.io" resaltada={paso === 'geojsonio'}>
          <p style={p}>Es una página web gratuita para dibujar sobre el mapa. Está en inglés; acá van los nombres tal como aparecen.</p>
          <ol style={ol}>
            <li>Abrí <a href="https://geojson.io" target="_blank" rel="noreferrer">geojson.io</a> en el navegador.</li>
          </ol>
          <Captura src={abrir} alt="geojson.io recién abierto: arriba las herramientas de dibujo y a la derecha el panel JSON" />
          <ol style={ol} start={2}>
            <li>Tocá <M>Search</M> (arriba, sobre el mapa), escribí el nombre de tu localidad y elegila de la lista: el mapa se
              mueve hasta ahí. Acercate con <M>+</M> hasta reconocer los límites.</li>
          </ol>
          <Captura src={buscar} alt="La búsqueda de geojson.io con resultados" />
          <ol style={ol} start={3}>
            <li>Elegí la herramienta de polígono: el pentágono de la barra de arriba (<M>Polygon</M>). Aparece la ayuda
              «Click to start the polygon, then click to add each vertex».</li>
          </ol>
          <Captura src={poligono} alt="La herramienta de polígono elegida, con su ayuda arriba del mapa" />
          <ol style={ol} start={4}>
            <li>Hacé clic en el mapa sobre cada esquina del límite del municipio, uno tras otro, siguiendo calles, rutas, arroyos
              o el río. Cuantos más puntos, más preciso.</li>
            <li>Para terminar, hacé clic sobre el primer punto, doble clic, o apretá <M>Enter</M> («Finish by clicking the
              starting point, double-clicking or hitting Enter»).</li>
          </ol>
          <Captura src={puntos} alt="El polígono a medio dibujar, con la ayuda para terminarlo" />
          <ol style={ol} start={6}>
            <li>Revisá el resultado: a la derecha, el panel <M>JSON</M> tiene que decir <M>"type": "Polygon"</M>. Si el municipio
              tiene islas, dibujá cada una como otro polígono.</li>
          </ol>
          <Captura src={terminado} alt="El polígono terminado y el panel JSON con el tipo Polygon" />
          <ol style={ol} start={7}>
            <li>Tocá <M>Export</M> (arriba a la derecha). En <M>File format</M> dejá <M>GeoJSON</M> y tocá el botón
              <M>Export</M>. Elegí dónde guardar el archivo.</li>
            <li>En ZARIS, tocá <strong>Subir archivo…</strong> y elegí el archivo que guardaste. Lo vas a ver en el mapa antes de
              guardarlo.</li>
          </ol>
          <Captura src={exportar} alt="El diálogo Export de geojson.io con el formato GeoJSON" />
        </Seccion>

        <Seccion id="qgis" titulo="Camino B — con QGIS, si tenés la capa del catastro" resaltada={paso === 'qgis'}>
          <p style={p}>Para quien ya tiene el límite en una capa (shapefile, KML, GeoPackage u otra). Los nombres son los de QGIS 3.44 en español.</p>
          <ol style={ol}>
            <li>Abrí la capa en QGIS con <M>Capa ► Agregar capa ► Agregar capa vectorial</M> (o <M>Ctrl + Shift + V</M>).</li>
            <li>Si la capa tiene más de un polígono, seleccioná solo el del municipio con la herramienta de selección.</li>
            <li>En el panel de capas, clic derecho sobre la capa ► <M>Exportar ► Guardar entidades como…</M> (o
              <M>Exportar ► Guardar entidades seleccionadas como…</M> si seleccionaste uno).</li>
            <li>En <M>Formato</M>, elegí <M>GeoJSON</M>. En <M>Nombre de archivo</M>, elegí dónde guardarlo.</li>
            <li>En <M>CRS</M>, elegí <M>EPSG:4326 - WGS 84</M>. Es el paso más importante: si queda en metros, ZARIS lo rechaza.</li>
            <li>Si seleccionaste un polígono, dejá marcada <M>Guardar solo entidades seleccionadas</M>. En la geometría, dejá sin
              marcar <M>Incluir dimensión z en geometrías</M>.</li>
            <li>Aceptá y subí el archivo en ZARIS con <strong>Subir archivo…</strong>.</li>
          </ol>
        </Seccion>

        <h3 style={h3}>Si da error</h3>
        {ERRORES.map((e) => (
          <Seccion key={e.paso} id={e.paso} titulo={e.titulo} resaltada={paso === e.paso}>
            <p style={p}><strong>Por qué:</strong> {e.causa}</p>
            <p style={p}><strong>Cómo se arregla:</strong> {e.arreglo}</p>
          </Seccion>
        ))}
      </div>
    </Modal>
  )
}
