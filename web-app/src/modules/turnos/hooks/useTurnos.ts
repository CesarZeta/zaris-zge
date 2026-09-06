import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelarTurno,
  llamarTurno,
  marcarAusente,
  crearPrestacion,
  crearTurno,
  cumplirTurno,
  editarPrestacion,
  eliminarPrestacion,
  listarAtenciones,
  listarPrestaciones,
  listarTurnos,
  listarUbicaciones,
  mesaUbicacion,
  reprogramarTurno,
} from '../api/turnosApi'
import type {
  CrearTurnoBody,
  CumplirTurnoBody,
  ListarTurnosFiltros,
  PrestacionInput,
  ReprogramarTurnoBody,
} from '../types/turno'

const HORA = 60 * 60 * 1000

/** Opciones de las queries de listado. `enabled: false` = búsqueda diferida
 *  (§23: la pantalla no pide nada al entrar); `version` va a la queryKey para
 *  que presionar Buscar con los mismos filtros vuelva a la red (ver
 *  `lib/busqueda.tsx`). Los prefijos de invalidación siguen matcheando. */
export interface OpcionesListado {
  enabled?: boolean
  version?: number
}

export function useTurnos(filtros: ListarTurnosFiltros, opts: OpcionesListado = {}) {
  return useQuery({
    queryKey: ['turnos', 'lista', filtros, opts.version ?? 0],
    queryFn: () => listarTurnos(filtros),
    staleTime: 15 * 1000,
    enabled: opts.enabled ?? true,
  })
}

// --- Ubicaciones de atencion (F2 plan ATENCION) ---
export function useUbicaciones(fecha?: string) {
  return useQuery({
    queryKey: ['turnos', 'ubicaciones', fecha ?? 'hoy'],
    queryFn: () => listarUbicaciones(fecha),
    staleTime: 30 * 1000,
  })
}

export function useMesaUbicacion(id_espacio: number | null, fecha?: string) {
  return useQuery({
    queryKey: ['turnos', 'mesa', id_espacio, fecha ?? 'hoy'],
    queryFn: () => mesaUbicacion(id_espacio as number, fecha),
    enabled: id_espacio != null,
    staleTime: 15 * 1000,
  })
}

// --- Prestaciones ---
export function usePrestaciones(
  params: { clase?: string; q?: string } = {},
  opts: OpcionesListado = {},
) {
  return useQuery({
    queryKey: ['turnos', 'prestaciones', params, opts.version ?? 0],
    queryFn: () => listarPrestaciones(params),
    staleTime: HORA,
    enabled: opts.enabled ?? true,
  })
}

function invalidarPrest(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['turnos', 'prestaciones'] })
}

export function useCrearPrestacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: PrestacionInput) => crearPrestacion(body),
    onSuccess: () => invalidarPrest(qc),
  })
}

export function useEditarPrestacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: PrestacionInput }) => editarPrestacion(id, body),
    onSuccess: () => invalidarPrest(qc),
  })
}

export function useEliminarPrestacion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => eliminarPrestacion(id),
    onSuccess: () => invalidarPrest(qc),
  })
}

// --- Turnos ---
function invalidar(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['turnos', 'lista'] })
  // La mesa y los contadores de la landing muestran los mismos turnos.
  qc.invalidateQueries({ queryKey: ['turnos', 'mesa'] })
  qc.invalidateQueries({ queryKey: ['turnos', 'ubicaciones'] })
}

export function useCrearTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CrearTurnoBody) => crearTurno(body),
    onSuccess: () => invalidar(qc),
  })
}

export function useReprogramarTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_turno, body }: { id_turno: number; body: ReprogramarTurnoBody }) =>
      reprogramarTurno(id_turno, body),
    onSuccess: () => invalidar(qc),
  })
}

export function useCumplirTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_turno, ...body }: { id_turno: number } & CumplirTurnoBody) =>
      cumplirTurno(id_turno, body),
    onSuccess: () => {
      invalidar(qc)
      qc.invalidateQueries({ queryKey: ['turnos', 'atenciones'] })
    },
  })
}

/** Historia de atenciones de un ciudadano (turnos con registra_atencion).
 *  Scopeada por nivel en el backend (mismo alcance que los turnos). */
export function useAtencionesCiudadano(id_ciudadano: number | null) {
  return useQuery({
    queryKey: ['turnos', 'atenciones', id_ciudadano],
    queryFn: () => listarAtenciones(id_ciudadano as number),
    enabled: id_ciudadano != null,
    staleTime: 15 * 1000,
  })
}

export function useCancelarTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id_turno: number) => cancelarTurno(id_turno),
    onSuccess: () => invalidar(qc),
  })
}

/* ── Colero (mig 105, F3) ─────────────────────────────────────────────── */

/** Llamar / re-llamar. Es el mismo endpoint: re-llamar no cambia el estado,
 *  suma una fila al log y refresca la pantalla de sala. */
export function useLlamarTurno() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_turno, puesto }: { id_turno: number; puesto?: string | null }) =>
      llamarTurno(id_turno, puesto),
    onSuccess: () => invalidar(qc),
  })
}

export function useMarcarAusente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id_turno, observaciones }: { id_turno: number; observaciones?: string | null }) =>
      marcarAusente(id_turno, observaciones),
    onSuccess: () => invalidar(qc),
  })
}
