# -*- coding: utf-8 -*-
"""
Verificador de F1 de IT-01 (multi-municipio): segmentación de la base por id_municipio
(migs 125, 125b, 125c, 125d). Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tareas 1-4.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_segmentacion_f1.py
    python smoke_segmentacion_f1.py --foto $env:TEMP\\f1_conteos_antes.json
    python smoke_segmentacion_f1.py --comparar $env:TEMP\\f1_conteos_antes.json

Contra local corre todos los chequeos; los que insertan (numeración, FK compuesta) lo hacen
dentro de una transacción que se revierte. Contra otra base solo acepta --solo-lectura, que
saltea esos dos (para verificar prod en el corte sin escribir nada).
"""
import argparse
import asyncio
import json
import os
import sys

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402

ES_LOCAL = "zaris_dev" in settings.ASYNC_DATABASE_URI

# Únicos compuestos que crea la 125c: (tabla, columnas, nulls_not_distinct).
UNICOS = [
    ("ciudadanos", ["id_municipio", "doc_pais", "doc_tipo", "doc_nro"], False),
    ("ciudadanos", ["id_municipio", "cuil"], False),
    ("empresas", ["id_municipio", "doc_pais", "cuit"], False),
    ("usuarios", ["id_municipio", "username"], False),
    ("reclamos", ["id_municipio", "nro_reclamo"], False),
    ("ordenes_trabajo", ["id_municipio", "nro_ot"], False),
    ("emergencia_evento", ["id_municipio", "numero_operativo"], False),
    ("activos", ["id_municipio", "codigo_unico"], False),
    ("agenda_feriado", ["id_municipio", "fecha"], False),
    ("emergencia_canal_ingreso", ["id_municipio", "codigo"], False),
    ("emergencia_prioridad", ["id_municipio", "codigo"], False),
    ("emergencia_organismo_derivacion", ["id_municipio", "codigo"], False),
    ("configuracion_general", ["id_municipio", "clave"], True),
]

# Lo que borra el lote de limpieza (mig 129b).
UNICOS_VIEJOS = [
    "uq_ciudadano_doc", "uq_ciudadano_cuil", "uq_empresa_cuit", "usuarios_username_key",
    "reclamos_nro_reclamo_key", "ordenes_trabajo_nro_ot_key", "emergencia_evento_numero_operativo_key",
    "activos_codigo_unico_key", "agenda_feriado_fecha_key", "emergencia_canal_ingreso_codigo_key",
    "emergencia_prioridad_codigo_key", "emergencia_organismo_derivacion_codigo_key",
    "configuracion_general_clave_key",
]
TABLAS_LEGADO = ["reclamos_tipo", "reclamos_subarea", "reclamos_area", "emergencia_numerador", "equipo_usuarios"]

RESULTADOS: list[tuple[str, bool, str]] = []


def _reg(nombre: str, ok: bool, detalle: str = "") -> None:
    RESULTADOS.append((nombre, ok, detalle))
    print(f"[{'OK   ' if ok else 'FALLA'}] {nombre}{(' — ' + detalle) if detalle else ''}")


async def _tablas_publicas(conn) -> list[str]:
    rows = await conn.execute(text("""
        SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
           AND table_name NOT LIKE '\\_backup%'
         ORDER BY 1"""))
    return [r[0] for r in rows]


async def _existe_clasificacion(conn) -> bool:
    return bool(await conn.scalar(text("SELECT to_regclass('public.municipio_tabla_clase') IS NOT NULL")))


async def _segmentadas(conn) -> list[str]:
    rows = await conn.execute(text(
        "SELECT tabla FROM municipio_tabla_clase WHERE clase IN ('catalogo','operativo') ORDER BY 1"))
    return [r[0] for r in rows]


async def contar(conn) -> dict[str, int]:
    conteos = {}
    for t in await _tablas_publicas(conn):
        conteos[t] = int(await conn.scalar(text(f'SELECT count(*) FROM public."{t}"')))
    return conteos


async def chk_toda_tabla_clasificada(conn) -> None:
    if not await _existe_clasificacion(conn):
        _reg("toda_tabla_clasificada", False, "municipio_tabla_clase no existe")
        return
    tablas = set(await _tablas_publicas(conn))
    filas = {r[0]: r[1] for r in await conn.execute(text("SELECT tabla, clase FROM municipio_tabla_clase"))}
    sin_clase = sorted(tablas - set(filas))
    # Las globales y las legado pueden faltar en un entorno (drift: tipos_representacion no está en local).
    inexistentes = sorted(t for t, c in filas.items() if c not in ("legado", "global") and t not in tablas)
    _reg("toda_tabla_clasificada", not sin_clase and not inexistentes,
         f"sin clase: {sin_clase}; clasificadas inexistentes: {inexistentes}" if (sin_clase or inexistentes) else "")


async def chk_id_municipio_completo(conn) -> None:
    if not await _existe_clasificacion(conn):
        _reg("id_municipio_completo", False, "municipio_tabla_clase no existe")
        return
    problemas = []
    for t in await _segmentadas(conn):
        if not await conn.scalar(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{t}"}):
            continue  # clasificada pero inexistente: lo reporta toda_tabla_clasificada
        col = (await conn.execute(text("""
            SELECT is_nullable FROM information_schema.columns
             WHERE table_schema='public' AND table_name=:t AND column_name='id_municipio'"""),
            {"t": t})).fetchone()
        if not col:
            problemas.append(f"{t}: sin columna")
            continue
        # IT-01 F3 (mig 127): usuarios admite NULL solo para el super administrador (nivel 0),
        # y lo garantiza ck_usuarios_municipio_nivel.
        excepcion_super = t == "usuarios" and bool(await conn.scalar(text(
            "SELECT 1 FROM pg_constraint WHERE conname = 'ck_usuarios_municipio_nivel'")))
        if col[0] != "NO" and not excepcion_super:
            problemas.append(f"{t}: nullable")
        if excepcion_super:
            mal = await conn.scalar(text(
                "SELECT count(*) FROM usuarios WHERE (id_municipio IS NULL) <> (nivel_acceso = 0)"))
            if mal:
                problemas.append(f"usuarios: {mal} filas con municipio y nivel incoherentes")
            fk = await conn.scalar(text("""
                SELECT count(*) FROM pg_constraint c
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                 WHERE c.conrelid = 'usuarios'::regclass AND c.contype = 'f'
                   AND c.confrelid = 'municipios'::regclass AND a.attname = 'id_municipio'
                   AND array_length(c.conkey, 1) = 1"""))
            if not fk:
                problemas.append("usuarios: sin FK a municipios")
            continue
        fk = await conn.scalar(text("""
            SELECT count(*) FROM pg_constraint c
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
             WHERE c.conrelid = CAST(:t AS regclass) AND c.contype = 'f'
               AND c.confrelid = 'municipios'::regclass AND a.attname = 'id_municipio'
               AND array_length(c.conkey, 1) = 1"""), {"t": f"public.{t}"})
        if not fk:
            problemas.append(f"{t}: sin FK a municipios")
        nulos = await conn.scalar(text(f'SELECT count(*) FROM public."{t}" WHERE id_municipio IS NULL'))
        if nulos:
            problemas.append(f"{t}: {nulos} filas NULL")
    _reg("id_municipio_completo", not problemas, "; ".join(problemas[:12]) + (" …" if len(problemas) > 12 else ""))


async def chk_sin_377(conn) -> None:
    n = await conn.scalar(text("SELECT count(*) FROM usuarios WHERE id_municipio = 377"))
    _reg("sin_377", n == 0, f"{n} usuarios con 377" if n else "")


async def chk_config_dividida(conn) -> None:
    tiene_col = await conn.scalar(text("""
        SELECT count(*) FROM information_schema.columns
         WHERE table_schema='public' AND table_name='configuracion_general' AND column_name='id_municipio'"""))
    if not tiene_col:
        _reg("config_dividida", False, "configuracion_general sin id_municipio")
        return
    # Globales esperadas: las vapid_* (F1) y, desde la mig 127b (IT-01 F3), la renovación de claves,
    # que es un parámetro de seguridad global que ningún municipio sobrescribe.
    globales_no_vapid = [r[0] for r in await conn.execute(text(
        "SELECT clave FROM configuracion_general WHERE id_municipio IS NULL AND clave NOT LIKE 'vapid\\_%' "
        "AND clave <> 'password_renovacion_dias'"))]
    globales_no_vapid += [f"{r[0]} (por municipio)" for r in await conn.execute(text(
        "SELECT clave FROM configuracion_general WHERE id_municipio IS NOT NULL "
        "AND clave = 'password_renovacion_dias' "
        "AND to_regclass('public.super_admin_acceso') IS NOT NULL"))]
    vapid_no_globales = [r[0] for r in await conn.execute(text(
        "SELECT clave FROM configuracion_general WHERE id_municipio IS NOT NULL AND clave LIKE 'vapid\\_%'"))]
    otro_municipio = await conn.scalar(text(
        "SELECT count(*) FROM configuracion_general WHERE id_municipio IS NOT NULL AND id_municipio <> 1"))
    ok = not globales_no_vapid and not vapid_no_globales and otro_municipio == 0
    _reg("config_dividida", ok,
         "" if ok else f"globales que no son vapid: {globales_no_vapid}; vapid no globales: {vapid_no_globales}; "
                       f"filas de otro municipio: {otro_municipio}")


async def chk_municipio_base(conn) -> None:
    tiene_col = await conn.scalar(text("""
        SELECT count(*) FROM information_schema.columns
         WHERE table_schema='public' AND table_name='municipios' AND column_name='direccion_base'"""))
    if not tiene_col:
        _reg("municipio_base", False, "municipios sin direccion_base")
        return
    base = (await conn.execute(text(
        "SELECT id_municipio, subdominio, codigo_pais FROM municipios WHERE direccion_base"))).fetchall()
    dos = await conn.scalar(text("SELECT activo FROM municipios WHERE id_municipio = 2"))
    ok = (len(base) == 1 and base[0].id_municipio == 1 and base[0].subdominio == "sanandres"
          and base[0].codigo_pais == "AR" and dos is not True)
    _reg("municipio_base", ok, "" if ok else f"base={[tuple(r) for r in base]}; municipio 2 activo={dos}")


async def chk_unicos_compuestos(conn) -> None:
    faltan = []
    for tabla, cols, nnd in UNICOS:
        rows = await conn.execute(text("""
            SELECT array_agg(a.attname::text ORDER BY k.ord) AS cols, i.indnullsnotdistinct AS nnd
              FROM pg_index i
              CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
              JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
             WHERE i.indrelid = CAST(:t AS regclass) AND i.indisunique
             GROUP BY i.indexrelid, i.indnullsnotdistinct"""), {"t": f"public.{tabla}"})
        if not any(list(r.cols) == cols and (r.nnd or not nnd) for r in rows):
            faltan.append(f"{tabla}({', '.join(cols)}){' NULLS NOT DISTINCT' if nnd else ''}")
    _reg("unicos_compuestos", not faltan, f"faltan: {faltan}" if faltan else "")


async def chk_lote_limpieza(conn) -> None:
    """Lote de limpieza (migs 129/129b): todo o nada. Aplicado = sin los únicos globales viejos,
    sin tablas legado y sin id_municipio en las globales, con el único del username de las
    cuentas sin municipio (129) que reemplaza al global."""
    viejos = await conn.scalar(text("SELECT count(*) FROM pg_class WHERE relname = ANY(:n)"),
                               {"n": UNICOS_VIEJOS})
    legado = await conn.scalar(text("SELECT count(*) FROM pg_class WHERE relkind = 'r' AND relname = ANY(:n)"),
                               {"n": TABLAS_LEGADO})
    columnas = await conn.scalar(text("""
        SELECT count(*) FROM information_schema.columns c
          JOIN municipio_tabla_clase m ON m.tabla = c.table_name AND m.clase = 'global'
         WHERE c.table_schema = 'public' AND c.column_name = 'id_municipio' AND c.table_name <> 'municipios'"""))
    sin_municipio = await conn.scalar(text(
        "SELECT count(*) FROM pg_class WHERE relname = 'uq_usuarios_username_sin_municipio'"))
    if viejos == legado == columnas == 0:
        _reg("lote_limpieza", bool(sin_municipio),
             "aplicado" if sin_municipio else "aplicado sin uq_usuarios_username_sin_municipio (falta la 129)")
    elif viejos and legado and columnas:
        _reg("lote_limpieza", True, "pendiente (129b sin aplicar)")
    else:
        _reg("lote_limpieza", False,
             f"a medias: {viejos} únicos viejos, {legado} tablas legado, {columnas} globales con id_municipio")


async def _ultimo(conn, entidad: str) -> int:
    v = await conn.scalar(text("""
        SELECT ultimo_numero FROM numerador_municipio
         WHERE id_municipio = 1 AND entidad = :e AND anio = EXTRACT(YEAR FROM NOW())::int"""), {"e": entidad})
    return int(v or 0)


async def chk_numeracion_nueva(conn_lectura) -> None:
    if not await conn_lectura.scalar(text("SELECT to_regclass('public.numerador_municipio') IS NOT NULL")):
        _reg("numeracion_nueva", False, "numerador_municipio no existe")
        return
    async with engine.connect() as conn:  # conexión propia: todo lo insertado se revierte
        await _numeracion_en_transaccion(conn)


async def _numeracion_en_transaccion(conn) -> None:
    trans = await conn.begin()
    problemas = []
    try:
        codigo = await conn.scalar(text("SELECT codigo_corto FROM municipios WHERE id_municipio = 1"))
        anio = await conn.scalar(text("SELECT EXTRACT(YEAR FROM NOW())::int"))
        u_rec, u_ot, u_em = await _ultimo(conn, "reclamo"), await _ultimo(conn, "ot"), await _ultimo(conn, "emergencia")
        rec = (await conn.execute(text("""
            INSERT INTO reclamos (descripcion, estado, id_municipio) VALUES ('smoke F1 numeracion', 'Sin asignar', 1)
            RETURNING id_reclamo, nro_reclamo"""))).fetchone()
        ot = await conn.scalar(text("""
            INSERT INTO ordenes_trabajo (id_reclamo, id_estado, id_municipio)
            VALUES (:r, (SELECT min(id_estado_ot) FROM estado_ot), 1) RETURNING nro_ot"""), {"r": rec.id_reclamo})
        em = await conn.scalar(text("""
            INSERT INTO emergencia_evento (direccion_evento, id_canal_ingreso, id_estado, id_prioridad,
                                           id_subarea, id_tipo, denunciante_anonimo, id_municipio)
            SELECT 'smoke F1 numeracion', id_canal_ingreso, id_estado, id_prioridad, id_subarea, id_tipo, TRUE, 1
              FROM emergencia_evento WHERE id_municipio = 1 LIMIT 1
            RETURNING numero_operativo"""))
        esperado = {
            "reclamo": (rec.nro_reclamo, f"REC-{codigo}-{anio}-{u_rec + 1:06d}"),
            "ot": (ot, f"OT-{codigo}-{anio}-{u_ot + 1:06d}"),
            "emergencia": (em, f"EM-{codigo}-{anio}-{u_em + 1:06d}"),
        }
        for entidad, (real, esp) in esperado.items():
            if real != esp:
                problemas.append(f"{entidad}: {real!r} (esperado {esp!r})")
    except Exception as exc:  # noqa: BLE001
        problemas.append(f"error: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
    finally:
        await trans.rollback()
    _reg("numeracion_nueva", not problemas, "; ".join(problemas))


async def chk_fk_compuesta_misma_accion(conn) -> None:
    """Cada FK compuesta fkm_* copia el ON DELETE de su FK simple original (si no, un DELETE con
    cascada se frena: la compuesta NO ACTION puede verificar antes de que la cascada borre)."""
    rows = (await conn.execute(text("""
        SELECT c2.conname, c1.confdeltype AS original, c2.confdeltype AS compuesta
          FROM pg_constraint c2
          JOIN pg_constraint c1
            ON c1.conrelid = c2.conrelid AND c1.confrelid = c2.confrelid AND c1.contype = 'f'
           AND array_length(c1.conkey, 1) = 1
           AND c1.conkey[1] = ANY (c2.conkey)
           AND c1.conkey[1] <> (SELECT a.attnum FROM pg_attribute a
                                 WHERE a.attrelid = c2.conrelid AND a.attname = 'id_municipio')
         WHERE c2.contype = 'f' AND c2.conname LIKE 'fkm\\_%'
           AND c1.confdeltype IS DISTINCT FROM c2.confdeltype"""))).fetchall()
    total = await conn.scalar(text("SELECT count(*) FROM pg_constraint WHERE contype = 'f' AND conname LIKE 'fkm\\_%'"))
    _reg("fk_compuesta_misma_accion", total > 0 and not rows,
         f"{len(rows)} de {total} con otra acción: {[r.conname for r in rows[:5]]}" if rows else
         ("no hay FK compuestas" if not total else ""))


async def chk_compat_codigo_viejo(conn_lectura) -> None:
    """Según el estado de la 126 (DEFAULT de id_municipio en las tablas catalogo/operativo):
    con DEFAULT (125c, código viejo) prueba la compatibilidad; sin DEFAULT (126) prueba el rechazo;
    con algunas sí y otras no, la 126 quedó a medias."""
    fila = (await conn_lectura.execute(text("""
        SELECT count(*) AS total, count(*) FILTER (WHERE c.column_default IS NOT NULL) AS con_default
          FROM information_schema.columns c
          JOIN municipio_tabla_clase m ON m.tabla = c.table_name
         WHERE c.table_schema = 'public' AND c.column_name = 'id_municipio'
           AND m.clase IN ('catalogo', 'operativo')"""))).fetchone()
    if fila.con_default == 0:
        await _sin_default_rechaza()
    elif fila.con_default == fila.total:
        await _compat_antes_de_126()
    else:
        _reg("sin_default_municipio", False,
             f"126 a medias: {fila.con_default} de {fila.total} tablas con DEFAULT de municipio")


async def _sin_default_rechaza() -> None:
    """Desde la 126: un INSERT con id_municipio NULL o 377 y un UPDATE a NULL se rechazan
    (sin DEFAULT y con trg_000_municipio_defecto inerte, ya no caen en el municipio 1)."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        problemas = []
        try:
            id_r = await conn.scalar(text("""
                INSERT INTO reclamos (descripcion, estado, id_municipio) VALUES ('smoke F1 126', 'Sin asignar', 1)
                RETURNING id_reclamo"""))
            casos = [
                ("INSERT con NULL", "INSERT INTO reclamos (descripcion, estado, id_municipio) "
                                    "VALUES ('smoke F1 126', 'Sin asignar', NULL)", {}),
                ("INSERT con 377", "INSERT INTO reclamos (descripcion, estado, id_municipio) "
                                   "VALUES ('smoke F1 126', 'Sin asignar', 377)", {}),
                ("UPDATE a NULL", "UPDATE reclamos SET id_municipio = NULL WHERE id_reclamo = :r", {"r": id_r}),
            ]
            for nombre, sql, params in casos:
                sp = await conn.begin_nested()
                try:
                    await conn.execute(text(sql), params)
                    problemas.append(f"{nombre}: se aceptó")
                except DBAPIError:
                    pass
                finally:
                    await sp.rollback()
        except Exception as exc:  # noqa: BLE001
            problemas.append(f"error: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
        finally:
            await trans.rollback()
    _reg("sin_default_municipio", not problemas, "; ".join(problemas))


async def _compat_antes_de_126() -> None:
    """Hasta la 126: un INSERT con id_municipio NULL explícito o 377 cae en el municipio 1, y un
    UPDATE que lo pisa con NULL conserva el anterior (trigger trg_000_municipio_defecto)."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        problemas = []
        try:
            nulo = (await conn.execute(text("""
                INSERT INTO reclamos (descripcion, estado, id_municipio) VALUES ('smoke F1 compat', 'Sin asignar', NULL)
                RETURNING id_reclamo, id_municipio"""))).fetchone()
            if nulo.id_municipio != 1:
                problemas.append(f"INSERT con NULL → {nulo.id_municipio}")
            m377 = await conn.scalar(text("""
                INSERT INTO reclamos (descripcion, estado, id_municipio) VALUES ('smoke F1 compat', 'Sin asignar', 377)
                RETURNING id_municipio"""))
            if m377 != 1:
                problemas.append(f"INSERT con 377 → {m377}")
            upd = await conn.scalar(text(
                "UPDATE reclamos SET id_municipio = NULL WHERE id_reclamo = :r RETURNING id_municipio"),
                {"r": nulo.id_reclamo})
            if upd != 1:
                problemas.append(f"UPDATE a NULL → {upd}")
        except Exception as exc:  # noqa: BLE001
            problemas.append(f"error: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
        finally:
            await trans.rollback()
    _reg("compat_codigo_viejo", not problemas, "; ".join(problemas))


async def chk_fk_compuesta(_conn_lectura) -> None:
    async with engine.connect() as conn:  # conexión propia: todo lo insertado se revierte
        await _fk_compuesta_en_transaccion(conn)


async def _fk_compuesta_en_transaccion(conn) -> None:
    trans = await conn.begin()
    detalle = ""
    ok = False
    try:
        tmp = await conn.scalar(text("""
            INSERT INTO municipios (nombre, codigo_corto, codigo_pais, activo)
            VALUES ('smoke F1 temporal', 'ZF1', 'AR', TRUE) RETURNING id_municipio"""))
        tipo_1 = await conn.scalar(text("SELECT id_tipo_reclamo FROM tipo_reclamo WHERE id_municipio = 1 LIMIT 1"))
        sp = await conn.begin_nested()
        try:
            await conn.execute(text("""
                INSERT INTO reclamos (descripcion, estado, id_municipio, id_tipo_reclamo)
                VALUES ('smoke F1 cruce', 'Sin asignar', :m, :t)"""), {"m": tmp, "t": tipo_1})
            await sp.commit()
            detalle = "el reclamo con el tipo de otro municipio se insertó"
        except IntegrityError as exc:
            await sp.rollback()
            ok = "foreign key" in str(exc.orig).lower() or "llave foránea" in str(exc.orig).lower()
            detalle = "" if ok else f"falló por otra causa: {str(exc.orig).splitlines()[0][:160]}"
    except Exception as exc:  # noqa: BLE001
        detalle = f"error: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
    finally:
        await trans.rollback()
    _reg("fk_compuesta", ok, detalle)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", help="guarda los conteos por tabla en este JSON y sale")
    ap.add_argument("--comparar", help="compara los conteos por tabla contra este JSON")
    ap.add_argument("--solo-lectura", action="store_true",
                    help="saltea los chequeos que insertan (obligatorio fuera de zaris_dev)")
    args = ap.parse_args()
    if not ES_LOCAL and not args.solo_lectura:
        sys.exit("ABORT: la base no es zaris_dev; fuera de local solo se corre con --solo-lectura.")
    print(f"Base: {settings.POSTGRES_SERVER} / {settings.POSTGRES_DB}")

    async with engine.connect() as conn:
        if args.foto:
            conteos = await contar(conn)
            with open(args.foto, "w", encoding="utf-8") as fh:
                json.dump(conteos, fh, indent=1, ensure_ascii=False)
            print(f"Foto guardada: {args.foto} ({len(conteos)} tablas)")
            return 0
        if args.comparar:
            with open(args.comparar, encoding="utf-8") as fh:
                antes = json.load(fh)
            ahora = await contar(conn)
            difs = [f"{t}: {n} → {ahora.get(t)}" for t, n in antes.items() if ahora.get(t) != n]
            _reg("conteos_iguales", not difs, "; ".join(difs))
        else:
            await chk_toda_tabla_clasificada(conn)
            await chk_id_municipio_completo(conn)
            await chk_sin_377(conn)
            await chk_config_dividida(conn)
            await chk_municipio_base(conn)
            await chk_unicos_compuestos(conn)
            await chk_lote_limpieza(conn)
            await chk_fk_compuesta_misma_accion(conn)
            if args.solo_lectura:
                print("[-----] numeracion_nueva y fk_compuesta salteados (--solo-lectura)")
            else:
                await chk_numeracion_nueva(conn)
                await chk_compat_codigo_viejo(conn)
                await chk_fk_compuesta(conn)
    fallas = [r for r in RESULTADOS if not r[1]]
    print(f"\n{len(RESULTADOS) - len(fallas)}/{len(RESULTADOS)} OK")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
