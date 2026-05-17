import type { TipoTramiteCampo } from '../types'
import { CampoDinamico } from './CampoDinamico'

interface FormularioDinamicoProps {
  campos: TipoTramiteCampo[]
  valores: Record<string, unknown>
  errores: Record<string, string>
  onChange: (nombre: string, valor: unknown) => void
}

export function FormularioDinamico({ campos, valores, errores, onChange }: FormularioDinamicoProps) {
  const ordenados = [...campos].sort((a, b) => a.orden - b.orden)

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {ordenados.map((campo) => (
        <CampoDinamico
          key={campo.id_tipo_tramite_campo}
          campo={campo}
          value={valores[campo.nombre_interno] ?? ''}
          onChange={onChange}
          error={errores[campo.nombre_interno]}
        />
      ))}
    </div>
  )
}

export function validarDatos(
  campos: TipoTramiteCampo[],
  valores: Record<string, unknown>,
): Record<string, string> {
  const errs: Record<string, string> = {}
  for (const c of campos) {
    if (!c.obligatorio) continue
    if (c.tipo_dato === 'archivo') continue
    const v = valores[c.nombre_interno]
    const vacio =
      v === null ||
      v === undefined ||
      v === '' ||
      (Array.isArray(v) && v.length === 0)
    if (vacio) errs[c.nombre_interno] = 'Campo obligatorio'
  }
  return errs
}
