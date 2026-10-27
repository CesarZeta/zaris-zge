# -*- coding: utf-8 -*-
"""
Smoke in-process — alta de municipios y estado del municipio (IT-01 F4+F5,
PLAN_MULTI_MUNICIPIO_F4_F5.md). Crece tarea a tarea.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_alta_municipio.py [prueba ...]

SOLO LOCAL. Mail en MOCK. Sin argumentos corre todas las pruebas; con nombres, solo esas.
"""
import asyncio
import os
import sys

os.environ.setdefault("ENV_FILE", ".env.local")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
settings.RESEND_API_KEY = ""

from app.core.database import AsyncSessionLocal  # noqa: E402

RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + str(detalle)) if detalle and not ok else ''}")


async def _falla(db, sql: str, params: dict | None = None, texto: str = "") -> tuple[bool, str]:
    """Corre `sql` en un savepoint; True si falló (y, si se da `texto`, si el error lo contiene)."""
    try:
        async with db.begin_nested():
            await db.execute(text(sql), params or {})
        return False, "no falló"
    except DBAPIError as e:
        msg = str(e.orig)
        return (texto in msg) if texto else True, msg[:200]


async def _escalar(db, sql: str, params: dict | None = None):
    return (await db.execute(text(sql), params or {})).scalar()


# ── Tarea 4 ───────────────────────────────────────────────────────────────────────────────────

async def test_base_f4() -> None:
    print("\ntest_base_f4")
    async with AsyncSessionLocal() as db:
        for tabla in ("paises", "municipio_modulo", "usuario_invitacion", "municipio_tarea"):
            check(f"existe la tabla {tabla}", await _escalar(db, "SELECT to_regclass(:t) IS NOT NULL",
                                                             {"t": f"public.{tabla}"}))
        cols = {r[0] for r in (await db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'municipios'"))).all()}
        for c in ("estado", "fue_produccion", "estado_antes_baja", "max_usuarios_activos", "id_provincia",
                  "id_partido"):
            check(f"municipios.{c}", c in cols)
        check("area.es_sistema", await _escalar(db,
              "SELECT count(*) FROM information_schema.columns WHERE table_name = 'area' AND column_name = 'es_sistema'") == 1)
        check("municipio_tabla_clase.grupo", await _escalar(db,
              "SELECT count(*) FROM information_schema.columns WHERE table_name = 'municipio_tabla_clase' "
              "AND column_name = 'grupo'") == 1)
        if "estado" not in cols:
            return
        base = (await db.execute(text(
            "SELECT m.estado, p.nombre FROM municipios m LEFT JOIN provincias p USING (id_provincia) "
            "WHERE m.direccion_base"))).one()
        check("el municipio base está en demo con provincia Buenos Aires", tuple(base) == ("demo", "Buenos Aires"), base)
        malos = (await db.execute(text(
            "SELECT id_municipio, estado, activo FROM municipios WHERE NOT activo AND estado <> 'baja' "
            "OR estado = 'baja' AND activo"))).all()
        check("inactivo <=> baja", not malos, malos)
        check("6 áreas de sistema en el municipio base", await _escalar(db,
              "SELECT count(*) FROM area a JOIN municipios m USING (id_municipio) "
              "WHERE m.direccion_base AND a.es_sistema AND a.activo") == 6)
        n_mod = await _escalar(db, "SELECT count(*) FROM modulos WHERE activo")
        n_mm = await _escalar(db, "SELECT count(*) FROM municipio_modulo mm JOIN municipios m USING (id_municipio) "
                                  "WHERE m.direccion_base AND mm.habilitado")
        check("municipio_modulo del base = módulos activos", n_mod == n_mm, f"{n_mm} de {n_mod}")
        sin = (await db.execute(text(
            "SELECT tabla FROM municipio_tabla_clase WHERE clase <> 'global' AND grupo IS NULL"))).scalars().all()
        check("toda tabla no global tiene grupo", not sin, sin)
        check("paises: AR habilitado, VE no", await _escalar(db,
              "SELECT string_agg(codigo_pais || ':' || habilitado_para_alta, ',' ORDER BY codigo_pais) FROM paises")
              == "AR:true,VE:false")


async def test_triggers_f4() -> None:
    print("\ntest_triggers_f4")
    async with AsyncSessionLocal() as db:
        if await _escalar(db, "SELECT to_regclass('public.paises') IS NULL"):
            check("las tablas de F4 existen", False)
            return
        try:
            area = await _escalar(db, "SELECT id_area FROM area WHERE es_sistema LIMIT 1")
            ok, d = await _falla(db, "UPDATE area SET activo = false WHERE id_area = :a", {"a": area},
                                 "Es un área fija del sistema")
            check("un área de sistema no se da de baja", ok, d)
            prov = await _escalar(db, "SELECT id_provincia FROM provincias WHERE nombre = 'Buenos Aires'")
            ok, d = await _falla(db, "INSERT INTO municipios (nombre, codigo_pais, estado) VALUES ('M1','AR','modelo'),"
                                     "('M2','AR','modelo')", texto="uq_municipio_modelo")
            check("un solo municipio modelo", ok, d)
            ok, d = await _falla(db, "INSERT INTO municipios (nombre, codigo_pais, estado) "
                                     "VALUES ('Sin prov', 'AR', 'puesta_en_marcha')")
            check("puesta_en_marcha sin provincia falla", ok, d)
            mid = await _escalar(db, "INSERT INTO municipios (nombre, codigo_pais, estado, id_provincia, codigo_corto, "
                                     "subdominio) VALUES ('Prueba triggers', 'AR', 'puesta_en_marcha', :p, 'PTR', "
                                     "'prueba-triggers') RETURNING id_municipio", {"p": prov})
            await db.execute(text("UPDATE municipios SET estado = 'produccion' WHERE id_municipio = :m"), {"m": mid})
            check("pasar a produccion marca fue_produccion", await _escalar(db,
                  "SELECT fue_produccion FROM municipios WHERE id_municipio = :m", {"m": mid}) is True)
            await db.execute(text("UPDATE municipios SET estado = 'puesta_en_marcha', fue_produccion = false "
                                  "WHERE id_municipio = :m"), {"m": mid})
            check("fue_produccion no vuelve a false", await _escalar(db,
                  "SELECT fue_produccion FROM municipios WHERE id_municipio = :m", {"m": mid}) is True)
            await db.execute(text("UPDATE municipios SET estado = 'baja' WHERE id_municipio = :m"), {"m": mid})
            fila = (await db.execute(text("SELECT activo, estado_antes_baja FROM municipios WHERE id_municipio = :m"),
                                     {"m": mid})).one()
            check("baja pone activo = false y recuerda el estado anterior",
                  tuple(fila) == (False, "puesta_en_marcha"), fila)
            await db.execute(text("UPDATE municipios SET estado = 'puesta_en_marcha' WHERE id_municipio = :m"),
                             {"m": mid})
            check("reactivar pone activo = true", await _escalar(db,
                  "SELECT activo FROM municipios WHERE id_municipio = :m", {"m": mid}) is True)
            ok, d = await _falla(db, "UPDATE municipios SET codigo_pais = 'VE' WHERE id_municipio = :m", {"m": mid},
                                 "provincia")
            check("la provincia tiene que ser del país del municipio", ok, d)
        finally:
            await db.rollback()


async def test_acciones_super() -> None:
    print("\ntest_acciones_super")
    from app.services.accesos_super import ACCIONES, registrar_acceso_super
    nuevas = {"municipio_alta", "municipio_estado", "municipio_modulos", "exportacion", "vaciado",
              "super_alta", "super_baja"}
    check("ACCIONES incluye las de F4", nuevas <= set(ACCIONES), nuevas - set(ACCIONES))
    async with AsyncSessionLocal() as db:
        uid = await _escalar(db, "SELECT id_usuario FROM usuarios ORDER BY nivel_acceso, id_usuario LIMIT 1")
        antes = await _escalar(db, "SELECT coalesce(max(id_super_admin_acceso), 0) FROM super_admin_acceso")
    try:
        await registrar_acceso_super(id_usuario=uid, accion="vaciado", id_municipio=None, detalle="smoke F4")
    except Exception as e:  # el 503 de la API, si el CHECK lo rechaza
        check("registrar_acceso_super acepta vaciado", False, repr(e)[:200])
        return
    async with AsyncSessionLocal() as db:
        check("registrar_acceso_super acepta vaciado", await _escalar(db,
              "SELECT count(*) FROM super_admin_acceso WHERE id_super_admin_acceso > :a AND accion = 'vaciado'",
              {"a": antes}) == 1)


PRUEBAS = {f.__name__: f for f in (test_base_f4, test_triggers_f4, test_acciones_super)}


async def main(nombres: list[str]) -> int:
    for nombre in nombres or PRUEBAS:
        await PRUEBAS[nombre]()
    fallas = [r for r in RES if not r[1]]
    print(f"\nRESULTADO: {len(RES) - len(fallas)} OK / {len(fallas)} FAIL")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
