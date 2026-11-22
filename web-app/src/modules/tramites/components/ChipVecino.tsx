/** Aviso de bandeja sobre el pedido al vecino (mig 139). «Respondió» gana sobre «Esperando». */
export function ChipVecino({ pedidoAbierto, respuestaSinVer }: { pedidoAbierto?: boolean; respuestaSinVer?: boolean }) {
  if (!pedidoAbierto && !respuestaSinVer) return null
  const respondio = !!respuestaSinVer
  return (
    <span
      title={respondio ? 'El vecino respondió el pedido y nadie abrió el trámite desde entonces' : 'Hay un pedido al vecino sin responder'}
      style={{
        display: 'inline-block', fontSize: 10, fontWeight: 600, fontFamily: 'var(--font-display)',
        padding: '1px 7px', borderRadius: 'var(--radius-pill)', whiteSpace: 'nowrap',
        background: respondio ? 'rgba(31,138,101,.14)' : 'rgba(192,133,50,.18)',
        color: respondio ? 'var(--color-success)' : 'var(--zaris-gold)',
      }}
    >
      {respondio ? 'Respondió el vecino' : 'Esperando al vecino'}
    </span>
  )
}
