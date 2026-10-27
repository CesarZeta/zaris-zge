import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { useAuthStore } from '../../../stores/auth'
import { useNotificationsStore } from '../../../stores/notifications'
import { altaSuper, bajaSuper, listarSupers, reenviarInvitacion, type SuperAdministrador } from '../api'
import { Campo, input, seccion, subtitulo, tabla, td, th, titulo } from './_comun'

// Super administradores (IT-01 F4+F5, Tarea 15; spec §4.6). El alta manda una invitación por mail
// (sale como ZARIS) para elegir la clave y vincular el segundo factor. Nadie se da de baja a sí
// mismo y siempre queda un super activo: el backend lo hace cumplir.

const EMAIL = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/

export function SuperAdministradoresPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const yo = useAuthStore((s) => s.user?.id_usuario)
  const q = useQuery({ queryKey: ['super', 'administradores'], queryFn: listarSupers })
  const [form, setForm] = useState({ nombre: '', apellido: '', email: '' })
  const [baja, setBaja] = useState<SuperAdministrador | null>(null)

  const refrescar = () => qc.invalidateQueries({ queryKey: ['super', 'administradores'] })
  const alta = useMutation({
    mutationFn: altaSuper,
    onSuccess: () => { refrescar(); push({ kind: 'success', title: 'Super administrador invitado' }) },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo dar de alta', body: e.message }),
  })
  const quitar = useMutation({
    mutationFn: bajaSuper,
    onSuccess: () => { refrescar(); push({ kind: 'success', title: 'Super administrador dado de baja' }) },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo dar de baja', body: e.message }),
  })
  const reenviar = useMutation({
    mutationFn: reenviarInvitacion,
    onSuccess: () => { refrescar(); push({ kind: 'success', title: 'Invitación reenviada' }) },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo reenviar', body: e.message }),
  })

  const valido = form.nombre.trim() !== '' && form.apellido.trim() !== '' && EMAIL.test(form.email.trim())
  const enviar = (e: React.FormEvent) => {
    e.preventDefault()
    if (!valido) return
    alta.mutate({ nombre: form.nombre.trim(), apellido: form.apellido.trim(), email: form.email.trim().toLowerCase() })
    setForm({ nombre: '', apellido: '', email: '' })
  }

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 900 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <h1 style={titulo}>Super administradores</h1>
        <Button variant="ghost" type="button" onClick={() => navigate('/municipios')}>← Municipios</Button>
      </header>

      <form style={seccion} onSubmit={enviar}>
        <h2 style={subtitulo}>Dar de alta</h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
          Recibe un mail para elegir su clave y vincular la app de autenticación. Su email no lo puede usar
          ninguna cuenta de un municipio.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
          <Campo etiqueta="Nombre">
            <input style={input} value={form.nombre} maxLength={70} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </Campo>
          <Campo etiqueta="Apellido">
            <input style={input} value={form.apellido} maxLength={70} onChange={(e) => setForm({ ...form, apellido: e.target.value })} />
          </Campo>
          <Campo etiqueta="Email" error={form.email && !EMAIL.test(form.email.trim()) ? 'Email inválido' : undefined}>
            <input style={input} type="email" value={form.email} maxLength={150}
                   onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Campo>
        </div>
        <div><Button variant="primary" type="submit" disabled={!valido || alta.isPending}>Invitar</Button></div>
      </form>

      {q.isLoading && <Skeleton height={120} />}
      {q.isError && <EmptyState title="No se pudo cargar la lista" description={q.error.message} />}
      {q.data && (
        <table style={tabla}>
          <thead><tr><th style={th}>Nombre</th><th style={th}>Email</th><th style={th}>Estado</th><th style={th} /></tr></thead>
          <tbody>
            {q.data.map((s) => (
              <tr key={s.id_usuario}>
                <td style={td}>{s.nombre}{s.id_usuario === yo && <> <Badge kind="neutral">vos</Badge></>}</td>
                <td style={td}>{s.email ?? '—'}</td>
                <td style={td}>
                  {!s.activo ? <Badge kind="error">de baja</Badge>
                    : s.invitacion_pendiente ? <Badge kind="warn">invitación pendiente</Badge>
                    : <Badge kind="success">activo</Badge>}
                </td>
                <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {s.activo && s.invitacion_pendiente && (
                    <Button type="button" disabled={reenviar.isPending} onClick={() => reenviar.mutate(s.id_usuario)}>
                      Reenviar invitación
                    </Button>
                  )}{' '}
                  {s.activo && s.id_usuario !== yo && (
                    <Button type="button" onClick={() => setBaja(s)}>Dar de baja</Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ConfirmModal open={baja != null} danger title="Dar de baja"
                    message={baja ? `${baja.nombre} no va a poder entrar más y se cierran sus sesiones abiertas.` : ''}
                    confirmLabel="Dar de baja"
                    onConfirm={() => { if (baja) quitar.mutate(baja.id_usuario); setBaja(null) }}
                    onCancel={() => setBaja(null)} />
    </div>
  )
}
