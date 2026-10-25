import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { getMunicipioActivo, setMunicipioActivo } from '../../lib/municipioActivo'

// Réplica, para el shell React de desarrollo (localhost:5173), del selector «Operando en» del
// shell vanilla de prod (frontend/js/menu.js, IT-01 F3). Solo para el super administrador.

interface MunicipioSuper {
  id_municipio: number
  nombre: string
  direccion_base: boolean
  activo: boolean
}

export function SelectorMunicipio({ className }: { className?: string }) {
  const [lista, setLista] = useState<MunicipioSuper[]>([])
  const [actual, setActual] = useState<number | null>(getMunicipioActivo())

  useEffect(() => {
    let vivo = true
    api.get<MunicipioSuper[]>('/api/v1/super/municipios').then(async (todos) => {
      const activos = todos.filter((m) => m.activo)
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
        {lista.map((m) => <option key={m.id_municipio} value={m.id_municipio}>{m.nombre}</option>)}
      </select>
    </label>
  )
}
