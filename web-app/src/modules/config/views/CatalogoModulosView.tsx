import { useEffect, useState } from 'react'
import { useActualizarModulo, useModulosCatalogo } from '../hooks/useConfig'
import { useNotificationsStore } from '../../../stores/notifications'

export function CatalogoModulosView() {
  const push = useNotificationsStore((s) => s.push)
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
    if (valor == null || valor < 1 || valor > 4) {
      push({ kind: 'error', title: 'Nivel inválido', body: 'Debe estar entre 1 y 4' })
      return
    }
    try {
      await mut.mutateAsync({ codigo, min_nivel_acceso: valor })
      push({ kind: 'success', title: `Módulo "${codigo}" actualizado`, body: `min_nivel_acceso = ${valor}` })
    } catch (err) {
      push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
    }
  }

  return (
    <div style={{ background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 18 }}>
      <div style={{ fontSize: '0.86rem', color: 'var(--fg-3)', marginBottom: 12 }}>
        Cada módulo declara un <strong>nivel mínimo de acceso</strong>. Un usuario con nivel ≤ ese valor ve el módulo por default.
        Por ejemplo, si <code>min_nivel_acceso = 3</code>, lo ven Admin (1), Supervisor (2) y Operador (3) — pero no Consultor (4).
        Los overrides por usuario (pestaña anterior) sobreescriben esto.
      </div>

      <div style={tableHeaderStyle}>
        <div style={{ flex: 1.5 }}>Módulo</div>
        <div style={{ flex: 2 }}>Descripción</div>
        <div style={{ width: 80, textAlign: 'center' }}>Activo</div>
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
            <div style={{ width: 80, textAlign: 'center' }}>
              <span style={{
                display: 'inline-block', padding: '2px 9px', borderRadius: 999,
                fontSize: '0.7rem', fontWeight: 600,
                background: m.activo ? '#e8f5e9' : '#fafafa',
                color: m.activo ? '#2e7d32' : '#616161',
                border: m.activo ? '1px solid #c8e6c9' : '1px solid #e0e0e0',
              }}>
                {m.activo ? 'sí' : 'no'}
              </span>
            </div>
            <div style={{ width: 200, display: 'flex', gap: 6, justifyContent: 'center', alignItems: 'center' }}>
              <select
                value={actual}
                onChange={(e) => setNiveles((p) => ({ ...p, [m.modulo_codigo]: Number(e.target.value) }))}
                style={selectStyle}
              >
                <option value={1}>1 — Admin</option>
                <option value={2}>2 — Supervisor</option>
                <option value={3}>3 — Operador</option>
                <option value={4}>4 — Consultor</option>
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
