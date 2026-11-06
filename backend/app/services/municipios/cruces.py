"""
Referencias a otro municipio (IT-01; cazado en la prueba de cierre de F4+F5, 2026-10-30).

Una fila de un municipio nunca apunta a una fila de otro. La base lo impide con las FK compuestas
(125d, 133b), pero solo donde la FK existe: en prod faltaban las de `tipo_reclamo.id_subarea` y
`subarea.id_area`, y el clonador (que reapunta solo las columnas con FK) copió el modelo con sus
gestiones y tipos de reclamo colgando de San Andrés. `contar_cruces` revisa las FK simples entre
tablas con municipio y, además, las columnas `id_subarea` e `id_area` aunque no tengan FK. El alta
la corre antes de terminar: si queda alguna, el alta no se hace.

Un id guardado DENTRO de un JSON de catálogo no tiene FK que lo frene (prueba de cierre de F4+F5,
2026-11-02: «Derivar» dio 500 porque el destino automático seguía apuntando a San Andrés).
`REFERENCIAS_JSON` los declara: el clonador los reapunta y `contar_cruces` los revisa. Una referencia
nueva dentro de un JSON se suma ahí.

Trabaja sobre una conexión asyncpg (la del AsyncSession, `conexion_asyncpg`): ve las filas de la
transacción en curso.
"""
import json
from collections import Counter
from typing import Any, Awaitable, Callable, Optional

# Columnas que se revisan aunque la base no tenga su FK (el drift que originó el chequeo).
SIN_FK = (("id_subarea", "subarea", "id_subarea"), ("id_area", "area", "id_area"))

# Tipo de referencia dentro de un JSON → (tabla, pk).
PADRES_JSON = {"subarea": ("subarea", "id_subarea"), "equipo": ("equipos", "id_equipo"),
               "agente": ("agentes", "id_agente")}
# (tabla, columna) → forma del JSON:
#   objeto:    {"tipo": "subarea", "id": 5, "nombre": "…"}; sin destino, NULL
#   por_clave: {"subareas": [5], "equipos": [2], "agentes": [1], "roles": […]}
#   lista:     [{"tipo": "agente", "id": 5, "rol_intervencion": "firma"}, …]
REFERENCIAS_JSON = {
    ("tipo_tramite_transicion", "destino_automatico_jsonb"): "objeto",
    ("tipo_tramite_transicion", "quien_puede_jsonb"): "por_clave",
    ("tipo_tramite_documento_requerido", "firmantes_jsonb"): "lista",
}
_CLAVES_POR_TIPO = {"subareas": "subarea", "equipos": "equipo", "agentes": "agente"}
_TIPO_POR_DEFECTO = "subarea"  # como lo interpreta el trámite al aplicar un destino automático


def como_id(valor: Any) -> Optional[int]:
    if isinstance(valor, bool):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _decodificar(valor: Any) -> Any:
    """La conexión del AsyncSession decodifica JSON a dict/list; una conexión cruda da texto."""
    return json.loads(valor) if isinstance(valor, str) else valor


def ids_en_json(forma: str, valor: Any) -> list[tuple[str, Any]]:
    """Las referencias de un valor JSON, como [(tipo, id)]. El id va como está guardado."""
    valor = _decodificar(valor)
    if forma == "objeto":
        if isinstance(valor, dict) and valor.get("id") is not None:
            tipo = valor.get("tipo") or _TIPO_POR_DEFECTO
            return [(tipo, valor["id"])] if tipo in PADRES_JSON else []
        return []
    if forma == "por_clave":
        if not isinstance(valor, dict):
            return []
        return [(tipo, i) for clave, tipo in _CLAVES_POR_TIPO.items()
                if isinstance(valor.get(clave), list) for i in valor[clave]]
    if isinstance(valor, list):
        return [(f["tipo"], f["id"]) for f in valor
                if isinstance(f, dict) and f.get("tipo") in PADRES_JSON and f.get("id") is not None]
    return []


async def reapuntar_json(forma: str, valor: Any,
                         mapear: Callable[[str, Any], Awaitable[Optional[int]]]) -> tuple[Any, int]:
    """El JSON con cada referencia pasada por `mapear` (None = no se puede copiar) y cuántas se quitaron.

    Una referencia que no se copia nunca amplía un permiso: en «quién puede» la clave queda con la lista
    vacía, que deniega a todos menos al administrador (`{}` abriría a cualquier operador); un destino
    automático queda en NULL, y el trámite sigue donde está.
    """
    valor = _decodificar(valor)
    quitadas = 0
    if forma == "objeto":
        if not ids_en_json(forma, valor):
            return valor, 0
        tipo, id_origen = ids_en_json(forma, valor)[0]
        nuevo = await mapear(tipo, id_origen)
        return (None, 1) if nuevo is None else ({**valor, "id": nuevo}, 0)
    if forma == "por_clave":
        if not isinstance(valor, dict):
            return valor, 0
        salida = dict(valor)
        for clave, tipo in _CLAVES_POR_TIPO.items():
            if not isinstance(valor.get(clave), list):
                continue
            salida[clave] = []
            for id_origen in valor[clave]:
                nuevo = await mapear(tipo, id_origen)
                if nuevo is None:
                    quitadas += 1
                else:
                    salida[clave].append(nuevo)
        return salida, quitadas
    if not isinstance(valor, list):
        return valor, 0
    salida_lista = []
    for f in valor:
        if isinstance(f, dict) and f.get("tipo") in PADRES_JSON and f.get("id") is not None:
            nuevo = await mapear(f["tipo"], f["id"])
            if nuevo is None:
                quitadas += 1
                continue
            f = {**f, "id": nuevo}
        salida_lista.append(f)
    return salida_lista, quitadas


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


async def _cruces_json(conn, id_municipio: int) -> list[tuple[str, int]]:
    """Las referencias dentro de un JSON que apuntan a otro municipio. Un id que no existe en ningún
    municipio no es un cruce (lo mismo que una columna con FK: no hay fila ajena a la que apunte)."""
    salida: list[tuple[str, int]] = []
    for (tabla, col), forma in REFERENCIAS_JSON.items():
        filas = await conn.fetch(
            f'SELECT "{col}" AS v FROM "{tabla}" WHERE id_municipio = $1 AND "{col}" IS NOT NULL', id_municipio)
        por_tipo: dict[str, Counter] = {}
        for f in filas:
            for tipo, id_ref in ids_en_json(forma, f["v"]):
                i = como_id(id_ref)
                if i is not None:
                    por_tipo.setdefault(tipo, Counter())[i] += 1
        for tipo, ids in por_tipo.items():
            padre, pk = PADRES_JSON[tipo]
            ajenos = await conn.fetch(
                f'SELECT "{pk}" AS id FROM "{padre}" WHERE "{pk}" = ANY($1::int[]) '
                'AND id_municipio IS DISTINCT FROM $2', list(ids), id_municipio)
            n = sum(ids[r["id"]] for r in ajenos)
            if n:
                salida.append((f"{tabla}.{col} → {padre}", n))
    return salida


async def contar_cruces(conn, id_municipio: int) -> list[tuple[str, int]]:
    """Las referencias de filas del municipio a filas de otro, como [('tabla.col → padre', cantidad)]."""
    pares = await conn.fetch(_PARES, *[list(x) for x in zip(*SIN_FK)])
    salida: list[tuple[str, int]] = []
    if pares:
        partes = [
            f"""SELECT '{p["tabla"]}.{p["col"]} → {p["padre"]}' AS k, count(*) AS n
                  FROM "{p["tabla"]}" h JOIN "{p["padre"]}" x ON x."{p["ref"]}" = h."{p["col"]}"
                 WHERE h.id_municipio = $1 AND x.id_municipio IS DISTINCT FROM h.id_municipio"""
            for p in pares]
        filas = await conn.fetch(" UNION ALL ".join(partes), id_municipio)
        salida = [(f["k"], f["n"]) for f in filas if f["n"]]
    return salida + await _cruces_json(conn, id_municipio)
