import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Button } from '../ui'

// IT-01 F4: un módulo deshabilitado en el municipio no aparece en el menú, pero su pantalla se
// abría igual escribiendo la dirección a mano (`#/entradas` con Entradas apagado usaba la API de
// Agenda; prueba de cierre de F4+F5). Este control lo frena en la ruta. Ante un error o un
// backend sin la lista deja pasar, como el menú: la barrera real son los routers del backend.
export function ModuloGuard({ codigo, children }: { codigo: string; children?: ReactNode }) {
  const navigate = useNavigate()
  const q = useQuery({
    queryKey: ['municipio', 'modulos-habilitados'],
    queryFn: () => api.get<{ modulos_habilitados?: string[] }>('/api/v1/config/identidad/actual'),
    staleTime: 5 * 60_000,
  })
  if (q.isLoading) return null
  const lista = q.data?.modulos_habilitados
  if (!Array.isArray(lista) || !lista.length || lista.includes(codigo)) return <>{children}</>

  return (
    <div style={{ minHeight: '100%', display: 'grid', placeItems: 'center', padding: 24, boxSizing: 'border-box' }}>
      <div style={{
        width: '100%', maxWidth: 460, boxSizing: 'border-box', padding: 32, background: 'var(--surface-100)',
        border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-xl)',
      }}>
        <h1 style={{ margin: '0 0 12px', fontFamily: 'var(--font-display)', fontSize: 24, fontWeight: 500, color: 'var(--fg-1)' }}>
          Este módulo no está habilitado
        </h1>
        <p style={{ margin: '0 0 24px', fontSize: 15, lineHeight: 1.5, color: 'var(--fg-2)' }}>
          El municipio no tiene este módulo. Si lo necesitás, pedíselo al administrador de ZARIS.
        </p>
        <Button variant="primary" type="button" onClick={() => navigate('/dashboard', { replace: true })}>Ir al inicio</Button>
      </div>
    </div>
  )
}
