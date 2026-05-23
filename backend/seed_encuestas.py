# -*- coding: utf-8 -*-
"""
Seed idempotente para el modulo Encuestas (CSAT) — migracion 57.

Crea la encuesta estandar ZARIS v1:
  - 1 plantilla "CSAT Reclamos ZARIS v1"
  - 8 preguntas (tronco likert5 + ramas satisfechos/neutrales/insatisfechos + comentario)
  - ~22 opciones para las preguntas tipo 'multiple'

Idempotente: cada entidad se busca por una clave natural antes de insertar
(plantilla por nombre, pregunta por (plantilla, orden, rama), opcion por
(pregunta, valor)). Re-correr el script no duplica nada.

Prerequisito: migracion 57 aplicada.

Uso:
  cd backend
  $env:ENV_FILE=".env.local"; python seed_encuestas.py
"""
import asyncio
import os
import sys

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


# =============================================================================
# Datos de la encuesta estandar ZARIS v1
# =============================================================================

PLANTILLA = {
    "nombre": "CSAT Reclamos ZARIS v1",
    "descripcion": "Encuesta de satisfaccion estandar disparada al cierre de reclamos",
    "version": "1.0",
    "tipo": "reclamos",
}

# (orden, rama, tipo, obligatoria, texto, [opciones (texto, valor)])
PREGUNTAS = [
    (1, "todos", "likert5", True,
     "¿Qué tan satisfecho estás con la resolución de tu reclamo?", []),

    (2, "satisfechos", "multiple", True,
     "¿Qué aspecto destacarías de la atención recibida?",
     [("Rapidez", "rapidez"),
      ("Claridad en la información", "claridad"),
      ("Trato del personal", "trato"),
      ("Calidad de la solución", "calidad"),
      ("Otro", "otro")]),

    (3, "satisfechos", "si_no", True,
     "¿Recomendarías este canal de reclamos a otros vecinos?", []),

    (2, "neutrales", "multiple", True,
     "¿Qué faltó para que tu experiencia fuera mejor?",
     [("Más rapidez", "mas_rapidez"),
      ("Más información", "mas_informacion"),
      ("Mejor comunicación", "mejor_comunicacion"),
      ("Mejor solución", "mejor_solucion"),
      ("Otro", "otro")]),

    (3, "neutrales", "multiple", True,
     "¿La resolución fue lo que esperabas?",
     [("Sí", "si"),
      ("Parcialmente", "parcialmente"),
      ("No", "no")]),

    (2, "insatisfechos", "multiple", True,
     "¿Cuál fue el principal problema?",
     [("Demora excesiva", "demora"),
      ("No resolvieron el problema", "no_resuelto"),
      ("Mala comunicación", "mala_comunicacion"),
      ("Mal trato", "mal_trato"),
      ("Solución incorrecta", "solucion_incorrecta"),
      ("Otro", "otro")]),

    (3, "insatisfechos", "si_no", True,
     "¿Querés que un responsable del municipio te contacte?", []),

    (99, "todos", "texto_libre", False,
     "¿Querés dejar algún comentario adicional?", []),
]


# =============================================================================
# Helpers
# =============================================================================

async def fetchval(conn, sql, params=None):
    r = await conn.execute(text(sql), params or {})
    row = r.fetchone()
    return row[0] if row else None


async def upsert_plantilla(conn):
    """Busca o crea la plantilla por nombre. Devuelve id_encuesta_plantilla."""
    pid = await fetchval(conn,
        "SELECT id_encuesta_plantilla FROM encuesta_plantilla "
        "WHERE nombre = :n LIMIT 1",
        {"n": PLANTILLA["nombre"]})
    if pid:
        return pid
    pid = await fetchval(conn, """
        INSERT INTO encuesta_plantilla (nombre, descripcion, version, tipo, id_municipio)
        VALUES (:nombre, :descripcion, :version, :tipo, :mun)
        ON CONFLICT DO NOTHING
        RETURNING id_encuesta_plantilla
    """, {**PLANTILLA, "mun": ID_MUNICIPIO})
    if pid is None:
        # carrera/insert previo: re-leer
        pid = await fetchval(conn,
            "SELECT id_encuesta_plantilla FROM encuesta_plantilla WHERE nombre = :n LIMIT 1",
            {"n": PLANTILLA["nombre"]})
    return pid


async def upsert_pregunta(conn, id_plantilla, orden, rama, tipo, obligatoria, texto):
    """Busca o crea una pregunta por (plantilla, orden, rama). Devuelve id."""
    qid = await fetchval(conn,
        "SELECT id_encuesta_pregunta FROM encuesta_pregunta "
        "WHERE id_plantilla = :p AND orden = :o AND rama = :r LIMIT 1",
        {"p": id_plantilla, "o": orden, "r": rama})
    if qid:
        return qid
    qid = await fetchval(conn, """
        INSERT INTO encuesta_pregunta
            (id_plantilla, texto, tipo, orden, rama, obligatoria, id_municipio)
        VALUES (:p, :texto, :tipo, :o, :r, :obl, :mun)
        ON CONFLICT DO NOTHING
        RETURNING id_encuesta_pregunta
    """, {"p": id_plantilla, "texto": texto, "tipo": tipo, "o": orden,
          "r": rama, "obl": obligatoria, "mun": ID_MUNICIPIO})
    if qid is None:
        qid = await fetchval(conn,
            "SELECT id_encuesta_pregunta FROM encuesta_pregunta "
            "WHERE id_plantilla = :p AND orden = :o AND rama = :r LIMIT 1",
            {"p": id_plantilla, "o": orden, "r": rama})
    return qid


async def upsert_opcion(conn, id_pregunta, texto, valor, orden):
    """Busca o crea una opcion por (pregunta, valor)."""
    oid = await fetchval(conn,
        "SELECT id_encuesta_opcion FROM encuesta_opcion "
        "WHERE id_pregunta = :q AND valor = :v LIMIT 1",
        {"q": id_pregunta, "v": valor})
    if oid:
        return oid
    await conn.execute(text("""
        INSERT INTO encuesta_opcion (id_pregunta, texto, valor, orden, id_municipio)
        VALUES (:q, :texto, :valor, :o, :mun)
        ON CONFLICT DO NOTHING
    """), {"q": id_pregunta, "texto": texto, "valor": valor,
           "o": orden, "mun": ID_MUNICIPIO})


# =============================================================================
# Main
# =============================================================================

async def seed():
    async with AsyncSessionLocal() as conn:
        id_plantilla = await upsert_plantilla(conn)
        print(f"[OK] plantilla id={id_plantilla}")

        for orden, rama, tipo, obligatoria, texto, opciones in PREGUNTAS:
            qid = await upsert_pregunta(conn, id_plantilla, orden, rama, tipo, obligatoria, texto)
            print(f"  [OK] pregunta id={qid} orden={orden} rama={rama} tipo={tipo}")
            for i, (otexto, ovalor) in enumerate(opciones, start=1):
                await upsert_opcion(conn, qid, otexto, ovalor, i)
            if opciones:
                print(f"       -> {len(opciones)} opciones")

        await conn.commit()

        # Verificacion
        np = await fetchval(conn, "SELECT count(*) FROM encuesta_plantilla")
        nq = await fetchval(conn, "SELECT count(*) FROM encuesta_pregunta")
        no = await fetchval(conn, "SELECT count(*) FROM encuesta_opcion")
        print("\n=== Conteos ===")
        print(f"  encuesta_plantilla = {np}")
        print(f"  encuesta_pregunta  = {nq}")
        print(f"  encuesta_opcion    = {no}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
