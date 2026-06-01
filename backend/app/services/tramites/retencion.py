"""
Politica de retencion y depuracion de documentos de Tramites (mig 75, Fases 3-5).

Dos motores, disparados por el endpoint de mantenimiento (cron diario, S35):

  1. archivar_inactivos(db)  -- Fase 3
     Tramites sin movimiento durante N dias (configuracion_general.
     tramite_inactividad_dias) que NO esten ya archivados ni en estado final:
       - setea tramite.fecha_archivado = NOW(), archivado_motivo = 'inactividad'
       - setea tramite.resultado = 'rechazado' (concluyo desfavorablemente)
       - asienta un movimiento 'archivado_inactividad' en el ledger
     El archivado es una marca de mantenimiento PARALELA al estado del FSM (no
     fuerza un estado del circuito, que puede no tener uno "archivado"), igual
     que `resultado` es paralelo al estado (S35).

  2. purgar_binarios(db, dry_run)  -- Fase 4
     Documentos cuyo binario fisico ya cumplio el plazo de retencion segun el
     resultado del tramite (aprobado -> retencion_dias_aprobado;
     rechazado/pendiente archivado -> retencion_dias_rechazado), EXCEPTO los de
     tipos con retencion_nunca_depurar = TRUE. El REGISTRO nunca se borra; solo
     se libera el binario del bucket y se marca binario_purgado = TRUE.

     El plazo se cuenta desde fecha_archivado (si el tramite fue archivado) o,
     en su defecto, desde la fecha del ultimo movimiento del tramite (proxy del
     cierre). Un documento solo se purga si su tramite ya concluyo (archivado o
     con resultado != 'pendiente').

     dry_run=True (default, controlado por configuracion_general.
     tramite_purga_binarios_real): NO borra del bucket ni marca la fila; solo
     reporta que se purgaria. Red de seguridad para la primera corrida.

El movimiento del cron usa como id_agente el id_agente_iniciador del propio
tramite (la columna es NOT NULL; no hay "agente sistema") e id_usuario NULL.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.services.tramites import movimientos as svc_mov
from app.services.tramites.documentos import TRAMITES_BUCKET

logger = logging.getLogger("zaris.tramites.retencion")

# Defaults seguros si la clave no existe / no se puede leer.
DEFAULT_INACTIVIDAD_DIAS = 180
DEFAULT_RETENCION_APROBADO_DIAS = 3650
DEFAULT_RETENCION_RECHAZADO_DIAS = 365


# ---------------------------------------------------------------------------
# Helpers de configuracion (configuracion_general)
# ---------------------------------------------------------------------------

async def _leer_int_config(db: AsyncSession, clave: str, default: int) -> int:
    """Lee una clave entera de configuracion_general. Default si ausente/invalida."""
    try:
        row = (await db.execute(text("""
            SELECT valor FROM configuracion_general
             WHERE clave = :c AND activo = TRUE LIMIT 1
        """), {"c": clave})).fetchone()
        if not row:
            return default
        return int(str(row[0]).strip())
    except Exception as e:
        logger.error("retencion: _leer_int_config(%s) fallo: %s", clave, e)
        return default


async def purga_binarios_es_real(db: AsyncSession) -> bool:
    """configuracion_general.tramite_purga_binarios_real. Default FALSE (dry-run).

    Solo devuelve True si la clave existe explicitamente con 'true'. Cualquier
    otra cosa (ausente, 'false', error) deja el motor en dry-run = no borra nada.
    """
    try:
        row = (await db.execute(text("""
            SELECT valor FROM configuracion_general
             WHERE clave = 'tramite_purga_binarios_real' AND activo = TRUE LIMIT 1
        """))).fetchone()
        return bool(row) and str(row[0]).strip().lower() == "true"
    except Exception as e:
        logger.error("retencion: purga_binarios_es_real fallo: %s", e)
        return False


# ---------------------------------------------------------------------------
# Fase 3: archivado por inactividad
# ---------------------------------------------------------------------------

async def archivar_inactivos(db: AsyncSession, limite: int = 500) -> dict[str, Any]:
    """Archiva tramites sin movimiento hace >= N dias. Idempotente.

    No toca los ya archivados ni los que estan en un estado final del circuito
    (no tiene sentido marcar 'rechazado por inactividad' algo que ya concluyo
    por el flujo). Devuelve {dias, archivados, ids}.
    """
    dias = await _leer_int_config(db, "tramite_inactividad_dias", DEFAULT_INACTIVIDAD_DIAS)

    # Candidatos: activos, no archivados, cuyo estado actual NO es final, y cuyo
    # ultimo movimiento (o fecha_alta si no hay) es mas viejo que `dias`.
    # make_interval(days => :d) — NO (:d || ' days')::interval (S42).
    candidatos = (await db.execute(text("""
        SELECT t.id_tramite, t.id_municipio, t.id_agente_iniciador,
               t.id_tipo_tramite_estado_actual
          FROM tramite t
          JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
         WHERE t.activo = TRUE
           AND t.fecha_archivado IS NULL
           AND COALESCE(e.es_final, FALSE) = FALSE
           AND COALESCE(
                 (SELECT MAX(m.fecha_alta) FROM tramite_movimiento m WHERE m.id_tramite = t.id_tramite),
                 t.fecha_alta
               ) < NOW() - make_interval(days => CAST(:d AS integer))
         ORDER BY t.id_tramite
         LIMIT :lim
    """), {"d": dias, "lim": limite})).fetchall()

    ids: list[int] = []
    for c in candidatos:
        await db.execute(text("""
            UPDATE tramite SET
                fecha_archivado = NOW(),
                archivado_motivo = 'inactividad',
                resultado = 'rechazado',
                fecha_modificacion = NOW()
            WHERE id_tramite = :id AND fecha_archivado IS NULL
        """), {"id": c.id_tramite})

        await svc_mov.registrar_movimiento(
            db, c.id_tramite, "archivado_inactividad",
            id_usuario=None, id_agente=c.id_agente_iniciador,
            id_municipio=c.id_municipio,
            comentario=f"Archivado automatico por inactividad ({dias} dias sin movimiento).",
            metadata_jsonb={"dias_inactividad": dias, "resultado_nuevo": "rechazado"},
        )
        ids.append(c.id_tramite)

    if ids:
        await db.commit()
        logger.info("retencion: archivados por inactividad=%s (dias=%s) ids=%s", len(ids), dias, ids)

    return {"dias": dias, "archivados": len(ids), "ids": ids}


# ---------------------------------------------------------------------------
# Fase 4: purga del binario fisico
# ---------------------------------------------------------------------------

async def purgar_binarios(db: AsyncSession, dry_run: bool | None = None, limite: int = 500) -> dict[str, Any]:
    """Depura los binarios fisicos vencidos. El registro (hash) nunca se borra.

    Reglas:
      - Solo documentos activos con binario_purgado = FALSE.
      - Solo de tramites ya concluidos: archivados (fecha_archivado IS NOT NULL)
        o con resultado != 'pendiente'.
      - Plazo segun resultado del tramite: aprobado -> retencion_dias_aprobado;
        cualquier otro (rechazado, o pendiente-pero-archivado) -> retencion_dias_rechazado.
      - Se cuenta desde la fecha de cierre (COALESCE(fecha_archivado, ultimo
        movimiento, fecha_alta)).
      - EXCEPTO los tipos con retencion_nunca_depurar = TRUE.

    dry_run None => lee configuracion_general.tramite_purga_binarios_real
    (real=True => dry_run=False). Devuelve {dry_run, evaluados, purgados, errores, ids}.
    """
    if dry_run is None:
        dry_run = not await purga_binarios_es_real(db)

    dias_aprob = await _leer_int_config(db, "retencion_dias_aprobado", DEFAULT_RETENCION_APROBADO_DIAS)
    dias_rech = await _leer_int_config(db, "retencion_dias_rechazado", DEFAULT_RETENCION_RECHAZADO_DIAS)

    # El plazo depende del resultado; resolvemos la "fecha de cierre" y el limite
    # en SQL para no traer todo a Python. El tipo se alcanza via la cadena
    # tramite -> version -> tipo (S35: tramite no tiene id_tipo_tramite directo).
    candidatos = (await db.execute(text("""
        WITH doc AS (
            SELECT d.id_tramite_documento, d.id_tramite, d.storage_path, d.id_municipio,
                   d.id_agente_subio, t.resultado, t.id_agente_iniciador,
                   COALESCE(
                       t.fecha_archivado,
                       (SELECT MAX(m.fecha_alta) FROM tramite_movimiento m WHERE m.id_tramite = t.id_tramite),
                       t.fecha_alta
                   ) AS fecha_cierre,
                   tt.retencion_nunca_depurar
              FROM tramite_documento d
              JOIN tramite t                ON t.id_tramite = d.id_tramite
              JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
              JOIN tipo_tramite tt          ON tt.id_tipo_tramite = ttv.id_tipo_tramite
             WHERE d.activo = TRUE
               AND d.binario_purgado = FALSE
               AND COALESCE(tt.retencion_nunca_depurar, FALSE) = FALSE
               AND (t.fecha_archivado IS NOT NULL OR t.resultado <> 'pendiente')
        )
        SELECT * FROM doc
         WHERE fecha_cierre < NOW() - make_interval(days =>
                   CASE WHEN resultado = 'aprobado'
                        THEN CAST(:da AS integer)
                        ELSE CAST(:dr AS integer) END)
         ORDER BY id_tramite_documento
         LIMIT :lim
    """), {"da": dias_aprob, "dr": dias_rech, "lim": limite})).fetchall()

    purgados: list[int] = []
    errores: list[dict] = []

    for c in candidatos:
        if dry_run:
            purgados.append(c.id_tramite_documento)
            continue
        try:
            # Best-effort: borra el binario del bucket. Si no existe, no-op.
            await storage.borrar_objeto(c.storage_path, bucket=TRAMITES_BUCKET)
            await db.execute(text("""
                UPDATE tramite_documento SET
                    binario_purgado = TRUE,
                    fecha_purga_binario = NOW(),
                    fecha_modificacion = NOW()
                WHERE id_tramite_documento = :id AND binario_purgado = FALSE
            """), {"id": c.id_tramite_documento})
            await svc_mov.registrar_movimiento(
                db, c.id_tramite, "purga_binario",
                id_usuario=None, id_agente=c.id_agente_iniciador,
                id_municipio=c.id_municipio,
                comentario="Archivo fisico depurado por antiguedad. El registro y su hash se conservan.",
                metadata_jsonb={"id_tramite_documento": c.id_tramite_documento, "resultado": c.resultado},
            )
            purgados.append(c.id_tramite_documento)
        except Exception as e:
            logger.error("retencion: purga doc=%s fallo: %s", c.id_tramite_documento, e)
            errores.append({"id_tramite_documento": c.id_tramite_documento, "error": str(e)})

    if purgados and not dry_run:
        await db.commit()

    logger.info(
        "retencion: purga dry_run=%s evaluados=%s purgados=%s errores=%s",
        dry_run, len(candidatos), len(purgados), len(errores),
    )
    return {
        "dry_run": dry_run,
        "evaluados": len(candidatos),
        "purgados": len(purgados),
        "errores": len(errores),
        "ids": purgados,
        "detalle_errores": errores,
    }
