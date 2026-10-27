import { useEffect, useState } from 'react'
// Hooks/API de permisos siguen viviendo en el módulo config (cross-module
// import permitido §29) — esta vista se movió acá porque los permisos son
// parte del maestro de Usuarios (pedido 2026-07-16).
import { useActualizarModulo, useModulosCatalogo } from '../../config/hooks/useConfig'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAuthStore } from '../../../stores/auth'

export function CatalogoModulosView() {
  const push = useNotificationsStore((s) => s.push)
  // IT-01 F4: los módulos son del municipio de la request (para el super, el del selector). El
  // administrador cambia el nivel mínimo; habilitar o quitar un módulo es solo del super. Los
  // módulos de nivel 0 son del super y su nivel no se edita.
  const esSuper = useAuthStore((s) => s.user?.es_super_admin === true)
  const { data: modulos = [], isLoading } = useModulosCatalogo()
  const mut = useActualizarModulo()

  const [niveles, setNiveles] = useState<Record<string, number>>({})

  // Hidratamos el estado local con lo que viene del backend
  useEffect(() => {
    const m: Record<string, number> = {}
    for (const x of modulos) m[x.modulo_codigo] = x.min_nivel_acceso
    setNiveles(m)
  }, [modulos])

  async function guardar(codigo: string) {
    const valor = niveles[codigo]
    if (valor == null || valor < 1 || valor > 5) {
      push({ kind: 'error', title: 'Nivel inválido', body: 'Debe estar entre 1 y 5' })
      return
    }
    try {
      await mut.mutateAsync({ codigo, min_nivel_acceso: valor })
      push({ kind: 'success', title: `Módulo "${codigo}" actualizado`, body: `min_nivel_acceso = ${valor}` })
    } catch (err) {
      push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
    }
  }

  async function cambiarHabilitado(codigo: string, habilitado: boolean) {
    try {
      await mut.mutateAsync({ codigo, habilitado })
      push({ kind: 'success', title: `Módulo "${codigo}" ${habilitado ? 'habilitado' : 'deshabilitado'}` })
    } catch (err) {
      push({ kind: 'error', title: 'No se pudo cambiar', body: (err as Error).message })
    }
  }

  return (
    <div style={{ background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 18 }}>
      <div style={{ fontSize: '0.86rem', color: 'var(--fg-3)', marginBottom: 12 }}>
        Cada módulo declara un <strong>nivel mínimo de acceso</strong>. Un usuario con nivel ≤ ese valor ve el módulo por default.
        Por ejemplo, si <code>min_nivel_acceso = 3</code>, lo ven Admin (1), Supervisor (2) y Atención (3) — pero no Gestión (4) ni Consultor (5).
        Los overrides por usuario (pestaña anterior) sobreescriben esto, pero no habilitan un módulo deshabilitado.
        Los niveles valen para este municipio.
        {esSuper
          ? <> Como super administrador, además habilitás o quitás módulos del municipio elegido en «Operando en».</>
          : <> Habilitar o quitar módulos lo hace el soporte de ZARIS.</>}
      </div>

      <div style={tableHeaderStyle}>
        <div style={{ flex: 1.5 }}>Módulo</div>
        <div style={{ flex: 2 }}>Descripción</div>
        <div style={{ width: 110, textAlign: 'center' }}>Habilitado</div>
        <div style={{ width: 200, textAlign: 'center' }}>Nivel mínimo</div>
      </div>

      {isLoading && <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)' }}>Cargando…</div>}

      {modulos.map((m) => {
        const original = m.min_nivel_acceso
        const actual = niveles[m.modulo_codigo] ?? original
        const cambio = actual !== original
        return (
          <div key={m.modulo_codigo} style={tableRowStyle}>
            <div style={{ flex: 1.5 }}>
              <div style={{ fontWeight: 600 }}>{m.nombre}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--fg-3)' }}>
                {m.modulo_codigo}
              </div>
            </div>
            <div style={{ flex: 2, fontSize: '0.82rem', color: 'var(--fg-2)' }}>
              {m.descripcion ?? '—'}
            </div>
            <div style={{ width: 110, textAlign: 'center' }}>
              {esSuper ? (
                <label title={m.fijo ? 'El municipio no funciona sin este módulo'
                  : m.dependencias.length ? `Necesita: ${m.dependencias.join(', ')}` : undefined}
                       style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: m.fijo ? 'default' : 'pointer' }}>
                  <input type="checkbox" checked={m.habilitado} disabled={m.fijo || mut.isPending}
                         onChange={(e) => cambiarHabilitado(m.modulo_codigo, e.target.checked)} />
                  <span style={{ fontSize: '0.76rem', color: 'var(--fg-2)' }}>{m.fijo ? 'fijo' : m.habilitado ? 'sí' : 'no'}</span>
                </label>
              ) : (
                <span style={{
                  display: 'inline-block', padding: '2px 9px', borderRadius: 999, fontSize: '0.7rem', fontWeight: 600,
                  background: m.habilitado ? 'var(--surface-400)' : 'transparent', color: m.habilitado ? 'var(--fg-1)' : 'var(--fg-3)',
                  border: '1px solid var(--border-primary)',
                }}>
                  {m.habilitado ? 'sí' : 'no'}
                </span>
              )}
            </div>
            <div style={{ width: 200, display: 'flex', gap: 6, justifyContent: 'center', alignItems: 'center' }}>
              <select
                value={actual}
                onChange={(e) => setNiveles((p) => ({ ...p, [m.modulo_codigo]: Number(e.target.value) }))}
                style={selectStyle}
                disabled={original === 0 || !m.habilitado}
              >
                {original === 0 && <option value={0}>0 — Super administrador</option>}
                <option value={1}>1 — Admin</option>
                <option value={2}>2 — Supervisor</option>
                <option value={3}>3 — Atención</option>
                <option value={4}>4 — Gestión</option>
                <option value={5}>5 — Consultor</option>
              </select>
              {cambio && (
                <button onClick={() => guardar(m.modulo_codigo)} disabled={mut.isPending} style={btnSmPrimary}>
                  {mut.isPending ? '…' : 'Guardar'}
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

const tableHeaderStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '8px 10px', borderBottom: '1px solid var(--border-primary)',
  fontSize: '0.72rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', fontWeight: 600,
}

const tableRowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '12px 10px', borderBottom: '1px solid var(--border-primary)',
  fontSize: '0.84rem',
}

const selectStyle: React.CSSProperties = {
  padding: '5px 8px', fontFamily: 'var(--font-display)', fontSize: '0.82rem',
  border: '1px solid var(--border-medium)', borderRadius: 6,
  background: 'var(--surface-100)', color: 'var(--fg-1)', outline: 'none',
}

const btnSmPrimary: React.CSSProperties = {
  padding: '5px 10px', background: 'var(--zaris-orange)', color: 'white',
  border: 'none', borderRadius: 6,
  fontFamily: 'var(--font-display)', fontSize: '0.76rem',
  fontWeight: 500, cursor: 'pointer',
}
