"""
Clonado de filas de un municipio a otro (IT-01 F4+F5, Tarea 11). Extraído de
`seed_municipio_aislamiento.py`, que lo sigue usando con `marca` (texto libre marcado para detectar
filtraciones); el alta de municipios lo usa sin marca para copiar catálogos del modelo.

Cada FK hacia una tabla segmentada (catalogo/operativo) se re-mapea clonando primero al padre
(recursivo). Con `permitidas`, solo se clonan esas tablas: una FK hacia otra tabla segmentada queda
en NULL si la columna lo admite y, si no, la fila se omite (`FilaOmitida`). Así una copia de
catálogos nunca arrastra personas, cuentas ni datos operativos.

Trabaja sobre una conexión asyncpg: en la app, la del AsyncSession (`conexion_asyncpg`), dentro de
su transacción.
"""
import json
import re
import uuid
from typing import Any, Optional

TEXTO_LIBRE = re.compile(
    r"^(nombre|apellido|descripcion|direccion\w*|domicilio\w*|observacion\w*|detalle\w*|titulo|mensaje|"
    r"comentario\w*|motivo\w*|texto|nota|notas|resolucion|razon_social|nombre_fantasia|asunto|contenido|"
    r"cuerpo|calle|lugar)$")
# Únicos globales de una columna que se regeneran al clonar (no son FK).
NUMEROS_POR_TRIGGER = {"nro_reclamo", "nro_ot", "numero_operativo"}


class FilaOmitida(Exception):
    """La fila necesita (NOT NULL) un padre de una tabla que no se puede clonar."""


async def conexion_asyncpg(db):
    """La conexión asyncpg del AsyncSession, en su transacción en curso."""
    conn = await db.connection()
    raw = await conn.get_raw_connection()
    return raw.driver_connection


class Clonador:
    def __init__(self, conn, id_mun: int, *, marca: Optional[str] = None,
                 permitidas: Optional[set[str]] = None, id_usuario_alta: Optional[int] = None):
        self.conn = conn
        self.B = id_mun
        self.marca = marca
        self.permitidas = permitidas
        self.id_usuario_alta = id_usuario_alta
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
        nuevo = f"{self.marca} {valor}"
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
        diferidas: list[tuple[str, str, str, int]] = []  # (col, padre, ref, id_padre) a completar después

        for col, (padre, ref) in m["fks"].items():
            if col in cambios or vals.get(col) is None:
                continue
            nulo_ok = not m["cols"][col]["no_nulo"]
            if padre in self.anclas:
                # Una FK única (agentes.id_usuario, usuarios.id_ciudadano…) no puede apuntar dos veces al ancla.
                vals[col] = None if (col in m["unicos"] and nulo_ok) else self.anclas[padre]
            elif padre == "usuarios":
                vals[col] = self.id_usuario_alta if nulo_ok and self.id_usuario_alta else \
                    (None if nulo_ok else self.anclas.get("usuarios"))
            elif self.segmentada(padre):
                if self.permitidas is not None and padre not in self.permitidas:
                    if nulo_ok:
                        vals[col] = None
                        continue
                    raise FilaOmitida(f"{tabla} {id_origen}: necesita {padre}")
                if padre == tabla and nulo_ok:
                    vals[col] = None  # auto-referencia (reclamo padre, etc.): no se arrastra
                    continue
                id_padre = await self._pk_padre(padre, ref, vals[col])
                # Ciclo mutuo con el otro lado NOT NULL (tipo_tramite.<versión vigente> ↔
                # tipo_tramite_version.id_tipo_tramite): esta columna admite nulo, así que la fila se
                # inserta sin ella y se completa cuando el padre (que la necesita) ya está copiado.
                mp = await self.meta(padre)
                if nulo_ok and (padre, id_padre) not in self.mapa and (padre, id_padre) not in self._en_curso and any(
                        p == tabla and mp["cols"][c]["no_nulo"] for c, (p, _) in mp["fks"].items()):
                    vals[col] = None
                    diferidas.append((col, padre, ref, id_padre))
                    continue
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
            if info["tipo"] in ("json", "jsonb") and not isinstance(valor, str):
                # La conexión del AsyncSession decodifica JSON a dict/list; para insertar va como texto.
                vals[col] = json.dumps(valor)
            elif col in NUMEROS_POR_TRIGGER:
                vals[col] = None
            elif col in m["unicos"] and col not in m["fks"]:
                if info["tipo"] == "uuid":
                    vals[col] = uuid.uuid4()
                elif isinstance(valor, str) and self.marca:
                    vals[col] = (f"AIS-{valor}")[: info["largo"]] if info["largo"] else f"AIS-{valor}"
            elif self.marca and isinstance(valor, str) and TEXTO_LIBRE.match(col) and col not in m["checks"] \
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
        for col, padre, ref, id_padre in diferidas:
            try:
                nuevo_padre = await self.clonar(padre, id_padre)
            except FilaOmitida:
                continue  # el padre no se puede copiar: la columna queda en NULL
            pk_padre = (await self.meta(padre))["pk"][0]
            valor = nuevo_padre if ref == pk_padre else await self.conn.fetchval(
                f'SELECT "{ref}" FROM "{padre}" WHERE "{pk_padre}" = $1', nuevo_padre)
            await self.conn.execute(f'UPDATE "{tabla}" SET "{col}" = $1 WHERE "{pk}" = $2', valor, nuevo)
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
