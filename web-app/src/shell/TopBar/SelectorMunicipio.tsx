import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { getMunicipioActivo, setMunicipioActivo } from '../../lib/municipioActivo'

// Réplica, para el shell React de desarrollo (localhost:5173), del selector «Operando en» del
// shell vanilla de prod (frontend/js/menu.js, IT-01 F3). Solo para el super administrador.
// IT-01 F4: agrupado por país y provincia; incluye el modelo; no muestra los de baja.

interface MunicipioSuper {
  id_municipio: number
  nombre: string
  direccion_base: boolean
  activo: boolean
  estado?: string
  pais_nombre?: string | null
  codigo_pais?: string
  provincia_nombre?: string | null
}

const operable = (m: MunicipioSuper) => (m.estado ? m.estado !== 'baja' : m.activo)
const grupoDe = (m: MunicipioSuper) =>
  m.estado === 'modelo' ? 'Modelo' : `${m.pais_nombre ?? m.codigo_pais ?? ''} · ${m.provincia_nombre ?? 'sin provincia'}`
const etiqueta = (m: MunicipioSuper) => (m.estado === 'modelo' ? `Modelo — ${m.nombre}` : m.nombre)

export function SelectorMunicipio({ className }: { className?: string }) {
  const [lista, setLista] = useState<MunicipioSuper[]>([])
  const [actual, setActual] = useState<number | null>(getMunicipioActivo())

  useEffect(() => {
    let vivo = true
    api.get<MunicipioSuper[]>('/api/v1/super/municipios').then(async (todos) => {
      const activos = todos.filter(operable)
      if (!vivo || activos.length === 0) return
      setLista(activos)
      const previo = getMunicipioActivo()
      const elegido = activos.some((m) => m.id_municipio === previo)
        ? (previo as number)
        : (activos.find((m) => m.direccion_base) ?? activos[0]).id_municipio
      await api.post('/api/v1/super/seleccion', { id_municipio: elegido })
      setMunicipioActivo(elegido)
      setActual(elegido)
      // Las pantallas ya pidieron sin municipio: se recarga una sola vez.
      if (previo !== elegido) window.location.reload()
    }).catch(() => { /* sin la lista no hay selector */ })
    return () => { vivo = false }
  }, [])

  if (lista.length === 0) return null
  const grupos = [...new Set(lista.map(grupoDe))]
  return (
    <label className={className}>
      <span>Operando en</span>
      <select
        value={actual ?? ''}
        onChange={async (e) => {
          const id = Number(e.target.value)
          await api.post('/api/v1/super/seleccion', { id_municipio: id })
          setMunicipioActivo(id)
          window.location.hash = '#/dashboard'
          window.location.reload()
        }}
      >
        {grupos.map((g) => (
          <optgroup key={g} label={g}>
            {lista.filter((m) => grupoDe(m) === g).map((m) => (
              <option key={m.id_municipio} value={m.id_municipio}>{etiqueta(m)}</option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  )
}
