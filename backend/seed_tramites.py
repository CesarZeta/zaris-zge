"""
Seed idempotente para el modulo Tramites/Expedientes.

Crea:
  - 5 subareas nuevas necesarias para el circuito de tramites
  - 9 tipos de tramite con sus versiones publicadas, campos, estados,
    transiciones y documentos requeridos
  - ~20 tramites instanciados en distintos estados con movimientos, documentos y firmas demo
  - 2 relaciones entre tramites de la misma empresa

Idempotente: cada entidad se busca por nombre/codigo antes de insertar.
Prerequisito: migraciones 47, 48, 49 aplicadas.

Uso:
  cd backend
  $env:ENV_FILE=".env.local"; python seed_tramites.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# Necesario para imports relativos desde la raiz de backend
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ENV_FILE", ".env.local")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import dotenv_values

# --- Config ---
env_file = os.environ.get("ENV_FILE", ".env.local")
cfg = dotenv_values(env_file)
DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or cfg.get("DATABASE_URL")
    or "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

ID_MUNICIPIO = 1
ANIO = 2026


# =============================================================================
# Helpers
# =============================================================================

async def fetchone(conn, sql, params=None):
    r = await conn.execute(text(sql), params or {})
    return r.fetchone()


async def fetchval(conn, sql, params=None):
    r = await conn.execute(text(sql), params or {})
    row = r.fetchone()
    return row[0] if row else None


async def upsert_subarea(conn, nombre, id_area, id_municipio=ID_MUNICIPIO):
    """Busca o crea una subarea por nombre (case-insensitive). Devuelve id_subarea."""
    row = await fetchone(conn,
        "SELECT id_subarea FROM subarea WHERE LOWER(nombre) = LOWER(:n) AND id_municipio = :m LIMIT 1",
        {"n": nombre, "m": id_municipio})
    if row:
        # Reactivar si estaba inactiva
        await conn.execute(text(
            "UPDATE subarea SET activo = TRUE WHERE id_subarea = :id"), {"id": row[0]})
        return row[0]

    r = await conn.execute(text("""
        INSERT INTO subarea (nombre, id_area, id_municipio, activo)
        VALUES (:n, :a, :m, TRUE)
        RETURNING id_subarea
    """), {"n": nombre, "a": id_area, "m": id_municipio})
    return r.fetchone()[0]


async def get_tipo_id(conn, codigo, id_municipio=ID_MUNICIPIO):
    return await fetchval(conn,
        "SELECT id_tipo_tramite FROM tipo_tramite WHERE codigo = :c AND id_municipio = :m",
        {"c": codigo, "m": id_municipio})


async def get_version_id(conn, id_tipo_tramite):
    return await fetchval(conn,
        "SELECT id_tipo_tramite_version FROM tipo_tramite_version WHERE id_tipo_tramite = :t ORDER BY version_num DESC LIMIT 1",
        {"t": id_tipo_tramite})


async def get_estado_id(conn, id_version, codigo):
    return await fetchval(conn,
        "SELECT id_tipo_tramite_estado FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND codigo = :c",
        {"v": id_version, "c": codigo})


async def proximo_numero(conn, id_tipo, id_municipio=ID_MUNICIPIO, anio=ANIO):
    r = await conn.execute(text("""
        INSERT INTO tipo_tramite_numerador (id_tipo_tramite, anio, id_municipio, ultimo_numero)
        VALUES (:t, :a, :m, 1)
        ON CONFLICT (id_tipo_tramite, anio, id_municipio)
        DO UPDATE SET ultimo_numero = tipo_tramite_numerador.ultimo_numero + 1,
                      fecha_modificacion = NOW()
        RETURNING ultimo_numero
    """), {"t": id_tipo, "a": anio, "m": id_municipio})
    return r.fetchone()[0]


def fmt_numero(prefijo, sep, incl_mun, incl_anio, cod_mun, anio, num, largo):
    partes = [prefijo]
    if incl_mun:
        partes.append(cod_mun)
    if incl_anio:
        partes.append(str(anio))
    partes.append(str(num).zfill(largo))
    return sep.join(partes)


def ts(dias_atras=0):
    return datetime.now(timezone.utc) - timedelta(days=dias_atras)


# =============================================================================
# 1. Subareas nuevas
# =============================================================================

async def seed_subareas(conn):
    print("  Subáreas del circuito de trámites...")

    # id_area: 1=Gobierno, 22=Servicios Publicos, 15=Gobierno Legal Tecnica, 6=Planeamiento
    id_area_gobierno = await fetchval(conn,
        "SELECT id_area FROM area WHERE LOWER(nombre) LIKE '%gobierno%' AND activo ORDER BY id_area LIMIT 1")
    id_area_servicios = await fetchval(conn,
        "SELECT id_area FROM area WHERE LOWER(nombre) LIKE '%servicios%publicos%' AND activo ORDER BY id_area LIMIT 1")
    id_area_legal = await fetchval(conn,
        "SELECT id_area FROM area WHERE LOWER(nombre) LIKE '%legal%' OR LOWER(nombre) LIKE '%gobierno%' AND activo ORDER BY id_area LIMIT 1")

    fallback_area = id_area_gobierno or 1

    sa_ids = {}
    sa_ids["mesa_entradas"] = await upsert_subarea(conn, "Mesa de Entradas", fallback_area)
    sa_ids["habilitaciones"] = await upsert_subarea(conn, "Habilitaciones Comerciales", id_area_legal or fallback_area)
    sa_ids["bromatologia"] = await upsert_subarea(conn, "Bromatologia e Inspecciones", id_area_servicios or fallback_area)
    sa_ids["obras_particulares"] = await upsert_subarea(conn, "Obras Particulares", id_area_legal or fallback_area)
    sa_ids["legales"] = await upsert_subarea(conn, "Asesoria Legal y Tecnica", id_area_legal or fallback_area)
    sa_ids["rrhh"] = await upsert_subarea(conn, "Recursos Humanos", fallback_area)
    sa_ids["espacios_verdes"] = await upsert_subarea(conn, "Espacios Verdes", id_area_servicios or fallback_area)

    print(f"    Mesa de Entradas: {sa_ids['mesa_entradas']}")
    print(f"    Habilitaciones: {sa_ids['habilitaciones']}")
    print(f"    Bromatología: {sa_ids['bromatologia']}")
    print(f"    Obras Particulares: {sa_ids['obras_particulares']}")
    print(f"    Legales: {sa_ids['legales']}")
    print(f"    RRHH: {sa_ids['rrhh']}")
    print(f"    Espacios Verdes: {sa_ids['espacios_verdes']}")

    # Asegurar codigo_corto en municipio
    await conn.execute(text(
        "UPDATE municipios SET codigo_corto = 'LPL' WHERE id_municipio = :m AND (codigo_corto IS NULL OR codigo_corto = '')"
    ), {"m": ID_MUNICIPIO})

    return sa_ids


# =============================================================================
# 2. Tipos de tramite + versiones + campos + estados + transiciones + docs
# =============================================================================

async def seed_tipo(conn, codigo, nombre, prefijo, iniciadores, permite_rep, icono, color,
                    campos, estados, transiciones, docs):
    """Crea o actualiza un tipo de tramite con toda su version publicada v1."""

    id_tipo = await get_tipo_id(conn, codigo)
    if not id_tipo:
        r = await conn.execute(text("""
            INSERT INTO tipo_tramite (
                codigo, nombre, prefijo, iniciadores_permitidos, permite_representante,
                icono, color, id_municipio, activo
            ) VALUES (:c, :n, :p, :i, :r, :ico, :col, :m, TRUE)
            RETURNING id_tipo_tramite
        """), {
            "c": codigo, "n": nombre, "p": prefijo,
            "i": iniciadores,
            "r": permite_rep, "ico": icono, "col": color, "m": ID_MUNICIPIO
        })
        id_tipo = r.fetchone()[0]
        print(f"    Creado tipo: {codigo} (id={id_tipo})")
    else:
        print(f"    Ya existe tipo: {codigo} (id={id_tipo})")

    # Version
    id_ver = await fetchval(conn,
        "SELECT id_tipo_tramite_version FROM tipo_tramite_version WHERE id_tipo_tramite = :t AND version_num = 1",
        {"t": id_tipo})
    if not id_ver:
        r = await conn.execute(text("""
            INSERT INTO tipo_tramite_version (
                id_tipo_tramite, version_num, estado, publicada_en, id_municipio, activo
            ) VALUES (:t, 1, 'publicado', NOW(), :m, TRUE)
            RETURNING id_tipo_tramite_version
        """), {"t": id_tipo, "m": ID_MUNICIPIO})
        id_ver = r.fetchone()[0]

    # Campos
    for campo in campos:
        existe = await fetchval(conn,
            "SELECT id_tipo_tramite_campo FROM tipo_tramite_campo WHERE id_tipo_tramite_version = :v AND nombre_interno = :n",
            {"v": id_ver, "n": campo["nombre_interno"]})
        opciones_raw = campo.get("opciones")
        opciones_str = json.dumps(opciones_raw) if opciones_raw is not None else None
        if not existe:
            await conn.execute(text("""
                INSERT INTO tipo_tramite_campo (
                    id_tipo_tramite_version, nombre_interno, etiqueta, tipo_dato,
                    obligatorio, orden, opciones_jsonb, ayuda, id_municipio, activo
                ) VALUES (:v, :ni, :et, :td, :ob, :or, CAST(:op AS jsonb), :ay, :m, TRUE)
            """), {
                "v": id_ver, "ni": campo["nombre_interno"], "et": campo["etiqueta"],
                "td": campo["tipo_dato"], "ob": campo.get("obligatorio", True),
                "or": campo["orden"],
                "op": opciones_str,
                "ay": campo.get("ayuda"),
                "m": ID_MUNICIPIO
            })
        else:
            # Actualizar tipo_dato (puede haber cambiado, ej: texto -> direccion)
            await conn.execute(text(
                "UPDATE tipo_tramite_campo SET tipo_dato = :td WHERE id_tipo_tramite_campo = :id"
            ), {"td": campo["tipo_dato"], "id": existe})

    # Estados: guardar mapa codigo->id
    estado_ids = {}
    for est in estados:
        eid = await fetchval(conn,
            "SELECT id_tipo_tramite_estado FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND codigo = :c",
            {"v": id_ver, "c": est["codigo"]})
        if not eid:
            r = await conn.execute(text("""
                INSERT INTO tipo_tramite_estado (
                    id_tipo_tramite_version, codigo, etiqueta, descripcion,
                    color, orden, es_inicial, es_final,
                    oculto_para_iniciador, id_municipio, activo
                ) VALUES (:v, :c, :e, :d, :col, :o, :ini, :fin, :oculto, :m, TRUE)
                RETURNING id_tipo_tramite_estado
            """), {
                "v": id_ver, "c": est["codigo"], "e": est["etiqueta"],
                "d": est.get("descripcion"), "col": est.get("color", "#6b7280"),
                "o": est["orden"], "ini": est.get("inicial", False),
                "fin": est.get("final", False),
                "oculto": est.get("oculto", False), "m": ID_MUNICIPIO
            })
            eid = r.fetchone()[0]
        estado_ids[est["codigo"]] = eid

    # Transiciones
    for tr in transiciones:
        oid = estado_ids.get(tr["origen"])
        did = estado_ids.get(tr["destino"])
        if not oid or not did:
            continue
        existe = await fetchval(conn,
            """SELECT 1 FROM tipo_tramite_transicion
               WHERE id_tipo_tramite_version = :v
                 AND id_estado_origen = :eo AND id_estado_destino = :ed""",
            {"v": id_ver, "eo": oid, "ed": did})
        if not existe:
            await conn.execute(text("""
                INSERT INTO tipo_tramite_transicion (
                    id_tipo_tramite_version, id_estado_origen, id_estado_destino,
                    etiqueta_accion, orden, quien_puede_jsonb,
                    requiere_comentario, requiere_adjunto, destino_automatico_jsonb,
                    id_municipio, activo
                ) VALUES (:v, :eo, :ed, :ea, :o, CAST(:qp AS jsonb), :rc, :ra, CAST(:da AS jsonb), :m, TRUE)
            """), {
                "v": id_ver, "eo": oid, "ed": did,
                "ea": tr["etiqueta"], "o": tr.get("orden", 0),
                "qp": json.dumps(tr.get("quien_puede", {})),
                "rc": tr.get("req_comentario", False),
                "ra": tr.get("req_adjunto", False),
                "da": json.dumps(tr["destino_auto"]) if tr.get("destino_auto") else None,
                "m": ID_MUNICIPIO
            })

    # Documentos requeridos
    for doc in docs:
        existe = await fetchval(conn,
            "SELECT 1 FROM tipo_tramite_documento_requerido WHERE id_tipo_tramite_version = :v AND nombre = :n",
            {"v": id_ver, "n": doc["nombre"]})
        if not existe:
            est_doc_id = estado_ids.get(doc.get("estado")) if doc.get("estado") else None
            await conn.execute(text("""
                INSERT INTO tipo_tramite_documento_requerido (
                    id_tipo_tramite_version, id_tipo_tramite_estado, nombre,
                    obligatorio, formatos_permitidos, requiere_firma,
                    aporta_quien, orden, id_municipio, activo
                ) VALUES (:v, :est, :n, :ob, :fmt, :rf, :aq, :o, :m, TRUE)
            """), {
                "v": id_ver, "est": est_doc_id, "n": doc["nombre"],
                "ob": doc.get("obligatorio", True),
                "fmt": doc.get("formatos", ["pdf", "jpg", "png"]),
                "rf": doc.get("requiere_firma", False),
                "aq": doc.get("aporta", "iniciador"),
                "o": doc.get("orden", 0), "m": ID_MUNICIPIO
            })

    # Vincular version publicada al tipo
    await conn.execute(text(
        "UPDATE tipo_tramite SET id_version_publicada = :v WHERE id_tipo_tramite = :t"),
        {"v": id_ver, "t": id_tipo})

    return id_tipo, id_ver, estado_ids


async def seed_tipos(conn, sa):
    """Siembra los 9 tipos de tramite."""
    tipos = {}

    # 1. poda-arbol
    tipos["poda-arbol"] = await seed_tipo(conn,
        "poda-arbol", "Solicitud de poda de arbol", "POD",
        ["ciudadano"], False, "trees", "#22c55e",
        campos=[
            {"nombre_interno": "direccion_arbol", "etiqueta": "Direccion del arbol", "tipo_dato": "direccion", "obligatorio": True, "orden": 1},
            {"nombre_interno": "especie_aproximada", "etiqueta": "Especie aproximada", "tipo_dato": "seleccion", "obligatorio": False, "orden": 2,
             "opciones": {"opciones": ["nativa", "exotica", "no_se"]}},
            {"nombre_interno": "motivo", "etiqueta": "Motivo del pedido", "tipo_dato": "texto_largo", "obligatorio": True, "orden": 3},
        ],
        estados=[
            {"codigo": "iniciado", "etiqueta": "Iniciado", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "en_evaluacion", "etiqueta": "En evaluacion", "color": "#f59e0b", "orden": 2},
            {"codigo": "aprobada", "etiqueta": "Aprobada", "color": "#22c55e", "orden": 3},
            {"codigo": "rechazada", "etiqueta": "Rechazada", "color": "#ef4444", "orden": 4},
            {"codigo": "archivado", "etiqueta": "Archivado", "color": "#6b7280", "orden": 5, "final": True},
        ],
        transiciones=[
            {"origen": "iniciado", "destino": "en_evaluacion", "etiqueta": "Derivar a Espacios Verdes",
             "quien_puede": {"subareas": [sa["mesa_entradas"]]},
             "destino_auto": {"tipo": "subarea", "id": sa["espacios_verdes"], "nombre": "Espacios Verdes"}},
            {"origen": "en_evaluacion", "destino": "aprobada", "etiqueta": "Aprobar",
             "req_comentario": True, "quien_puede": {"subareas": [sa["espacios_verdes"]]}},
            {"origen": "en_evaluacion", "destino": "rechazada", "etiqueta": "Rechazar",
             "req_comentario": True, "quien_puede": {"subareas": [sa["espacios_verdes"]]}},
            {"origen": "aprobada", "destino": "archivado", "etiqueta": "Archivar",
             "quien_puede": {"subareas": [sa["espacios_verdes"]]}},
            {"origen": "rechazada", "destino": "archivado", "etiqueta": "Archivar",
             "quien_puede": {"subareas": [sa["espacios_verdes"]]}},
        ],
        docs=[
            {"nombre": "Foto del arbol", "obligatorio": True, "aporta": "iniciador",
             "estado": "iniciado", "formatos": ["jpg", "png", "pdf"]},
        ]
    )

    # 2. pedido-informe
    tipos["pedido-informe"] = await seed_tipo(conn,
        "pedido-informe", "Pedido de informe a otra area", "INF",
        ["area_interna"], False, "file-text", "#6366f1",
        campos=[
            {"nombre_interno": "asunto_informe", "etiqueta": "Asunto del informe", "tipo_dato": "texto", "obligatorio": True, "orden": 1},
            {"nombre_interno": "detalle", "etiqueta": "Detalle", "tipo_dato": "texto_largo", "obligatorio": True, "orden": 2},
            {"nombre_interno": "subarea_destinataria", "etiqueta": "Subarea destinataria", "tipo_dato": "subarea", "obligatorio": True, "orden": 3},
        ],
        estados=[
            {"codigo": "solicitado", "etiqueta": "Solicitado", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "respondiendo", "etiqueta": "Respondiendo", "color": "#f59e0b", "orden": 2},
            {"codigo": "respondido", "etiqueta": "Respondido", "color": "#22c55e", "orden": 3},
            {"codigo": "archivado", "etiqueta": "Archivado", "color": "#6b7280", "orden": 4, "final": True},
        ],
        transiciones=[
            {"origen": "solicitado", "destino": "respondiendo", "etiqueta": "Tomar y responder"},
            {"origen": "respondiendo", "destino": "respondido", "etiqueta": "Enviar respuesta", "req_comentario": True},
            {"origen": "respondido", "destino": "archivado", "etiqueta": "Archivar"},
        ],
        docs=[
            {"nombre": "Informe respondido", "obligatorio": True, "aporta": "oficina_actual",
             "estado": "respondiendo", "requiere_firma": True},
        ]
    )

    # 3. licencia-ordinaria
    tipos["licencia-ordinaria"] = await seed_tipo(conn,
        "licencia-ordinaria", "Licencia ordinaria de personal", "LIC",
        ["area_interna"], False, "calendar-days", "#8b5cf6",
        campos=[
            {"nombre_interno": "agente_solicitante", "etiqueta": "Agente solicitante", "tipo_dato": "agente", "obligatorio": True, "orden": 1},
            {"nombre_interno": "fecha_desde", "etiqueta": "Fecha desde", "tipo_dato": "fecha", "obligatorio": True, "orden": 2},
            {"nombre_interno": "fecha_hasta", "etiqueta": "Fecha hasta", "tipo_dato": "fecha", "obligatorio": True, "orden": 3},
            {"nombre_interno": "motivo", "etiqueta": "Motivo (opcional)", "tipo_dato": "texto_largo", "obligatorio": False, "orden": 4},
        ],
        estados=[
            {"codigo": "solicitada", "etiqueta": "Solicitada", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "aprobada_jefe", "etiqueta": "Aprobada por jefe", "color": "#a3e635", "orden": 2},
            {"codigo": "aprobada_rrhh", "etiqueta": "Aprobada por RRHH", "color": "#22c55e", "orden": 3},
            {"codigo": "notificada", "etiqueta": "Notificada", "color": "#10b981", "orden": 4, "final": True},
            {"codigo": "rechazada", "etiqueta": "Rechazada", "color": "#ef4444", "orden": 5, "final": True},
        ],
        transiciones=[
            {"origen": "solicitada", "destino": "aprobada_jefe", "etiqueta": "Aprobar (Jefe directo)", "req_comentario": True},
            {"origen": "aprobada_jefe", "destino": "aprobada_rrhh", "etiqueta": "Aprobar (RRHH)",
             "destino_auto": {"tipo": "subarea", "id": sa["rrhh"], "nombre": "Recursos Humanos"}},
            {"origen": "aprobada_rrhh", "destino": "notificada", "etiqueta": "Notificar al agente"},
            {"origen": "solicitada", "destino": "rechazada", "etiqueta": "Rechazar", "req_comentario": True},
            {"origen": "aprobada_jefe", "destino": "rechazada", "etiqueta": "Rechazar en RRHH", "req_comentario": True},
        ],
        docs=[]
    )

    # 4. habilitacion-comercial
    tipos["habilitacion-comercial"] = await seed_tipo(conn,
        "habilitacion-comercial", "Habilitacion comercial", "HAB",
        ["empresa"], True, "store", "#f59e0b",
        campos=[
            {"nombre_interno": "rubro", "etiqueta": "Rubro", "tipo_dato": "seleccion", "obligatorio": True, "orden": 1,
             "opciones": {"opciones": ["gastronomico", "comercial", "industrial", "servicios", "otro"]}},
            {"nombre_interno": "direccion_local", "etiqueta": "Direccion del local", "tipo_dato": "direccion", "obligatorio": True, "orden": 2},
            {"nombre_interno": "superficie_m2", "etiqueta": "Superficie (m2)", "tipo_dato": "decimal", "obligatorio": True, "orden": 3},
            {"nombre_interno": "horario_atencion", "etiqueta": "Horario de atencion", "tipo_dato": "texto", "obligatorio": True, "orden": 4},
            {"nombre_interno": "tiene_cartel", "etiqueta": "Tiene cartel publicitario", "tipo_dato": "booleano", "obligatorio": False, "orden": 5},
        ],
        estados=[
            {"codigo": "iniciado", "etiqueta": "Iniciado", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "revision_documental", "etiqueta": "Revision documental", "color": "#f59e0b", "orden": 2},
            {"codigo": "subsanacion", "etiqueta": "Subsanacion pendiente", "color": "#fb923c", "orden": 3},
            {"codigo": "inspeccion", "etiqueta": "En inspeccion", "color": "#a78bfa", "orden": 4},
            {"codigo": "aprobada", "etiqueta": "Aprobada", "color": "#22c55e", "orden": 5},
            {"codigo": "rechazada", "etiqueta": "Rechazada", "color": "#ef4444", "orden": 6, "final": True},
            {"codigo": "emitida", "etiqueta": "Habilitacion emitida", "color": "#10b981", "orden": 7, "final": True},
        ],
        transiciones=[
            {"origen": "iniciado", "destino": "revision_documental", "etiqueta": "Derivar a Habilitaciones",
             "destino_auto": {"tipo": "subarea", "id": sa["habilitaciones"], "nombre": "Habilitaciones Comerciales"}},
            {"origen": "revision_documental", "destino": "subsanacion", "etiqueta": "Pedir subsanacion",
             "req_comentario": True},
            {"origen": "subsanacion", "destino": "revision_documental", "etiqueta": "Reenviar corregido",
             "req_adjunto": True, "quien_puede": {"iniciador": True}},
            {"origen": "revision_documental", "destino": "inspeccion", "etiqueta": "Programar inspeccion",
             "destino_auto": {"tipo": "subarea", "id": sa["bromatologia"], "nombre": "Bromatologia e Inspecciones"}},
            {"origen": "inspeccion", "destino": "aprobada", "etiqueta": "Inspeccion OK", "req_comentario": True},
            {"origen": "inspeccion", "destino": "rechazada", "etiqueta": "Inspeccion rechazada", "req_comentario": True},
            {"origen": "aprobada", "destino": "emitida", "etiqueta": "Emitir habilitacion", "req_adjunto": True},
        ],
        docs=[
            {"nombre": "Contrato de locacion", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado"},
            {"nombre": "Plano del local", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado"},
            {"nombre": "Libreta sanitaria", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado"},
            {"nombre": "Certificado de bomberos", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado"},
            {"nombre": "Acta de inspeccion", "obligatorio": True, "aporta": "oficina_actual", "estado": "inspeccion", "requiere_firma": True},
            {"nombre": "Certificado de habilitacion", "obligatorio": True, "aporta": "oficina_actual", "estado": "aprobada", "requiere_firma": True},
        ]
    )

    # 5. cambio-domicilio-comercial
    tipos["cambio-domicilio-comercial"] = await seed_tipo(conn,
        "cambio-domicilio-comercial", "Cambio de domicilio comercial", "CDC",
        ["empresa"], True, "map-pin", "#14b8a6",
        campos=[
            {"nombre_interno": "direccion_anterior", "etiqueta": "Direccion anterior", "tipo_dato": "direccion", "obligatorio": True, "orden": 1},
            {"nombre_interno": "direccion_nueva", "etiqueta": "Direccion nueva", "tipo_dato": "direccion", "obligatorio": True, "orden": 2},
            {"nombre_interno": "fecha_efectiva", "etiqueta": "Fecha efectiva del cambio", "tipo_dato": "fecha", "obligatorio": True, "orden": 3},
            {"nombre_interno": "nro_habilitacion_actual", "etiqueta": "N° de habilitacion actual", "tipo_dato": "texto", "obligatorio": True, "orden": 4},
        ],
        estados=[
            {"codigo": "iniciado", "etiqueta": "Iniciado", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "en_revision", "etiqueta": "En revision", "color": "#f59e0b", "orden": 2},
            {"codigo": "aprobada", "etiqueta": "Aprobada", "color": "#22c55e", "orden": 3},
            {"codigo": "rechazada", "etiqueta": "Rechazada", "color": "#ef4444", "orden": 4, "final": True},
            {"codigo": "archivado", "etiqueta": "Archivado", "color": "#6b7280", "orden": 5, "final": True},
        ],
        transiciones=[
            {"origen": "iniciado", "destino": "en_revision", "etiqueta": "Derivar a Habilitaciones",
             "destino_auto": {"tipo": "subarea", "id": sa["habilitaciones"], "nombre": "Habilitaciones Comerciales"}},
            {"origen": "en_revision", "destino": "aprobada", "etiqueta": "Aprobar cambio", "req_comentario": True},
            {"origen": "en_revision", "destino": "rechazada", "etiqueta": "Rechazar", "req_comentario": True},
            {"origen": "aprobada", "destino": "archivado", "etiqueta": "Archivar"},
            {"origen": "rechazada", "destino": "archivado", "etiqueta": "Archivar"},
        ],
        docs=[
            {"nombre": "Constancia de habilitacion actual", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado"},
            {"nombre": "Constancia del nuevo domicilio", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado"},
        ]
    )

    # 6. transferencia-habilitacion
    tipos["transferencia-habilitacion"] = await seed_tipo(conn,
        "transferencia-habilitacion", "Transferencia de habilitacion comercial", "THC",
        ["empresa"], True, "arrow-right-left", "#0ea5e9",
        campos=[
            {"nombre_interno": "nro_habilitacion", "etiqueta": "N° de habilitacion a transferir", "tipo_dato": "texto", "obligatorio": True, "orden": 1},
            {"nombre_interno": "cuit_titular_anterior", "etiqueta": "CUIT titular anterior", "tipo_dato": "texto", "obligatorio": True, "orden": 2},
            {"nombre_interno": "cuit_titular_nuevo", "etiqueta": "CUIT titular nuevo", "tipo_dato": "texto", "obligatorio": True, "orden": 3},
            {"nombre_interno": "fecha_efectiva", "etiqueta": "Fecha efectiva", "tipo_dato": "fecha", "obligatorio": True, "orden": 4},
        ],
        estados=[
            {"codigo": "iniciado", "etiqueta": "Iniciado", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "validando_anterior", "etiqueta": "Validando titular anterior", "color": "#f59e0b", "orden": 2},
            {"codigo": "validando_nuevo", "etiqueta": "Validando nuevo titular", "color": "#fb923c", "orden": 3},
            {"codigo": "aprobada", "etiqueta": "Aprobada", "color": "#22c55e", "orden": 4},
            {"codigo": "rechazada", "etiqueta": "Rechazada", "color": "#ef4444", "orden": 5, "final": True},
            {"codigo": "archivado", "etiqueta": "Archivado", "color": "#6b7280", "orden": 6, "final": True},
        ],
        transiciones=[
            {"origen": "iniciado", "destino": "validando_anterior", "etiqueta": "Iniciar validacion"},
            {"origen": "validando_anterior", "destino": "validando_nuevo", "etiqueta": "Titular anterior OK", "req_comentario": True},
            {"origen": "validando_nuevo", "destino": "aprobada", "etiqueta": "Nuevo titular OK", "req_comentario": True},
            {"origen": "validando_anterior", "destino": "rechazada", "etiqueta": "Rechazar por deuda", "req_comentario": True},
            {"origen": "validando_nuevo", "destino": "rechazada", "etiqueta": "Rechazar nuevo titular", "req_comentario": True},
            {"origen": "aprobada", "destino": "archivado", "etiqueta": "Archivar"},
        ],
        docs=[
            {"nombre": "Boleto de transferencia", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado", "requiere_firma": True},
            {"nombre": "Libre deuda titular anterior", "obligatorio": True, "aporta": "oficina_actual", "estado": "validando_anterior"},
        ]
    )

    # 7. inspeccion-bromatologica
    tipos["inspeccion-bromatologica"] = await seed_tipo(conn,
        "inspeccion-bromatologica", "Solicitud de inspeccion bromatologica", "BRO",
        ["empresa"], True, "microscope", "#ef4444",
        campos=[
            {"nombre_interno": "rubro_solicitud", "etiqueta": "Rubro", "tipo_dato": "seleccion", "obligatorio": True, "orden": 1,
             "opciones": {"opciones": ["gastronomico", "panaderia", "carniceria", "verduleria", "otro"]}},
            {"nombre_interno": "motivo", "etiqueta": "Motivo", "tipo_dato": "texto_largo", "obligatorio": True, "orden": 2},
            {"nombre_interno": "fecha_solicitada", "etiqueta": "Fecha preferida", "tipo_dato": "fecha", "obligatorio": False, "orden": 3},
        ],
        estados=[
            {"codigo": "solicitada", "etiqueta": "Solicitada", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "programada", "etiqueta": "Programada", "color": "#f59e0b", "orden": 2},
            {"codigo": "realizada", "etiqueta": "Realizada", "color": "#a78bfa", "orden": 3},
            {"codigo": "aprobada", "etiqueta": "Aprobada", "color": "#22c55e", "orden": 4, "final": True},
            {"codigo": "rechazada", "etiqueta": "Rechazada", "color": "#ef4444", "orden": 5, "final": True},
        ],
        transiciones=[
            {"origen": "solicitada", "destino": "programada", "etiqueta": "Programar inspeccion"},
            {"origen": "programada", "destino": "realizada", "etiqueta": "Marcar como realizada"},
            {"origen": "realizada", "destino": "aprobada", "etiqueta": "Aprobar", "req_comentario": True},
            {"origen": "realizada", "destino": "rechazada", "etiqueta": "Rechazar", "req_comentario": True},
        ],
        docs=[
            {"nombre": "Acta de inspeccion bromatologica", "obligatorio": True, "aporta": "oficina_actual",
             "estado": "realizada", "requiere_firma": True},
        ]
    )

    # 8. cartel-publicitario
    tipos["cartel-publicitario"] = await seed_tipo(conn,
        "cartel-publicitario", "Instalacion de cartel publicitario", "CAR",
        ["empresa"], True, "megaphone", "#f97316",
        campos=[
            {"nombre_interno": "direccion_local", "etiqueta": "Direccion del local", "tipo_dato": "direccion", "obligatorio": True, "orden": 1},
            {"nombre_interno": "dimensiones", "etiqueta": "Dimensiones del cartel", "tipo_dato": "texto", "obligatorio": True, "orden": 2},
            {"nombre_interno": "tipo_cartel", "etiqueta": "Tipo de cartel", "tipo_dato": "seleccion", "obligatorio": True, "orden": 3,
             "opciones": {"opciones": ["frontal", "marquesina", "saliente", "luminoso"]}},
            {"nombre_interno": "monto_tasa", "etiqueta": "Monto de la tasa", "tipo_dato": "moneda", "obligatorio": True, "orden": 4},
        ],
        estados=[
            {"codigo": "iniciado", "etiqueta": "Iniciado", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "revision_tecnica", "etiqueta": "Revision tecnica", "color": "#f59e0b", "orden": 2},
            {"codigo": "pago_pendiente", "etiqueta": "Pago pendiente", "color": "#fb923c", "orden": 3},
            {"codigo": "instalado", "etiqueta": "Instalado", "color": "#22c55e", "orden": 4, "final": True},
            {"codigo": "rechazado", "etiqueta": "Rechazado", "color": "#ef4444", "orden": 5, "final": True},
        ],
        transiciones=[
            {"origen": "iniciado", "destino": "revision_tecnica", "etiqueta": "Derivar a Obras Particulares",
             "destino_auto": {"tipo": "subarea", "id": sa["obras_particulares"], "nombre": "Obras Particulares"}},
            {"origen": "revision_tecnica", "destino": "pago_pendiente", "etiqueta": "Aprobar tecnicamente"},
            {"origen": "pago_pendiente", "destino": "instalado", "etiqueta": "Confirmar pago e instalacion", "req_adjunto": True},
            {"origen": "revision_tecnica", "destino": "rechazado", "etiqueta": "Rechazar", "req_comentario": True},
        ],
        docs=[
            {"nombre": "Plano del cartel", "obligatorio": True, "aporta": "iniciador", "estado": "iniciado"},
            {"nombre": "Comprobante de pago de tasa", "obligatorio": True, "aporta": "iniciador", "estado": "pago_pendiente"},
        ]
    )

    # 9. recurso-administrativo
    tipos["recurso-administrativo"] = await seed_tipo(conn,
        "recurso-administrativo", "Recurso administrativo", "REA",
        ["ciudadano", "empresa"], True, "scale", "#7c3aed",
        campos=[
            {"nombre_interno": "numero_acto_recurrido", "etiqueta": "N° del acto recurrido", "tipo_dato": "texto", "obligatorio": True, "orden": 1},
            {"nombre_interno": "tipo_acto", "etiqueta": "Tipo de acto", "tipo_dato": "seleccion", "obligatorio": True, "orden": 2,
             "opciones": {"opciones": ["resolucion", "disposicion", "decreto", "multa", "otro"]}},
            {"nombre_interno": "fecha_notificacion", "etiqueta": "Fecha de notificacion", "tipo_dato": "fecha", "obligatorio": True, "orden": 3},
            {"nombre_interno": "fundamentos", "etiqueta": "Fundamentos", "tipo_dato": "texto_largo", "obligatorio": True, "orden": 4},
            {"nombre_interno": "pretension", "etiqueta": "Pretension", "tipo_dato": "texto_largo", "obligatorio": True, "orden": 5},
        ],
        estados=[
            {"codigo": "presentado", "etiqueta": "Presentado", "color": "#3b82f6", "orden": 1, "inicial": True},
            {"codigo": "admitido", "etiqueta": "Admitido", "color": "#f59e0b", "orden": 2},
            {"codigo": "inadmisible", "etiqueta": "Inadmisible", "color": "#ef4444", "orden": 3, "final": True},
            {"codigo": "resolucion_dictada", "etiqueta": "Resolucion dictada", "color": "#22c55e", "orden": 4, "final": True},
            {"codigo": "archivado", "etiqueta": "Archivado", "color": "#6b7280", "orden": 5, "final": True},
        ],
        transiciones=[
            {"origen": "presentado", "destino": "admitido", "etiqueta": "Admitir formalmente",
             "req_comentario": True, "quien_puede": {"subareas": [sa["legales"]]}},
            {"origen": "presentado", "destino": "inadmisible", "etiqueta": "Declarar inadmisible",
             "req_comentario": True, "req_adjunto": True},
            {"origen": "admitido", "destino": "resolucion_dictada", "etiqueta": "Dictar resolucion",
             "req_adjunto": True},
            {"origen": "resolucion_dictada", "destino": "archivado", "etiqueta": "Archivar"},
        ],
        docs=[
            {"nombre": "Copia del acto recurrido", "obligatorio": True, "aporta": "iniciador", "estado": "presentado"},
            {"nombre": "Resolucion del recurso", "obligatorio": True, "aporta": "oficina_actual",
             "estado": "admitido", "requiere_firma": True},
        ]
    )

    print(f"    9 tipos de tramite listos.")
    return tipos


# =============================================================================
# 3. Tramites instanciados
# =============================================================================

def hash_dummy():
    import hashlib
    import uuid
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


async def crear_tramite(conn, tipo_dict, estado_codigo, asunto, iniciador_tipo,
                        id_iniciador, id_destinatario_subarea, id_agente, datos_jsonb,
                        id_representante=None, dias_atras=5):
    """Crea un tramite con su numeracion y devuelve (id_tramite, numero)."""
    id_tipo, id_ver, estado_ids = tipo_dict

    id_estado = estado_ids[estado_codigo]
    num = await proximo_numero(conn, id_tipo)

    tipo_row = await fetchone(conn,
        "SELECT prefijo, separador, incluye_municipio, incluye_anio, largo_correlativo FROM tipo_tramite WHERE id_tipo_tramite = :t",
        {"t": id_tipo})
    cod_mun = await fetchval(conn, "SELECT COALESCE(codigo_corto, 'MUN') FROM municipios WHERE id_municipio = :m", {"m": ID_MUNICIPIO})

    numero = fmt_numero(
        tipo_row.prefijo, tipo_row.separador,
        tipo_row.incluye_municipio, tipo_row.incluye_anio,
        cod_mun, ANIO, num, tipo_row.largo_correlativo
    )

    # Verificar si ya existe
    existe = await fetchval(conn, "SELECT id_tramite FROM tramite WHERE numero_expediente = :n", {"n": numero})
    if existe:
        return existe, numero

    ts_alta = ts(dias_atras)

    # Build iniciador columns
    ck = {"ciudadano": {"id_ciudadano_iniciador": id_iniciador},
          "empresa": {"id_empresa_iniciadora": id_iniciador},
          "area_interna": {"id_subarea_iniciadora": id_iniciador}}
    col, val = list(ck[iniciador_tipo].items())[0]

    r = await conn.execute(text(f"""
        INSERT INTO tramite (
            numero_expediente, id_tipo_tramite_version, asunto, datos_jsonb,
            iniciador_tipo, {col}, id_ciudadano_representante, id_agente_iniciador,
            id_tipo_tramite_estado_actual, fecha_entrada_estado_actual,
            destinatario_actual_tipo, id_subarea_actual,
            activo, id_municipio, fecha_alta, fecha_modificacion
        ) VALUES (
            :num, :ver, :asunto, CAST(:datos AS jsonb),
            :it, :iv, :rep, :ag,
            :est, :feca,
            'subarea', :dest_sa,
            TRUE, :m, :fa, :fa
        ) RETURNING id_tramite
    """), {
        "num": numero, "ver": id_ver, "asunto": asunto,
        "datos": json.dumps(datos_jsonb),
        "it": iniciador_tipo, "iv": val, "rep": id_representante, "ag": id_agente,
        "est": id_estado, "feca": ts_alta,
        "dest_sa": id_destinatario_subarea, "m": ID_MUNICIPIO, "fa": ts_alta,
    })
    id_tramite = r.fetchone()[0]
    return id_tramite, numero


async def agregar_movimiento(conn, id_tramite, orden, tipo, id_agente, comentario=None,
                              id_estado_origen=None, id_estado_destino=None,
                              origen_jsonb=None, destino_jsonb=None, dias_atras=4):
    await conn.execute(text("""
        INSERT INTO tramite_movimiento (
            id_tramite, orden_secuencial, tipo, id_agente,
            id_estado_origen, id_estado_destino,
            origen_jsonb, destino_jsonb, comentario,
            activo, id_municipio, fecha_alta, fecha_modificacion
        ) VALUES (
            :t, :o, :ti, :ag,
            :eo, :ed,
            CAST(:oj AS jsonb), CAST(:dj AS jsonb), :c,
            TRUE, :m, :fa, :fa
        )
        ON CONFLICT (id_tramite, orden_secuencial) DO NOTHING
    """), {
        "t": id_tramite, "o": orden, "ti": tipo, "ag": id_agente,
        "eo": id_estado_origen, "ed": id_estado_destino,
        "oj": json.dumps(origen_jsonb) if origen_jsonb else None,
        "dj": json.dumps(destino_jsonb) if destino_jsonb else None,
        "c": comentario, "m": ID_MUNICIPIO,
        "fa": ts(dias_atras),
    })


async def agregar_documento(conn, id_tramite, nombre, mime="application/pdf",
                             id_agente=1, requiere_firma=False, estado_firma="no_requiere",
                             posicion=1):
    existe = await fetchval(conn,
        "SELECT id_tramite_documento FROM tramite_documento WHERE id_tramite = :t AND nombre = :n",
        {"t": id_tramite, "n": nombre})
    if existe:
        return existe

    r = await conn.execute(text("""
        INSERT INTO tramite_documento (
            id_tramite, nombre, nombre_archivo_original, storage_path,
            mime_type, tamano_bytes, hash_sha256,
            requiere_firma, estado_firma, posicion_orden, id_agente_subio,
            activo, id_municipio
        ) VALUES (
            :t, :n, :nao, :sp, :mt, :tb, :hs,
            :rf, :ef, :po, :ag,
            TRUE, :m
        ) RETURNING id_tramite_documento
    """), {
        "t": id_tramite, "n": nombre,
        "nao": nombre.lower().replace(" ", "-") + (".pdf" if "pdf" in mime else ".jpg"),
        "sp": f"tramites/{ANIO}/placeholder/{nombre.lower().replace(' ', '-')}.pdf",
        "mt": mime, "tb": 150000 + (posicion * 50000), "hs": hash_dummy(),
        "rf": requiere_firma, "ef": estado_firma, "po": posicion,
        "ag": id_agente, "m": ID_MUNICIPIO,
    })
    return r.fetchone()[0]


async def agregar_firma(conn, id_doc, id_subarea, estado="pendiente", orden=1):
    existe = await fetchval(conn,
        "SELECT 1 FROM tramite_firma WHERE id_tramite_documento = :d AND id_subarea_asignada = :s",
        {"d": id_doc, "s": id_subarea})
    if not existe:
        await conn.execute(text("""
            INSERT INTO tramite_firma (
                id_tramite_documento, rol_intervencion, orden,
                id_subarea_asignada, estado, activo, id_municipio
            ) VALUES (:d, 'firma', :o, :s, :e, TRUE, :m)
        """), {"d": id_doc, "o": orden, "s": id_subarea, "e": estado, "m": ID_MUNICIPIO})


async def seed_tramites_instancias(conn, sa, tipos, cids, eids, rep_eid):
    """Crea los ~20 tramites demo con movimientos, documentos y firmas."""
    existing = await fetchval(conn, "SELECT COUNT(*) FROM tramite WHERE activo = TRUE")
    if existing and existing >= 20:
        print(f"  Ya existen {existing} tramites demo, salteo creacion.")
        return
    print("  Tramites instanciados...")

    id_ag = 1  # agente admin para todos los movimientos demo

    # ---- poda-arbol (4 tramites) ----
    t_poda = tipos["poda-arbol"]
    eid_poda = t_poda[2]

    # 1: iniciado
    tid, num = await crear_tramite(conn, t_poda, "iniciado",
        "Poda del fresno frente a Mitre 1234", "ciudadano",
        cids[0], sa["mesa_entradas"], id_ag,
        {"direccion_arbol": "Mitre 1234", "especie_aproximada": "exotica", "motivo": "Ramas sobre cables"},
        dias_atras=2)
    await agregar_movimiento(conn, tid, 1, "creacion", id_ag, dias_atras=2)
    await agregar_movimiento(conn, tid, 2, "numeracion", id_ag, comentario=num, dias_atras=2)
    print(f"    {num} (poda/iniciado)")

    # 2: en_evaluacion
    tid2, num2 = await crear_tramite(conn, t_poda, "en_evaluacion",
        "Poda jacaranda Plaza San Martin", "ciudadano",
        cids[1], sa["espacios_verdes"], id_ag,
        {"direccion_arbol": "Plaza San Martin", "motivo": "Exceso de crecimiento"},
        dias_atras=7)
    await agregar_movimiento(conn, tid2, 1, "creacion", id_ag, dias_atras=7)
    await agregar_movimiento(conn, tid2, 2, "numeracion", id_ag, comentario=num2, dias_atras=7)
    await agregar_movimiento(conn, tid2, 3, "pase", id_ag,
        id_estado_origen=eid_poda.get("iniciado"), id_estado_destino=eid_poda.get("en_evaluacion"),
        comentario="Derivado a Espacios Verdes", dias_atras=5)
    print(f"    {num2} (poda/en_evaluacion)")

    # 3: aprobada
    tid3, num3 = await crear_tramite(conn, t_poda, "aprobada",
        "Poda paraiso calle Belgrano", "ciudadano",
        cids[2], sa["espacios_verdes"], id_ag,
        {"direccion_arbol": "Belgrano 500", "motivo": "Ramas sobre vereda"},
        dias_atras=15)
    await agregar_movimiento(conn, tid3, 1, "creacion", id_ag, dias_atras=15)
    await agregar_movimiento(conn, tid3, 2, "numeracion", id_ag, dias_atras=15)
    await agregar_movimiento(conn, tid3, 3, "pase", id_ag,
        id_estado_origen=eid_poda.get("iniciado"), id_estado_destino=eid_poda.get("en_evaluacion"),
        dias_atras=12)
    await agregar_movimiento(conn, tid3, 4, "cambio_estado", id_ag,
        id_estado_origen=eid_poda.get("en_evaluacion"), id_estado_destino=eid_poda.get("aprobada"),
        comentario="Poda aprobada. Cuadrilla programada para semana proxima.", dias_atras=3)
    await agregar_documento(conn, tid3, "Foto del arbol", "image/jpeg", id_ag, posicion=1)
    print(f"    {num3} (poda/aprobada)")

    # 4: archivado
    tid4, num4 = await crear_tramite(conn, t_poda, "archivado",
        "Poda del sauce lloron en parque", "ciudadano",
        cids[3], sa["espacios_verdes"], id_ag,
        {"direccion_arbol": "Parque Central s/n", "motivo": "Rutinaria"},
        dias_atras=30)
    await agregar_movimiento(conn, tid4, 1, "creacion", id_ag, dias_atras=30)
    await agregar_movimiento(conn, tid4, 2, "numeracion", id_ag, dias_atras=30)
    await agregar_movimiento(conn, tid4, 3, "pase", id_ag, dias_atras=27)
    await agregar_movimiento(conn, tid4, 4, "cambio_estado", id_ag, dias_atras=20)
    await agregar_movimiento(conn, tid4, 5, "cambio_estado", id_ag, comentario="Archivado tras completar poda.", dias_atras=10)
    print(f"    {num4} (poda/archivado)")

    # ---- pedido-informe (2 tramites) ----
    t_inf = tipos["pedido-informe"]
    eid_inf = t_inf[2]

    tid5, num5 = await crear_tramite(conn, t_inf, "solicitado",
        "Informe sobre estado de calles en Zona Norte", "area_interna",
        sa["mesa_entradas"], sa["mesa_entradas"], id_ag,
        {"asunto_informe": "Estado calles Zona Norte", "detalle": "Se solicita informe tecnico"},
        dias_atras=3)
    await agregar_movimiento(conn, tid5, 1, "creacion", id_ag, dias_atras=3)
    await agregar_movimiento(conn, tid5, 2, "numeracion", id_ag, dias_atras=3)
    print(f"    {num5} (informe/solicitado)")

    tid6, num6 = await crear_tramite(conn, t_inf, "respondido",
        "Informe disponibilidad turnos para vacunacion", "area_interna",
        sa["rrhh"], sa["rrhh"], id_ag,
        {"asunto_informe": "Disponibilidad vacunacion", "detalle": "Ver memo adjunto"},
        dias_atras=20)
    await agregar_movimiento(conn, tid6, 1, "creacion", id_ag, dias_atras=20)
    await agregar_movimiento(conn, tid6, 2, "numeracion", id_ag, dias_atras=20)
    await agregar_movimiento(conn, tid6, 3, "cambio_estado", id_ag, dias_atras=15)
    await agregar_movimiento(conn, tid6, 4, "cambio_estado", id_ag, comentario="Informe respondido, ver adjunto.", dias_atras=10)
    id_doc_inf = await agregar_documento(conn, tid6, "Informe respondido", posicion=1, requiere_firma=True, estado_firma="firmado", id_agente=id_ag)
    print(f"    {num6} (informe/respondido)")

    # ---- licencia-ordinaria (3 tramites) ----
    t_lic = tipos["licencia-ordinaria"]

    tid7, num7 = await crear_tramite(conn, t_lic, "solicitada",
        "Licencia ordinaria - Perez Juan - 5 dias", "area_interna",
        sa["rrhh"], sa["rrhh"], id_ag,
        {"agente_solicitante": 1, "fecha_desde": "2026-06-02", "fecha_hasta": "2026-06-06"},
        dias_atras=2)
    await agregar_movimiento(conn, tid7, 1, "creacion", id_ag, dias_atras=2)
    await agregar_movimiento(conn, tid7, 2, "numeracion", id_ag, dias_atras=2)
    print(f"    {num7} (licencia/solicitada)")

    tid8, num8 = await crear_tramite(conn, t_lic, "aprobada_jefe",
        "Licencia ordinaria - Martinez Laura - 10 dias", "area_interna",
        sa["rrhh"], sa["rrhh"], id_ag,
        {"agente_solicitante": 2, "fecha_desde": "2026-06-10", "fecha_hasta": "2026-06-20"},
        dias_atras=5)
    await agregar_movimiento(conn, tid8, 1, "creacion", id_ag, dias_atras=5)
    await agregar_movimiento(conn, tid8, 2, "numeracion", id_ag, dias_atras=5)
    await agregar_movimiento(conn, tid8, 3, "cambio_estado", id_ag, comentario="Aprobada por jefe directo.", dias_atras=3)
    print(f"    {num8} (licencia/aprobada_jefe)")

    tid9, num9 = await crear_tramite(conn, t_lic, "notificada",
        "Licencia ordinaria - Gonzalez Maria - 7 dias", "area_interna",
        sa["rrhh"], sa["rrhh"], id_ag,
        {"agente_solicitante": 3, "fecha_desde": "2026-05-05", "fecha_hasta": "2026-05-12"},
        dias_atras=20)
    await agregar_movimiento(conn, tid9, 1, "creacion", id_ag, dias_atras=20)
    await agregar_movimiento(conn, tid9, 2, "numeracion", id_ag, dias_atras=20)
    await agregar_movimiento(conn, tid9, 3, "cambio_estado", id_ag, dias_atras=18)
    await agregar_movimiento(conn, tid9, 4, "cambio_estado", id_ag, dias_atras=15)
    await agregar_movimiento(conn, tid9, 5, "cambio_estado", id_ag, comentario="Agente notificado.", dias_atras=12)
    print(f"    {num9} (licencia/notificada)")

    # ---- habilitacion-comercial (4 tramites: subsanacion, emitida, 2 en revision) ----
    t_hab = tipos["habilitacion-comercial"]
    eid_hab = t_hab[2]

    # Empresa 1, representante ciudadano 2 (hay relacion en ciudadano_empresa)
    eid1 = eids[0]
    rep1 = rep_eid  # ciudadano que representa

    tid10, num10 = await crear_tramite(conn, t_hab, "subsanacion",
        "Habilitacion comercial - Almacen Centro", "empresa",
        eid1, sa["habilitaciones"], id_ag,
        {"rubro": "comercial", "direccion_local": "Mitre 456", "superficie_m2": 85.0, "horario_atencion": "9 a 20"},
        id_representante=rep1, dias_atras=12)
    await agregar_movimiento(conn, tid10, 1, "creacion", id_ag, dias_atras=12)
    await agregar_movimiento(conn, tid10, 2, "numeracion", id_ag, dias_atras=12)
    await agregar_movimiento(conn, tid10, 3, "pase", id_ag, dias_atras=10)
    await agregar_movimiento(conn, tid10, 4, "cambio_estado", id_ag,
        comentario="Falta libreta sanitaria actualizada y certificado de bomberos vigente.", dias_atras=8)
    id_doc_hab = await agregar_documento(conn, tid10, "Contrato de locacion", posicion=1)
    id_doc_hab2 = await agregar_documento(conn, tid10, "Plano del local", posicion=2)
    print(f"    {num10} (habilitacion/subsanacion)")

    eid2 = eids[1] if len(eids) > 1 else eids[0]
    tid11, num11 = await crear_tramite(conn, t_hab, "emitida",
        "Habilitacion comercial - Servicios Ambientales", "empresa",
        eid2, sa["habilitaciones"], id_ag,
        {"rubro": "servicios", "direccion_local": "Av. Libertad 789", "superficie_m2": 200.0, "horario_atencion": "8 a 18"},
        dias_atras=45)
    await agregar_movimiento(conn, tid11, 1, "creacion", id_ag, dias_atras=45)
    await agregar_movimiento(conn, tid11, 2, "numeracion", id_ag, dias_atras=45)
    await agregar_movimiento(conn, tid11, 3, "pase", id_ag, dias_atras=42)
    await agregar_movimiento(conn, tid11, 4, "cambio_estado", id_ag, dias_atras=38)
    await agregar_movimiento(conn, tid11, 5, "cambio_estado", id_ag, dias_atras=30)
    await agregar_movimiento(conn, tid11, 6, "cambio_estado", id_ag, comentario="Habilitacion emitida.", dias_atras=20)
    id_doc_hab_cert = await agregar_documento(conn, tid11, "Certificado de habilitacion", posicion=1,
                                               requiere_firma=True, estado_firma="firmado")
    print(f"    {num11} (habilitacion/emitida)")

    eid3 = eids[2] if len(eids) > 2 else eids[0]
    tid12, num12 = await crear_tramite(conn, t_hab, "revision_documental",
        "Habilitacion comercial - Kiosco Belgrano", "empresa",
        eid3, sa["habilitaciones"], id_ag,
        {"rubro": "comercial", "direccion_local": "Belgrano 1100", "superficie_m2": 30.0, "horario_atencion": "7 a 22"},
        dias_atras=6)
    await agregar_movimiento(conn, tid12, 1, "creacion", id_ag, dias_atras=6)
    await agregar_movimiento(conn, tid12, 2, "numeracion", id_ag, dias_atras=6)
    await agregar_movimiento(conn, tid12, 3, "pase", id_ag, dias_atras=4)
    print(f"    {num12} (habilitacion/revision_documental)")

    eid4 = eids[3] if len(eids) > 3 else eids[0]
    tid13, num13 = await crear_tramite(conn, t_hab, "revision_documental",
        "Habilitacion comercial - Distribuidora Norte", "empresa",
        eid4, sa["habilitaciones"], id_ag,
        {"rubro": "industrial", "direccion_local": "Ruta 9 km 5", "superficie_m2": 500.0, "horario_atencion": "6 a 14"},
        dias_atras=9)
    await agregar_movimiento(conn, tid13, 1, "creacion", id_ag, dias_atras=9)
    await agregar_movimiento(conn, tid13, 2, "numeracion", id_ag, dias_atras=9)
    await agregar_movimiento(conn, tid13, 3, "pase", id_ag, dias_atras=7)
    print(f"    {num13} (habilitacion/revision_documental)")

    # ---- cambio-domicilio-comercial (2 tramites) ----
    t_cdc = tipos["cambio-domicilio-comercial"]

    tid14, num14 = await crear_tramite(conn, t_cdc, "iniciado",
        "Cambio domicilio - PLANTAS FAITFUL S.A.", "empresa",
        eid1, sa["mesa_entradas"], id_ag,
        {"direccion_anterior": "San Martin 200", "direccion_nueva": "Rivadavia 450",
         "fecha_efectiva": "2026-06-01", "nro_habilitacion_actual": "HAB-LPL-2026-0002"},
        id_representante=rep1, dias_atras=1)
    await agregar_movimiento(conn, tid14, 1, "creacion", id_ag, dias_atras=1)
    await agregar_movimiento(conn, tid14, 2, "numeracion", id_ag, dias_atras=1)
    print(f"    {num14} (cambio_domicilio/iniciado)")

    tid15, num15 = await crear_tramite(conn, t_cdc, "en_revision",
        "Cambio domicilio - Cooperativa Municipal", "empresa",
        eid4, sa["habilitaciones"], id_ag,
        {"direccion_anterior": "Urquiza 100", "direccion_nueva": "San Martin 555",
         "fecha_efectiva": "2026-05-20", "nro_habilitacion_actual": "HAB-LPL-2026-0001"},
        dias_atras=10)
    await agregar_movimiento(conn, tid15, 1, "creacion", id_ag, dias_atras=10)
    await agregar_movimiento(conn, tid15, 2, "numeracion", id_ag, dias_atras=10)
    await agregar_movimiento(conn, tid15, 3, "pase", id_ag, dias_atras=8)
    print(f"    {num15} (cambio_domicilio/en_revision)")

    # ---- transferencia-habilitacion (1) ----
    t_thc = tipos["transferencia-habilitacion"]

    tid16, num16 = await crear_tramite(conn, t_thc, "validando_anterior",
        "Transferencia habilitacion - Tecnologia Urbana a Servicios Ambientales", "empresa",
        eid2, sa["habilitaciones"], id_ag,
        {"nro_habilitacion": "HAB-LPL-2026-0003",
         "cuit_titular_anterior": "30912345609", "cuit_titular_nuevo": "30689012341",
         "fecha_efectiva": "2026-07-01"},
        dias_atras=5)
    await agregar_movimiento(conn, tid16, 1, "creacion", id_ag, dias_atras=5)
    await agregar_movimiento(conn, tid16, 2, "numeracion", id_ag, dias_atras=5)
    await agregar_movimiento(conn, tid16, 3, "cambio_estado", id_ag, dias_atras=3)
    id_doc_trf = await agregar_documento(conn, tid16, "Boleto de transferencia", posicion=1,
                                          requiere_firma=True, estado_firma="pendiente")
    await agregar_firma(conn, id_doc_trf, sa["habilitaciones"], "pendiente")
    print(f"    {num16} (transferencia/validando_anterior)")

    # ---- inspeccion-bromatologica (1) ----
    t_bro = tipos["inspeccion-bromatologica"]

    tid17, num17 = await crear_tramite(conn, t_bro, "programada",
        "Inspeccion bromatologica - Almacen demo", "empresa",
        eid3, sa["bromatologia"], id_ag,
        {"rubro_solicitud": "gastronomico", "motivo": "Habilitacion nueva"},
        dias_atras=7)
    await agregar_movimiento(conn, tid17, 1, "creacion", id_ag, dias_atras=7)
    await agregar_movimiento(conn, tid17, 2, "numeracion", id_ag, dias_atras=7)
    await agregar_movimiento(conn, tid17, 3, "cambio_estado", id_ag, dias_atras=5)
    print(f"    {num17} (bromatologia/programada)")

    # ---- cartel-publicitario (2) ----
    t_car = tipos["cartel-publicitario"]

    tid18, num18 = await crear_tramite(conn, t_car, "revision_tecnica",
        "Cartel marquesina - Servicios Ambientales", "empresa",
        eid2, sa["obras_particulares"], id_ag,
        {"direccion_local": "Av. Libertad 789", "dimensiones": "3x1.5m",
         "tipo_cartel": "marquesina", "monto_tasa": 45000},
        dias_atras=8)
    await agregar_movimiento(conn, tid18, 1, "creacion", id_ag, dias_atras=8)
    await agregar_movimiento(conn, tid18, 2, "numeracion", id_ag, dias_atras=8)
    await agregar_movimiento(conn, tid18, 3, "pase", id_ag, dias_atras=6)
    await agregar_documento(conn, tid18, "Plano del cartel", posicion=1)
    print(f"    {num18} (cartel/revision_tecnica)")

    tid19, num19 = await crear_tramite(conn, t_car, "pago_pendiente",
        "Cartel luminoso - Tecnologia Urbana", "empresa",
        eid1, sa["obras_particulares"], id_ag,
        {"direccion_local": "San Martin 789", "dimensiones": "5x2m",
         "tipo_cartel": "luminoso", "monto_tasa": 72000},
        dias_atras=20)
    await agregar_movimiento(conn, tid19, 1, "creacion", id_ag, dias_atras=20)
    await agregar_movimiento(conn, tid19, 2, "numeracion", id_ag, dias_atras=20)
    await agregar_movimiento(conn, tid19, 3, "pase", id_ag, dias_atras=18)
    await agregar_movimiento(conn, tid19, 4, "cambio_estado", id_ag, dias_atras=14)
    print(f"    {num19} (cartel/pago_pendiente)")

    # ---- recurso-administrativo (1, empresa con representante) ----
    t_rea = tipos["recurso-administrativo"]

    tid20, num20 = await crear_tramite(conn, t_rea, "presentado",
        "Recurso contra multa por deposito de residuos", "empresa",
        eid3, sa["legales"], id_ag,
        {"numero_acto_recurrido": "DISP-2026-0034",
         "tipo_acto": "multa",
         "fecha_notificacion": "2026-05-10",
         "fundamentos": "La disposicion es arbitraria y carece de fundamentos tecnicos.",
         "pretension": "Se solicita dejar sin efecto la multa."},
        id_representante=rep1, dias_atras=4)
    await agregar_movimiento(conn, tid20, 1, "creacion", id_ag, dias_atras=4)
    await agregar_movimiento(conn, tid20, 2, "numeracion", id_ag, dias_atras=4)
    await agregar_documento(conn, tid20, "Copia del acto recurrido", posicion=1)
    print(f"    {num20} (recurso/presentado)")

    # ---- Relaciones entre tramites ----
    # habilitacion (tid10) relacionada con cambio de domicilio (tid14) de la misma empresa
    if tid10 and tid14:
        a, b = (min(tid10, tid14), max(tid10, tid14))
        existe = await fetchval(conn,
            "SELECT 1 FROM tramite_relacion WHERE id_tramite_a = :a AND id_tramite_b = :b",
            {"a": a, "b": b})
        if not existe:
            await conn.execute(text("""
                INSERT INTO tramite_relacion (id_tramite_a, id_tramite_b, tipo_relacion, id_agente_creador, id_municipio, activo)
                VALUES (:a, :b, 'asociacion_simple', :ag, :m, TRUE)
            """), {"a": a, "b": b, "ag": id_ag, "m": ID_MUNICIPIO})
            print(f"    Relacion: {num10} <-> {num14}")

    # habilitacion (tid11) relacionada con cartel (tid18) de la misma empresa
    if tid11 and tid18:
        a, b = (min(tid11, tid18), max(tid11, tid18))
        existe = await fetchval(conn,
            "SELECT 1 FROM tramite_relacion WHERE id_tramite_a = :a AND id_tramite_b = :b",
            {"a": a, "b": b})
        if not existe:
            await conn.execute(text("""
                INSERT INTO tramite_relacion (id_tramite_a, id_tramite_b, tipo_relacion, id_agente_creador, id_municipio, activo)
                VALUES (:a, :b, 'asociacion_simple', :ag, :m, TRUE)
            """), {"a": a, "b": b, "ag": id_ag, "m": ID_MUNICIPIO})
            print(f"    Relacion: {num11} <-> {num18}")

    print(f"    20 tramites creados.")


# =============================================================================
# Main
# =============================================================================

async def main():
    print("=== SEED TRAMITES ===")
    async with AsyncSessionLocal() as session:
        async with session.begin():
            conn = session

            # Paso 1: subáreas
            print("\n[1/3] Subareas y municipio...")
            sa = await seed_subareas(conn)

            # Paso 2: resolver ciudadanos y empresas para los seeds
            print("\n[2/3] Resolviendo ciudadanos y empresas del BUC...")
            cid_rows = (await conn.execute(text(
                "SELECT id_ciudadano FROM ciudadanos WHERE activo = TRUE ORDER BY id_ciudadano LIMIT 5"
            ))).fetchall()
            cids = [r[0] for r in cid_rows]
            if len(cids) < 4:
                print(f"  ADVERTENCIA: solo {len(cids)} ciudadanos activos. Se reutilizaran.")
                while len(cids) < 4:
                    cids.append(cids[0])

            eid_rows = (await conn.execute(text(
                "SELECT id_empresa FROM empresas WHERE activo = TRUE ORDER BY id_empresa LIMIT 5"
            ))).fetchall()
            eids = [r[0] for r in eid_rows]
            if len(eids) < 2:
                raise RuntimeError("Se necesitan al menos 2 empresas activas en la BUC.")
            print(f"  Ciudadanos: {cids}")
            print(f"  Empresas: {eids}")

            # Representante: buscar ciudadano que represente a la primera empresa
            rep_row = (await conn.execute(text(
                "SELECT id_ciudadano FROM ciudadano_empresa WHERE id_empresa = :e AND activo = TRUE LIMIT 1"
            ), {"e": eids[0]})).fetchone()
            rep_eid = rep_row[0] if rep_row else cids[0]
            print(f"  Representante de empresa {eids[0]}: ciudadano {rep_eid}")

            # Paso 3: tipos de tramite
            print("\n[3/3] Tipos de tramite, versiones, estados, transiciones, docs...")
            tipos = await seed_tipos(conn, sa)

            # Paso 4: tramites instanciados
            print("\n[4/4] Tramites instanciados...")
            await seed_tramites_instancias(conn, sa, tipos, cids, eids, rep_eid)

    print("\n=== SEED COMPLETADO ===")
    print("Verificar con:")
    print("  curl http://localhost:8000/api/v1/tramites/tipos | jq '.total'")
    print("  curl 'http://localhost:8000/api/v1/tramites?limit=5' | jq '{total, items_count: (.items | length)}'")


if __name__ == "__main__":
    asyncio.run(main())
