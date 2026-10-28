"""
Alta de un municipio (IT-01 F4+F5, Tarea 11; spec §4.4).

Todo en UNA transacción (la del llamador, que commitea): municipio en `puesta_en_marcha` → copia de
catálogos del modelo (Clonador sin marca, re-mapeo de FK, solo tablas de catálogo) → módulos →
configuración (todas las claves del modelo, pisadas por la identidad recibida; las que apuntan por id
a entidades se re-siembran por nombre) → ficha BUC + agente + usuario nivel 1 del primer
administrador. Si algo falla, no queda nada. La invitación NO sale acá: el super la manda desde la ficha
cuando las tres direcciones del municipio responden (César, 2026-10-28).
"""
import re
import secrets
from datetime import date
from typing import Literal, Optional

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo_zona import CLAVES_ZONA, SIN_ZONA_BUSQUEDA, zona_completa
from app.services.contorno import (
    MAX_ENTRADA, OrigenIn, codigo_del_partido, guardar_contorno, normalizar_contorno, origen_limpio,
    validar_origen)
from app.services.municipios.clonado import Clonador, FilaOmitida, conexion_asyncpg
from app.services.municipios.constantes import (
    CODIGO_CORTO_LARGO, MODULOS_FIJOS, PATRON_CODIGO_CORTO, PATRON_SUBDOMINIO, SUBDOMINIOS_RESERVADOS)
from app.services.municipios.modulos import validar_dependencias

# Grupos de catálogos que el super elige copiar del modelo (casillas del asistente). Las áreas fijas y
# la configuración se copian siempre. Los padres que una fila necesita se copian aunque su grupo no
# esté elegido (p. ej. la subárea de un tipo de reclamo).
CATALOGOS_COPIABLES: dict[str, list[str]] = {
    "areas_subareas": ["area", "subarea"],
    "cargos": ["cargos"],
    "tipos_reclamo": ["tipo_reclamo"],
    "prestaciones": ["tipo_prestacion"],
    "tramites": ["tipo_tramite", "tipo_tramite_version", "tipo_tramite_estado", "tipo_tramite_campo",
                 "tipo_tramite_transicion", "tipo_tramite_documento_requerido",
                 "tipo_tramite_aprobacion_requerida"],
    "emergencias": ["emergencia_prioridad", "emergencia_canal_ingreso", "emergencia_organismo_derivacion",
                    "emergencia_tipo", "emergencia_subtipo"],
    "encuestas": ["encuesta_plantilla", "encuesta_pregunta", "encuesta_opcion"],
    "agenda": ["agenda_clase", "agenda_feriado"],
}
# Nombre visible de cada grupo en el asistente (mismo orden que CATALOGOS_COPIABLES).
CATALOGOS_ETIQUETAS: dict[str, str] = {
    "areas_subareas": "Áreas y subáreas",
    "cargos": "Cargos",
    "tipos_reclamo": "Tipos de reclamo",
    "prestaciones": "Prestaciones de turnos",
    "tramites": "Trámites",
    "emergencias": "Catálogos de emergencias",
    "encuestas": "Encuestas",
    "agenda": "Clases de evento y feriados",
}
_TABLAS_COPIABLES = {t for ts in CATALOGOS_COPIABLES.values() for t in ts}
# Sin zona de búsqueda, el geocoding de un municipio nuevo responde 409 (geo.py), no busca en otro lado.
SIN_CONTORNO = SIN_ZONA_BUSQUEDA


class IdentidadAlta(BaseModel):
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: Optional[str] = Field(None, max_length=500)
    # Contorno (PLAN_CONTORNO_MUNICIPIO_DISENO.md): se depura con services/contorno.py antes de
    # escribir nada; su origen dice si vino del IGN o de un archivo.
    geo_limite_geojson: Optional[str] = Field(None, max_length=MAX_ENTRADA + 1_000)
    geo_limite_origen: Optional[OrigenIn] = None
    geo_bbox_centro_lat: Optional[float] = Field(None, ge=-90, le=90)
    geo_bbox_centro_lon: Optional[float] = Field(None, ge=-180, le=180)
    geo_bbox_delta_grados: Optional[float] = Field(None, gt=0, le=5)


class AdministradorAlta(BaseModel):
    """Datos de la ficha BUC del primer administrador: los obligatorios de la BUC, sin placeholders."""
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    dni: str = Field(..., pattern=r"^[0-9]{7,8}$")
    cuil: str = Field(..., pattern=r"^[0-9]{11}$")
    sexo: Literal["HOMBRE", "MUJER", "OTROS"]
    fecha_nac: date
    telefono: str = Field(..., min_length=6, max_length=15)
    email: str = Field(..., max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AltaMunicipioIn(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=150)
    codigo_pais: str = Field(..., pattern=r"^[A-Z]{2}$")
    id_provincia: int = Field(..., ge=1, le=2_147_483_647)
    id_partido: Optional[int] = Field(None, ge=1, le=2_147_483_647)
    # Municipio de demo o de prueba, sin partido. Uno real lleva su partido (el municipio ES el partido).
    ficticio: bool = False
    zona_horaria: Optional[str] = Field(None, max_length=64)
    codigo_corto: str = Field(..., max_length=CODIGO_CORTO_LARGO)
    subdominio: str = Field(..., max_length=63)
    identidad: IdentidadAlta = IdentidadAlta()
    copiar: list[str] = []
    modulos: list[str]
    max_usuarios_activos: Optional[int] = Field(None, ge=1, le=100_000)
    administrador: AdministradorAlta


CODIGO_INVALIDO = f"El código corto lleva {CODIGO_CORTO_LARGO} letras mayúsculas, sin tildes"
SUBDOMINIO_INVALIDO = "Subdominio inválido: minúsculas, números y guiones, sin tildes"
SUBDOMINIO_RESERVADO = "Ese subdominio está reservado"
PARTIDO_TOMADO = "Ese partido ya tiene un municipio"


async def problema_codigo(db: AsyncSession, codigo: str) -> Optional[tuple[int, str]]:
    if not re.fullmatch(PATRON_CODIGO_CORTO, codigo):
        return 422, CODIGO_INVALIDO
    if await db.scalar(text("SELECT 1 FROM municipios WHERE codigo_corto = :c"), {"c": codigo}):
        return 409, "Ese código corto ya lo usa otro municipio"
    return None


async def problema_subdominio(db: AsyncSession, sub: str, excluir: Optional[int] = None) -> Optional[tuple[int, str]]:
    if not re.fullmatch(PATRON_SUBDOMINIO, sub):
        return 422, SUBDOMINIO_INVALIDO
    if sub in SUBDOMINIOS_RESERVADOS:
        return 422, SUBDOMINIO_RESERVADO
    if await db.scalar(text("SELECT 1 FROM municipios WHERE subdominio = :s AND id_municipio <> COALESCE(:x, 0)"),
                       {"s": sub, "x": excluir}):
        return 409, "Ese subdominio ya lo usa otro municipio"
    return None


async def problema_partido(db: AsyncSession, id_partido: int, excluir: Optional[int] = None) -> Optional[tuple[int, str]]:
    """Un partido, un municipio vigente (el índice uq_municipios_partido_vigente lo sostiene)."""
    if await db.scalar(text(
            "SELECT 1 FROM municipios WHERE id_partido = :p AND estado <> 'baja' AND id_municipio <> COALESCE(:x, 0)"),
            {"p": id_partido, "x": excluir}):
        return 409, PARTIDO_TOMADO
    return None


def _si_hay(problema: Optional[tuple[int, str]]) -> None:
    if problema:
        raise HTTPException(*problema)


async def _validar(db: AsyncSession, d: AltaMunicipioIn) -> dict:
    sub, cod = await problema_subdominio(db, d.subdominio), await problema_codigo(db, d.codigo_corto)
    for p in (sub, cod):  # primero los de formato (422), después los ocupados (409)
        if p and p[0] == 422:
            _si_hay(p)
    if d.ficticio and d.id_partido is not None:
        raise HTTPException(422, "Un municipio ficticio no lleva partido")
    if not d.ficticio and d.id_partido is None:
        raise HTTPException(422, "Elegí el partido del municipio, o marcalo como ficticio (demo o prueba)")
    pais = (await db.execute(text(
        "SELECT nombre, zona_horaria FROM paises WHERE codigo_pais = :p AND habilitado_para_alta AND activo"),
        {"p": d.codigo_pais})).first()
    if pais is None:
        raise HTTPException(422, "Ese país todavía no está habilitado para dar de alta municipios")
    provincia = await db.scalar(text("SELECT nombre FROM provincias WHERE id_provincia = :i AND codigo_pais = :p"),
                                {"i": d.id_provincia, "p": d.codigo_pais})
    if provincia is None:
        raise HTTPException(422, "La provincia no es del país del municipio")
    if d.id_partido is not None and not await db.scalar(text(
            "SELECT 1 FROM partidos WHERE id_partido = :i AND id_provincia = :p"),
            {"i": d.id_partido, "p": d.id_provincia}):
        raise HTTPException(422, "El partido no es de la provincia del municipio")
    zona = d.zona_horaria or pais.zona_horaria
    if not await db.scalar(text("SELECT 1 FROM pg_timezone_names WHERE name = :z"), {"z": zona}):
        raise HTTPException(422, "Zona horaria inválida")
    desconocidos = set(d.copiar) - set(CATALOGOS_COPIABLES)
    if desconocidos:
        raise HTTPException(422, f"Catálogos desconocidos: {sorted(desconocidos)}")
    # Los fijos se habilitan siempre: el asistente no los ofrece (no se pueden destildar).
    modulos = set(d.modulos) | MODULOS_FIJOS
    catalogo = {r[0] for r in (await db.execute(text("SELECT modulo_codigo FROM modulos WHERE activo"))).all()}
    if modulos - catalogo:
        raise HTTPException(422, f"Módulos desconocidos: {sorted(modulos - catalogo)}")
    await validar_dependencias(modulos)
    _si_hay(sub)
    _si_hay(cod)
    if d.id_partido is not None:
        _si_hay(await problema_partido(db, d.id_partido))
    modelo = await db.scalar(text("SELECT id_municipio FROM municipios WHERE estado = 'modelo'"))
    if modelo is None:
        raise HTTPException(422, "No hay municipio modelo del que copiar los catálogos")
    contorno = None
    if (d.identidad.geo_limite_geojson or "").strip():
        origen = d.identidad.geo_limite_origen or OrigenIn(via="archivo")
        await validar_origen(db, origen, await codigo_del_partido(db, d.id_partido))
        contorno = (normalizar_contorno(d.identidad.geo_limite_geojson, codigo_pais=d.codigo_pais), origen_limpio(origen))
    return {"pais": pais.nombre, "provincia": provincia, "zona": zona, "modelo": modelo, "modulos": modulos,
            "contorno": contorno}


async def _copiar_catalogos(db: AsyncSession, d: AltaMunicipioIn, id_mun: int, modelo: int,
                            id_super: int) -> int:
    """Copia del modelo las tablas elegidas (y siempre las áreas fijas). Devuelve las filas omitidas."""
    conn = await conexion_asyncpg(db)
    c = Clonador(conn, id_mun, permitidas=_TABLAS_COPIABLES, id_usuario_alta=id_super, solo_activas=True)
    await c.cargar_clases()
    tablas: list[str] = [] if "areas_subareas" in d.copiar else ["area"]
    for grupo in CATALOGOS_COPIABLES:
        if grupo in d.copiar:
            tablas += CATALOGOS_COPIABLES[grupo]
    omitidas = 0
    for tabla in tablas:
        m = await c.meta(tabla)
        if not m["cols"] or len(m["pk"]) != 1:
            continue
        pk = m["pk"][0]
        filtro = " AND activo" if "activo" in m["cols"] else ""
        if tabla == "area" and "areas_subareas" not in d.copiar:
            filtro += " AND es_sistema"
        ids = [r[pk] for r in await conn.fetch(
            f'SELECT "{pk}" FROM "{tabla}" WHERE id_municipio = $1{filtro} ORDER BY "{pk}"', modelo)]
        for id_origen in ids:
            try:
                await c.clonar(tabla, id_origen)
            except FilaOmitida:
                omitidas += 1
    return omitidas


async def _poner_config(db: AsyncSession, id_mun: int, clave: str, valor: Optional[str], tipo: str = "string") -> None:
    if valor is None:
        return
    await db.execute(text("""
        INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
        VALUES (:c, :v, :t, :d, TRUE, :m)
        ON CONFLICT (id_municipio, clave) DO UPDATE SET valor = EXCLUDED.valor, fecha_modificacion = NOW()"""),
        {"c": clave, "v": valor, "t": tipo, "d": clave, "m": id_mun})


async def resembrar_claves_por_id(db: AsyncSession, id_mun: int, solo: Optional[set[str]] = None) -> None:
    """Claves de configuración que apuntan por id a entidades del municipio: se re-siembran por nombre
    (§21). El alta las siembra todas; el vaciado, solo las que quedaron apuntando a nada (`solo`)."""
    async def poner(clave: str, valor: str) -> None:
        if solo is None or clave in solo:
            await _poner_config(db, id_mun, clave, valor, "integer")
    salud = await db.scalar(text("""
        SELECT id_area FROM area WHERE id_municipio = :m AND activo AND es_sistema
           AND lower(translate(nombre, 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou')) LIKE 'secretaria de salud%'"""), {"m": id_mun})
    await poner("id_area_salud", str(salud) if salud else "")
    guardia = await db.scalar(text(
        "SELECT id_espacio FROM espacios_agenda WHERE id_municipio = :m AND activo AND nombre = 'Guardia'"),
        {"m": id_mun})
    await poner("id_espacio_guardia", str(guardia) if guardia else "")
    from app.services.municipios.defectos import nacionalidad_por_pais, representacion_por_nombre
    nac = await nacionalidad_por_pais(db, id_mun)
    await poner("id_nacionalidad_defecto", str(nac) if nac else "")
    rep = await representacion_por_nombre(db)
    await poner("id_tipo_representacion_defecto", str(rep) if rep else "")


async def _configuracion(db: AsyncSession, d: AltaMunicipioIn, id_mun: int, modelo: int,
                         contorno: Optional[tuple] = None) -> list[str]:
    await db.execute(text("""
        INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
        SELECT clave, valor, COALESCE(tipo, 'string'), descripcion, TRUE, :d
          FROM configuracion_general WHERE id_municipio = :m AND activo"""), {"d": id_mun, "m": modelo})
    i = d.identidad
    await _poner_config(db, id_mun, "municipio_nombre", d.nombre)
    await _poner_config(db, id_mun, "municipio_color_primary", i.color)
    await _poner_config(db, id_mun, "municipio_logo_url", i.logo_url)
    # Con contorno, la zona sale de él salvo que el super la haya escrito (el asistente la muestra derivada).
    zona_derivada = await guardar_contorno(db, id_mun, *contorno) if contorno else {}
    for clave in ("geo_bbox_centro_lat", "geo_bbox_centro_lon", "geo_bbox_delta_grados"):
        valor = getattr(i, clave)
        await _poner_config(db, id_mun, clave, str(valor) if valor is not None else zona_derivada.get(clave))
    await resembrar_claves_por_id(db, id_mun)
    advertencias = []
    if not zona_completa({c: str(getattr(i, c)) if getattr(i, c) is not None else zona_derivada.get(c)
                          for c in CLAVES_ZONA}):
        advertencias.append(SIN_CONTORNO)
    return advertencias


async def _subarea_admin(db: AsyncSession, id_mun: int) -> int:
    """Primera subárea activa del área fija «Secretaría de Gobierno»; si no se copió ninguna, la crea
    («Administración»). Sin subárea, crear un trámite da 500 (ck_tramite_destinatario)."""
    gob = await db.scalar(text("""
        SELECT id_area FROM area WHERE id_municipio = :m AND activo AND es_sistema
           AND lower(translate(nombre, 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou')) LIKE 'secretaria de gobierno%'"""), {"m": id_mun})
    if gob is None:
        raise HTTPException(422, "El modelo no tiene el área fija «Secretaría de Gobierno»")
    sub = await db.scalar(text(
        "SELECT id_subarea FROM subarea WHERE id_area = :a AND activo ORDER BY id_subarea LIMIT 1"), {"a": gob})
    if sub is None:
        sub = await db.scalar(text("""
            INSERT INTO subarea (nombre, id_area, activo, id_municipio)
            VALUES ('Administración', :a, TRUE, :m) RETURNING id_subarea"""), {"a": gob, "m": id_mun})
    return sub


async def _administrador(db: AsyncSession, d: AltaMunicipioIn, id_mun: int, id_super: int,
                         background_tasks: BackgroundTasks) -> int:
    from app.models.buc import Ciudadano
    from app.schemas.buc import UsuarioCreate
    from app.services.cuenta_zaris import crear_usuario_interno
    a = d.administrador
    nacionalidad = await db.scalar(text(
        "SELECT id FROM nacionalidades WHERE lower(pais) LIKE lower(:p) || '%' ORDER BY id LIMIT 1"),
        {"p": (await db.scalar(text("SELECT nombre FROM paises WHERE codigo_pais = :c"), {"c": d.codigo_pais}))[:8]})
    if nacionalidad is None:
        raise HTTPException(422, "No hay una nacionalidad para el país del municipio")
    id_ciudadano = await db.scalar(text("""
        INSERT INTO ciudadanos (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac, telefono, email,
                                id_nacionalidad, email_chk, emp_chk, ren_chk, activo, es_funcionario,
                                estado_validacion, id_municipio, id_usuario_alta)
        VALUES ('DNI', :dni, :cuil, :nombre, :apellido, :sexo, :fnac, :tel, :email, :nac,
                FALSE, FALSE, FALSE, TRUE, TRUE, 'verificado', :m, :u)
        RETURNING id_ciudadano"""), {
        "dni": a.dni, "cuil": a.cuil, "nombre": a.nombre.strip(), "apellido": a.apellido.strip(), "sexo": a.sexo,
        "fnac": a.fecha_nac, "tel": a.telefono, "email": a.email.lower(), "nac": nacionalidad, "m": id_mun,
        "u": id_super})
    ciudadano = await db.get(Ciudadano, id_ciudadano)
    datos = UsuarioCreate(
        nombre=f"{a.apellido.strip()}, {a.nombre.strip()}", nivel_acceso=1,
        username=f"admin.{d.codigo_corto.lower()}", email=a.email.lower(), cuil=a.cuil,
        id_subarea=await _subarea_admin(db, id_mun), es_externo=False,
        # Clave aleatoria que nadie conoce: no sale el mail de clave temporal; la persona elige la suya
        # con la invitación que el super manda desde la ficha.
        password=secrets.token_urlsafe(32))
    usuario = await crear_usuario_interno(db, data=datos, background_tasks=background_tasks, id_municipio=id_mun,
                                          ciudadano=ciudadano)
    return usuario.id_usuario


async def dar_de_alta(db: AsyncSession, d: AltaMunicipioIn, *, id_super: int,
                      background_tasks: BackgroundTasks) -> dict:
    """Alta completa en la transacción del llamador (que registra y commitea). 422/409 antes de escribir."""
    v = await _validar(db, d)
    try:
        id_mun = await db.scalar(text("""
            INSERT INTO municipios (nombre, codigo_corto, subdominio, codigo_pais, pais, id_provincia, provincia,
                                    id_partido, zona_horaria, estado, max_usuarios_activos, id_usuario_alta)
            VALUES (:nombre, :codigo, :sub, :pais_cod, :pais, :prov, :prov_nombre, :partido, :zona,
                    'puesta_en_marcha', :tope, :u)
            RETURNING id_municipio"""), {
            "nombre": d.nombre.strip(), "codigo": d.codigo_corto, "sub": d.subdominio, "pais_cod": d.codigo_pais,
            "pais": v["pais"], "prov": d.id_provincia, "prov_nombre": v["provincia"], "partido": d.id_partido,
            "zona": v["zona"], "tope": d.max_usuarios_activos, "u": id_super})
    except IntegrityError:
        raise HTTPException(409, "El subdominio, el código corto o el partido ya los usa otro municipio")
    omitidas = await _copiar_catalogos(db, d, id_mun, v["modelo"], id_super)
    await db.execute(text("""
        INSERT INTO municipio_modulo (id_municipio, modulo_codigo, habilitado, min_nivel_acceso, id_usuario_alta)
        SELECT :m, modulo_codigo, modulo_codigo = ANY(:hab), min_nivel_acceso, :u FROM modulos WHERE activo"""),
        {"m": id_mun, "hab": sorted(v["modulos"]), "u": id_super})
    advertencias = await _configuracion(db, d, id_mun, v["modelo"], v["contorno"])
    if omitidas:
        advertencias.append(f"{omitidas} filas del modelo no se copiaron: dependen de catálogos no elegidos")
    id_admin = await _administrador(db, d, id_mun, id_super, background_tasks)
    return {"id_municipio": id_mun, "id_administrador": id_admin, "advertencias": advertencias}
