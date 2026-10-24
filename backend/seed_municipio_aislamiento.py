# -*- coding: utf-8 -*-
"""
Municipio de aislamiento para los smokes de IT-01 (multi-municipio). SOLO LOCAL.
Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md, Tarea 5.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python seed_municipio_aislamiento.py

Crea el municipio «AISLAB Municipio de Aislamiento» (código AIS, subdominio `aislamiento`) con al
menos una fila de cada tabla catalogo/operativo que tenga datos en el municipio 1, clonando filas
reales del municipio 1: cada FK hacia una tabla del municipio se re-mapea clonando primero al padre
(recursivo), y las referencias a los recursos principales van a las anclas de B (área, subárea,
usuario admin, agente, vecino, empresa, espacio, equipo). Todo texto libre lleva la marca AISLAB:
si una respuesta del municipio 1 la contiene, es una filtración (smoke_aislamiento.py).

Cuentas (clave dev 123456): admin.b@aislamiento.test (nivel 1), super.b@aislamiento.test (nivel 2),
doble@aislamiento.test en el municipio 1 (nivel 5) y en B (nivel 1). Vecino de B: DNI 97000001.
Idempotente: si el municipio ya existe, solo imprime sus ids.
"""
import asyncio
import os
import re
import sys
import uuid
from typing import Any, Optional

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import asyncpg  # noqa: E402
import bcrypt  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

MARCA = "AISLAB"
SUBDOMINIO = "aislamiento"
CLAVE_DEV = "123456"
DNI_VECINO_B = "97000001"

# Texto libre que se marca (columnas con CHECK quedan afuera: estados, canales, prioridades…).
TEXTO_LIBRE = re.compile(
    r"^(nombre|apellido|descripcion|direccion\w*|domicilio\w*|observacion\w*|detalle\w*|titulo|mensaje|"
    r"comentario\w*|motivo\w*|texto|nota|notas|resolucion|razon_social|nombre_fantasia|asunto|contenido|"
    r"cuerpo|calle|lugar)$")
# Únicos globales de una columna que se regeneran al clonar (no son FK).
NUMEROS_POR_TRIGGER = {"nro_reclamo", "nro_ot", "numero_operativo"}
# Tablas que el seed no necesita clonar: las cubre la numeración o no aportan al barrido.
SIN_COBERTURA = {"numerador_municipio"}


def _dsn() -> str:
    s = settings
    return f"postgresql://{s.POSTGRES_USER}:{s.POSTGRES_PASSWORD}@{s.POSTGRES_SERVER}:{s.POSTGRES_PORT}/{s.POSTGRES_DB}"


def _dv_modulo11(diez: str) -> int:
    """Dígito verificador con la misma regla que schemas/buc.py::_validar_modulo11."""
    suma = sum(int(d) * m for d, m in zip(diez, [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]))
    resto = suma % 11
    return 0 if resto == 0 else (9 if resto == 1 else 11 - resto)


def cuil_valido(prefijo: str, dni: str) -> str:
    base = f"{prefijo}{int(dni):08d}"
    return base + str(_dv_modulo11(base))


class Clonador:
    def __init__(self, conn: asyncpg.Connection, id_mun: int):
        self.conn = conn
        self.B = id_mun
        self.mapa: dict[tuple[str, int], int] = {}
        self.anclas: dict[str, int] = {}
        self._en_curso: list[tuple[str, int]] = []
        self._meta: dict[str, dict] = {}
        self._clases: dict[str, str] = {}

    async def cargar_clases(self) -> None:
        rows = await self.conn.fetch("SELECT tabla, clase FROM municipio_tabla_clase")
        self._clases = {r["tabla"]: r["clase"] for r in rows}

    def segmentada(self, tabla: str) -> bool:
        return self._clases.get(tabla) in ("catalogo", "operativo")

    async def meta(self, tabla: str) -> dict:
        if tabla in self._meta:
            return self._meta[tabla]
        cols = await self.conn.fetch("""
            SELECT a.attname AS col, format_type(a.atttypid, a.atttypmod) AS tipo, a.attnotnull AS no_nulo,
                   CASE WHEN a.atttypmod > 4 AND t.typname IN ('varchar', 'bpchar') THEN a.atttypmod - 4 END AS largo
              FROM pg_attribute a JOIN pg_type t ON t.oid = a.atttypid
             WHERE a.attrelid = $1::regclass AND a.attnum > 0 AND NOT a.attisdropped
             ORDER BY a.attnum""", f"public.{tabla}")
        pk = await self.conn.fetch("""
            SELECT a.attname FROM pg_index i
              JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
             WHERE i.indrelid = $1::regclass AND i.indisprimary""", f"public.{tabla}")
        fks = await self.conn.fetch("""
            SELECT (SELECT attname FROM pg_attribute WHERE attrelid = c.conrelid  AND attnum = c.conkey[1])  AS col,
                   pa.relname AS padre,
                   (SELECT attname FROM pg_attribute WHERE attrelid = c.confrelid AND attnum = c.confkey[1]) AS ref
              FROM pg_constraint c JOIN pg_class pa ON pa.oid = c.confrelid
             WHERE c.conrelid = $1::regclass AND c.contype = 'f' AND array_length(c.conkey, 1) = 1""",
            f"public.{tabla}")
        checks = await self.conn.fetch("""
            SELECT DISTINCT a.attname FROM pg_constraint c
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
             WHERE c.conrelid = $1::regclass AND c.contype = 'c'""", f"public.{tabla}")
        unicos = await self.conn.fetch("""
            SELECT a.attname FROM pg_index i
              JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
             WHERE i.indrelid = $1::regclass AND i.indisunique AND NOT i.indisprimary AND i.indnatts = 1""",
            f"public.{tabla}")
        m = {
            "cols": {r["col"]: r for r in cols},
            "pk": [r["attname"] for r in pk],
            "fks": {r["col"]: (r["padre"], r["ref"]) for r in fks if r["col"] != "id_municipio"},
            "checks": {r["attname"] for r in checks},
            "unicos": {r["attname"] for r in unicos},
        }
        self._meta[tabla] = m
        return m

    def _marcar(self, valor: str, largo: Optional[int]) -> str:
        nuevo = f"{MARCA} {valor}"
        return nuevo[:largo] if largo else nuevo

    async def _pk_padre(self, padre: str, ref: str, valor: Any) -> Optional[int]:
        mp = await self.meta(padre)
        pk = mp["pk"][0]
        if ref == pk:
            return valor
        return await self.conn.fetchval(f'SELECT "{pk}" FROM "{padre}" WHERE "{ref}" = $1', valor)

    async def clonar(self, tabla: str, id_origen: int, cambios: Optional[dict] = None,
                     copia_nueva: bool = False) -> int:
        """copia_nueva=True: otra copia de una fila ya clonada (p. ej. dos cuentas desde el mismo
        usuario de origen); no reemplaza el mapeo de la primera."""
        clave = (tabla, id_origen)
        if clave in self.mapa and not copia_nueva:
            return self.mapa[clave]
        m = await self.meta(tabla)
        if len(m["pk"]) != 1:
            raise RuntimeError(f"{tabla}: PK compuesta, clonar a mano")
        pk = m["pk"][0]
        fila = await self.conn.fetchrow(f'SELECT * FROM "{tabla}" WHERE "{pk}" = $1', id_origen)
        if fila is None:
            raise RuntimeError(f"{tabla} {id_origen} no existe")
        cambios = dict(cambios or {})
        vals = dict(fila)
        vals.pop(pk)
        vals["id_municipio"] = self.B

        for col, (padre, ref) in m["fks"].items():
            if col in cambios or vals.get(col) is None:
                continue
            nulo_ok = not m["cols"][col]["no_nulo"]
            if padre in self.anclas:
                # Una FK única (agentes.id_usuario, usuarios.id_ciudadano…) no puede apuntar dos veces al ancla.
                vals[col] = None if (col in m["unicos"] and nulo_ok) else self.anclas[padre]
            elif padre == "usuarios":
                vals[col] = None if nulo_ok else self.anclas.get("usuarios")
            elif self.segmentada(padre):
                if padre == tabla and nulo_ok:
                    vals[col] = None  # auto-referencia (reclamo padre, etc.): no se arrastra
                    continue
                id_padre = await self._pk_padre(padre, ref, vals[col])
                if (padre, id_padre) in self._en_curso:
                    if nulo_ok:
                        vals[col] = None  # ciclo entre tablas (A → B → A): se corta en la columna nullable
                        continue
                    raise RuntimeError(f"ciclo de FK NOT NULL: {self._en_curso + [(tabla, id_origen)]}")
                self._en_curso.append(clave)
                try:
                    nuevo = await self.clonar(padre, id_padre)
                finally:
                    self._en_curso.remove(clave)
                vals[col] = nuevo if ref == (await self.meta(padre))["pk"][0] else \
                    await self.conn.fetchval(f'SELECT "{ref}" FROM "{padre}" WHERE "{(await self.meta(padre))["pk"][0]}" = $1', nuevo)

        for col, valor in list(vals.items()):
            info = m["cols"][col]
            if col in cambios or valor is None:
                continue
            if col in NUMEROS_POR_TRIGGER:
                vals[col] = None
            elif col in m["unicos"] and col not in m["fks"]:
                if info["tipo"] == "uuid":
                    vals[col] = uuid.uuid4()
                elif isinstance(valor, str):
                    vals[col] = (f"AIS-{valor}")[: info["largo"]] if info["largo"] else f"AIS-{valor}"
            elif isinstance(valor, str) and TEXTO_LIBRE.match(col) and col not in m["checks"] \
                    and info["tipo"].startswith(("character varying", "text", "character(")):
                vals[col] = self._marcar(valor, info["largo"])

        vals.update(cambios)
        cols = list(vals)
        sql = (f'INSERT INTO "{tabla}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) '
               f'VALUES ({", ".join(f"${i}" for i in range(1, len(cols) + 1))}) RETURNING "{pk}"')
        try:
            nuevo = await self.conn.fetchval(sql, *[vals[c] for c in cols])
        except Exception as exc:
            raise RuntimeError(f"clonando {tabla} {id_origen}: {exc}") from exc
        if clave not in self.mapa:
            self.mapa[clave] = nuevo
        return nuevo

    async def clonar_hijos(self, tabla: str, col_padre: str, id_padre_origen: int,
                           limite: Optional[int] = None, cambios: Optional[dict] = None) -> list[int]:
        pk = (await self.meta(tabla))["pk"][0]
        rows = await self.conn.fetch(
            f'SELECT "{pk}" FROM "{tabla}" WHERE "{col_padre}" = $1 AND id_municipio <> $2 ORDER BY "{pk}"'
            + (f" LIMIT {int(limite)}" if limite else ""), id_padre_origen, self.B)
        return [await self.clonar(tabla, r[pk], cambios) for r in rows]

    async def uno(self, sql: str, *args) -> Optional[int]:
        return await self.conn.fetchval(sql, *args)


async def ids_aislamiento(db) -> dict[str, int]:
    """Tabla → un id del municipio de aislamiento (y 'municipio' → su id). `db`: AsyncSession o
    AsyncConnection de SQLAlchemy. La usa smoke_aislamiento.py; busca por subdominio, no guarda archivos."""
    id_b = (await db.execute(text("SELECT id_municipio FROM municipios WHERE subdominio = :s"),
                             {"s": SUBDOMINIO})).scalar()
    if id_b is None:
        raise RuntimeError("No existe el municipio de aislamiento: correr seed_municipio_aislamiento.py")
    tablas = (await db.execute(text("""
        SELECT m.tabla, a.attname AS pk
          FROM municipio_tabla_clase m
          JOIN pg_index i ON i.indrelid = to_regclass('public.' || quote_ident(m.tabla)) AND i.indisprimary
                         AND i.indnatts = 1
          JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
         WHERE m.clase IN ('catalogo', 'operativo')
         ORDER BY m.tabla"""))).fetchall()
    ids = {"municipio": id_b}
    for t in tablas:
        v = (await db.execute(text(f'SELECT min("{t.pk}") FROM "{t.tabla}" WHERE id_municipio = :b'),
                              {"b": id_b})).scalar()
        if v is not None:
            ids[t.tabla] = v
    return ids


async def asegurar_cuentas_dobles(conn: asyncpg.Connection, B: int, hash_dev: str) -> None:
    """Mismo email (doble@aislamiento.test) en el municipio 1 (nivel 5) y en B (nivel 1): prueba del
    login dentro del municipio de origen. Crea las que falten (el username sí es distinto: el índice
    global viejo de username sigue hasta el lote de limpieza)."""
    subarea_b = await conn.fetchval("SELECT min(id_subarea) FROM subarea WHERE id_municipio = $1", B)
    for username, nombre, nivel, mun, subarea in (
            ("doble.a@aislamiento.test", "Doble Aislamiento (municipio 1)", 5, 1, None),
            ("doble.b@aislamiento.test", f"{MARCA} Doble B", 1, B, subarea_b)):
        if await conn.fetchval("SELECT 1 FROM usuarios WHERE username = $1", username):
            continue
        await conn.execute("""
            INSERT INTO usuarios (nombre, nivel_acceso, username, password_hash, activo, buc_acceso, email,
                                  id_municipio, id_subarea)
            VALUES ($1, $2, $3, $4, TRUE, FALSE, 'doble@aislamiento.test', $5, $6)""",
            nombre, nivel, username, hash_dev, mun, subarea)


async def asegurar_aprobaciones(conn: asyncpg.Connection, B: int) -> None:
    """Aprobación requerida del circuito de B y su instancia en el trámite de B. Se crean a mano
    porque el municipio 1 de local puede no tener ninguna para clonar."""
    tramite = await conn.fetchrow("SELECT id_tramite, id_tipo_tramite_version FROM tramite WHERE id_municipio = $1 "
                                  "ORDER BY id_tramite LIMIT 1", B)
    estado = await conn.fetchval("SELECT min(id_tipo_tramite_estado) FROM tipo_tramite_estado "
                                 "WHERE id_tipo_tramite_version = $1", tramite["id_tipo_tramite_version"])
    req = await conn.fetchval("SELECT min(id_tipo_tramite_aprobacion_requerida) FROM tipo_tramite_aprobacion_requerida "
                              "WHERE id_municipio = $1", B)
    if req is None:
        req = await conn.fetchval("""
            INSERT INTO tipo_tramite_aprobacion_requerida
                (id_tipo_tramite_version, id_tipo_tramite_estado, aprobador_tipo, id_subarea_aprobadora,
                 etiqueta, bloqueante, orden, activo, id_municipio)
            VALUES ($1, $2, 'subarea', (SELECT min(id_subarea) FROM subarea WHERE id_municipio = $3),
                    $4, TRUE, 1, TRUE, $3)
            RETURNING id_tipo_tramite_aprobacion_requerida""",
            tramite["id_tipo_tramite_version"], estado, B, f"{MARCA} aprobación de prueba")
    if not await conn.fetchval("SELECT count(*) FROM tramite_aprobacion WHERE id_municipio = $1", B):
        await conn.execute("""
            INSERT INTO tramite_aprobacion (id_tramite, id_tipo_tramite_aprobacion_requerida, id_tipo_tramite_estado,
                                            estado, comentario, activo, id_municipio)
            VALUES ($1, $2, $3, 'pendiente', $4, TRUE, $5)""",
            tramite["id_tramite"], req, estado, f"{MARCA} comentario de prueba", B)


async def _recurso_b(c: Clonador, tipo: Optional[str]) -> Optional[int]:
    return {"agente": c.anclas.get("agentes"), "espacio": c.anclas.get("espacios_agenda"),
            "equipo": c.anclas.get("equipos")}.get((tipo or "").lower())


async def sembrar(conn: asyncpg.Connection) -> int:
    hash_dev = bcrypt.hashpw(CLAVE_DEV.encode(), bcrypt.gensalt()).decode()
    B = await conn.fetchval("""
        INSERT INTO municipios (nombre, codigo_corto, subdominio, codigo_pais, pais, provincia, activo, direccion_base)
        VALUES ('AISLAB Municipio de Aislamiento', 'AIS', $1, 'AR', 'Argentina', 'Buenos Aires', TRUE, FALSE)
        RETURNING id_municipio""", SUBDOMINIO)
    c = Clonador(conn, B)
    await c.cargar_clases()

    # Anclas: el agente de origen define la subárea (y el área) de B.
    agente_a = await c.uno("""
        SELECT a.id_agente FROM agentes a JOIN subarea s ON s.id_subarea = a.id_subarea
         WHERE a.id_municipio = 1 AND a.activo AND a.id_usuario IS NOT NULL ORDER BY a.id_agente LIMIT 1""")
    subarea_a = await c.uno("SELECT id_subarea FROM agentes WHERE id_agente = $1", agente_a)
    c.anclas["subarea"] = await c.clonar("subarea", subarea_a)
    c.anclas["area"] = await c.uno("SELECT id_area FROM subarea WHERE id_subarea = $1", c.anclas["subarea"])

    admin_a = await c.uno("SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo "
                          "ORDER BY id_usuario LIMIT 1")
    cuenta = dict(password_hash=hash_dev, id_ciudadano=None, activo=True, debe_cambiar_password=False,
                  foto_url=None, token_recovery=None, es_externo=False, fecha_ultimo_login=None,
                  id_subarea=c.anclas["subarea"])
    c.anclas["usuarios"] = await c.clonar("usuarios", admin_a, dict(
        cuenta, email="admin.b@aislamiento.test", username="admin.b@aislamiento.test",
        nombre=f"{MARCA} Admin B", nivel_acceso=1))
    c.anclas["agentes"] = await c.clonar("agentes", agente_a, dict(
        id_usuario=c.anclas["usuarios"], email="admin.b@aislamiento.test", dni="97000101",
        id_subarea=c.anclas["subarea"]))
    super_b = await c.uno("SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 2 AND activo "
                          "ORDER BY id_usuario LIMIT 1") or admin_a
    super_b_id = await c.clonar("usuarios", super_b, dict(
        cuenta, email="super.b@aislamiento.test", username="super.b@aislamiento.test",
        nombre=f"{MARCA} Supervisor B", nivel_acceso=2), copia_nueva=True)
    agente_super_a = await c.uno("SELECT id_agente FROM agentes WHERE id_municipio = 1 AND id_agente <> $1 "
                                 "AND id_usuario IS NOT NULL ORDER BY id_agente LIMIT 1", agente_a)
    await c.clonar("agentes", agente_super_a, dict(
        id_usuario=super_b_id, email="super.b@aislamiento.test", dni="97000102", id_subarea=c.anclas["subarea"]))
    await asegurar_cuentas_dobles(conn, B, hash_dev)

    # Vecino de B con credencial activada, canal preferido y push (inactivo, endpoint inválido).
    vecino_a = await c.uno("""
        SELECT c.id_ciudadano FROM ciudadanos c
          JOIN ciudadano_credencial cc ON cc.id_ciudadano = c.id_ciudadano AND cc.activado
         WHERE c.id_municipio = 1 AND c.activo
         ORDER BY EXISTS (SELECT 1 FROM ciudadano_canal_preferido p WHERE p.id_ciudadano = c.id_ciudadano) DESC,
                  c.id_ciudadano LIMIT 1""")
    c.anclas["ciudadanos"] = await c.clonar("ciudadanos", vecino_a, dict(
        doc_nro=DNI_VECINO_B, cuil=cuil_valido("27", DNI_VECINO_B), email="vecino.b@aislamiento.test",
        nombre=f"{MARCA} Vecina", apellido=f"{MARCA} Prueba", es_funcionario=False))
    await c.clonar_hijos("ciudadano_credencial", "id_ciudadano", vecino_a, 1, dict(
        password_hash=hash_dev, activado=True, activo=True, token_activacion=None, token_recovery=None,
        intentos_fallidos=0, bloqueada_hasta=None, debe_cambiar_password=False))
    await c.clonar_hijos("ciudadano_canal_preferido", "id_ciudadano", vecino_a, 1)
    push_a = await c.uno("SELECT min(id_ciudadano_push_subscription) FROM ciudadano_push_subscription WHERE id_municipio = 1")
    if push_a:
        await c.clonar("ciudadano_push_subscription", push_a, dict(
            id_ciudadano=c.anclas["ciudadanos"], activo=False, endpoint="https://aislamiento.invalid/push/vecino"))
    push_u = await c.uno("SELECT min(id_usuario_push_subscription) FROM usuario_push_subscription WHERE id_municipio = 1")
    if push_u:
        await c.clonar("usuario_push_subscription", push_u, dict(
            id_usuario=c.anclas["usuarios"], activo=False, endpoint="https://aislamiento.invalid/push/usuario"))

    empresa_a = await c.uno("""
        SELECT e.id_empresa FROM empresas e WHERE e.id_municipio = 1
         ORDER BY EXISTS (SELECT 1 FROM ciudadano_empresa ce WHERE ce.id_empresa = e.id_empresa) DESC, e.id_empresa
         LIMIT 1""")
    c.anclas["empresas"] = await c.clonar("empresas", empresa_a, dict(
        cuit=cuil_valido("30", "97000001"), email="empresa.b@aislamiento.test"))
    await c.clonar_hijos("ciudadano_empresa", "id_empresa", empresa_a, 1, dict(id_ciudadano=c.anclas["ciudadanos"]))

    # Espacio y equipo de B (anclas de las referencias polimórficas).
    espacio_a = await c.uno("""
        SELECT id_espacio FROM espacios_agenda WHERE id_municipio = 1 AND activo
         ORDER BY EXISTS (SELECT 1 FROM turnos t WHERE t.id_espacio = espacios_agenda.id_espacio) DESC, id_espacio LIMIT 1""")
    c.anclas["espacios_agenda"] = await c.clonar("espacios_agenda", espacio_a)
    await c.clonar_hijos("espacio_agentes", "id_espacio", espacio_a, 1)
    equipo_a = await c.uno("""
        SELECT e.id_equipo FROM equipos e WHERE e.id_municipio = 1
         ORDER BY EXISTS (SELECT 1 FROM equipo_agentes ea WHERE ea.id_equipo = e.id_equipo) DESC, e.id_equipo LIMIT 1""")
    c.anclas["equipos"] = await c.clonar("equipos", equipo_a)
    await c.clonar_hijos("equipo_agentes", "id_equipo", equipo_a, 1)

    # Reclamo con historial, OT y adjuntos.
    rec_a = await c.uno("""
        SELECT r.id_reclamo FROM reclamos r WHERE r.id_municipio = 1
         ORDER BY EXISTS (SELECT 1 FROM ordenes_trabajo o WHERE o.id_reclamo = r.id_reclamo
                          AND EXISTS (SELECT 1 FROM ot_adjuntos x WHERE x.id_ot = o.id_ot)) DESC,
                  EXISTS (SELECT 1 FROM ordenes_trabajo o WHERE o.id_reclamo = r.id_reclamo) DESC,
                  EXISTS (SELECT 1 FROM reclamo_adjuntos x WHERE x.id_reclamo = r.id_reclamo) DESC,
                  r.id_reclamo DESC LIMIT 1""")
    rec_b = await c.clonar("reclamos", rec_a)
    await c.clonar_hijos("reclamo_historial", "id_reclamo", rec_a, 3)
    await c.clonar_hijos("reclamo_adjuntos", "id_reclamo", rec_a, 1)
    for id_ot_a in [r["id_ot"] for r in await conn.fetch(
            "SELECT id_ot FROM ordenes_trabajo WHERE id_reclamo = $1 ORDER BY id_ot LIMIT 1", rec_a)]:
        await c.clonar("ordenes_trabajo", id_ot_a)
        await c.clonar_hijos("ot_adjuntos", "id_ot", id_ot_a, 1)
    if not await c.uno("SELECT count(*) FROM reclamo_adjuntos WHERE id_municipio = $1", B):
        adj = await c.uno("SELECT min(id_adjunto) FROM reclamo_adjuntos WHERE id_municipio = 1")
        if adj:
            await c.clonar("reclamo_adjuntos", adj, dict(id_reclamo=rec_b))
    if not await c.uno("SELECT count(*) FROM ot_adjuntos WHERE id_municipio = $1", B):
        adj = await c.uno("SELECT min(id_adjunto) FROM ot_adjuntos WHERE id_municipio = 1")
        ot_b = await c.uno("SELECT min(id_ot) FROM ordenes_trabajo WHERE id_municipio = $1", B)
        if adj and ot_b:
            await c.clonar("ot_adjuntos", adj, dict(id_ot=ot_b))

    # Emergencia con log, atención de Guardia y contacto eventual.
    em_a = await c.uno("""
        SELECT e.id_emergencia_evento FROM emergencia_evento e WHERE e.id_municipio = 1
         ORDER BY (e.id_contacto_eventual IS NOT NULL) DESC,
                  EXISTS (SELECT 1 FROM emergencia_atencion x WHERE x.id_emergencia_evento = e.id_emergencia_evento) DESC,
                  e.id_emergencia_evento DESC LIMIT 1""")
    await c.clonar("emergencia_evento", em_a)
    await c.clonar_hijos("emergencia_log", "id_evento", em_a, 2)
    await c.clonar_hijos("emergencia_atencion", "id_emergencia_evento", em_a, 1)

    # Turno con atención y llamado; acceso a historia clínica.
    turno_a = await c.uno("""
        SELECT t.id_turno FROM turnos t WHERE t.id_municipio = 1
         ORDER BY EXISTS (SELECT 1 FROM turno_atencion x WHERE x.id_turno = t.id_turno) DESC,
                  EXISTS (SELECT 1 FROM turno_llamado x WHERE x.id_turno = t.id_turno) DESC, t.id_turno DESC LIMIT 1""")
    turno_b = await c.clonar("turnos", turno_a)
    await c.clonar_hijos("turno_atencion", "id_turno", turno_a, 1)
    await c.clonar_hijos("turno_llamado", "id_turno", turno_a, 1)

    # Evento con reserva, encargado y ocupación (referencias polimórficas a los recursos de B).
    ev_a = await c.uno("""
        SELECT e.id_evento FROM eventos e WHERE e.id_municipio = 1
         ORDER BY EXISTS (SELECT 1 FROM evento_reservas x WHERE x.id_evento = e.id_evento) DESC,
                  EXISTS (SELECT 1 FROM evento_encargados x WHERE x.id_evento = e.id_evento) DESC, e.id_evento DESC LIMIT 1""")
    ev_b = await c.clonar("eventos", ev_a)
    await c.clonar_hijos("evento_reservas", "id_evento", ev_a, 1)
    for enc in await conn.fetch("SELECT id_evento_encargado, tipo_recurso FROM evento_encargados "
                                "WHERE id_evento = $1 ORDER BY 1 LIMIT 1", ev_a):
        await c.clonar("evento_encargados", enc["id_evento_encargado"],
                       dict(id_recurso=await _recurso_b(c, enc["tipo_recurso"])))
    oc = await conn.fetchrow("SELECT id_ocupacion, tipo_recurso FROM ocupaciones WHERE id_municipio = 1 "
                             "ORDER BY (id_evento IS NOT NULL) DESC, id_ocupacion DESC LIMIT 1")
    if oc:
        await c.clonar("ocupaciones", oc["id_ocupacion"], dict(
            id_recurso=await _recurso_b(c, oc["tipo_recurso"]), id_evento=ev_b, id_orden_trabajo=None))

    # Trámite con su circuito completo (versión, campos, estados, transiciones, documentos) y movimientos.
    tr_a = await c.uno("""
        SELECT t.id_tramite FROM tramite t WHERE t.id_municipio = 1
         ORDER BY EXISTS (SELECT 1 FROM tramite_documento x
                           JOIN tramite_firma f ON f.id_tramite_documento = x.id_tramite_documento
                          WHERE x.id_tramite = t.id_tramite) DESC,
                  EXISTS (SELECT 1 FROM tramite_documento x WHERE x.id_tramite = t.id_tramite) DESC,
                  EXISTS (SELECT 1 FROM tramite_relacion x WHERE x.id_tramite_a = t.id_tramite) DESC,
                  t.id_tramite DESC LIMIT 1""")
    numero_a = await c.uno("SELECT numero_expediente FROM tramite WHERE id_tramite = $1", tr_a)
    await c.clonar("tramite", tr_a, dict(numero_expediente=f"AIS-{numero_a}"[:40]))
    version_a = await c.uno("SELECT id_tipo_tramite_version FROM tramite WHERE id_tramite = $1", tr_a)
    for hija in ("tipo_tramite_campo", "tipo_tramite_estado", "tipo_tramite_transicion",
                 "tipo_tramite_documento_requerido", "tipo_tramite_aprobacion_requerida"):
        await c.clonar_hijos(hija, "id_tipo_tramite_version", version_a)
    for hija in ("tramite_movimiento", "tramite_documento", "tramite_aprobacion"):
        await c.clonar_hijos(hija, "id_tramite", tr_a, 3)
    for doc in await conn.fetch("SELECT id_tramite_documento FROM tramite_documento WHERE id_tramite = $1 "
                                "ORDER BY 1 LIMIT 3", tr_a):
        await c.clonar_hijos("tramite_firma", "id_tramite_documento", doc["id_tramite_documento"], 2)
    rel = await c.uno("SELECT min(id_tramite_relacion) FROM tramite_relacion WHERE id_tramite_a = $1", tr_a) \
        or await c.uno("SELECT min(id_tramite_relacion) FROM tramite_relacion WHERE id_municipio = 1")
    if rel:
        await c.clonar("tramite_relacion", rel)
    tipo_a = await c.uno("SELECT id_tipo_tramite FROM tipo_tramite_version WHERE id_tipo_tramite_version = $1", version_a)
    tipo_b = c.mapa[("tipo_tramite", tipo_a)]
    await conn.execute("""
        INSERT INTO tipo_tramite_numerador (id_tipo_tramite, anio, id_municipio, ultimo_numero)
        SELECT $1, anio, $2, ultimo_numero FROM tipo_tramite_numerador WHERE id_tipo_tramite = $3
        ON CONFLICT DO NOTHING""", tipo_b, B, tipo_a)

    # Encuesta enviada con respuesta y detalle (el envío apunta al reclamo o turno de B).
    env = await conn.fetchrow("""
        SELECT e.id_encuesta_envio, e.id_reclamo, e.id_turno FROM encuesta_envio e
          JOIN encuesta_respuesta r ON r.id_envio = e.id_encuesta_envio
         WHERE e.id_municipio = 1
         ORDER BY EXISTS (SELECT 1 FROM encuesta_respuesta_detalle d WHERE d.id_respuesta = r.id_encuesta_respuesta) DESC,
                  e.id_encuesta_envio DESC LIMIT 1""")
    if env:
        cambios_env = {}
        if env["id_reclamo"]:
            cambios_env["id_reclamo"] = rec_b
        if env["id_turno"]:
            cambios_env["id_turno"] = turno_b
        await c.clonar("encuesta_envio", env["id_encuesta_envio"], cambios_env)
        for r in await conn.fetch("SELECT id_encuesta_respuesta FROM encuesta_respuesta WHERE id_envio = $1",
                                  env["id_encuesta_envio"]):
            await c.clonar("encuesta_respuesta", r["id_encuesta_respuesta"])
            await c.clonar_hijos("encuesta_respuesta_detalle", "id_respuesta", r["id_encuesta_respuesta"], 2)

    # Sueltos: una fila de cada tabla que todavía no tenga datos de B.
    # Texto propio: el clonado conservaría números del municipio 1 dentro del mensaje.
    referencias = {"recurso_tipo": "reclamo", "recurso_id": rec_b, "url_destino": None,
                   "titulo": f"{MARCA} aviso de prueba", "mensaje": f"{MARCA} mensaje de prueba"}
    sueltos = {
        "notificacion": dict(referencias, id_usuario=c.anclas["usuarios"]),
        "ciudadano_aviso": dict(referencias, id_ciudadano=c.anclas["ciudadanos"]),
        "agenda_feriado": dict(fecha=__import__("datetime").date(2099, 12, 31)),
        "agenda_audit_log": dict(entidad="evento", id_entidad=ev_b, datos_anteriores=None, datos_nuevos=None),
        "usuario_modulos": dict(id_usuario=c.anclas["usuarios"]),
        "usuario_login_log": dict(id_usuario=c.anclas["usuarios"]),
        "historia_clinica_acceso": dict(id_ciudadano=c.anclas["ciudadanos"]),
    }
    restantes = [t for t, cl in c._clases.items() if cl in ("catalogo", "operativo") and t not in SIN_COBERTURA]
    for tabla in sorted(restantes):
        if not await c.uno("SELECT to_regclass($1) IS NOT NULL", f"public.{tabla}"):
            continue
        if await c.uno(f'SELECT count(*) FROM "{tabla}" WHERE id_municipio = $1', B):
            continue
        m = await c.meta(tabla)
        if len(m["pk"]) != 1:
            continue
        origen = await c.uno(f'SELECT min("{m["pk"][0]}") FROM "{tabla}" WHERE id_municipio = 1')
        if origen is None:
            continue
        cambios = dict(sueltos.get(tabla, {}))
        if "tipo_recurso" in m["cols"]:
            tipo = await c.uno(f'SELECT tipo_recurso FROM "{tabla}" WHERE "{m["pk"][0]}" = $1', origen)
            cambios["id_recurso"] = await _recurso_b(c, tipo)
        if tabla == "conflictos_log":
            cambios.update(id_ocupacion_origen=None, id_ocupacion_conflicto=None)
        await c.clonar(tabla, origen, cambios)
    return B


async def cobertura(conn: asyncpg.Connection, B: int) -> list[str]:
    faltan = []
    for r in await conn.fetch("SELECT tabla FROM municipio_tabla_clase WHERE clase IN ('catalogo','operativo') ORDER BY 1"):
        t = r["tabla"]
        if t in SIN_COBERTURA or not await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{t}"):
            continue
        en_a = await conn.fetchval(f'SELECT count(*) FROM "{t}" WHERE id_municipio = 1')
        en_b = await conn.fetchval(f'SELECT count(*) FROM "{t}" WHERE id_municipio = $1', B)
        if en_a and not en_b:
            faltan.append(t)
    return faltan


async def main() -> int:
    if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
        sys.exit("ABORT: este seed es SOLO LOCAL (la DB configurada no es zaris_dev).")
    conn = await asyncpg.connect(_dsn())
    try:
        B = await conn.fetchval("SELECT id_municipio FROM municipios WHERE subdominio = $1", SUBDOMINIO)
        if B is None:
            async with conn.transaction():
                B = await sembrar(conn)
            print(f"Municipio de aislamiento creado: id {B}")
        else:
            await asegurar_cuentas_dobles(conn, B, bcrypt.hashpw(CLAVE_DEV.encode(), bcrypt.gensalt()).decode())
            for tabla in ("ciudadano_aviso", "notificacion"):  # fixtures creadas antes del texto propio
                await conn.execute(f"UPDATE {tabla} SET titulo = $1, mensaje = $2 WHERE id_municipio = $3 "
                                   "AND mensaje IS DISTINCT FROM $2", f"{MARCA} aviso de prueba",
                                   f"{MARCA} mensaje de prueba", B)
            print(f"El municipio de aislamiento ya existe: id {B} (solo se completan cuentas faltantes)")
        await asegurar_aprobaciones(conn, B)
        faltan = await cobertura(conn, B)
    finally:
        await conn.close()

    from app.core.database import engine  # noqa: E402
    async with engine.connect() as db:
        ids = await ids_aislamiento(db)
    for t, i in ids.items():
        print(f"  {t:36} {i}")
    if faltan:
        print(f"\nSIN COBERTURA en B (tienen datos en el municipio 1): {faltan}")
        return 1
    print(f"\nCobertura completa: {len(ids) - 1} tablas con datos de B.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
