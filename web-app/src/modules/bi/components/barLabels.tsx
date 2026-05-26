// Componentes de etiqueta para barras de recharts. Compartidos entre vistas.
// Recharts tipa x/y/width/height/value como string | number.

type LblProps = {
  x?: string | number; y?: string | number
  width?: string | number; height?: string | number
  value?: string | number
}
const num = (v: string | number | undefined): number => (v == null ? 0 : Number(v))

// Fondo OSCURO translúcido para las etiquetas de total (sobre fg-1 #26251e), con
// texto claro encima — máxima legibilidad sobre cream o sobre barras de color.
const PILL = 'rgba(38,37,30,0.78)'
const PILL_TEXT = '#f7f7f4'

// Valor DENTRO de un segmento (barra vertical apilada). Oculto si el segmento es bajo.
export function SegLabel(p: LblProps) {
  const x = num(p.x), y = num(p.y), width = num(p.width), height = num(p.height), value = num(p.value)
  if (!value || height < 16) return null
  return (
    <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="central"
      fontFamily="var(--font-display)" fontSize={11} fontWeight={600} fill="#fff">
      {value}
    </text>
  )
}

// Total ARRIBA de una barra vertical apilada, con pastilla de fondo.
export function TotalLabel(p: LblProps) {
  const x = num(p.x), y = num(p.y), width = num(p.width), value = num(p.value)
  if (!value) return null
  const cx = x + width / 2
  const cy = y - 10
  const w = String(value).length * 8 + 10
  return (
    <g>
      <rect x={cx - w / 2} y={cy - 9} width={w} height={17} rx={5} fill={PILL} />
      <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={12} fontWeight={700} fill={PILL_TEXT}>
        {value}
      </text>
    </g>
  )
}

// Valor DENTRO de un segmento (barra horizontal). Oculto si es angosto.
export function SegLabelH(p: LblProps) {
  const x = num(p.x), y = num(p.y), width = num(p.width), height = num(p.height), value = num(p.value)
  if (!value || width < 22) return null
  return (
    <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="central"
      fontFamily="var(--font-display)" fontSize={11} fontWeight={600} fill="#fff">
      {value}
    </text>
  )
}

// Total a la DERECHA de una barra horizontal apilada, con pastilla de fondo.
export function TotalLabelH(p: LblProps) {
  const x = num(p.x), y = num(p.y), width = num(p.width), height = num(p.height), value = num(p.value)
  if (!value) return null
  const tx = x + width + 6
  const cy = y + height / 2
  const w = String(value).length * 8 + 10
  return (
    <g>
      <rect x={tx - 3} y={cy - 9} width={w} height={17} rx={5} fill={PILL} />
      <text x={tx + 2} y={cy} textAnchor="start" dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={12} fontWeight={700} fill={PILL_TEXT}>
        {value}
      </text>
    </g>
  )
}
