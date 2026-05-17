"""
Helpers de validacion y resolucion para la creacion de tramites.

Valida campos del formulario contra el tipo, resuelve el iniciador
polimorficamente y determina el destinatario inicial.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Validacion de campos del formulario
# ---------------------------------------------------------------------------

_TIPO_DATO_ESCALARES = {
    "texto", "texto_largo", "numero", "decimal", "fecha",
    "fecha_hora", "booleano", "moneda",
}

_TIPO_DATO_FK = {
    "ciudadano": ("ciudadanos", "id_ciudadano"),
    "empresa": ("empresas", "id_empresa"),
    "agente": ("agentes", "id_agente"),
    "subarea": ("subarea", "id_subarea"),
    "equipo": ("equipos", "id_equipo"),
}


async def _verificar_fk(db: AsyncSession, tabla: str, pk: str, valor: Any, municipio: int) -> bool:
    """Verifica que exista una fila activa con esa PK en el municipio."""
    tiene_mun = tabla not in ("ciudadanos", "empresas")
    if tiene_mun:
        row = (await db.execute(
            text(f"SELECT 1 FROM {tabla} WHERE {pk} = :v AND activo = TRUE AND id_municipio = :m LIMIT 1"),
            {"v": valor, "m": municipio},
        )).fetchone()
    else:
        row = (await db.execute(
            text(f"SELECT 1 FROM {tabla} WHERE {pk} = :v AND activo = TRUE LIMIT 1"),
            {"v": valor},
        )).fetchone()
    return row is not None


def _validar_escalar(nombre: str, valor: Any, tipo_dato: str, validacion: dict | None) -> str | None:
    """Valida un campo escalar. Devuelve mensaje de error o None si ok."""
    if valor is None:
        return None

    if tipo_dato == "booleano":
        if not isinstance(valor, bool):
            return f"'{nombre}' debe ser booleano"
        return None

    if tipo_dato in ("numero", "moneda"):
        try:
            v = int(valor)
        except (TypeError, ValueError):
            return f"'{nombre}' debe ser un entero"
        if validacion:
            if "min" in validacion and v < validacion["min"]:
                return f"'{nombre}' debe ser >= {validacion['min']}"
            if "max" in validacion and v > validacion["max"]:
                return f"'{nombre}' debe ser <= {validacion['max']}"
        return None

    if tipo_dato == "decimal":
        try:
            v = float(valor)
        except (TypeError, ValueError):
            return f"'{nombre}' debe ser un numero decimal"
        return None

    if tipo_dato in ("texto", "texto_largo", "direccion"):
        if not isinstance(valor, str):
            return f"'{nombre}' debe ser texto"
        if validacion:
            if "min" in validacion and len(valor) < validacion["min"]:
                return f"'{nombre}' tiene menos de {validacion['min']} caracteres"
            if "max" in validacion and len(valor) > validacion["max"]:
                return f"'{nombre}' supera los {validacion['max']} caracteres"
            if "regex" in validacion and not re.fullmatch(validacion["regex"], valor):
                return f"'{nombre}' no cumple el formato requerido"
        return None

    if tipo_dato in ("fecha", "fecha_hora"):
        try:
            if isinstance(valor, (date, datetime)):
                return None
            datetime.fromisoformat(str(valor))
        except (TypeError, ValueError):
            return f"'{nombre}' no es una fecha valida (ISO 8601)"
        return None

    return None


async def validar_campos_contra_tipo(
    datos: dict,
    id_tipo_tramite_version: int,
    id_municipio: int,
    db: AsyncSession,
) -> None:
    """
    Valida todos los campos del formulario contra la definicion del tipo.
    Lanza HTTPException 400 con detalle si algo falla.
    """
    campos = (await db.execute(
        text("""
            SELECT nombre_interno, etiqueta, tipo_dato, obligatorio,
                   opciones_jsonb, validacion_jsonb
            FROM tipo_tramite_campo
            WHERE id_tipo_tramite_version = :ver AND activo = TRUE
            ORDER BY orden
        """),
        {"ver": id_tipo_tramite_version},
    )).fetchall()

    errores: list[str] = []

    for c in campos:
        nombre = c.nombre_interno
        valor = datos.get(nombre)

        # Obligatorio
        if c.obligatorio and (valor is None or valor == ""):
            # Los de tipo archivo se validan post-upload
            if c.tipo_dato != "archivo":
                errores.append(f"'{c.etiqueta}' es obligatorio")
            continue

        if valor is None or valor == "":
            continue

        # Tipo archivo: ignorar en creacion
        if c.tipo_dato == "archivo":
            continue

        # Seleccion
        if c.tipo_dato == "seleccion":
            opciones = c.opciones_jsonb or []
            if isinstance(opciones, list):
                vals = [o["valor"] if isinstance(o, dict) else o for o in opciones]
            else:
                vals = list(opciones.values()) if isinstance(opciones, dict) else []
            if valor not in vals:
                errores.append(f"'{c.etiqueta}': valor '{valor}' no es una opcion valida")
            continue

        if c.tipo_dato == "seleccion_multiple":
            if not isinstance(valor, list):
                errores.append(f"'{c.etiqueta}' debe ser una lista")
                continue
            opciones = c.opciones_jsonb or []
            if isinstance(opciones, list):
                vals = [o["valor"] if isinstance(o, dict) else o for o in opciones]
            else:
                vals = list(opciones.values()) if isinstance(opciones, dict) else []
            invalidos = [v for v in valor if v not in vals]
            if invalidos:
                errores.append(f"'{c.etiqueta}': valores no validos {invalidos}")
            continue

        # FK a entidades del sistema
        if c.tipo_dato in _TIPO_DATO_FK:
            tabla, pk = _TIPO_DATO_FK[c.tipo_dato]
            try:
                fk_id = int(valor)
            except (TypeError, ValueError):
                errores.append(f"'{c.etiqueta}' debe ser un ID entero")
                continue
            existe = await _verificar_fk(db, tabla, pk, fk_id, id_municipio)
            if not existe:
                errores.append(f"'{c.etiqueta}': entidad con id {fk_id} no encontrada o inactiva")
            continue

        # Escalares
        msg = _validar_escalar(nombre, valor, c.tipo_dato, c.validacion_jsonb)
        if msg:
            errores.append(msg)

    if errores:
        raise HTTPException(400, {"errores_validacion": errores})


# ---------------------------------------------------------------------------
# Resolucion de iniciador
# ---------------------------------------------------------------------------

async def resolver_iniciador(
    body_iniciador: dict,
    tipo_tramite: dict,
    id_municipio: int,
    db: AsyncSession,
) -> dict:
    """
    Valida y resuelve el iniciador polimorficamente.
    Devuelve {id_ciudadano_iniciador, id_empresa_iniciadora,
              id_ciudadano_representante, id_subarea_iniciadora}.
    """
    tipo = body_iniciador.get("tipo")
    iniciadores_permitidos = tipo_tramite.get("iniciadores_permitidos") or []

    if tipo not in iniciadores_permitidos:
        raise HTTPException(
            400,
            f"Tipo de iniciador '{tipo}' no permitido para este tipo de tramite. "
            f"Permitidos: {iniciadores_permitidos}",
        )

    resultado = {
        "id_ciudadano_iniciador": None,
        "id_empresa_iniciadora": None,
        "id_ciudadano_representante": None,
        "id_subarea_iniciadora": None,
    }

    if tipo == "ciudadano":
        id_cid = body_iniciador.get("id_ciudadano")
        if not id_cid:
            raise HTTPException(400, "Falta id_ciudadano para iniciador tipo 'ciudadano'")
        exists = await _verificar_fk(db, "ciudadanos", "id_ciudadano", id_cid, id_municipio)
        if not exists:
            raise HTTPException(404, f"Ciudadano {id_cid} no encontrado o inactivo")
        resultado["id_ciudadano_iniciador"] = id_cid

    elif tipo == "empresa":
        id_emp = body_iniciador.get("id_empresa")
        if not id_emp:
            raise HTTPException(400, "Falta id_empresa para iniciador tipo 'empresa'")
        exists = await _verificar_fk(db, "empresas", "id_empresa", id_emp, id_municipio)
        if not exists:
            raise HTTPException(404, f"Empresa {id_emp} no encontrada o inactiva")
        resultado["id_empresa_iniciadora"] = id_emp

        # Representante opcional pero validado si viene
        id_rep = body_iniciador.get("id_ciudadano_representante")
        if id_rep:
            if not tipo_tramite.get("permite_representante"):
                raise HTTPException(400, "Este tipo de tramite no permite representante")
            # Validar vinculo ciudadano-empresa activo
            vinculo = (await db.execute(
                text("""
                    SELECT 1 FROM ciudadano_empresa
                    WHERE id_ciudadano = :cid AND id_empresa = :eid AND activo = TRUE
                    LIMIT 1
                """),
                {"cid": id_rep, "eid": id_emp},
            )).fetchone()
            if not vinculo:
                raise HTTPException(
                    400,
                    f"El ciudadano {id_rep} no tiene vinculo activo con la empresa {id_emp}",
                )
            resultado["id_ciudadano_representante"] = id_rep

    elif tipo == "area_interna":
        id_sub = body_iniciador.get("id_subarea")
        if not id_sub:
            raise HTTPException(400, "Falta id_subarea para iniciador tipo 'area_interna'")
        exists = await _verificar_fk(db, "subarea", "id_subarea", id_sub, id_municipio)
        if not exists:
            raise HTTPException(404, f"Subarea {id_sub} no encontrada o inactiva")
        resultado["id_subarea_iniciadora"] = id_sub

    return resultado


# ---------------------------------------------------------------------------
# Determinacion del destinatario inicial
# ---------------------------------------------------------------------------

def determinar_destinatario_inicial(agente_info: dict) -> tuple[str, int]:
    """
    v1: el destinatario inicial es siempre la subarea del agente creador.
    """
    return "subarea", agente_info["id_subarea"]
