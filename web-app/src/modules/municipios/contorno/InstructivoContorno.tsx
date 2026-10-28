import { Modal } from '../../agenda/components/Modal'
import type { PasoInstructivo } from './api'

// Instructivo para armar el archivo del contorno (contenido completo en la tarea 7 del plan).
export function InstructivoContorno({ abierto, paso, onCerrar }: {
  abierto: boolean; paso?: PasoInstructivo; onCerrar: () => void
}) {
  return (
    <Modal open={abierto} onClose={onCerrar} title="¿Cómo armo el archivo del contorno?" width={760}>
      <div data-instructivo data-paso={paso ?? ''} />
    </Modal>
  )
}
