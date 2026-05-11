import { Modal } from './Modal'
import { Button } from '../../../ui'

interface Props {
  open: boolean
  title?: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  open,
  title = 'Confirmar accion',
  message,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  danger = false,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      width={420}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>{cancelLabel}</Button>
          <Button variant={danger ? 'default' : 'accent'} onClick={onConfirm}>{confirmLabel}</Button>
        </>
      }
    >
      <p style={{ margin: 0, fontSize: 14, color: 'var(--fg-1)', lineHeight: 1.5 }}>{message}</p>
    </Modal>
  )
}
