"""Historia clinica minima viable (proyecto ATENCION F5, migs 107 + 107b).

Union de turno_atencion (mig 86) + emergencia_atencion (mig 106) por ciudadano.
Dato sensible (Ley 25.326 art. 2/7; HC informatizada Ley 26.529 art. 13): permiso
restringido a la gestion Salud + nivel 1, resuelto SIEMPRE desde el agente
vinculado (agentes.id_subarea, regla 1:1 §39) y NUNCA desde usuarios.id_subarea.
"Gestion Salud" = area senalada por configuracion_general.id_area_salud (107b),
como la Guardia se senala con id_espacio_guardia (services/guardia.py): sin la
clave, nadie salvo nivel 1 ve la historia (no se adivina).
Cada consulta (ok | denegado | inexistente) deja fila en historia_clinica_acceso
(mig 107) DENTRO de la misma transaccion, antes de responder.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CLAVE_AREA_SALUD = "id_area_salud"

CONTEXTOS = ("turno", "guardia", "mesa", "consulta", "otro")

DETALLE_403: dict[str, str] = {
    "nivel":       "La historia clínica está disponible solo para la gestión Salud y los administradores (el nivel Consultor no accede).",
    "sin_config":  "La historia clínica no está habilitada: falta configurar la gestión Salud (clave id_area_salud, Config > Sistema). Avisá a un administrador.",
    "sin_agente":  "Tu usuario no tiene un agente vinculado; sin agente no se puede determinar tu gestión (Usuarios > vincular agente).",
    "sin_subarea": "Tu agente no tiene una subárea activa asignada; pedile al administrador que la complete.",
    "fuera_salud": "Tu gestión no pertenece a la Secretaría de Salud: no podés consultar historias clínicas.",
}


async def area_salud(db: AsyncSession) -> Optional[dict]:
    """Area ACTIVA que actua como gestion Salud segun la clave de config, o None si la
    clave falta / esta inactiva / no es numerica / apunta a un area inactiva o
    inexistente. El CASE evita el 500 por cast de basura (mejora sobre guardia.py:23)."""
    row = (await db.execute(text("""
        SELECT a.id_area, a.nombre
          FROM configuracion_general cg
          JOIN area a
            ON a.id_area = CASE WHEN TRIM(cg.valor) ~ '^[0-9]{1,9}$' THEN TRIM(cg.valor)::int END
         WHERE cg.clave = :k AND cg.activo = TRUE AND a.activo = TRUE
         LIMIT 1
    """), {"k": CLAVE_AREA_SALUD})).mappings().first()
    return dict(row) if row else None


async def permiso_historia_clinica(db: AsyncSession, user: dict) -> dict[str, Any]:
    """UNICA fuente de verdad del permiso (la usan el guard del GET de datos y el
    endpoint /permiso que consume la UI). Devuelve {"puede": bool, "motivo": str,
    "id_agente": int|None}.

    Tabla de verdad:
      nivel 1, clave OK                          -> True,  'admin'
      nivel 1, clave ausente/invalida            -> True,  'admin_sin_config'  (la UI le avisa que configure)
      nivel 5 (Consultor) o nivel raro (>4)      -> False, 'nivel'             (aunque su agente sea de Salud)
      nivel 2-4, clave ausente/invalida          -> False, 'sin_config'        (fail-closed)
      nivel 2-4, sin agente ACTIVO vinculado     -> False, 'sin_agente'        (fail-closed; NO el fail-open de emergencias.py:273)
      nivel 2-4, agente con subarea NULL o subarea INACTIVA -> False, 'sin_subarea'
      nivel 2-4, subarea.id_area NULL o != area Salud (incluye areas 'Salud' INACTIVAS,
                 caso administrativo@ local)     -> False, 'fuera_salud'
      nivel 2-4, subarea activa del area Salud activa -> True, 'salud'
    """
    nivel = int(user.get("nivel_acceso", 99))
    base: dict[str, Any] = {"id_agente": None}
    if nivel == 1:
        salud = await area_salud(db)
        return {**base, "puede": True, "motivo": "admin" if salud else "admin_sin_config"}
    if nivel > 4:
        return {**base, "puede": False, "motivo": "nivel"}
    salud = await area_salud(db)
    if salud is None:
        return {**base, "puede": False, "motivo": "sin_config"}
    ag = (await db.execute(text("""
        SELECT g.id_agente, g.id_subarea, s.activo AS subarea_activa, s.id_area
          FROM agentes g
          LEFT JOIN subarea s ON s.id_subarea = g.id_subarea
         WHERE g.id_usuario = :u AND g.activo = TRUE
         LIMIT 1
    """), {"u": user["id_usuario"]})).mappings().first()
    if ag is None:
        return {**base, "puede": False, "motivo": "sin_agente"}
    info = {"id_agente": ag["id_agente"]}
    if ag["id_subarea"] is None or not ag["subarea_activa"]:
        return {**info, "puede": False, "motivo": "sin_subarea"}
    if ag["id_area"] is None or ag["id_area"] != salud["id_area"]:
        return {**info, "puede": False, "motivo": "fuera_salud"}
    return {**info, "puede": True, "motivo": "salud"}


async def registrar_acceso(db: AsyncSession, *, id_usuario: int, id_ciudadano: int,
                           contexto: str, resultado: str, motivo: str,
                           n_registros: Optional[int], ip: Optional[str],
                           user_agent: Optional[str]) -> None:
    """INSERT en historia_clinica_acceso (mig 107). Se llama DENTRO de la misma
    transaccion del GET y el handler hace commit antes de responder: si el
    registro falla, la lectura falla ("sin registro no hay acceso")."""
    await db.execute(text("""
        INSERT INTO historia_clinica_acceso
            (id_usuario, id_ciudadano, origen, contexto, resultado, motivo, n_registros, ip, user_agent)
        VALUES (:u, :c, 'historia', :ctx, :r, :m, :n, :ip, :ua)
    """), {"u": id_usuario, "c": id_ciudadano, "ctx": contexto, "r": resultado, "m": motivo,
           "n": n_registros, "ip": (ip or "")[:64] or None, "ua": (user_agent or "")[:255] or None})


# Sin filtro activo: la baja logica en la BUC no borra hechos clinicos (26.529 art. 18);
# el encabezado expone `activo` y la UI lo senala.
SQL_CIUDADANO = text("""
    SELECT c.id_ciudadano, c.apellido, c.nombre, c.doc_tipo, c.doc_nro, c.fecha_nac,
           CASE WHEN c.fecha_nac IS NOT NULL
                THEN EXTRACT(YEAR FROM age(CURRENT_DATE, c.fecha_nac))::int END AS edad,
           c.activo
      FROM ciudadanos c
     WHERE c.id_ciudadano = :ic
""")

# Dos fuentes, columnas homogeneas (tipos explicitos por posicion), UNION ALL.
# Zona: el proyecto usa UTC-3 fijo (app/utils/fechas.py TZ_MUNICIPIO; turnos.py:715 hace
# la inversa). turno: t.fecha DATE + t.hora_inicio TIME (hora local naive) -> +3h y se
# interpreta como UTC. emergencia: atendido_en / fecha_modificacion ya son timestamptz.
# Ubicacion del turno: COALESCE(t.id_espacio_ubicacion, tp.id_espacio_ubicacion, t.id_espacio)
# porque los turnos previos a la mig 103 tienen NULL (las 2 filas locales, turnos 34/35).
# Gestion NO se lee de turno_atencion.id_subarea (NULL en legacy): sale de la prestacion.
# COUNT(*) OVER () evita una segunda query para el total.
SQL_HISTORIA = text("""
    SELECT h.*, COUNT(*) OVER () AS total
      FROM (
        SELECT 'turno'::text               AS origen,
               ta.id_turno_atencion         AS id,
               ((t.fecha + t.hora_inicio) + INTERVAL '3 hours') AT TIME ZONE 'UTC' AS fecha_hora,
               'atendida'::text             AS estado,
               COALESCE(tp.nombre, 'Atención')::text AS titulo,
               s.nombre::text               AS gestion_nombre,
               ub.nombre::text              AS ubicacion_nombre,
               CASE WHEN a.id_agente IS NOT NULL
                    THEN COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '')
                    ELSE u.nombre END::text AS profesional_nombre,
               ta.id_turno                  AS id_turno,
               NULL::int                    AS id_emergencia_evento,
               NULL::text                   AS numero_operativo,
               NULL::text                   AS motivo_derivacion,
               ta.intervencion::text        AS intervencion,
               ta.recomendaciones::text     AS recomendaciones,
               ta.fecha_alta                AS registrado_en
          FROM turno_atencion ta
          JOIN turnos t                ON t.id_turno = ta.id_turno
          LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
          LEFT JOIN espacios_agenda ub ON ub.id_espacio = COALESCE(t.id_espacio_ubicacion, tp.id_espacio_ubicacion, t.id_espacio)
          LEFT JOIN subarea s          ON s.id_subarea = COALESCE(tp.id_subarea, ub.id_subarea)
          LEFT JOIN agentes a          ON a.id_agente = t.id_agente
          LEFT JOIN usuarios u         ON u.id_usuario = ta.id_usuario_alta
         WHERE ta.activo = TRUE AND ta.id_ciudadano = :ic

        UNION ALL

        SELECT 'emergencia'::text,
               ea.id_emergencia_atencion,
               COALESCE(ea.atendido_en, ea.fecha_modificacion, ea.derivado_en),
               ea.estado::text,
               (COALESCE(et.nombre, 'Emergencia') || COALESCE(' · ' || st.nombre, ''))::text,
               s2.nombre::text,
               ub2.nombre::text,
               CASE WHEN ag.id_agente IS NOT NULL
                    THEN COALESCE(ag.apellido, '') || ', ' || COALESCE(ag.nombre, '') END::text,
               NULL::int,
               ea.id_emergencia_evento,
               ev.numero_operativo::text,
               ea.motivo_derivacion::text,
               ea.intervencion::text,
               ea.recomendaciones::text,
               COALESCE(ea.atendido_en, ea.fecha_modificacion)
          FROM emergencia_atencion ea
          JOIN emergencia_evento ev        ON ev.id_emergencia_evento = ea.id_emergencia_evento
          LEFT JOIN emergencia_tipo et     ON et.id_emergencia_tipo = ev.id_tipo
          LEFT JOIN emergencia_subtipo st  ON st.id_emergencia_subtipo = ev.id_subtipo
          LEFT JOIN espacios_agenda ub2    ON ub2.id_espacio = ea.id_espacio_ubicacion
          LEFT JOIN subarea s2             ON s2.id_subarea = ub2.id_subarea
          LEFT JOIN agentes ag             ON ag.id_agente = ea.id_agente_atiende
         WHERE ea.activo = TRUE AND ea.id_ciudadano = :ic
           AND ea.estado IN ('atendida', 'ausente')   -- 'pendiente' es la cola viva de la Guardia, no historia
      ) h
     ORDER BY h.fecha_hora DESC, h.origen, h.id DESC
     LIMIT :lim OFFSET :off
""")
