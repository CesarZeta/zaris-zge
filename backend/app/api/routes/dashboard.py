"""
ZARIS API - Dashboard "Resumen de actividad municipal" (home del shell).

Un solo endpoint agregado que devuelve, en una pasada, los conteos de las 6
tarjetas y las capas geoposicionadas del mapa. Agregacion 100% en SQL para
pagar una sola vez la latencia Railway<->Supabase (~2s, patron batch §27).

Semantica de las tarjetas (definida por el usuario 2026-07-02):
- emergencias_activas: emergencia_evento en estado NO terminal.
- reclamos_activos:    reclamos con estado fuera de Resuelto/Cancelado.
- espacios_disponibles: espacios_agenda con activo=TRUE.
- turnos_otorgados:    turnos 'reservado' con fecha hoy o futura (vigentes).
- entradas_emitidas:   reservas no canceladas de eventos activos hoy o futuros.
- tramites_abiertos:   tramite cuyo estado FSM actual NO es final.

Capas geo: reclamos y emergencias con lat/lon propias; espacios con el pin de
la mig 93 (turnos y entradas se ubican via su espacio: se devuelven agregados
por espacio); tramites via el primer campo dinamico tipo 'direccion' cuyo
valor sea el shape nuevo {texto, lat, lon}.

Mono-municipio: NO se filtra por id_municipio (puede venir NULL en datos
viejos y un `= :mun` estricto vacia listados en silencio, §43).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# Filtro compartido entre tarjeta y capa de entradas: reservas emitidas (no
# canceladas) de eventos activos vigentes/futuros.
_ENTRADAS_VIGENTES_WHERE = """
    r.activo = TRUE AND e.activo = TRUE
    AND er.codigo <> 'cancelada'
    AND ee.codigo = 'activo'
    AND e.fecha >= CURRENT_DATE
"""


@router.get("/resumen")
async def resumen_dashboard(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    # --- Tarjetas (1 query, 6 subselects) -----------------------------------
    tarjetas = (await db.execute(text(f"""
        SELECT
            (SELECT COUNT(*) FROM emergencia_evento ev
              JOIN emergencia_estado es ON es.id_emergencia_estado = ev.id_estado
             WHERE ev.activo = TRUE AND es.es_terminal = FALSE) AS emergencias_activas,
            (SELECT COUNT(*) FROM reclamos rc
             WHERE rc.activo = TRUE AND rc.estado NOT IN ('Resuelto', 'Cancelado')) AS reclamos_activos,
            (SELECT COUNT(*) FROM espacios_agenda ea
             WHERE ea.activo = TRUE) AS espacios_disponibles,
            (SELECT COUNT(*) FROM turnos t
             WHERE t.activo = TRUE AND t.estado = 'reservado' AND t.fecha >= CURRENT_DATE) AS turnos_otorgados,
            (SELECT COUNT(*) FROM evento_reservas r
              JOIN eventos e ON e.id_evento = r.id_evento
              JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
              JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
             WHERE {_ENTRADAS_VIGENTES_WHERE}) AS entradas_emitidas,
            (SELECT COUNT(*) FROM tramite tr
              JOIN tipo_tramite_estado te ON te.id_tipo_tramite_estado = tr.id_tipo_tramite_estado_actual
             WHERE tr.activo = TRUE AND te.es_final = FALSE) AS tramites_abiertos
    """))).mappings().first()

    # --- Capa reclamos activos con geo ---------------------------------------
    reclamos = (await db.execute(text("""
        SELECT r.id_reclamo, r.nro_reclamo, r.estado, r.prioridad,
               LEFT(COALESCE(r.descripcion, ''), 140) AS descripcion,
               -- ::float: NUMERIC sale como Decimal y FastAPI lo serializa string
               r.latitud::float AS latitud, r.longitud::float AS longitud,
               tr.nombre AS tipo_nombre
        FROM reclamos r
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        WHERE r.activo = TRUE AND r.estado NOT IN ('Resuelto', 'Cancelado')
          AND r.latitud IS NOT NULL AND r.longitud IS NOT NULL
        ORDER BY r.fecha_alta DESC
        LIMIT 500
    """))).mappings().all()

    # --- Capa emergencias activas con geo -------------------------------------
    emergencias = (await db.execute(text("""
        SELECT ev.id_emergencia_evento, ev.numero_operativo, ev.direccion_evento,
               ev.latitud::float AS latitud, ev.longitud::float AS longitud,
               et.nombre AS tipo_nombre, es.codigo AS estado_codigo, es.nombre AS estado_nombre
        FROM emergencia_evento ev
        JOIN emergencia_estado es ON es.id_emergencia_estado = ev.id_estado
        LEFT JOIN emergencia_tipo et ON et.id_emergencia_tipo = ev.id_tipo
        WHERE ev.activo = TRUE AND es.es_terminal = FALSE
          AND ev.latitud IS NOT NULL AND ev.longitud IS NOT NULL
        ORDER BY ev.fecha_hora_recepcion DESC
        LIMIT 500
    """))).mappings().all()

    # --- Capa espacios activos con geo (+ agregados de turnos/entradas) ------
    # Turnos y entradas no tienen geo propia: se ubican via el pin del espacio.
    espacios = (await db.execute(text(f"""
        SELECT ea.id_espacio, ea.nombre, ea.direccion,
               ea.latitud::float AS latitud, ea.longitud::float AS longitud, ea.atendido,
               (SELECT COUNT(*) FROM turnos t
                 WHERE t.activo = TRUE AND t.estado = 'reservado'
                   AND t.fecha >= CURRENT_DATE AND t.id_espacio = ea.id_espacio) AS turnos_vigentes,
               (SELECT COUNT(*) FROM evento_reservas r
                  JOIN eventos e ON e.id_evento = r.id_evento
                  JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
                  JOIN estado_evento ee ON ee.id_estado_evento = e.id_estado_evento
                 WHERE {_ENTRADAS_VIGENTES_WHERE} AND e.id_espacio = ea.id_espacio) AS entradas_vigentes
        FROM espacios_agenda ea
        WHERE ea.activo = TRUE
          AND ea.latitud IS NOT NULL AND ea.longitud IS NOT NULL
        ORDER BY ea.nombre
        LIMIT 200
    """))).mappings().all()

    # --- Capa tramites abiertos con direccion georreferenciada ---------------
    # Toma el primer campo tipo 'direccion' de la version del tramite cuyo
    # valor tenga el shape nuevo {texto, lat, lon}. Los tramites viejos con
    # direccion en texto plano no aparecen en el mapa (si en la tarjeta).
    tramites = (await db.execute(text("""
        SELECT t.id_tramite, t.numero_expediente, t.asunto,
               tt.nombre AS tipo_nombre, te.etiqueta AS estado_etiqueta,
               d.dir ->> 'texto' AS direccion,
               (d.dir ->> 'lat')::float AS latitud,
               (d.dir ->> 'lon')::float AS longitud
        FROM tramite t
        JOIN tipo_tramite_estado te ON te.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
        JOIN tipo_tramite_version tv ON tv.id_tipo_tramite_version = t.id_tipo_tramite_version
        JOIN tipo_tramite tt ON tt.id_tipo_tramite = tv.id_tipo_tramite
        JOIN LATERAL (
            SELECT t.datos_jsonb -> tc.nombre_interno AS dir
            FROM tipo_tramite_campo tc
            WHERE tc.id_tipo_tramite_version = t.id_tipo_tramite_version
              AND tc.tipo_dato = 'direccion'
              AND jsonb_typeof(t.datos_jsonb -> tc.nombre_interno) = 'object'
              AND jsonb_typeof(t.datos_jsonb -> tc.nombre_interno -> 'lat') = 'number'
              AND jsonb_typeof(t.datos_jsonb -> tc.nombre_interno -> 'lon') = 'number'
            ORDER BY tc.orden
            LIMIT 1
        ) d ON TRUE
        WHERE t.activo = TRUE AND te.es_final = FALSE
        ORDER BY t.fecha_alta DESC
        LIMIT 500
    """))).mappings().all()

    return {
        "tarjetas": dict(tarjetas) if tarjetas else {},
        "geo": {
            "reclamos": [dict(r) for r in reclamos],
            "emergencias": [dict(r) for r in emergencias],
            "espacios": [dict(r) for r in espacios],
            "tramites": [dict(r) for r in tramites],
        },
    }
