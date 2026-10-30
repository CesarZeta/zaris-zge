"""
Referencias a otro municipio (IT-01; cazado en la prueba de cierre de F4+F5, 2026-10-30).

Una fila de un municipio nunca apunta a una fila de otro. La base lo impide con las FK compuestas
(125d, 133b), pero solo donde la FK existe: en prod faltaban las de `tipo_reclamo.id_subarea` y
`subarea.id_area`, y el clonador (que reapunta solo las columnas con FK) copió el modelo con sus
gestiones y tipos de reclamo colgando de San Andrés. `contar_cruces` revisa las FK simples entre
tablas con municipio y, además, las columnas `id_subarea` e `id_area` aunque no tengan FK. El alta
la corre antes de terminar: si queda alguna, el alta no se hace.

Trabaja sobre una conexión asyncpg (la del AsyncSession, `conexion_asyncpg`): ve las filas de la
transacción en curso.
"""

# Columnas que se revisan aunque la base no tenga su FK (el drift que originó el chequeo).
SIN_FK = (("id_subarea", "subarea", "id_subarea"), ("id_area", "area", "id_area"))

_PARES = """
WITH fks AS (
    SELECT ch.relname AS tabla, a.attname AS col, pa.relname AS padre, ar.attname AS ref
      FROM pg_constraint c
      JOIN pg_class ch ON ch.oid = c.conrelid
      JOIN pg_class pa ON pa.oid = c.confrelid
      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
      JOIN pg_attribute ar ON ar.attrelid = c.confrelid AND ar.attnum = c.confkey[1]
     WHERE c.contype = 'f' AND array_length(c.conkey, 1) = 1 AND ch.relnamespace = 'public'::regnamespace
), por_nombre AS (
    SELECT x.table_name::text AS tabla, d.col, d.padre, d.ref
      FROM information_schema.columns x
      JOIN unnest($1::text[], $2::text[], $3::text[]) AS d(col, padre, ref) ON d.col = x.column_name
     WHERE x.table_schema = 'public' AND x.table_name <> d.padre
), con_municipio AS (
    SELECT c.relname AS tabla FROM pg_class c
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'id_municipio' AND NOT a.attisdropped
     WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p')
)
SELECT DISTINCT p.tabla, p.col, p.padre, p.ref
  FROM (SELECT * FROM fks UNION SELECT * FROM por_nombre) p
 WHERE p.col <> 'id_municipio' AND p.padre NOT IN ('usuarios', 'municipios')
   AND p.tabla NOT LIKE '\\_backup%'
   AND p.tabla IN (SELECT tabla FROM con_municipio) AND p.padre IN (SELECT tabla FROM con_municipio)
 ORDER BY 1, 2"""


async def contar_cruces(conn, id_municipio: int) -> list[tuple[str, int]]:
    """Las referencias de filas del municipio a filas de otro, como [('tabla.col → padre', cantidad)]."""
    pares = await conn.fetch(_PARES, *[list(x) for x in zip(*SIN_FK)])
    if not pares:
        return []
    partes = [
        f"""SELECT '{p["tabla"]}.{p["col"]} → {p["padre"]}' AS k, count(*) AS n
              FROM "{p["tabla"]}" h JOIN "{p["padre"]}" x ON x."{p["ref"]}" = h."{p["col"]}"
             WHERE h.id_municipio = $1 AND x.id_municipio IS DISTINCT FROM h.id_municipio"""
        for p in pares]
    filas = await conn.fetch(" UNION ALL ".join(partes), id_municipio)
    return [(f["k"], f["n"]) for f in filas if f["n"]]
