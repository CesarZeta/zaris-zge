// Constantes de la grilla Gantt. Compartidas entre GanttGrid y la logica DnD
// para que el snap de minutos se compute exactamente igual que el render.
export const HOUR_START = 7         // 07:00
export const HOUR_END   = 20        // 20:00
export const PX_PER_HOUR = 90
export const ROW_HEIGHT = 56
export const COL_LEFT_WIDTH = 200
export const SNAP_MIN = 15          // 15 minutos
