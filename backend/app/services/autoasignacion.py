"""
ZARIS — Autoasignación de reclamos por gestión (mig 114, decisión de César 2026-10-20).

Cuando entra un reclamo «Sin asignar» de una gestión (subárea) con
`subarea.asignacion_automatica = TRUE`, el sistema crea la OT y la agenda solo,
sin mesa ni supervisor:

  1. Candidatos según `tipo_reclamo.asignacion_a`:
       - 'agente': agentes activos de la gestión con usuario activo de nivel
         Gestión (4), no auditores.
       - 'equipo': cuadrillas (tipo_grupo 'trabajo_reclamos') de la gestión con
         al menos un integrante que pueda operar (nivel ≤ 4).
  2. Disponibilidad: desde hoy, día por día hasta HORIZONTE_DIAS — si un día
     está completo pasa al siguiente (César). Hoy solo cuentan los huecos que
     empiezan dentro de MARGEN_HOY_MIN o más.
  3. Dentro de cada día: el de MENOR CARGA (OTs operativas abiertas) y, si
     empatan, el que hace más tiempo que no recibe una (rotación).

Sin hueco en el horizonte (o nadie con horario cargado): el reclamo queda
«Sin asignar», se deja constancia en el historial y se avisa en la campana a
los supervisores de la gestión (fallback admins). Sin mail: con la gestión
autoasignando, un mail por reclamo sería ruido.

Corre como BackgroundTask (post-commit, sesión propia) desde todas las vías que
crean reclamos; un advisory lock por gestión serializa dos reclamos simultáneos
para que no elijan el mismo hueco. Best-effort: nunca levanta.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.services.ot_slots import slots_libres_recurso

logger = logging.getLogger("zaris.autoasignacion")

HORIZONTE_DIAS = 30
MARGEN_HOY_MIN = 30
TZ_MUNICIPIO = ZoneInfo("America/Argentina/Buenos_Aires")
# Base del advisory lock por gestión (cualquier número fijo; + id_subarea).
_LOCK_BASE = 114_000_000

_ESTADOS_OT_ABIERTOS = ("En gestión", "En espera", "Pendiente")


async def _candidatos(db, tipo: str, id_subarea: int) -> list[dict]:
    if tipo == "equipo":
        sql = """
            SELECT e.id_equipo AS id, e.nombre AS nombre,
                   (SELECT COUNT(*) FROM ordenes_trabajo ot
                      JOIN estado_ot eo ON eo.id_estado_ot = ot.id_estado
                     WHERE ot.activo AND NOT ot.es_auditoria AND ot.id_equipo = e.id_equipo
                       AND eo.nombre = ANY(:abiertos)) AS carga,
                   (SELECT MAX(ot.fecha_alta) FROM ordenes_trabajo ot
                     WHERE ot.id_equipo = e.id_equipo AND NOT ot.es_auditoria) AS ultima
              FROM equipos e
             WHERE e.activo AND e.tipo_grupo = 'trabajo_reclamos' AND e.id_subarea = :s
               AND EXISTS (SELECT 1 FROM equipo_agentes ea
                             JOIN agentes a ON a.id_agente = ea.id_agente AND a.activo
                             JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo
                            WHERE ea.id_equipo = e.id_equipo AND ea.activo AND u.nivel_acceso <= 4)
             ORDER BY carga ASC, ultima ASC NULLS FIRST, e.id_equipo
        """
    else:
        sql = """
            SELECT a.id_agente AS id, (a.apellido || ', ' || a.nombre) AS nombre,
                   (SELECT COUNT(*) FROM ordenes_trabajo ot
                      JOIN estado_ot eo ON eo.id_estado_ot = ot.id_estado
                     WHERE ot.activo AND NOT ot.es_auditoria AND ot.id_agente = a.id_agente
                       AND eo.nombre = ANY(:abiertos)) AS carga,
                   (SELECT MAX(ot.fecha_alta) FROM ordenes_trabajo ot
                     WHERE ot.id_agente = a.id_agente AND NOT ot.es_auditoria) AS ultima
              FROM agentes a
              JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo
             WHERE a.activo AND a.id_subarea = :s AND u.nivel_acceso = 4 AND NOT a.es_auditor
             ORDER BY carga ASC, ultima ASC NULLS FIRST, a.id_agente
        """
    rows = (await db.execute(text(sql), {"s": id_subarea, "abiertos": list(_ESTADOS_OT_ABIERTOS)})).mappings().all()
    return [dict(r) for r in rows]


async def _primer_hueco(db, tipo: str, candidatos: list[dict], duracion: int, ahora: datetime):
    """(fecha, slot, candidato) del primer día con hueco; dentro del día, el
    primer candidato en el orden carga → rotación que tenga lugar."""
    hoy = ahora.date()
    # Comparar fecha+hora completas: con solo la hora, a las 23:40 «ahora + 30 min»
    # da 00:10 y dejaba pasar huecos de HOY que ya pasaron (cazado por el smoke).
    desde = (ahora + timedelta(minutes=MARGEN_HOY_MIN)).replace(tzinfo=None)
    for d in range(HORIZONTE_DIAS):
        fecha = hoy + timedelta(days=d)
        for c in candidatos:
            slots = await slots_libres_recurso(db, tipo, c["id"], fecha, duracion)
            slots = [s for s in slots
                     if datetime.combine(fecha, time.fromisoformat(s["hora_inicio"])) >= desde]
            if slots:
                return fecha, slots[0], c
    return None


async def _avisar_supervisores_sin_hueco(db, r, motivo: str) -> int:
    """Campana (sin mail) a los supervisores de la gestión; fallback admins."""
    usuarios = [x.id_usuario for x in (await db.execute(text("""
        SELECT DISTINCT u.id_usuario FROM agentes a
          JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo = TRUE
         WHERE a.id_subarea = :s AND a.activo = TRUE AND u.nivel_acceso = 2
    """), {"s": r.id_subarea})).fetchall()]
    if not usuarios:
        usuarios = [x.id_usuario for x in (await db.execute(text(
            "SELECT id_usuario FROM usuarios WHERE activo = TRUE AND nivel_acceso = 1"))).fetchall()]
    nro = r.nro_reclamo or f"#{r.id_reclamo}"
    for uid in usuarios:
        await db.execute(text("""
            INSERT INTO notificacion (id_usuario, tipo, titulo, mensaje, url_destino,
                                      recurso_tipo, recurso_id, id_municipio)
            VALUES (:u, 'autoasignacion_sin_hueco', :t, :m, :url, 'reclamo', :rid, :mun)
        """), {"u": uid, "t": f"{nro} no se pudo asignar solo",
               "m": f"{motivo} El reclamo quedó «Sin asignar» en la mesa del supervisor.",
               "url": f"#/reclamos/{r.id_reclamo}", "rid": r.id_reclamo, "mun": r.id_municipio})
    return len(usuarios)


async def autoasignar_reclamo(id_reclamo: int, ahora: Optional[datetime] = None) -> dict[str, Any]:
    """Intenta asignar solo un reclamo recién creado. Devuelve qué pasó (para el
    log y los smokes): {'asignada': bool, 'motivo'?, 'id_ot'?, 'recurso'?, 'fecha'?, 'hora'?}."""
    ahora = ahora or datetime.now(TZ_MUNICIPIO)
    try:
        async with AsyncSessionLocal() as db:
            r = (await db.execute(text("""
                SELECT r.id_reclamo, r.nro_reclamo, r.estado, r.id_municipio,
                       tr.id_subarea, tr.asignacion_a, tr.duracion_estimada_min,
                       s.asignacion_automatica
                  FROM reclamos r
                  JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
                  JOIN subarea s ON s.id_subarea = tr.id_subarea
                 WHERE r.id_reclamo = :id AND r.activo = TRUE
            """), {"id": id_reclamo})).fetchone()
            if not r or not r.asignacion_automatica:
                return {"asignada": False, "motivo": "la gestión no tiene asignación automática"}
            if r.estado != "Sin asignar":
                return {"asignada": False, "motivo": f"el reclamo está {r.estado}"}

            # Serializa la gestión: dos reclamos simultáneos no eligen el mismo hueco.
            await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_BASE + int(r.id_subarea)})
            ya_tiene = await db.scalar(text(
                "SELECT 1 FROM ordenes_trabajo WHERE id_reclamo = :id AND activo AND NOT es_auditoria LIMIT 1"),
                {"id": id_reclamo})
            if ya_tiene:
                return {"asignada": False, "motivo": "el reclamo ya tiene OT"}

            tipo = "equipo" if r.asignacion_a == "equipo" else "agente"
            duracion = r.duracion_estimada_min if 15 <= (r.duracion_estimada_min or 0) <= 480 else 60
            candidatos = await _candidatos(db, tipo, r.id_subarea)
            hallado = await _primer_hueco(db, tipo, candidatos, duracion, ahora) if candidatos else None

            if not hallado:
                motivo = ("Nadie de la gestión puede recibirlo (sin agentes de nivel Gestión ni cuadrillas con integrantes)."
                          if not candidatos else
                          f"Nadie de la gestión tiene horario libre en los próximos {HORIZONTE_DIAS} días.")
                await db.execute(text("""
                    INSERT INTO reclamo_historial (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
                    VALUES (:id, 'Asignación automática sin hueco', 'Sin asignar', 'Sin asignar', :nota, NOW(), NULL)
                """), {"id": id_reclamo, "nota": motivo})
                avisados = await _avisar_supervisores_sin_hueco(db, r, motivo)
                await db.commit()
                logger.info("autoasignar %s: sin hueco (%s) — %d avisos", r.nro_reclamo, motivo, avisados)
                return {"asignada": False, "motivo": motivo}

            fecha, slot, c = hallado
            id_estado = await db.scalar(text(
                "SELECT id_estado_ot FROM estado_ot WHERE nombre = 'En gestión' AND activo = TRUE LIMIT 1"))
            ot = (await db.execute(text("""
                INSERT INTO ordenes_trabajo
                    (id_reclamo, id_estado, id_agente, id_equipo, es_auditoria, asignacion_automatica,
                     id_supervisor_asigna, activo, fecha_alta, fecha_modificacion)
                VALUES (:r, :e, :ag, :eq, FALSE, TRUE, NULL, TRUE, NOW(), NOW())
                RETURNING id_ot, nro_ot
            """), {"r": id_reclamo, "e": id_estado,
                   "ag": c["id"] if tipo == "agente" else None,
                   "eq": c["id"] if tipo == "equipo" else None})).fetchone()
            nro_ot = ot.nro_ot or f"OT-{ot.id_ot}"
            await db.execute(text("""
                INSERT INTO ocupaciones (tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
                                         id_orden_trabajo, id_municipio, activo, fecha_alta, fecha_modificacion)
                VALUES ('ot', :tr, :ir, :f, :hi, :hf, :ot, :mun, TRUE, NOW(), NOW())
            """), {"tr": tipo, "ir": c["id"], "f": fecha,
                   "hi": time.fromisoformat(slot["hora_inicio"]), "hf": time.fromisoformat(slot["hora_fin"]),
                   "ot": ot.id_ot, "mun": r.id_municipio or 1})
            await db.execute(text("""
                UPDATE reclamos SET estado = 'En gestión', fecha_modificacion = NOW(),
                       fecha_primer_asignacion = COALESCE(fecha_primer_asignacion, NOW())
                 WHERE id_reclamo = :id AND estado = 'Sin asignar'
            """), {"id": id_reclamo})
            quien = f"{'la cuadrilla' if tipo == 'equipo' else ''} {c['nombre']}".strip()
            await db.execute(text("""
                INSERT INTO reclamo_historial (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
                VALUES (:id, :acc, 'Sin asignar', 'En gestión', :nota, NOW(), NULL)
            """), {"id": id_reclamo, "acc": f"OT {nro_ot} asignada automáticamente",
                   "nota": f"Asignada a {quien} para el {fecha.strftime('%d/%m/%Y')} a las {slot['hora_inicio'][:5]} "
                           f"(menor carga de la gestión con horario libre)."})
            await db.commit()

        # Avisos post-commit (best-effort, sesión propia cada uno).
        from app.services import push as svc_push
        await svc_push.notificar_ot_asignada(ot.id_ot)
        await svc_push.notificar_estado_reclamo(id_reclamo)
        logger.info("autoasignar %s → %s %s (%s %s)", r.nro_reclamo, tipo, c["id"], fecha, slot["hora_inicio"])
        return {"asignada": True, "id_ot": ot.id_ot, "nro_ot": nro_ot, "tipo_recurso": tipo,
                "id_recurso": c["id"], "recurso": c["nombre"], "fecha": fecha.isoformat(),
                "hora": slot["hora_inicio"][:5]}
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.error("autoasignar_reclamo(%s) fallo: %s", id_reclamo, e, exc_info=True)
        return {"asignada": False, "motivo": f"error: {e}"}
