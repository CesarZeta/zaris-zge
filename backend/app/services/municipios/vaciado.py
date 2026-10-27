"""
Vaciado de datos de un municipio por grupos (IT-01 F4+F5, Tarea 16; spec §4.7).

Se borran las filas del municipio de las tablas de los grupos elegidos y lo que las referencia (el
«arrastre», calculado con las FK, no con una lista a mano): una fila que apunta a una borrada se borra
si es operativa o si su columna no admite nulo; si no, se desvincula (p. ej. `usuarios.id_ciudadano`
cuando no se eligió el grupo usuarios). Nunca se tocan las tablas globales, el grupo configuración,
las áreas fijas ni el administrador principal (el primer nivel 1 del municipio) con su agente, su
ficha, su subárea y sus filas de cuenta (segundo factor, módulos, invitaciones).

Todo en una transacción con `pg_advisory_xact_lock(id_municipio)`. Los objetos de Storage de los
adjuntos se leen antes de borrar las filas y se borran después del commit (si la transacción falla,
los archivos siguen). Solo en `puesta_en_marcha` o `demo` y si el municipio nunca estuvo en producción.
"""
import logging
import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.municipios.constantes import ESTADOS_VACIABLES

logger = logging.getLogger("zaris.municipios")

GRUPOS_VACIABLES = ("operativo", "contactos", "maestros", "usuarios")
NO_VACIABLE = "Este municipio está o estuvo en producción: sus datos no se pueden vaciar."
CONFIRMAR = "Escribí el nombre del municipio para confirmar."
EN_CURSO = "Ya hay un vaciado en curso para este municipio."

# (tabla, columna del bucket o bucket fijo, columna de la ruta). `None` en el bucket = el de adjuntos.
_ARCHIVOS = (
    ("reclamo_adjuntos", "storage_bucket", "storage_path"),
    ("ot_adjuntos", "storage_bucket", "storage_path"),
    ("tramite_documento", "'tramites-documentos'", "storage_path"),
    ("ciudadanos", None, "foto_path"),
)
_PREFIJO_FOTO_USUARIO = "/storage/v1/object/public/config-assets/"


@dataclass
class _Fk:
    hija: str
    col: str
    padre: str
    ref: str
    nulo_ok: bool
    al_borrar: str  # a (no action) | r (restrict) | c (cascade)


@dataclass
class Plan:
    borrar: dict[str, set] = field(default_factory=dict)
    desvincular: dict[tuple[str, str], set] = field(default_factory=dict)
    orden: list[str] = field(default_factory=list)
    cortes: list[tuple[str, str]] = field(default_factory=list)  # FK anulables que se cortan para un ciclo


async def validar(db: AsyncSession, id_municipio: int, grupos: set[str], confirmacion: str | None = None,
                  bloquear: bool = False) -> str:
    """Guardas comunes del plan y del vaciado. Devuelve el nombre del municipio."""
    if not grupos or not grupos <= set(GRUPOS_VACIABLES):
        raise HTTPException(422, f"Grupos a vaciar: alguno de {', '.join(GRUPOS_VACIABLES)}")
    m = (await db.execute(text(
        "SELECT nombre, estado, fue_produccion FROM municipios WHERE id_municipio = :m"
        + (" FOR UPDATE" if bloquear else "")), {"m": id_municipio})).first()
    if m is None:
        raise HTTPException(404, "Municipio no encontrado")
    if m.estado not in ESTADOS_VACIABLES or m.fue_produccion:
        raise HTTPException(409, NO_VACIABLE)
    if confirmacion is not None and confirmacion.strip() != m.nombre:
        raise HTTPException(422, CONFIRMAR)
    return m.nombre


async def _metadatos(db: AsyncSession) -> tuple[dict[str, str], dict[str, str], list[_Fk]]:
    grupos = {r.tabla: r.grupo for r in (await db.execute(text("""
        SELECT t.tabla, t.grupo FROM municipio_tabla_clase t
         WHERE t.clase IN ('catalogo', 'operativo', 'mixta') AND to_regclass('public.' || t.tabla) IS NOT NULL
           AND EXISTS (SELECT 1 FROM information_schema.columns c WHERE c.table_schema = 'public'
                          AND c.table_name = t.tabla AND c.column_name = 'id_municipio')"""))).all()}
    pks = {r.tabla: r.pk for r in (await db.execute(text("""
        SELECT c.relname AS tabla, a.attname AS pk FROM pg_index i
          JOIN pg_class c ON c.oid = i.indrelid JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
         WHERE i.indisprimary AND i.indnatts = 1 AND c.relnamespace = 'public'::regnamespace"""))).all()}
    # Una fila por par de columnas de cada FK, sin la de id_municipio de las compuestas (fkm_*).
    filas = (await db.execute(text("""
        SELECT ch.relname AS hija, ac.attname AS col, pa.relname AS padre, ap.attname AS ref,
               NOT ac.attnotnull AS nulo_ok, c.confdeltype::text AS al_borrar
          FROM pg_constraint c
          JOIN pg_class ch ON ch.oid = c.conrelid JOIN pg_class pa ON pa.oid = c.confrelid
          CROSS JOIN LATERAL unnest(c.conkey, c.confkey) AS k(hk, pk)
          JOIN pg_attribute ac ON ac.attrelid = c.conrelid AND ac.attnum = k.hk
          JOIN pg_attribute ap ON ap.attrelid = c.confrelid AND ap.attnum = k.pk
         WHERE c.contype = 'f' AND ch.relnamespace = 'public'::regnamespace
           AND c.confdeltype IN ('a', 'r', 'c') AND ac.attname <> 'id_municipio'"""))).all()
    fks = {(f.hija, f.col, f.padre): _Fk(f.hija, f.col, f.padre, f.ref, f.nulo_ok, f.al_borrar) for f in filas
           if f.padre in grupos and f.hija in grupos}
    return grupos, pks, list(fks.values())


async def _ids(db: AsyncSession, tabla: str, pk: str, where: str, params: dict) -> set:
    return {r[0] for r in (await db.execute(text(f'SELECT "{pk}" FROM "{tabla}" WHERE {where}'), params)).all()}


async def _protegidos(db: AsyncSession, id_municipio: int, grupos: dict[str, str], pks: dict[str, str],
                      fks: list[_Fk]) -> dict[str, set]:
    p: dict[str, set] = {t: set() for t in grupos}
    admin = (await db.execute(text("""
        SELECT id_usuario, id_ciudadano, id_subarea FROM usuarios
         WHERE id_municipio = :m AND nivel_acceso = 1 ORDER BY fecha_alta, id_usuario LIMIT 1"""),
        {"m": id_municipio})).first()
    p["area"] = await _ids(db, "area", "id_area", "id_municipio = :m AND es_sistema", {"m": id_municipio})
    if admin:
        p["usuarios"] = {admin.id_usuario}
        p["agentes"] = await _ids(db, "agentes", "id_agente", "id_usuario = :u", {"u": admin.id_usuario})
        if admin.id_ciudadano:
            p["ciudadanos"] = {admin.id_ciudadano}
        subareas = {admin.id_subarea} if admin.id_subarea else set()
        subareas |= {r[0] for r in (await db.execute(text(
            "SELECT id_subarea FROM agentes WHERE id_usuario = :u AND id_subarea IS NOT NULL"),
            {"u": admin.id_usuario})).all()}
        p["subarea"] = subareas
        # Las filas de su cuenta (segundo factor, módulos, invitaciones, accesos) quedan con él.
        for fk in fks:
            if fk.padre in ("usuarios", "agentes") and grupos.get(fk.hija) == "usuarios" and fk.hija not in (
                    "usuarios", "agentes"):
                p[fk.hija] |= await _ids(db, fk.hija, pks[fk.hija], f'"{fk.col}" = ANY(:ids)',
                                         {"ids": list(p[fk.padre])})
    return p


async def calcular(db: AsyncSession, id_municipio: int, grupos_elegidos: set[str]) -> Plan:
    grupos, pks, fks = await _metadatos(db)
    protegidos = await _protegidos(db, id_municipio, grupos, pks, fks)
    elegidas = [t for t, g in grupos.items() if g in grupos_elegidos and t in pks]
    base: dict[str, set] = {}
    for t in elegidas:
        base[t] = await _ids(db, t, pks[t], "id_municipio = :m", {"m": id_municipio})

    # Punto fijo: el arrastre puede proteger padres (una fila protegida que los necesita) y eso cambia
    # lo que se borra; se recalcula hasta que nada cambie.
    while True:
        borrar = {t: ids - protegidos.get(t, set()) for t, ids in base.items()}
        desvincular: dict[tuple[str, str], set] = {}
        cambio_proteccion = False
        pendiente = True
        while pendiente:
            pendiente = False
            for fk in fks:
                padres = borrar.get(fk.padre)
                if not padres or fk.hija not in pks:
                    continue
                valores = list(padres) if fk.ref == pks[fk.padre] else [r[0] for r in (await db.execute(text(
                    f'SELECT "{fk.ref}" FROM "{fk.padre}" WHERE "{pks[fk.padre]}" = ANY(:ids)'), {"ids": list(padres)})).all()]
                hijas = await _ids(db, fk.hija, pks[fk.hija], f'"{fk.col}" = ANY(:v)', {"v": valores})
                hijas -= borrar.get(fk.hija, set())
                if fk.hija == fk.padre:
                    hijas -= padres
                if not hijas:
                    continue
                prot = hijas & protegidos.get(fk.hija, set())
                libres = hijas - prot
                if prot:
                    if fk.nulo_ok and fk.al_borrar != "c":
                        desvincular.setdefault((fk.hija, fk.col), set()).update(prot)
                    else:
                        # La fila protegida necesita a su padre: el padre también queda.
                        refs = {r[0] for r in (await db.execute(text(
                            f'SELECT "{fk.col}" FROM "{fk.hija}" WHERE "{pks[fk.hija]}" = ANY(:ids)'),
                            {"ids": list(prot)})).all()}
                        nuevos = await _ids(db, fk.padre, pks[fk.padre], f'"{fk.ref}" = ANY(:v)', {"v": list(refs)})
                        if not nuevos <= protegidos.setdefault(fk.padre, set()):
                            protegidos[fk.padre] |= nuevos
                            cambio_proteccion = True
                if libres:
                    if fk.al_borrar == "c" or not fk.nulo_ok or grupos.get(fk.hija) == "operativo":
                        borrar.setdefault(fk.hija, set()).update(libres)
                        pendiente = True
                    else:
                        desvincular.setdefault((fk.hija, fk.col), set()).update(libres)
            if cambio_proteccion:
                break
        if not cambio_proteccion:
            break

    borrar = {t: ids for t, ids in borrar.items() if ids}
    desvincular = {k: ids - borrar.get(k[0], set()) for k, ids in desvincular.items()}
    plan = Plan(borrar=borrar, desvincular={k: v for k, v in desvincular.items() if v})
    _ordenar(plan, fks)
    return plan


def _ordenar(plan: Plan, fks: list[_Fk]) -> None:
    """Hijas antes que padres. Un ciclo se corta anulando una FK que lo admite."""
    pendientes = set(plan.borrar)
    aristas = {(fk.hija, fk.padre, fk.col, fk.nulo_ok) for fk in fks
               if fk.hija in pendientes and fk.padre in pendientes and fk.hija != fk.padre}
    while pendientes:
        libres = sorted(t for t in pendientes if not any(p == t and h in pendientes for h, p, _, _ in aristas))
        if libres:
            plan.orden += libres
            pendientes -= set(libres)
            continue
        corte = next(((h, p, c, n) for h, p, c, n in sorted(aristas)
                      if n and h in pendientes and p in pendientes), None)
        if corte is None:
            raise RuntimeError(f"ciclo de FK NOT NULL entre {sorted(pendientes)}")
        plan.cortes.append((corte[0], corte[2]))
        aristas.discard(corte)


def resumen(plan: Plan) -> list[dict]:
    salida = [{"tabla": t, "filas": len(plan.borrar[t]), "accion": "borrar"} for t in plan.orden]
    salida += [{"tabla": f"{t}.{c}", "filas": len(ids), "accion": "desvincular"}
               for (t, c), ids in sorted(plan.desvincular.items())]
    return salida


async def _archivos(db: AsyncSession, plan: Plan, pks: dict[str, str]) -> list[tuple[str, str]]:
    """Rutas de los archivos de las filas que se borran, salvo las que usa una fila que queda."""
    salida: list[tuple[str, str]] = []
    for tabla, col_bucket, col_ruta in _ARCHIVOS:
        ids = plan.borrar.get(tabla)
        if not ids:
            continue
        bucket_sql = col_bucket or f"'{settings.SUPABASE_ADJUNTOS_BUCKET}'"
        filas = (await db.execute(text(f"""
            SELECT DISTINCT {bucket_sql} AS bucket, x."{col_ruta}" AS ruta FROM "{tabla}" x
             WHERE x."{pks[tabla]}" = ANY(:ids) AND x."{col_ruta}" IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM "{tabla}" y WHERE y."{col_ruta}" = x."{col_ruta}"
                                  AND NOT (y."{pks[tabla]}" = ANY(:ids)))"""), {"ids": list(ids)})).all()
        salida += [(f.bucket, f.ruta) for f in filas]
    ids = plan.borrar.get("usuarios")
    if ids:
        for (url,) in (await db.execute(text(
                "SELECT foto_url FROM usuarios WHERE id_usuario = ANY(:ids) AND foto_url IS NOT NULL"),
                {"ids": list(ids)})).all():
            if _PREFIJO_FOTO_USUARIO in url:
                salida.append(("config-assets", url.split(_PREFIJO_FOTO_USUARIO, 1)[1]))
    return salida


async def _triggers_de_solo_agregar(db: AsyncSession, tablas: list[str]) -> list[tuple[str, str]]:
    """Triggers que hacen de una tabla un registro de solo agregar: el vaciado los apaga dentro de su
    transacción (vuelven solos si se revierte)."""
    return [(r.tabla, r.tgname) for r in (await db.execute(text("""
        SELECT c.relname AS tabla, t.tgname FROM pg_trigger t
          JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid
         WHERE NOT t.tgisinternal AND c.relname = ANY(:t) AND p.prosrc ILIKE '%append-only%'"""),
        {"t": tablas})).all()]


async def vaciar(db: AsyncSession, id_municipio: int, grupos: set[str]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Ejecuta el vaciado en la transacción de `db` (el llamador commitea). Devuelve el resumen y los
    archivos a borrar después del commit."""
    from app.services.municipios.alta import resembrar_claves_por_id
    await db.execute(text("SELECT pg_advisory_xact_lock(:m)"), {"m": id_municipio})
    await validar(db, id_municipio, grupos, bloquear=True)
    _, pks, _ = await _metadatos(db)
    plan = await calcular(db, id_municipio, grupos)
    archivos = await _archivos(db, plan, pks)
    apagados = await _triggers_de_solo_agregar(db, list(plan.borrar) + [t for t, _ in plan.desvincular])
    for tabla, trig in apagados:
        await db.execute(text(f'ALTER TABLE "{tabla}" DISABLE TRIGGER "{trig}"'))
    for (tabla, col), ids in plan.desvincular.items():
        await db.execute(text(f'UPDATE "{tabla}" SET "{col}" = NULL WHERE "{pks[tabla]}" = ANY(:ids)'),
                         {"ids": list(ids)})
    for tabla, col in plan.cortes:
        await db.execute(text(f'UPDATE "{tabla}" SET "{col}" = NULL WHERE "{pks[tabla]}" = ANY(:ids)'),
                         {"ids": list(plan.borrar[tabla])})
    for tabla in plan.orden:
        await db.execute(text(f'DELETE FROM "{tabla}" WHERE "{pks[tabla]}" = ANY(:ids)'),
                         {"ids": list(plan.borrar[tabla])})
    for tabla, trig in apagados:
        await db.execute(text(f'ALTER TABLE "{tabla}" ENABLE TRIGGER "{trig}"'))
    await resembrar_claves_por_id(db, id_municipio)
    return resumen(plan), archivos


async def ejecutar_vaciado(id_tarea: uuid.UUID, id_municipio: int, grupos: set[str], id_super: int) -> None:
    """Segundo plano: exporta y, solo si la exportación terminó ok, vacía. El estado queda en la tarea."""
    from app.services.accesos_super import registrar_acceso_super_en
    from app.services.municipios.exportacion import crear_tarea, ejecutar_exportacion, marcar_tarea
    async with AsyncSessionLocal() as db:
        id_exp = await crear_tarea(db, id_municipio, "exportacion", id_super, {"previa_al_vaciado": str(id_tarea)})
        await db.commit()
    await marcar_tarea(id_tarea, "corriendo", detalle={"grupos": sorted(grupos), "exportacion": str(id_exp)})
    if not await ejecutar_exportacion(id_exp, id_municipio):
        await marcar_tarea(id_tarea, "error", detalle={"grupos": sorted(grupos), "exportacion": str(id_exp),
                                                       "error": "la exportación previa falló: no se vació nada"})
        return
    try:
        async with AsyncSessionLocal() as db:
            plan, archivos = await vaciar(db, id_municipio, grupos)
            await registrar_acceso_super_en(
                db, id_usuario=id_super, accion="vaciado", id_municipio=id_municipio,
                detalle=f"vaciado de {', '.join(sorted(grupos))}: {sum(p['filas'] for p in plan if p['accion'] == 'borrar')} filas")
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("vaciado del municipio %s", id_municipio)
        await marcar_tarea(id_tarea, "error", detalle={"grupos": sorted(grupos), "exportacion": str(id_exp),
                                                       "error": str(exc)[:500]})
        return
    no_borrados = 0
    for bucket, ruta in archivos:
        try:
            await storage.borrar_objeto(ruta, bucket=bucket)
        except Exception:  # noqa: BLE001
            no_borrados += 1
            logger.exception("vaciado %s: no se pudo borrar %s/%s", id_municipio, bucket, ruta)
    await marcar_tarea(id_tarea, "ok", detalle={"grupos": sorted(grupos), "exportacion": str(id_exp), "plan": plan,
                                                "archivos": len(archivos), "archivos_no_borrados": no_borrados})
