import { Badge } from '../../../ui'

/** Aviso de bandeja sobre el pedido al vecino (mig 139). «Respondió» gana sobre «Esperando». */
export function ChipVecino({ pedidoAbierto, respuestaSinVer }: { pedidoAbierto?: boolean; respuestaSinVer?: boolean }) {
  if (!pedidoAbierto && !respuestaSinVer) return null
  const respondio = !!respuestaSinVer
  return (
    <span
      title={respondio ? 'El vecino respondió el pedido y nadie abrió el trámite desde entonces' : 'Hay un pedido al vecino sin responder'}
      style={{ whiteSpace: 'nowrap' }}
    >
      <Badge kind={respondio ? 'success' : 'warn'}>
        {respondio ? 'Respondió el vecino' : 'Esperando al vecino'}
      </Badge>
    </span>
  )
}
