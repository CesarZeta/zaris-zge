import { useEffect, useMemo, useState } from 'react'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useModulosCatalogo,
  usePermisosUsuario,
  useSetPermisosUsuario,
  useUsuarios,
} from '../hooks/useConfig'
import type { OverrideIn } from '../types/config'

// Estado por modulo: 'default' (sigue por nivel), 'allow' (override true), 'deny' (override false)
type EstadoModulo = 'default' | 'allow' | 'deny'

export function UsuariosPermisosView() {
  const push = useNotificationsStore((s) => s.push)
  const usuariosQ = useUsuarios()
  const modulosQ  = useModulosCatalogo()

  const [idUsuario, setIdUsuario] = useState<number | null>(null)
  const permisosQ = usePermisosUsuario(idUsuario)
  const mut = useSetPermisosUsuario(idUsuario)

  const [estados, setEstados] = useState<Record<string, EstadoModulo>>({})
  const [motivos, setMotivos] = useState<Record<string, string>>({})

  // Cuando llega data del backend, hidratamos los estados locales.
  useEffect(() => {
    if (!permisosQ.data || !modulosQ.data) return
    const overrideMap = new Map(permisosQ.data.overrides.map((o) => [o.modulo_codigo, o]))
    const nuevoEstado: Record<string, EstadoModulo> = {}
    const nuevoMotivo: Record<string, string> = {}
    for (const m of modulosQ.data) {
      const ov = overrideMap.get(m.modulo_codigo)
      if (!ov) nuevoEstado[m.modulo_codigo] = 'default'
      else nuevoEstado[m.modulo_codigo] = ov.permitido ? 'allow' : 'deny'
      if (ov?.motivo) nuevoMotivo[m.modulo_codigo] = ov.motivo
    }
    setEstados(nuevoEstado)
    setMotivos(nuevoMotivo)
  }, [permisosQ.data, modulosQ.data])

  const usuarios = usuariosQ.data ?? []
  const modulos = modulosQ.data ?? []
  const nivel = permisosQ.data?.nivel_acceso ?? null

  // Indica si el modulo seria accesible por default (sin overrides) segun el nivel.
  const accesibleDefault = useMemo(() => {
    const out: Record<string, boolean> = {}
    if (!nivel) return out
    for (const m of modulos) out[m.modulo_codigo] = m.min_nivel_acceso >= nivel
    return out
  }, [modulos, nivel])

  function setEstadoMod(codigo: string, valor: EstadoModulo) {
    setEstados((prev) => ({ ...prev, [codigo]: valor }))
  }

  async function guardar() {
    if (!idUsuario) return
    const overrides: OverrideIn[] = modulos
      .filter((m) => estados[m.modulo_codigo] !== 'default')
      .map((m) => ({
        modulo_codigo: m.modulo_codigo,
        permitido: estados[m.modulo_codigo] === 'allow',
        motivo: motivos[m.modulo_codigo]?.trim() || null,
      }))
    try {
      await mut.mutateAsync(overrides)
      push({ kind: 'success', title: 'Permisos actualizados', body: `${overrides.length} override(s) activo(s)` })
    } catch (err) {
      push({ kind: 'error', title: 'Error al guardar permisos', body: (err as Error).message })
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, alignItems: 'start' }}>
      {/* Selector usuario */}
      <aside style={{
        background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
        borderRadius: 12, padding: '12px 8px', maxHeight: '70vh', overflowY: 'auto',
      }}>
        <div style={asideTitleStyle}>Usuarios ({usuarios.length})</div>
        {usuariosQ.isLoading && <div style={mutedStyle}>Cargando…</div>}
        {usuariosQ.isError && <div style={mutedStyle}>Error al cargar usuarios</div>}
        {usuarios.map((u) => (
          <button
            key={u.id_usuario}
            onClick={() => setIdUsuario(u.id_usuario)}
            style={{
              ...userBtnStyle,
              background: idUsuario === u.id_usuario ? 'var(--surface-400)' : 'transparent',
              color: idUsuario === u.id_usuario ? 'var(--fg-1)' : 'var(--fg-2)',
              borderLeft: idUsuario === u.id_usuario ? '3px solid var(--zaris-orange)' : '3px solid transparent',
            }}
          >
            <div style={{ fontWeight: 600 }}>{u.nombre}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
              nivel {u.nivel_acceso} · {u.email ?? `id ${u.id_usuario}`}
            </div>
          </button>
        ))}
      </aside>

      {/* Matriz de modulos */}
      <main>
        {!idUsuario && (
          <div style={emptyStyle}>Seleccioná un usuario del panel izquierdo para ver y editar sus permisos.</div>
        )}
        {idUsuario && permisosQ.isLoading && <div style={emptyStyle}>Cargando permisos…</div>}
        {idUsuario && permisosQ.data && (
          <div style={{ background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 18 }}>
            <div style={{ marginBottom: 14, fontSize: '0.86rem', color: 'var(--fg-3)' }}>
              Nivel actual: <strong style={{ color: 'var(--fg-1)' }}>{nivel}</strong>.
              El acceso por <em>default</em> se calcula por nivel (módulo accesible si su <code>min_nivel_acceso</code> ≥ nivel del usuario). Los <em>overrides</em> permiten otorgar o bloquear acceso puntual.
            </div>

            <div style={tableHeaderStyle}>
              <div style={{ flex: 2 }}>Módulo</div>
              <div style={{ width: 70, textAlign: 'center' }}>Nivel min</div>
              <div style={{ width: 110, textAlign: 'center' }}>Default</div>
              <div style={{ width: 240, textAlign: 'center' }}>Override</div>
              <div style={{ flex: 1 }}>Motivo (opcional)</div>
            </div>

            {modulos.map((m) => {
              const estado = estados[m.modulo_codigo] ?? 'default'
              const defaultOk = accesibleDefault[m.modulo_codigo]
              const efectivo = estado === 'allow' ? true : estado === 'deny' ? false : defaultOk
              return (
                <div key={m.modulo_codigo} style={tableRowStyle}>
                  <div style={{ flex: 2 }}>
                    <div style={{ fontWeight: 600 }}>{m.nombre}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--fg-3)' }}>
                      {m.modulo_codigo}
                    </div>
                  </div>
                  <div style={{ width: 70, textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                    {m.min_nivel_acceso}
                  </div>
                  <div style={{ width: 110, textAlign: 'center' }}>
                    <Pill ok={defaultOk}>{defaultOk ? 'permite' : 'bloquea'}</Pill>
                  </div>
                  <div style={{ width: 240, display: 'flex', gap: 4, justifyContent: 'center' }}>
                    <SegBtn active={estado === 'default'} onClick={() => setEstadoMod(m.modulo_codigo, 'default')}>Default</SegBtn>
                    <SegBtn active={estado === 'allow'} onClick={() => setEstadoMod(m.modulo_codigo, 'allow')} tone="success">Otorgar</SegBtn>
                    <SegBtn active={estado === 'deny'} onClick={() => setEstadoMod(m.modulo_codigo, 'deny')} tone="danger">Bloquear</SegBtn>
                  </div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <input
                      type="text"
                      value={motivos[m.modulo_codigo] ?? ''}
                      onChange={(e) => setMotivos((p) => ({ ...p, [m.modulo_codigo]: e.target.value }))}
                      placeholder={estado === 'default' ? '—' : 'Motivo (queda registrado)'}
                      disabled={estado === 'default'}
                      maxLength={200}
                      style={{
                        ...inputStyle,
                        opacity: estado === 'default' ? 0.4 : 1,
                      }}
                    />
                    <div style={{ fontSize: '0.7rem', color: efectivo ? 'var(--color-success, #2e7d32)' : 'var(--color-error)' }}>
                      Efectivo: {efectivo ? '✓ ve este módulo' : '✗ no ve este módulo'}
                    </div>
                  </div>
                </div>
              )
            })}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
              <button onClick={guardar} disabled={mut.isPending} style={btnPrimary}>
                {mut.isPending ? 'Guardando…' : 'Guardar cambios'}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

function Pill({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span style={{
      display: 'inline-block',
      background: ok ? '#e8f5e9' : '#ffebee',
      color: ok ? '#2e7d32' : '#c62828',
      border: `1px solid ${ok ? '#c8e6c9' : '#ffcdd2'}`,
      borderRadius: 999,
      padding: '2px 9px',
      fontSize: '0.7rem',
      fontWeight: 600,
    }}>{children}</span>
  )
}

function SegBtn({ active, onClick, tone, children }: {
  active: boolean; onClick: () => void; tone?: 'success' | 'danger'; children: React.ReactNode
}) {
  const bg = active
    ? (tone === 'success' ? '#2e7d32' : tone === 'danger' ? 'var(--color-error)' : 'var(--zaris-orange)')
    : 'var(--surface-100)'
  const color = active ? 'white' : 'var(--fg-2)'
  return (
    <button
      onClick={onClick}
      style={{
        background: bg, color,
        border: active ? `1px solid ${bg}` : '1px solid var(--border-medium)',
        borderRadius: 6, padding: '4px 9px',
        fontSize: '0.74rem', fontWeight: 500,
        fontFamily: 'var(--font-display)',
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  )
}

const asideTitleStyle: React.CSSProperties = {
  fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em',
  color: 'var(--fg-3)', padding: '4px 8px 10px', borderBottom: '1px solid var(--border-primary)',
  marginBottom: 6,
}

const userBtnStyle: React.CSSProperties = {
  display: 'block', width: '100%', textAlign: 'left',
  padding: '8px 10px', border: 'none', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: '0.86rem',
}

const mutedStyle: React.CSSProperties = { padding: 12, color: 'var(--fg-3)', fontSize: '0.84rem' }

const emptyStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 32, textAlign: 'center',
  color: 'var(--fg-3)', fontSize: '0.88rem',
}

const tableHeaderStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '8px 10px', borderBottom: '1px solid var(--border-primary)',
  fontSize: '0.72rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', fontWeight: 600,
}

const tableRowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '10px', borderBottom: '1px solid var(--border-primary)',
  fontSize: '0.84rem',
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '6px 10px',
  fontFamily: 'var(--font-display)', fontSize: '0.82rem',
  border: '1px solid var(--border-medium)', borderRadius: 6,
  background: 'var(--surface-100)', color: 'var(--fg-1)', outline: 'none',
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 18px', background: 'var(--zaris-orange)', color: 'white',
  border: 'none', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.86rem',
  fontWeight: 500, cursor: 'pointer',
}
