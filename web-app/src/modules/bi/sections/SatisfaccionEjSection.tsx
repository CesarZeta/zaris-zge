import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, CenterMsg } from '../components/ui'
import { AXIS, Seccion, legendStyle, tooltipStyle } from '../components/SeccionHeader'
import { DashboardMap } from '../../dashboard/components/DashboardMap'
import type { GeoReclamo } from '../../dashboard/hooks/useDashboardData'
import { useEjGeo, useEjSatCierre } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import type { BiFiltros, EjSatCierreItem } from '../lib/types'

// Sección SATISFACCIÓN del tablero Ejecutivo (VL "Satisfacción vs cierre del
// mes"): % satisfacción vs % cierre por subárea y por localidad, y los dos
// mapas (encuestas clasificadas / abiertos-cerrados).

const COLOR_SAT = '#6a1b9a'
const COLOR_CIERRE = '#2f7fd1'
const COLOR_ABIERTO = '#c62828'
const COLOR_CERRADO = '#1f8a65'

const pctLabel = { fontFamily: 'var(--font-display)', fontSize: 10, fill: 'var(--fg-2)' }
// Valor 0 NO se etiqueta (César 2026-08-31: "si los valores son ceros no debe
// mostrar ningún valor").
const fmtPct = (v: unknown) => (v == null || v === '' || v === 0 ? '' : `${v}%`)

function BarrasSatCierre({ data, titulo }: { data: EjSatCierreItem[] | undefined; titulo: string }) {
  // Filas con AMBOS indicadores en cero (o sin dato) no se muestran (César 2026-08-31).
  const rows = (data ?? []).filter((r) => (r.pct_sat ?? 0) > 0 || (r.pct_cierre ?? 0) > 0)
  return (
    <ChartCard title={titulo} height={Math.max(220, rows.length * 52 + 70)}>
      {!rows.length ? (
        <CenterMsg>Sin datos para el filtro elegido.</CenterMsg>
      ) : (
        <ResponsiveContainer>
          <BarChart data={rows} layout="vertical" margin={{ left: 12, right: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" horizontal={false} />
            <XAxis type="number" tick={AXIS} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
            <YAxis type="category" dataKey="nombre" tick={AXIS} width={170} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => (v == null ? '—' : `${v}%`)} />
            <Legend wrapperStyle={legendStyle} />
            <Bar dataKey="pct_sat" name="% Satisfacción" fill={COLOR_SAT} radius={[0, 4, 4, 0]} barSize={14}>
              <LabelList dataKey="pct_sat" position="right" style={pctLabel} formatter={fmtPct} />
            </Bar>
            <Bar dataKey="pct_cierre" name="% Cierre" fill={COLOR_CIERRE} radius={[0, 4, 4, 0]} barSize={14}>
              <LabelList dataKey="pct_cierre" position="right" style={pctLabel} formatter={fmtPct} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

// Leyenda de colores en RECUADRO debajo de cada mapa (César 2026-08-31: la
// línea de corrido única para los dos mapas confundía).
function LeyendaMapa({ items }: { items: { color: string; label: string }[] }) {
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: '4px 16px', alignItems: 'center',
      border: '1px solid var(--border-primary)', borderRadius: 8,
      background: 'var(--surface-300)', padding: '6px 12px',
      fontFamily: 'var(--font-display)', fontSize: '0.76rem', color: 'var(--fg-2)',
    }}>
      {items.map((it) => (
        <span key={it.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: it.color, display: 'inline-block', flexShrink: 0 }} />
          {it.label}
        </span>
      ))}
    </div>
  )
}

export function SatisfaccionEjSection({ filtros }: { filtros: BiFiltros }) {
  const porSubarea = useEjSatCierre(filtros, 'subarea')
  const porLocalidad = useEjSatCierre(filtros, 'localidad')
  const geo = useEjGeo(filtros)

  const puntos = geo.data ?? []
  const encuestados = useMemo(() => puntos.filter((p) => p.clasificacion != null), [puntos])

  // Lookups para colorear los markers (DashboardMap pasa el GeoReclamo casteado).
  const clasifPorId = useMemo(() => new Map(encuestados.map((p) => [p.id_reclamo, p.clasificacion!])), [encuestados])
  const cerradoPorId = useMemo(() => new Map(puntos.map((p) => [p.id_reclamo, p.cerrado])), [puntos])

  const colorClasif = (r: GeoReclamo) => {
    const c = clasifPorId.get(r.id_reclamo)
    if (c == null) return '#9e9e9e'
    if (c >= 4) return '#1f8a65'
    if (c === 3) return '#f57f17'
    return '#c62828'
  }
  const colorCierre = (r: GeoReclamo) => (cerradoPorId.get(r.id_reclamo) ? COLOR_CERRADO : COLOR_ABIERTO)

  return (
    <Seccion
      id="satisfaccion"
      titulo="Satisfacción vs cierre"
      periodo={periodoEnLetras(filtros).actual}
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
        <BarrasSatCierre data={porSubarea.data} titulo="% Satisfacción vs % Cierre por subárea" />
        <BarrasSatCierre data={porLocalidad.data} titulo="% Satisfacción vs % Cierre por localidad" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
        <ChartCard title="Satisfacción geolocalizada (según encuestas)" height={420}>
          {geo.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !encuestados.length ? (
            <CenterMsg>Sin encuestas respondidas con ubicación en el período.</CenterMsg>
          ) : (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {/* isolation + zIndex: el mapa Leaflet no debe dibujarse sobre la barra fija (§ modulo-bi). */}
              <div style={{ flex: 1, minHeight: 0, borderRadius: 8, overflow: 'hidden', isolation: 'isolate', zIndex: 0, position: 'relative' }}>
                <DashboardMap
                  reclamos={encuestados as unknown as GeoReclamo[]}
                  emergencias={[]}
                  espacios={[]}
                  tramites={[]}
                  visibles={{ reclamos: true, emergencias: false, espacios: false, tramites: false }}
                  colorReclamo={colorClasif}
                  marcadorPunto
                />
              </div>
              <LeyendaMapa items={[
                { color: '#1f8a65', label: 'Satisfecho (4-5)' },
                { color: '#f57f17', label: 'Neutro (3)' },
                { color: '#c62828', label: 'Insatisfecho (1-2)' },
              ]} />
            </div>
          )}
        </ChartCard>

        <ChartCard title="Cierres sobre incidentes (abierto / cerrado)" height={420}>
          {geo.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !puntos.length ? (
            <CenterMsg>Sin incidentes con ubicación en el período.</CenterMsg>
          ) : (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ flex: 1, minHeight: 0, borderRadius: 8, overflow: 'hidden', isolation: 'isolate', zIndex: 0, position: 'relative' }}>
                <DashboardMap
                  reclamos={puntos as unknown as GeoReclamo[]}
                  emergencias={[]}
                  espacios={[]}
                  tramites={[]}
                  visibles={{ reclamos: true, emergencias: false, espacios: false, tramites: false }}
                  colorReclamo={colorCierre}
                  marcadorPunto
                />
              </div>
              <LeyendaMapa items={[
                { color: COLOR_CERRADO, label: 'Cerrado' },
                { color: COLOR_ABIERTO, label: 'Abierto' },
              ]} />
            </div>
          )}
        </ChartCard>
      </div>
    </Seccion>
  )
}
