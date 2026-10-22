"""
Orden por columna de los listados con tope (CLAUDE.md §23, estándar de la suite).

Si el endpoint tiene `limit` (o paginado), el orden lo resuelve el SQL: ordenar
en pantalla solo lo cargado escondería filas. El frontend manda `orden` + `dir`
y cada router declara su lista CERRADA de columnas: lo que se interpola en el
ORDER BY sale del dict, nunca del texto del query param.

    _ORDEN = {"fecha": ("t.fecha", "t.hora_inicio"), "nombre": "lower(x.nombre)"}
    order_sql = clausula_orden(orden, dir, _ORDEN, desempate="t.id", por_defecto="t.fecha DESC")

Una columna puede ser una expresión o una tupla (criterios encadenados, todos
en el mismo sentido). Los vacíos van al final en ambas direcciones.
"""
from __future__ import annotations

from fastapi import HTTPException

Columnas = dict[str, "str | tuple[str, ...]"]


def descripcion_orden(columnas: Columnas, por_defecto: str) -> str:
    """Texto para el `description` del query param (queda en OpenAPI)."""
    return "Columna de orden: " + ", ".join(sorted(columnas)) + f". Sin valor: {por_defecto}."


def clausula_orden(
    orden: str | None,
    dir: str,
    columnas: Columnas,
    *,
    desempate: str,
    por_defecto: str,
) -> str:
    """Devuelve el contenido del ORDER BY. 422 si `orden` no está en la lista."""
    if not orden:
        return por_defecto
    if orden not in columnas:
        raise HTTPException(422, f"orden inválido: {orden}")
    sentido = "DESC" if dir == "desc" else "ASC"
    exprs = columnas[orden]
    if isinstance(exprs, str):
        exprs = (exprs,)
    partes = [f"{e} {sentido} NULLS LAST" for e in exprs]
    partes.append(f"{desempate} {sentido}")
    return ", ".join(partes)
