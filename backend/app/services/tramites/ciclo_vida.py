"""
Ciclo de vida del tramite hacia el VECINO (mig 101 — decisiones de Cesar 2026-08-30).

Tres piezas, todas paralelas al FSM del circuito (no fuerzan estados):

  1. derivar_resultado_por_transicion(...)  -- en transicionar_tramite, ANTES del commit
     La transicion que lleva a un estado final trae `tipo_accion`: 'aprobar' ->
     resultado='aprobado', 'rechazar' -> 'rechazado'. Sin paso manual. Si la
     transicion final es 'avanzar'/'otro' (ambigua) el resultado queda
     'pendiente' para que lo marque un supervisor (POST /resultado). Nunca pisa
     una marca manual previa.

  2. al_terminar(id_tramite)  -- POST-commit, best-effort (sesion propia)
     Comunica al iniciador que el tramite TERMINO y su resultado: aviso en la
     bandeja de la PWA (mig 99, tipo 'tramite_estado') + push; opcionalmente
     email. Si termino aprobado/rechazado, dispara la encuesta CSAT de tramites
     (encuestas_service.crear_envio_para_tramite).

  3. procesar_desistimientos(db)  -- cron diario (tramites_mantenimiento.py)
     Timer para tramites en un estado marcado `espera_iniciador` (catalogo):
       t0 = GREATEST(fecha_alta + SLA del tipo, entrada al estado de espera)
       t0 + aviso1_dias  -> aviso 1 al vecino (+ aviso interno al colectivo)
       t0 + aviso2_dias  -> aviso 2
       t0 + desistir_dias - aviso_final_horas -> ultimo aviso
       t0 + desistir_dias -> DESISTIDO automatico (resultado='desistido',
                             fecha_archivado, archivado_motivo='desistimiento')
     Avanza a lo sumo UN nivel por corrida (no inunda al vecino si hay backlog).
     El nivel vive en tramite.desist_aviso_nivel y se resetea a 0 en cada
     transicion (el vecino respondio / el circuito se movio). Solo iniciadores
     ciudadano/empresa: un tramite interno no se "desiste".

Plazos en configuracion_general (seed 101b, Config -> Sistema §41) con defaults
seguros. El movimiento del cron usa id_agente_iniciador (NOT NULL; no hay
"agente sistema") e id_usuario NULL, igual que retencion.py.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services import push as svc_push
from app.services.avisos import registrar_aviso_ciudadano
from app.services.email import enviar_mail
from app.services.tramites import movimientos as svc_mov
from app.services.tramites.retencion import _leer_int_config
from app.utils.log_helpers import mask_email

logger = logging.getLogger("zaris.tramites.ciclo_vida")

RESULTADO_POR_ACCION = {"aprobar": "aprobado", "rechazar": "rechazado"}
RESULTADOS_CON_ENCUESTA = ("aprobado", "rechazado")
# La PWA no tiene pantallas de tramites: el aviso se lee en la bandeja.
URL_PWA_AVISOS = "/alertas"

CFG_ACTIVO = "tramite_desistimiento_activo"
CFG_SLA_DEFAULT = "tramite_sla_dias_default"
CFG_AVISO1 = "tramite_desistimiento_aviso1_dias"
CFG_AVISO2 = "tramite_desistimiento_aviso2_dias"
CFG_DESISTIR = "tramite_desistimiento_dias"
CFG_FINAL_HORAS = "tramite_desistimiento_aviso_final_horas"
DEFAULTS = {CFG_SLA_DEFAULT: 30, CFG_AVISO1: 30, CFG_AVISO2: 60,
            CFG_DESISTIR: 90, CFG_FINAL_HORAS: 72}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _leer_bool_config(db: AsyncSession, clave: str, default: bool) -> bool:
    try:
        row = (await db.execute(text(
            "SELECT valor FROM configuracion_general WHERE clave = :c AND activo = TRUE LIMIT 1"
        ), {"c": clave})).fetchone()
        if not row:
            return default
        return str(row[0]).strip().lower() == "true"
    except Exception as e:  # noqa: BLE001
        logger.error("ciclo_vida: _leer_bool_config(%s) fallo: %s", clave, e)
        return default


def _esc(s: Optional[str]) -> str:
    return ((s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


async def _datos_para_vecino(db: AsyncSession, id_tramite: int) -> Optional[dict]:
    row = (await db.execute(text("""
        SELECT t.id_tramite, t.numero_expediente, t.resultado, t.iniciador_tipo,
               t.id_ciudadano_iniciador, t.id_empresa_iniciadora, t.id_municipio,
               tt.nombre AS tipo_nombre, e.etiqueta AS estado_etiqueta,
               COALESCE(e.es_final, FALSE) AS es_final,
               ci.email AS email_ciudadano,
               TRIM(COALESCE(ci.nombre, '') || ' ' || COALESCE(ci.apellido, '')) AS nombre_ciudadano,
               em.email AS email_empresa, em.nombre AS nombre_empresa
          FROM tramite t
          JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
          JOIN tipo_tramite_version v ON v.id_tipo_tramite_version = t.id_tipo_tramite_version
          JOIN tipo_tramite tt ON tt.id_tipo_tramite = v.id_tipo_tramite
          LEFT JOIN ciudadanos ci ON ci.id_ciudadano = t.id_ciudadano_iniciador
          LEFT JOIN empresas em ON em.id_empresa = t.id_empresa_iniciadora
         WHERE t.id_tramite = :id AND t.activo = TRUE
    """), {"id": id_tramite})).mappings().first()
    return dict(row) if row else None


async def _mail_vecino(dest: str, nombre: Optional[str], asunto: str, cuerpo: str,
                       numero: str, tipo_nombre: str) -> None:
    html = (
        f"<p>Hola {_esc(nombre) or ''},</p>"
        f"<p>{_esc(cuerpo)}</p>"
        f"<p>Número de expediente: <strong>{_esc(numero)}</strong><br>"
        f"Tipo: {_esc(tipo_nombre)}</p>"
    )
    texto = f"{cuerpo}\n\nExpediente: {numero}\nTipo: {tipo_nombre}"
    try:
        ok = await enviar_mail(dest, asunto, html, texto)
        logger.info("ciclo_vida: mail %s a %s -> %s", numero, mask_email(dest), ok)
    except Exception as e:  # noqa: BLE001
        logger.warning("ciclo_vida: mail %s a %s fallo: %s", numero, mask_email(dest), e)


async def _avisar_vecino(d: dict, tipo_aviso: str, titulo: str, cuerpo: str,
                         *, con_email: bool) -> None:
    """Bandeja PWA + push (solo ciudadano — la empresa no tiene app) y,
    si `con_email`, correo al iniciador (ciudadano o empresa). Best-effort."""
    id_c = d.get("id_ciudadano_iniciador")
    if d.get("iniciador_tipo") == "ciudadano" and id_c:
        await registrar_aviso_ciudadano(
            int(id_c), tipo_aviso, titulo, cuerpo, URL_PWA_AVISOS,
            recurso_tipo="tramite", recurso_id=int(d["id_tramite"]),
        )
        await svc_push.enviar_push_ciudadano(int(id_c), titulo=titulo, cuerpo=cuerpo, url=URL_PWA_AVISOS)
    if con_email:
        if d.get("iniciador_tipo") == "ciudadano":
            dest, nombre = d.get("email_ciudadano"), d.get("nombre_ciudadano")
        else:
            dest, nombre = d.get("email_empresa"), d.get("nombre_empresa")
        if dest and "@" in dest:
            await _mail_vecino(dest, nombre, titulo, cuerpo, d["numero_expediente"], d.get("tipo_nombre") or "trámite")


def _texto_terminacion(d: dict) -> tuple[str, str]:
    n = d["numero_expediente"]
    tipo = d.get("tipo_nombre") or "Trámite"
    r = d.get("resultado") or "pendiente"
    if r == "aprobado":
        return f"Tu trámite {n} terminó: APROBADO", f"{tipo}: tu trámite fue aprobado."
    if r == "rechazado":
        return f"Tu trámite {n} terminó: RECHAZADO", f"{tipo}: tu trámite fue rechazado."
    if r == "desistido":
        return (f"Tu trámite {n} fue dado por desistido",
                f"{tipo}: no recibimos tu respuesta dentro del plazo. "
                "Si querés continuar, iniciá un trámite nuevo o comunicate con el municipio.")
    return (f"Tu trámite {n} terminó",
            f"{tipo}: estado \"{d.get('estado_etiqueta') or 'finalizado'}\". "
            "El resultado se informará cuando esté disponible.")


# ---------------------------------------------------------------------------
# 1. Resultado derivado de la transicion final (pre-commit, misma transaccion)
# ---------------------------------------------------------------------------

async def derivar_resultado_por_transicion(
    db: AsyncSession,
    id_tramite: int,
    tramite: dict,
    tipo_accion: Optional[str],
    id_usuario: int,
    id_agente: int,
    request: Optional[Request] = None,
) -> Optional[str]:
    """Si la transicion final es 'aprobar'/'rechazar' y el tramite no tiene
    resultado manual previo, sella resultado + movimiento 'resultado'
    (metadata.automatico=true). Devuelve el resultado nuevo o None."""
    nuevo = RESULTADO_POR_ACCION.get((tipo_accion or "").strip().lower())
    if not nuevo:
        return None
    if (tramite.get("resultado") or "pendiente") != "pendiente":
        return None  # marca manual previa: se respeta
    await db.execute(text("""
        UPDATE tramite SET resultado = :r, fecha_modificacion = NOW(),
                           id_usuario_modificacion = :uid
         WHERE id_tramite = :id
    """), {"r": nuevo, "uid": id_usuario, "id": id_tramite})
    await svc_mov.registrar_movimiento(
        db, id_tramite, "resultado", id_usuario, id_agente,
        tramite["id_municipio"], request,
        comentario=f"Resultado derivado de la transición final ({tipo_accion}).",
        metadata_jsonb={"resultado_anterior": "pendiente", "resultado_nuevo": nuevo,
                        "automatico": True, "tipo_accion": tipo_accion},
    )
    return nuevo


# ---------------------------------------------------------------------------
# 2. Comunicar la terminacion (post-commit, best-effort)
# ---------------------------------------------------------------------------

async def al_terminar(id_tramite: int, *, con_email: bool = False) -> None:
    """Aviso PWA + push al ciudadano iniciador ("terminó: aprobado/rechazado",
    o "terminó, resultado pendiente", o "desistido") y encuesta CSAT si el
    resultado es aprobado/rechazado. `con_email=True` suma el correo (cuando
    no lo manda ya la transicion via notifica_iniciador)."""
    try:
        async with AsyncSessionLocal() as db:
            d = await _datos_para_vecino(db, id_tramite)
        if not d or d.get("iniciador_tipo") not in ("ciudadano", "empresa"):
            return
        titulo, cuerpo = _texto_terminacion(d)
        await _avisar_vecino(d, "tramite_estado", titulo, cuerpo, con_email=con_email)

        if d.get("iniciador_tipo") == "ciudadano" and d.get("resultado") in RESULTADOS_CON_ENCUESTA:
            # Import tardio: encuestas_service es pesado y no debe cargarse al importar tramites.
            from app.services import encuestas_service as svc_enc
            async with AsyncSessionLocal() as db2:
                envio, motivo = await svc_enc.crear_envio_para_tramite(db2, id_tramite)
            logger.info("ciclo_vida: encuesta tramite=%s -> %s (%s)",
                        id_tramite, envio["id_encuesta_envio"] if envio else None, motivo)
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.warning("ciclo_vida.al_terminar(%s) fallo: %s", id_tramite, e)


# ---------------------------------------------------------------------------
# 3. Timer de desistimiento (cron)
# ---------------------------------------------------------------------------

_ETIQUETA_NIVEL = {1: "1er aviso", 2: "2do aviso", 3: "último aviso"}


def _texto_aviso(nivel: int, d: dict, dias_restantes: int, final_horas: int) -> tuple[str, str]:
    n = d["numero_expediente"]
    tipo = d.get("tipo_nombre") or "Trámite"
    estado = d.get("estado_etiqueta") or "a la espera de tu respuesta"
    if nivel == 1:
        return (f"Tu trámite {n} está pendiente de tu respuesta",
                f"{tipo}: el expediente está en \"{estado}\" y necesitamos que completes lo solicitado. "
                f"Si no hay novedades en los próximos {dias_restantes} días, el trámite se dará por desistido.")
    if nivel == 2:
        return (f"Recordatorio: tu trámite {n} sigue pendiente",
                f"{tipo}: todavía no recibimos tu respuesta (\"{estado}\"). "
                f"Quedan {dias_restantes} días antes de que el trámite se dé por desistido.")
    return (f"Último aviso: tu trámite {n} se dará por desistido en {final_horas} horas",
            f"{tipo}: si no completás lo solicitado (\"{estado}\") en las próximas {final_horas} horas, "
            "el trámite se dará por desistido automáticamente.")


async def procesar_desistimientos(db: AsyncSession, limite: int = 500) -> dict[str, Any]:
    """Corrida diaria del timer. Devuelve {activo, config, avisos, desistidos, ids}."""
    if not await _leer_bool_config(db, CFG_ACTIVO, True):
        return {"activo": False, "avisos": 0, "desistidos": 0, "ids": []}

    cfg = {k: await _leer_int_config(db, k, v) for k, v in DEFAULTS.items()}
    a1, a2 = cfg[CFG_AVISO1], cfg[CFG_AVISO2]
    dd, fh = cfg[CFG_DESISTIR], cfg[CFG_FINAL_HORAS]
    umbral_final = dd - (fh / 24.0)

    # asyncpg: cada bind param casteado (make_interval(days => CAST(...)), §35 quirks).
    rows = (await db.execute(text("""
        SELECT t.id_tramite, t.numero_expediente, t.id_municipio, t.id_agente_iniciador,
               t.iniciador_tipo, t.id_ciudadano_iniciador, t.id_empresa_iniciadora,
               t.desist_aviso_nivel,
               tt.nombre AS tipo_nombre, e.etiqueta AS estado_etiqueta,
               ci.email AS email_ciudadano,
               TRIM(COALESCE(ci.nombre, '') || ' ' || COALESCE(ci.apellido, '')) AS nombre_ciudadano,
               em.email AS email_empresa, em.nombre AS nombre_empresa,
               EXTRACT(EPOCH FROM (NOW() - GREATEST(
                   t.fecha_alta + make_interval(days => COALESCE(NULLIF(tt.sla_dias, 0), CAST(:sla AS integer))),
                   t.fecha_entrada_estado_actual
               ))) / 86400.0 AS dias_desde_t0
          FROM tramite t
          JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
          JOIN tipo_tramite_version v ON v.id_tipo_tramite_version = t.id_tipo_tramite_version
          JOIN tipo_tramite tt ON tt.id_tipo_tramite = v.id_tipo_tramite
          LEFT JOIN ciudadanos ci ON ci.id_ciudadano = t.id_ciudadano_iniciador
          LEFT JOIN empresas em ON em.id_empresa = t.id_empresa_iniciadora
         WHERE t.activo = TRUE
           AND t.fecha_archivado IS NULL
           AND COALESCE(e.es_final, FALSE) = FALSE
           AND COALESCE(e.espera_iniciador, FALSE) = TRUE
           AND t.iniciador_tipo IN ('ciudadano', 'empresa')
           AND COALESCE(t.resultado, 'pendiente') = 'pendiente'
         ORDER BY t.id_tramite
         LIMIT :lim
    """), {"sla": cfg[CFG_SLA_DEFAULT], "lim": limite})).mappings().all()

    avisos = 0
    desistidos: list[int] = []
    avisados: list[dict] = []
    for r in rows:
        d = dict(r)
        nivel = int(d.get("desist_aviso_nivel") or 0)
        dias = float(d.get("dias_desde_t0") or 0.0)
        id_t = int(d["id_tramite"])

        if nivel <= 0 and dias >= a1:
            nuevo_nivel = 1
        elif nivel == 1 and dias >= a2:
            nuevo_nivel = 2
        elif nivel == 2 and dias >= umbral_final:
            nuevo_nivel = 3
        elif nivel >= 3 and dias >= dd:
            nuevo_nivel = None  # desistir
        else:
            continue

        if nuevo_nivel is not None:
            restantes = max(0, int(round(dd - dias)))
            titulo, cuerpo = _texto_aviso(nuevo_nivel, d, restantes, fh)
            await db.execute(text("""
                UPDATE tramite SET desist_aviso_nivel = :n, desist_aviso_en = NOW(),
                                   fecha_modificacion = NOW()
                 WHERE id_tramite = :id
            """), {"n": nuevo_nivel, "id": id_t})
            await svc_mov.registrar_movimiento(
                db, id_t, "aviso_iniciador",
                id_usuario=None, id_agente=d["id_agente_iniciador"],
                id_municipio=d["id_municipio"],
                comentario=f"{_ETIQUETA_NIVEL[nuevo_nivel]} de desistimiento al iniciador "
                           f"({int(dias)} días desde el vencimiento del SLA / entrada a la espera).",
                metadata_jsonb={"nivel": nuevo_nivel, "dias_desde_t0": round(dias, 1),
                                "dias_restantes": restantes, "automatico": True},
            )
            await db.commit()
            # Post-commit, best-effort: vecino (bandeja + push + mail) e interno.
            await _avisar_vecino(d, "tramite_pendiente", titulo, cuerpo, con_email=True)
            try:
                from app.services import notificaciones as svc_notif
                await svc_notif.notificar_tramite_pendiente_vecino(db, id_t, nuevo_nivel, int(dias))
            except Exception as e:  # noqa: BLE001
                logger.warning("ciclo_vida: notificacion interna tramite=%s fallo: %s", id_t, e)
            avisos += 1
            avisados.append({"id_tramite": id_t, "nivel": nuevo_nivel})
            logger.info("ciclo_vida: aviso %s tramite=%s (%s dias)", nuevo_nivel, d["numero_expediente"], int(dias))
        else:
            await db.execute(text("""
                UPDATE tramite SET resultado = 'desistido',
                                   fecha_archivado = NOW(),
                                   archivado_motivo = 'desistimiento',
                                   desist_aviso_en = NOW(),
                                   fecha_modificacion = NOW()
                 WHERE id_tramite = :id AND fecha_archivado IS NULL
            """), {"id": id_t})
            await svc_mov.registrar_movimiento(
                db, id_t, "desistido",
                id_usuario=None, id_agente=d["id_agente_iniciador"],
                id_municipio=d["id_municipio"],
                comentario=f"Desistimiento automático: sin respuesta del iniciador tras {int(dias)} días "
                           f"(SLA + {dd} días, {a1}/{a2}/{fh}h de avisos).",
                metadata_jsonb={"dias_desde_t0": round(dias, 1), "resultado_nuevo": "desistido",
                                "archivado_motivo": "desistimiento", "automatico": True},
            )
            await db.commit()
            await al_terminar(id_t, con_email=True)
            desistidos.append(id_t)
            logger.info("ciclo_vida: DESISTIDO tramite=%s (%s dias)", d["numero_expediente"], int(dias))

    return {"activo": True, "config": cfg, "avisos": avisos, "avisados": avisados,
            "desistidos": len(desistidos), "ids": desistidos}
