# -*- coding: utf-8 -*-
"""Generador de expedientes (Tramites) demo — hermano de demo_datos.py (2026-10-21).

Pedido de Cesar: la demo tiene que mostrar tramites que entran y SE CIERRAN, con
la misma regla de SLA que los reclamos (app/services/demo_sla.py): cada mes una
fraccion p entre 60 % y 85 % termina dentro del SLA del tipo y el resto fuera;
queda pendiente lo reciente cuyo fin planificado no llego.

Respeta el modelo real del modulo (skill `modulo-tramites`):
  - solo tipos activos con version PUBLICADA y un camino inicial -> final;
  - numeracion atomica con el numerador del modulo (services/tramites/numerador.py:
    proximo_numero + formatear_numero), año = año del alta;
  - iniciador polimorfico segun tipo_tramite.iniciadores_permitidos (vecinos y
    empresas DEMO, o un area interna) y destinatario polimorfico (Mesa de Entradas,
    destino_automatico de cada transicion, pase cuando la transicion exige otra
    subarea en quien_puede_jsonb);
  - ledger append-only tramite_movimiento: creacion, numeracion, pase, toma,
    transicion (con comentario si la transicion lo exige), aprobacion (visados,
    instanciados con services/tramites/aprobaciones.py) y resultado;
  - resultado aprobado/rechazado (~78/22): automatico si la transicion final es
    aprobar/rechazar (mig 101), si no lo sella un supervisor de la gestion (como
    POST /tramites/{ref}/resultado);
  - encuesta CSAT de tramites (plantilla tipo 'tramites') al ~85 % de los
    iniciados por un vecino, NUNCA en estado 'pendiente'.

SLA del tipo: tipo_tramite.sla_dias; si es NULL/0, el default del producto
(configuracion_general.tramite_sla_dias_default, 30 si falta) — la misma regla
que usa el timer de desistimiento. Duracion maxima de un tramite demo:
max(20 dias, 3 x SLA): lo mas viejo queda siempre cerrado.

SEGURIDAD (sin mails): todo se escribe por SQL, sin services de notificacion.
Un tramite demo pendiente NUNCA queda parado en un estado con
`espera_iniciador = TRUE` (el timer de desistimiento le mandaria mails al
iniciador): si el plan lo deja ahi en `ahora`, se difiere ese paso hasta que el
plan tambien lo saque de ese estado.

Sin documentos: el generador no toca el Storage; las transiciones que exigen
adjunto dejan en el comentario que la documentacion se presento en ventanilla.

Idempotente por dia (un dia con tramites demo se saltea). Todo atribuido al
usuario 'generador.demo'.
"""
from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import demo_datos, demo_sla
from app.services.tramites import aprobaciones as svc_aprob
from app.services.tramites import numerador as svc_num

logger = logging.getLogger(__name__)

UTC = timezone.utc
TRAMITES_MENSUAL = (60, 120)
# Ventanilla: lunes a viernes.
PESO_DIA_HABIL = (1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0)
TASA_RECHAZO = 0.22
TASA_ENCUESTA = 0.85
EMPRESAS_DEMO = 60
SLA_DEFAULT = 30
VENTANA_AVANCE_DIAS = 120
# Peso relativo por codigo de tipo (los que no estan: PESO_OTRO).
PESO_TIPO = {
    "habilitacion-comercial": 20, "poda-arbol": 18, "licencia-ordinaria": 15, "pedido-informe": 12,
    "cartel-publicitario": 10, "inspeccion-bromatologica": 8, "cambio-domicilio-comercial": 8,
    "transferencia-habilitacion": 5, "recurso-administrativo": 4,
}
PESO_OTRO = 6
_RX_RECHAZO = re.compile(r"rechaz|inadmis|deneg|desestim", re.I)

RUBROS_EMPRESA = [
    ("Panadería", "S.R.L."), ("Almacén", "S.A.S."), ("Ferretería", "S.R.L."), ("Farmacia", "S.A."),
    ("Verdulería", "S.R.L."), ("Gastronomía", "S.A."), ("Librería", "S.R.L."), ("Indumentaria", "S.A.S."),
    ("Taller mecánico", "S.R.L."), ("Peluquería", "S.A.S."), ("Distribuidora", "S.A."), ("Heladería", "S.R.L."),
]
NOMBRES_FANTASIA = [
    "La Espiga", "Don Julio", "El Molino", "Los Andes", "San Cayetano", "El Ceibo", "La Esquina",
    "Del Río", "Las Acacias", "El Faro", "Nueva Era", "La Estación", "El Roble", "Punto Norte",
    "La Rueda", "Sol de Mayo", "Los Tilos", "El Puente", "La Plaza", "Buen Día",
]
COMENTARIOS_AVANCE = [
    "Se verificó la documentación presentada.",
    "Revisado por el área, sin observaciones.",
    "Se continúa con el circuito.",
    "Cumple los requisitos de la etapa.",
    "Informe técnico favorable.",
    "Se deja constancia de la revisión realizada.",
]
COMENTARIOS_RECHAZO = [
    "No cumple los requisitos establecidos por la normativa vigente.",
    "La documentación presentada es insuficiente.",
    "El informe técnico resultó desfavorable.",
    "La solicitud no corresponde a la competencia del área.",
]
# Textos libres por (campo, prefijo del codigo del tipo); '*' = cualquier tipo.
TEXTOS_LARGOS = {
    "motivo": {
        "poda": ["Ramas sobre el cableado y la vereda.", "El árbol está inclinado sobre la vivienda.",
                 "Las raíces levantaron la vereda.", "Ramas secas con riesgo de caída."],
        "licencia": ["Licencia anual ordinaria.", "Uso de días pendientes del período anterior.",
                     "Viaje familiar programado."],
        "inspeccion": ["Control previo a la apertura del local.", "Renovación del certificado bromatológico.",
                       "Inspección por cambio de rubro."],
        "*": ["Según lo presentado en ventanilla."],
    },
    "detalle": {"*": ["Se solicita informe sobre el estado del expediente de referencia.",
                      "Se requiere detalle de las actuaciones realizadas durante el último trimestre."]},
    "fundamentos": {"*": ["El acto recurrido carece de fundamentación suficiente.",
                          "No se consideraron los descargos presentados en término."]},
    "pretension": {"*": ["Se solicita la revocación del acto.", "Se solicita la suspensión de los efectos del acto."]},
}


def _texto_largo(rnd: random.Random, campo: str, codigo_tipo: str) -> str:
    clave = next((k for k in TEXTOS_LARGOS if k in campo), None)
    if clave is None:
        return "Se adjunta la presentación correspondiente."
    por_tipo = TEXTOS_LARGOS[clave]
    lista = next((v for k, v in por_tipo.items() if k != "*" and codigo_tipo.startswith(k)), por_tipo.get("*"))
    return rnd.choice(lista)


# ── Catalogo ────────────────────────────────────────────────────────────────

@dataclass
class _Version:
    id_version: int
    estados: dict[int, dict]
    inicial: int | None
    trans_por_origen: dict[int, list[dict]]
    campos: list[dict]
    caminos: dict[str, list[list[dict]]]
    con_requisitos: set[int]


@dataclass
class _Tipo:
    id: int
    codigo: str
    nombre: str
    prefijo: str
    separador: str
    incl_mun: bool
    incl_anio: bool
    largo: int
    iniciadores: list[str]
    id_version: int
    id_subarea: int | None
    sla: int
    id_municipio: int
    cod_muni: str
    peso: int


@dataclass
class _Ctx:
    uid: int
    tipos: dict[int, _Tipo] = field(default_factory=dict)
    versiones: dict[int, _Version] = field(default_factory=dict)
    agentes_sub: dict[int, list[int]] = field(default_factory=dict)
    supervisores_sub: dict[int, list[int]] = field(default_factory=dict)
    agentes_area: dict[int, list[int]] = field(default_factory=dict)
    agentes_todos: list[int] = field(default_factory=list)
    area_de_sub: dict[int, int] = field(default_factory=dict)
    nombre_sub: dict[int, str] = field(default_factory=dict)
    sub_de_equipo: dict[int, int] = field(default_factory=dict)
    subareas_con_agentes: list[int] = field(default_factory=list)
    mesa_entradas: int | None = None
    pool_vecinos: list[tuple[int, str]] = field(default_factory=list)
    pool_empresas: list[int] = field(default_factory=list)
    id_plantilla: int | None = None
    cat_reclamos: object = None


def _norm(s: str | None) -> str:
    return demo_datos._norm(s)


def _caminos(inicial: int, trans_por_origen: dict[int, list[dict]], estados: dict[int, dict],
             maximo: int = 200) -> list[list[dict]]:
    """Caminos inicial -> final (cada estado a lo sumo 2 veces: admite UN ciclo de
    subsanacion), hasta 10 pasos."""
    out: list[list[dict]] = []

    def dfs(estado: int, camino: list[dict], visitas: dict[int, int]) -> None:
        if len(out) >= maximo:
            return
        if estados[estado]["es_final"]:
            if camino:
                out.append(list(camino))
            return
        if len(camino) >= 10:
            return
        for t in trans_por_origen.get(estado, []):
            d = t["id_estado_destino"]
            if d not in estados or visitas.get(d, 0) >= 2:
                continue
            visitas[d] = visitas.get(d, 0) + 1
            camino.append(t)
            dfs(d, camino, visitas)
            camino.pop()
            visitas[d] -= 1

    dfs(inicial, [], {inicial: 1})
    return out


def _es_rechazo(camino: list[dict], estados: dict[int, dict]) -> bool:
    for t in camino:
        if (t.get("tipo_accion") or "") == "rechazar":
            return True
        e = estados.get(t["id_estado_destino"], {})
        if _RX_RECHAZO.search(f"{e.get('codigo', '')} {e.get('etiqueta', '')}"):
            return True
    return False


async def _cargar_version(db: AsyncSession, id_version: int) -> _Version:
    estados = {f.id_tipo_tramite_estado: dict(f._mapping) for f in (await db.execute(text("""
        SELECT id_tipo_tramite_estado, codigo, etiqueta, es_inicial, es_final,
               COALESCE(espera_iniciador, FALSE) AS espera_iniciador
          FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND activo
    """), {"v": id_version})).fetchall()}
    trans: dict[int, list[dict]] = {}
    for f in (await db.execute(text("""
        SELECT id_tipo_tramite_transicion, id_estado_origen, id_estado_destino, tipo_accion,
               requiere_comentario, requiere_adjunto, quien_puede_jsonb, destino_automatico_jsonb
          FROM tipo_tramite_transicion WHERE id_tipo_tramite_version = :v AND activo
         ORDER BY id_tipo_tramite_transicion
    """), {"v": id_version})).fetchall():
        trans.setdefault(f.id_estado_origen, []).append(dict(f._mapping))
    campos = [dict(f._mapping) for f in (await db.execute(text("""
        SELECT nombre_interno, etiqueta, tipo_dato, obligatorio, opciones_jsonb, validacion_jsonb
          FROM tipo_tramite_campo WHERE id_tipo_tramite_version = :v AND activo ORDER BY orden
    """), {"v": id_version})).fetchall()]
    con_req = {f.id_tipo_tramite_estado for f in (await db.execute(text("""
        SELECT DISTINCT id_tipo_tramite_estado FROM tipo_tramite_aprobacion_requerida
         WHERE id_tipo_tramite_version = :v AND activo
    """), {"v": id_version})).fetchall()}
    inicial = next((i for i, e in estados.items() if e["es_inicial"]), None)
    caminos: dict[str, list[list[dict]]] = {"aprobado": [], "rechazado": []}
    if inicial is not None:
        for c in _caminos(inicial, trans, estados):
            caminos["rechazado" if _es_rechazo(c, estados) else "aprobado"].append(c)
    return _Version(id_version, estados, inicial, trans, campos, caminos, con_req)


async def _personal(db: AsyncSession, ctx: _Ctx) -> None:
    """Agentes que firman los movimientos: nivel 2-4 activos con usuario activo,
    sin la app de agentes instalada en un telefono real (push activo)."""
    tiene_push = bool(await db.scalar(text("SELECT to_regclass('public.usuario_push_subscription') IS NOT NULL")))
    filtro_push = ("AND NOT EXISTS (SELECT 1 FROM usuario_push_subscription ps "
                   "WHERE ps.id_usuario = u.id_usuario AND ps.activo)") if tiene_push else ""
    for f in (await db.execute(text("SELECT id_subarea, id_area, nombre FROM subarea"))).fetchall():
        ctx.area_de_sub[f.id_subarea] = f.id_area
        ctx.nombre_sub[f.id_subarea] = f.nombre
    for f in (await db.execute(text(f"""
        SELECT ag.id_agente, ag.id_subarea, u.nivel_acceso FROM agentes ag
          JOIN usuarios u ON u.id_usuario = ag.id_usuario AND u.activo
          JOIN subarea s ON s.id_subarea = ag.id_subarea AND s.activo
         WHERE ag.activo AND u.nivel_acceso BETWEEN 2 AND 4 {filtro_push}
         ORDER BY ag.id_agente
    """))).fetchall():
        ctx.agentes_sub.setdefault(f.id_subarea, []).append(f.id_agente)
        ctx.agentes_todos.append(f.id_agente)
        area = ctx.area_de_sub.get(f.id_subarea)
        if area is not None:
            ctx.agentes_area.setdefault(area, []).append(f.id_agente)
        if f.nivel_acceso == 2:
            ctx.supervisores_sub.setdefault(f.id_subarea, []).append(f.id_agente)
    ctx.subareas_con_agentes = sorted(ctx.agentes_sub)
    for f in (await db.execute(text("SELECT id_equipo, id_subarea FROM equipos WHERE id_subarea IS NOT NULL"))).fetchall():
        ctx.sub_de_equipo[f.id_equipo] = f.id_subarea
    for sid, nombre in ctx.nombre_sub.items():
        if _norm(nombre) == "mesa de entradas":
            ctx.mesa_entradas = sid
            break


def _agente(ctx: _Ctx, id_subarea: int | None, rnd: random.Random) -> int | None:
    """Agente de la subarea; si no tiene, de la misma secretaria; si no, cualquiera."""
    for cands in (ctx.agentes_sub.get(id_subarea), ctx.agentes_area.get(ctx.area_de_sub.get(id_subarea)),
                  ctx.agentes_todos):
        if cands:
            return rnd.choice(cands)
    return None


async def _empresas_demo(db: AsyncSession, ctx: _Ctx, rnd: random.Random) -> list[int]:
    """Pool de empresas DEMO (email @vecinos-demo.zaris.com.ar); crea las que falten
    con CUIT sintetico valido (prefijo 30/33 + verificador mod-11)."""
    dominio = demo_datos.DOMINIO_VECINO_DEMO
    ya = (await db.execute(text("SELECT id_empresa FROM empresas WHERE activo AND email LIKE :d ORDER BY id_empresa"),
                           {"d": f"%@{dominio}"})).fetchall()
    faltan = EMPRESAS_DEMO - len(ya)
    if faltan > 0:
        actividades = [f.id for f in (await db.execute(text(
            "SELECT id FROM actividades WHERE activo ORDER BY id"))).fetchall()]
        if actividades:
            cuits = {f.cuit for f in (await db.execute(text("SELECT cuit FROM empresas"))).fetchall()}
            filas = []
            while len(filas) < faltan:
                base = f"30{rnd.randint(70_000_000, 79_999_999):08d}"
                pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
                ver = 11 - sum(int(d) * p for d, p in zip(base, pesos)) % 11
                if ver == 10:
                    continue
                cuit = f"{base}{0 if ver == 11 else ver}"
                if cuit in cuits:
                    continue
                cuits.add(cuit)
                rubro, sociedad = rnd.choice(RUBROS_EMPRESA)
                nombre = f"{rubro} {rnd.choice(NOMBRES_FANTASIA)} {sociedad}"
                loc = demo_datos._elegir_localidad(rnd, ctx.cat_reclamos)
                lat, lon = demo_datos._ubicar(rnd, ctx.cat_reclamos, loc[2], loc[3], loc[4])
                slug = re.sub(r"[^a-z0-9]+", ".", _norm(nombre)).strip(".")
                filas.append({"cuit": cuit, "nombre": nombre, "act": rnd.choice(actividades),
                              "calle": rnd.choice(demo_datos.CALLES), "altura": str(rnd.randint(100, 5900)),
                              "loc": loc[1], "lat": lat, "lon": lon,
                              "tel": f"11{rnd.randint(40_000_000, 69_999_999)}",
                              "email": f"{slug}.{cuit[-4:]}@{dominio}", "uid": ctx.uid,
                              # empresas.fecha_alta es timestamp SIN zona (como ciudadanos).
                              "fa": datetime.now() - timedelta(days=rnd.randint(60, 900))})
            # Mismas columnas que el alta publica (publico_alta.py), id_municipio incluido.
            mun = min((t.id_municipio for t in ctx.tipos.values()), default=1)
            await db.execute(text("""
                INSERT INTO empresas (cuit, nombre, id_actividad, calle, altura, localidad, provincia,
                                      latitud, longitud, telefono, email, email_chk, activo,
                                      id_municipio, fecha_alta, id_usuario_alta)
                VALUES (:cuit, :nombre, :act, :calle, :altura, :loc, 'Buenos Aires',
                        :lat, :lon, :tel, :email, FALSE, TRUE, :mun, :fa, :uid)
            """), [{**f, "mun": mun} for f in filas])
            ya = (await db.execute(text("SELECT id_empresa FROM empresas WHERE activo AND email LIKE :d ORDER BY id_empresa"),
                                   {"d": f"%@{dominio}"})).fetchall()
    return [f.id_empresa for f in ya]


async def _cargar_ctx(db: AsyncSession, rnd: random.Random, crear_pools: bool) -> _Ctx | None:
    uid = await demo_datos._usuario_generador(db, crear=crear_pools)
    if uid is None:
        return None
    ctx = _Ctx(uid=uid)
    sla_default = await db.scalar(text("""
        SELECT CASE WHEN valor ~ '^[0-9]{1,4}$' THEN CAST(valor AS integer) END
          FROM configuracion_general WHERE clave = 'tramite_sla_dias_default' AND activo
    """)) or SLA_DEFAULT
    for f in (await db.execute(text("""
        SELECT tt.id_tipo_tramite, tt.codigo, tt.nombre, tt.prefijo, tt.separador, tt.incluye_municipio,
               tt.incluye_anio, tt.largo_correlativo, tt.iniciadores_permitidos, tt.id_version_publicada,
               tt.id_subarea, tt.sla_dias, tt.id_municipio, COALESCE(m.codigo_corto, '') AS cod
          FROM tipo_tramite tt JOIN municipios m ON m.id_municipio = tt.id_municipio
         WHERE tt.activo AND tt.id_version_publicada IS NOT NULL
         ORDER BY tt.id_tipo_tramite
    """))).fetchall():
        ctx.tipos[f.id_tipo_tramite] = _Tipo(
            f.id_tipo_tramite, f.codigo, f.nombre, f.prefijo, f.separador, f.incluye_municipio,
            f.incluye_anio, f.largo_correlativo, list(f.iniciadores_permitidos or []),
            f.id_version_publicada, f.id_subarea, int(f.sla_dias or sla_default), f.id_municipio, f.cod,
            PESO_TIPO.get(f.codigo, PESO_OTRO))
    for t in ctx.tipos.values():
        ctx.versiones[t.id_version] = await _cargar_version(db, t.id_version)
    await _personal(db, ctx)
    ctx.id_plantilla = await db.scalar(text(
        "SELECT id_encuesta_plantilla FROM encuesta_plantilla WHERE tipo = 'tramites' AND activo "
        "ORDER BY id_encuesta_plantilla LIMIT 1"))
    ctx.cat_reclamos = await demo_datos._cargar_catalogos(db)
    if crear_pools:
        ctx.pool_vecinos = await demo_datos._asegurar_vecinos(db, ctx.cat_reclamos, uid, 250, rnd)
        ctx.pool_empresas = await _empresas_demo(db, ctx, rnd)
    return ctx


async def _version(db: AsyncSession, ctx: _Ctx, id_version: int) -> _Version:
    if id_version not in ctx.versiones:
        ctx.versiones[id_version] = await _cargar_version(db, id_version)
    return ctx.versiones[id_version]


# ── Plan determinista de un tramite ─────────────────────────────────────────

@dataclass
class _Plan:
    resultado: str                 # aprobado | rechazado
    camino: list[dict]             # transiciones
    tiempos: list[datetime]        # fecha de cada transicion (la ultima = fin)
    tomas: list[datetime]          # fecha de toma antes de cada transicion
    fin: datetime
    dentro: bool
    sello_min: float               # minutos entre el fin y el sello manual del resultado


def _elegir_camino(rnd: random.Random, caminos: list[list[dict]], estados: dict[int, dict]) -> list[dict]:
    pesos = []
    for c in caminos:
        visit = [t["id_estado_destino"] for t in c]
        ciclo = len(visit) != len(set(visit))
        pesos.append((0.25 if ciclo else 1.0) / (1 + 0.15 * len(c)))
    return rnd.choices(caminos, weights=pesos, k=1)[0]


def _plan_tramite(id_tramite: int, alta: datetime, tipo: _Tipo, ver: _Version) -> _Plan | None:
    rnd = demo_sla.rnd_de("tramite", id_tramite)
    p = demo_sla.p_mes("tramites", alta.year, alta.month)
    dentro = demo_sla.cae_dentro("tramites", id_tramite, p)
    tope = max(demo_sla.TOPE_DIAS, 3.0 * tipo.sla)
    dias = demo_sla.demora_dentro(rnd, tipo.sla) if dentro else demo_sla.demora_fuera(rnd, tipo.sla, tope)
    u_res = rnd.random()
    clase = "rechazado" if u_res < TASA_RECHAZO else "aprobado"
    if not ver.caminos[clase]:
        clase = "aprobado" if ver.caminos["aprobado"] else "rechazado"
    if not ver.caminos[clase]:
        return None
    camino = _elegir_camino(rnd, ver.caminos[clase], ver.estados)
    n = len(camino)
    fracs = sorted(rnd.random() for _ in range(n - 1)) + [1.0]
    f_toma = [rnd.uniform(0.1, 0.5) for _ in range(n)]
    sello = rnd.uniform(5, 180)
    fin = alta + timedelta(days=dias)
    tiempos: list[datetime] = []
    tomas: list[datetime] = []
    prev = alta + timedelta(minutes=2)
    for i in range(n):
        t = max(alta + (fin - alta) * fracs[i], prev + timedelta(minutes=10))
        tomas.append(prev + (t - prev) * f_toma[i])
        tiempos.append(t)
        prev = t
    return _Plan(clase, camino, tiempos, tomas, tiempos[-1], dentro, sello)


def _camino_desde(ver: _Version, estado: int, clase: str) -> list[dict] | None:
    """Camino mas corto (BFS) desde un estado cualquiera a un final de la clase
    pedida (o de la otra si no hay). Para tramites cuyo ledger no sigue el plan."""
    for objetivo in (clase, "rechazado" if clase == "aprobado" else "aprobado"):
        cola: list[tuple[int, list[dict]]] = [(estado, [])]
        vistos = {estado}
        while cola:
            e, camino = cola.pop(0)
            if ver.estados.get(e, {}).get("es_final") and camino:
                if (objetivo == "rechazado") == _es_rechazo(camino, ver.estados):
                    return camino
                continue
            for t in ver.trans_por_origen.get(e, []):
                d = t["id_estado_destino"]
                if d in vistos or d not in ver.estados:
                    continue
                vistos.add(d)
                cola.append((d, camino + [t]))
    return None


# ── Datos del formulario ────────────────────────────────────────────────────

def _opciones(opciones) -> list:
    if isinstance(opciones, dict):
        opciones = opciones.get("opciones") or list(opciones.values())
    vals = []
    for o in opciones or []:
        vals.append(o.get("valor") if isinstance(o, dict) else o)
    return [v for v in vals if v is not None]


def _direccion(rnd: random.Random, ctx: _Ctx) -> dict:
    loc = demo_datos._elegir_localidad(rnd, ctx.cat_reclamos)
    lat, lon = demo_datos._ubicar(rnd, ctx.cat_reclamos, loc[2], loc[3], loc[4])
    return {"texto": f"{rnd.choice(demo_datos.CALLES)} {rnd.randint(100, 5900)}, {loc[1]}",
            "lat": float(lat), "lon": float(lon)}


def _cuit(rnd: random.Random) -> str:
    while True:
        base = f"{rnd.choice(('20', '27', '30'))}{rnd.randint(10_000_000, 49_999_999):08d}"
        ver = 11 - sum(int(d) * p for d, p in zip(base, [5, 4, 3, 2, 7, 6, 5, 4, 3, 2])) % 11
        if ver != 10:
            return f"{base}{0 if ver == 11 else ver}"


def _datos(rnd: random.Random, ctx: _Ctx, campos: list[dict], alta: datetime,
           id_agente_ini: int | None, codigo_tipo: str = "") -> dict:
    """Valores plausibles por tipo_dato (obligatorios siempre, opcionales al 60 %)."""
    datos: dict = {}
    for c in campos:
        if not c["obligatorio"] and rnd.random() > 0.6:
            continue
        nombre, tipo = c["nombre_interno"], c["tipo_dato"]
        nn = _norm(nombre)
        v = None
        if tipo in ("seleccion", "seleccion_multiple"):
            ops = _opciones(c.get("opciones_jsonb"))
            if ops:
                v = rnd.choice(ops) if tipo == "seleccion" else rnd.sample(ops, k=min(len(ops), rnd.randint(1, 2)))
        elif tipo == "direccion":
            v = _direccion(rnd, ctx)
        elif tipo in ("numero", "moneda"):
            val = c.get("validacion_jsonb") or {}
            lo, hi = (5_000, 90_000) if tipo == "moneda" else (1, 50)
            lo, hi = int(val.get("min", lo)), int(val.get("max", hi))
            v = rnd.randint(lo, max(lo, hi))
        elif tipo == "decimal":
            v = round(rnd.uniform(18, 420), 1)
        elif tipo == "booleano":
            v = rnd.random() < 0.5
        elif tipo in ("fecha", "fecha_hora"):
            if "hasta" in nn:
                d = alta + timedelta(days=rnd.randint(12, 40))
            elif "notific" in nn or "anterior" in nn:
                d = alta - timedelta(days=rnd.randint(3, 25))
            else:
                d = alta + timedelta(days=rnd.randint(5, 20))
            v = d.date().isoformat() if tipo == "fecha" else d.replace(microsecond=0).isoformat()
        elif tipo == "ciudadano" and ctx.pool_vecinos:
            v = rnd.choice(ctx.pool_vecinos)[0]
        elif tipo == "empresa" and ctx.pool_empresas:
            v = rnd.choice(ctx.pool_empresas)
        elif tipo == "agente":
            v = id_agente_ini or (rnd.choice(ctx.agentes_todos) if ctx.agentes_todos else None)
        elif tipo == "subarea" and ctx.subareas_con_agentes:
            v = rnd.choice(ctx.subareas_con_agentes)
        elif tipo == "equipo" and ctx.sub_de_equipo:
            v = rnd.choice(sorted(ctx.sub_de_equipo))
        elif tipo == "texto_largo":
            v = _texto_largo(rnd, nn, codigo_tipo)
        elif tipo in ("texto", "direccion_texto"):
            if "cuit" in nn:
                v = _cuit(rnd)
            elif "habilitacion" in nn:
                v = f"HAB-{rnd.randint(1000, 9999)}/{rnd.randint(2018, 2025)}"
            elif "horario" in nn:
                v = rnd.choice(["Lunes a viernes de 9 a 18", "Lunes a sábado de 8 a 20", "Martes a domingo de 12 a 23"])
            elif "dimension" in nn:
                v = f"{rnd.choice(['1,20', '2,00', '3,50'])} x {rnd.choice(['0,60', '0,80', '1,00'])} m"
            elif "acto" in nn or "numero" in nn:
                v = f"{rnd.choice(['RES', 'DISP', 'DEC'])}-{rnd.randint(100, 4999)}/{alta.year}"
            elif "asunto" in nn:
                v = rnd.choice(["Pedido de informe de gestión", "Solicitud de antecedentes", "Consulta interna"])
            else:
                v = "Según lo presentado en ventanilla"
        if v is not None:
            datos[nombre] = v
    return datos


# ── Escritura ───────────────────────────────────────────────────────────────

_SQL_MOV = text("""
    INSERT INTO tramite_movimiento (id_tramite, orden_secuencial, tipo, id_tipo_tramite_transicion,
                                    id_estado_origen, id_estado_destino, origen_jsonb, destino_jsonb,
                                    comentario, metadata_jsonb, id_agente, id_municipio,
                                    fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
    VALUES (:t, :o, :tipo, :tr, :eo, :ed, CAST(:oj AS jsonb), CAST(:dj AS jsonb), :c, CAST(:mj AS jsonb),
            :ag, :mun, CAST(:f AS timestamptz), CAST(:f AS timestamptz), :uid, :uid)
""")


@dataclass
class _Estado:
    """Estado vivo de un tramite mientras se le aplican pasos."""
    id_tramite: int
    id_version: int
    id_municipio: int
    estado: int
    dest_tipo: str | None
    dest_id: int | None
    tomado_por: int | None
    tomado_en: datetime | None
    orden: int
    entrada: datetime
    resultado: str
    ultimo: datetime
    iniciador_tipo: str
    id_ciudadano: int | None
    email: str | None
    id_subarea_tipo: int | None
    movs: list[dict] = field(default_factory=list)


def _sub_dest(ctx: _Ctx, st: _Estado) -> int | None:
    if st.dest_tipo == "subarea":
        return st.dest_id
    if st.dest_tipo == "equipo":
        return ctx.sub_de_equipo.get(st.dest_id)
    return None


def _mov(st: _Estado, ctx: _Ctx, tipo: str, fecha: datetime, id_agente: int, **kw) -> None:
    st.orden += 1
    st.movs.append({"t": st.id_tramite, "o": st.orden, "tipo": tipo, "tr": kw.get("tr"),
                    "eo": kw.get("eo"), "ed": kw.get("ed"),
                    "oj": json.dumps(kw["oj"]) if kw.get("oj") else None,
                    "dj": json.dumps(kw["dj"]) if kw.get("dj") else None,
                    "c": kw.get("c"), "mj": json.dumps(kw["mj"]) if kw.get("mj") else None,
                    "ag": id_agente, "mun": st.id_municipio, "f": fecha, "uid": ctx.uid})
    st.ultimo = max(st.ultimo, fecha)


async def _aplicar_pasos(db: AsyncSession, ctx: _Ctx, ver: _Version, st: _Estado,
                         pasos: list[tuple[datetime, datetime, dict]], rnd: random.Random,
                         nota: str | None, aplicar: bool) -> None:
    """Ejecuta transiciones [(fecha_toma, fecha, transicion)] sobre `st`, en orden,
    con sus movimientos (pase si quien_puede exige otra subarea, toma, visados,
    transicion). No sella el resultado (ver _sellar_resultado)."""
    for t_toma, t, tr in pasos:
        t_toma = max(t_toma, st.ultimo + timedelta(minutes=1))
        t = max(t, t_toma + timedelta(minutes=1))
        qp = tr.get("quien_puede_jsonb") or {}
        subs_qp = [s for s in (qp.get("subareas") or []) if isinstance(s, int)]
        sub_actual = _sub_dest(ctx, st)
        if subs_qp and (st.dest_tipo != "subarea" or sub_actual not in subs_qp):
            # La transicion la ejecuta otra subarea: el expediente se le pasa primero.
            nuevo = subs_qp[0]
            ag_pase = st.tomado_por or _agente(ctx, sub_actual, rnd) or _agente(ctx, nuevo, rnd)
            if ag_pase is None:
                return
            _mov(st, ctx, "pase", t_toma - timedelta(minutes=2) if t_toma - timedelta(minutes=2) > st.ultimo
                 else st.ultimo + timedelta(seconds=30), ag_pase,
                 oj={"tipo": st.dest_tipo, "id": st.dest_id}, dj={"tipo": "subarea", "id": nuevo},
                 c=f"Pase a {ctx.nombre_sub.get(nuevo, 'la subárea responsable')}." + (f" {nota}" if nota else ""))
            st.dest_tipo, st.dest_id, st.tomado_por, st.tomado_en = "subarea", nuevo, None, None
            t_toma = max(t_toma, st.ultimo + timedelta(minutes=1))
            t = max(t, t_toma + timedelta(minutes=1))
        if st.dest_tipo == "agente":
            agente = st.dest_id
        else:
            agente = st.tomado_por or _agente(ctx, _sub_dest(ctx, st), rnd)
        if agente is None:
            return
        if st.tomado_por != agente and st.dest_tipo != "agente":
            _mov(st, ctx, "toma", t_toma, agente)
            st.tomado_por, st.tomado_en = agente, t_toma
        # Visados (mig 73) del estado que se deja: aprobados por el area antes de avanzar.
        if st.estado in ver.con_requisitos and aplicar:
            r = await db.execute(text("""
                UPDATE tramite_aprobacion SET estado = 'aprobada', resuelto_por_agente = :ag,
                       resuelto_en = CAST(:f AS timestamptz), comentario = 'Visado sin observaciones.',
                       fecha_modificacion = CAST(:f AS timestamptz), id_usuario_modificacion = :uid
                 WHERE id_tramite = :t AND id_tipo_tramite_estado = :e AND activo AND estado <> 'aprobada'
                RETURNING id_tramite_aprobacion
            """), {"ag": agente, "f": t - timedelta(minutes=1), "uid": ctx.uid, "t": st.id_tramite, "e": st.estado})
            ids = [f.id_tramite_aprobacion for f in r.fetchall()]
            if ids:
                _mov(st, ctx, "aprobacion", t - timedelta(minutes=1), agente, c="Visados de la etapa aprobados.",
                     mj={"aprobadas": ids})
        destino = tr["id_estado_destino"]
        es_final = ver.estados.get(destino, {}).get("es_final", False)
        dest_auto = tr.get("destino_automatico_jsonb") or None
        comentario = None
        if tr.get("requiere_comentario"):
            comentario = rnd.choice(COMENTARIOS_RECHAZO if _es_rechazo([tr], ver.estados) else COMENTARIOS_AVANCE)
        if tr.get("requiere_adjunto"):
            comentario = ((comentario + " ") if comentario else "") + "Documentación presentada en ventanilla."
        if nota:
            comentario = ((comentario + " ") if comentario else "") + nota
        oj = dj = None
        if dest_auto:
            oj = {"tipo": st.dest_tipo, "id": st.dest_id}
            dj = {"tipo": dest_auto.get("tipo", "subarea"), "id": dest_auto.get("id")}
        _mov(st, ctx, "transicion", t, agente, tr=tr["id_tipo_tramite_transicion"], eo=st.estado, ed=destino,
             oj=oj, dj=dj, c=comentario)
        st.estado, st.entrada = destino, t
        if dest_auto and dest_auto.get("id"):
            st.dest_tipo, st.dest_id = dest_auto.get("tipo", "subarea"), int(dest_auto["id"])
        if dest_auto or es_final:
            st.tomado_por, st.tomado_en = None, None
        # Visados del estado al que se entra (helper del modulo; fechas del plan).
        if destino in ver.con_requisitos and aplicar:
            n = await svc_aprob.instanciar_aprobaciones_de_estado(db, st.id_tramite, st.id_version, destino)
            if n:
                await db.execute(text("""
                    UPDATE tramite_aprobacion SET fecha_alta = CAST(:f AS timestamptz),
                           fecha_modificacion = CAST(:f AS timestamptz), id_usuario_alta = :uid
                     WHERE id_tramite = :t AND id_tipo_tramite_estado = :e AND estado = 'pendiente'
                """), {"f": t, "uid": ctx.uid, "t": st.id_tramite, "e": destino})


def _sellar_resultado(ctx: _Ctx, ver: _Version, st: _Estado, plan_resultado: str, ultima: dict | None,
                      t_fin: datetime, sello_min: float, rnd: random.Random, ahora: datetime,
                      nota: str | None) -> bool:
    """Resultado del tramite que llego a un estado final. Automatico si la transicion
    final es aprobar/rechazar (mig 101, mismo comentario y metadata que
    ciclo_vida.derivar_resultado_por_transicion); si no, lo sella un supervisor de la
    gestion `sello_min` minutos despues (POST /resultado). Devuelve True si sello."""
    accion = (ultima or {}).get("tipo_accion") or ""
    agente = st.tomado_por or _agente(ctx, st.id_subarea_tipo, rnd)
    if accion in ("aprobar", "rechazar"):
        nuevo = "aprobado" if accion == "aprobar" else "rechazado"
        if agente is None:
            return False
        _mov(st, ctx, "resultado", t_fin + timedelta(seconds=1), agente,
             c=f"Resultado derivado de la transición final ({accion}).",
             mj={"resultado_anterior": "pendiente", "resultado_nuevo": nuevo, "automatico": True,
                 "tipo_accion": accion})
    else:
        t = t_fin + timedelta(minutes=sello_min)
        if t > ahora:
            return False
        sups = ctx.supervisores_sub.get(st.id_subarea_tipo) or []
        firmante = rnd.choice(sups) if sups else agente
        if firmante is None:
            return False
        nuevo = plan_resultado
        _mov(st, ctx, "resultado", t, firmante,
             c=("Trámite aprobado." if nuevo == "aprobado" else "Trámite rechazado.") + (f" {nota}" if nota else ""),
             mj={"resultado_anterior": "pendiente", "resultado_nuevo": nuevo})
    st.resultado = nuevo
    return True


async def _guardar(db: AsyncSession, st: _Estado, ctx: _Ctx) -> None:
    if st.movs:
        await db.execute(_SQL_MOV, st.movs)
    await db.execute(text("""
        UPDATE tramite SET id_tipo_tramite_estado_actual = :e, fecha_entrada_estado_actual = CAST(:fe AS timestamptz),
               destinatario_actual_tipo = :dt,
               id_subarea_actual = :dsa, id_equipo_actual = :deq, id_agente_actual = :dag,
               id_agente_tomado_por = :tp, tomado_en = CAST(:te AS timestamptz),
               desist_aviso_nivel = 0, desist_aviso_en = NULL, resultado = :res,
               fecha_modificacion = CAST(:fm AS timestamptz), id_usuario_modificacion = :uid
         WHERE id_tramite = :id
    """), {"e": st.estado, "fe": st.entrada, "dt": st.dest_tipo,
           "dsa": st.dest_id if st.dest_tipo == "subarea" else None,
           "deq": st.dest_id if st.dest_tipo == "equipo" else None,
           "dag": st.dest_id if st.dest_tipo == "agente" else None,
           "tp": st.tomado_por, "te": st.tomado_en if st.tomado_por else None,
           "res": st.resultado, "fm": st.ultimo, "uid": ctx.uid, "id": st.id_tramite})
    st.movs = []


def _envio_encuesta(rnd: random.Random, ctx: _Ctx, st: _Estado, t_sello: datetime,
                    ahora: datetime) -> tuple[dict, dict | None] | None:
    """Encuesta CSAT del tramite terminado (iniciador ciudadano), nunca 'pendiente'."""
    if st.iniciador_tipo != "ciudadano" or not ctx.id_plantilla or not st.email or rnd.random() > TASA_ENCUESTA:
        return None
    par = demo_datos._armar_envio(
        random.Random(rnd.random()),
        {"fecha_cierre": t_sello, "id_ciudadano": st.id_ciudadano, "email": st.email,
         "id_subarea": st.id_subarea_tipo}, ahora, ctx.id_plantilla, ctx.uid)
    return par


async def _escribir_encuesta(db: AsyncSession, par, id_tramite: int) -> int:
    envio, respuesta = par
    id_env = await db.scalar(text("""
        INSERT INTO encuesta_envio (id_plantilla, id_ciudadano, id_tramite, email_destino_snapshot,
                                    fecha_envio, fecha_apertura, fecha_completada, fecha_expiracion,
                                    estado, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta)
        VALUES (:id_plantilla, :id_ciudadano, :it, :email, :fecha_envio, :fecha_apertura,
                :fecha_completada, :fecha_expiracion, :estado, :id_subarea, :fecha_envio, :fecha_envio, :uid)
        RETURNING id_encuesta_envio
    """), {**{k: envio[k] for k in ("id_plantilla", "id_ciudadano", "email", "fecha_envio", "fecha_apertura",
                                     "fecha_completada", "fecha_expiracion", "estado", "id_subarea", "uid")},
           "it": id_tramite})
    if respuesta:
        await db.execute(demo_datos._SQL_INSERT_RESPUESTA, {**respuesta, "id_envio": id_env})
    return 1


def _pasos_a_realizar(plan: _Plan, ver: _Version, desde_k: int, piso: datetime, ahora: datetime,
                      forzar: bool) -> list[tuple[datetime, datetime, dict]]:
    """Transiciones del plan desde la k-esima con fecha <= ahora (forzar: todas,
    comprimidas contra ahora). Sin forzar, nunca deja el tramite parado en un estado
    que espera al iniciador (el timer de desistimiento le mandaria mails)."""
    restantes = list(zip(plan.tomas[desde_k:], plan.tiempos[desde_k:], plan.camino[desde_k:]))
    if forzar:
        n = len(restantes)
        out = []
        for i, (tt, t, tr) in enumerate(restantes):
            lim = ahora - timedelta(minutes=3 * (n - i))
            out.append((min(max(tt, piso), lim - timedelta(minutes=1)), min(max(t, piso), lim), tr))
        return out
    vencidas = [x for x in restantes if x[1] <= ahora]
    while vencidas and len(vencidas) < len(restantes) and \
            ver.estados.get(vencidas[-1][2]["id_estado_destino"], {}).get("espera_iniciador"):
        vencidas.pop()
    return vencidas


def _plan_desde_estado(plan: _Plan, ver: _Version, estado: int, piso: datetime) -> _Plan | None:
    """Re-plan para un tramite cuyo ledger no sigue su plan (datos viejos o catalogo
    cambiado): camino mas corto desde su estado actual a un final de la misma clase,
    repartido entre el piso y el fin del plan (o pegado al piso si ya paso)."""
    camino = _camino_desde(ver, estado, plan.resultado)
    if not camino:
        return None
    fin = max(plan.fin, piso + timedelta(hours=6 * len(camino)))
    n = len(camino)
    tiempos = [piso + (fin - piso) * (i + 1) / n for i in range(n)]
    tomas = [(tiempos[i - 1] if i else piso) + (tiempos[i] - (tiempos[i - 1] if i else piso)) * 0.3 for i in range(n)]
    clase = "rechazado" if _es_rechazo(camino, ver.estados) else "aprobado"
    return _Plan(clase, camino, tiempos, tomas, tiempos[-1], plan.dentro, plan.sello_min)


# ── API del modulo ──────────────────────────────────────────────────────────

async def generar_periodo_tramites(db: AsyncSession, desde: date, hasta: date,
                                   min_mensual: int = TRAMITES_MENSUAL[0],
                                   max_mensual: int = TRAMITES_MENSUAL[1],
                                   semilla: int | None = None,
                                   ahora: datetime | None = None) -> dict:
    """Genera expedientes demo en [desde, hasta] (dias habiles) aplicando su plan
    hasta `ahora`. Idempotente por dia. Commitea al final."""
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(UTC)
    ctx = await _cargar_ctx(db, rnd, crear_pools=True)
    out = {"tramites": 0, "por_tipo": {}, "terminados": 0, "pendientes": 0, "aprobados": 0, "rechazados": 0,
           "encuestas": 0, "movimientos": 0, "dias_omitidos_con_demo": 0, "tipos_sin_circuito": [],
           "desde": str(desde), "hasta": str(hasta)}
    tipos = [t for t in ctx.tipos.values()
             if ctx.versiones[t.id_version].caminos["aprobado"] or ctx.versiones[t.id_version].caminos["rechazado"]]
    out["tipos_sin_circuito"] = sorted(t.codigo for t in ctx.tipos.values() if t not in tipos)
    if not tipos or not ctx.agentes_todos:
        out["omitido"] = "sin tipos con circuito publicado o sin agentes activos"
        return out
    r = await db.execute(text("""
        SELECT DISTINCT (fecha_alta AT TIME ZONE 'UTC')::date AS d FROM tramite
         WHERE id_usuario_alta = :uid AND fecha_alta >= CAST(:d0 AS timestamptz) AND fecha_alta < CAST(:d1 AS timestamptz)
    """), {"uid": ctx.uid, "d0": datetime(desde.year, desde.month, desde.day, tzinfo=UTC),
           "d1": datetime(hasta.year, hasta.month, hasta.day, tzinfo=UTC) + timedelta(days=1)})
    ya = {f.d for f in r.fetchall()}

    base: list[dict] = []
    for dia in demo_datos.dias_rango(desde, hasta):
        if dia > ahora.date():
            continue
        if dia in ya:
            out["dias_omitidos_con_demo"] += 1
            continue
        for _ in range(demo_datos.volumen_dia(rnd, "tramites", dia, min_mensual, max_mensual, semilla,
                                              PESO_DIA_HABIL)):
            alta = datetime(dia.year, dia.month, dia.day, rnd.randint(12, 19), rnd.randint(0, 59),
                            rnd.randint(0, 59), tzinfo=UTC)  # 9 a 16 h de la ventanilla
            tipo = rnd.choices(tipos, weights=[t.peso for t in tipos], k=1)[0]
            if alta <= ahora - timedelta(minutes=5):
                base.append({"alta": alta, "tipo": tipo})
    base.sort(key=lambda x: x["alta"])
    ids = await demo_datos.reservar_ids(db, "tramite", "id_tramite", len(base))

    for item, id_tramite in zip(base, ids):
        tipo: _Tipo = item["tipo"]
        alta: datetime = item["alta"]
        ver = ctx.versiones[tipo.id_version]
        plan = _plan_tramite(id_tramite, alta, tipo, ver)
        if plan is None:
            continue
        # Iniciador y destinatario inicial.
        ini = rnd.choice(tipo.iniciadores) if tipo.iniciadores else "ciudadano"
        id_c = id_e = id_sa = None
        email = None
        if ini == "ciudadano" and ctx.pool_vecinos:
            id_c, email = rnd.choice(ctx.pool_vecinos)
        elif ini == "empresa" and ctx.pool_empresas:
            id_e = rnd.choice(ctx.pool_empresas)
        elif ini == "area_interna" and ctx.subareas_con_agentes:
            id_sa = rnd.choice(ctx.subareas_con_agentes)
        else:
            continue
        if ini == "area_interna":
            dest = id_sa
        else:
            dest = ctx.mesa_entradas or tipo.id_subarea or ctx.subareas_con_agentes[0]
        ag_ini = _agente(ctx, dest, rnd)
        if ag_ini is None:
            continue
        datos = _datos(rnd, ctx, ver.campos, alta, ag_ini, tipo.codigo)
        detalle = next((v["texto"] for v in datos.values() if isinstance(v, dict) and v.get("texto")), None)
        asunto = f"{tipo.nombre}" + (f": {detalle}" if detalle else "")
        # Numerador atomico del modulo; si un numero ya existiera (expediente cargado a mano
        # sin pasar por el numerador) se pide el siguiente: un choque abortaria la corrida.
        for _ in range(50):
            correlativo = await svc_num.proximo_numero(db, tipo.id, tipo.id_municipio, alta.year)
            numero = svc_num.formatear_numero(tipo.prefijo, tipo.separador, tipo.incl_mun, tipo.incl_anio,
                                              tipo.cod_muni, alta.year, correlativo, tipo.largo)
            if not await db.scalar(text(
                    "SELECT 1 FROM tramite WHERE numero_expediente = :n AND id_municipio = :m"),
                    {"n": numero, "m": tipo.id_municipio}):
                break
        await db.execute(text("""
            INSERT INTO tramite (id_tramite, numero_expediente, id_tipo_tramite_version, asunto, datos_jsonb,
                                 iniciador_tipo, id_ciudadano_iniciador, id_empresa_iniciadora, id_subarea_iniciadora,
                                 id_agente_iniciador, id_tipo_tramite_estado_actual, fecha_entrada_estado_actual,
                                 destinatario_actual_tipo, id_subarea_actual, activo, id_municipio,
                                 fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
            VALUES (:id, :num, :ver, :asunto, CAST(:datos AS jsonb), :ini, :c, :e, :sa, :ag, :est,
                    CAST(:fa AS timestamptz), 'subarea', :dest, TRUE, :mun,
                    CAST(:fa AS timestamptz), CAST(:fa AS timestamptz), :uid, :uid)
        """), {"id": id_tramite, "num": numero, "ver": tipo.id_version, "asunto": asunto[:250],
               "datos": json.dumps(datos), "ini": ini, "c": id_c, "e": id_e, "sa": id_sa, "ag": ag_ini,
               "est": ver.inicial, "fa": alta, "dest": dest, "mun": tipo.id_municipio, "uid": ctx.uid})
        st = _Estado(id_tramite, tipo.id_version, tipo.id_municipio, ver.inicial, "subarea", dest, None, None,
                     0, alta, "pendiente", alta, ini, id_c, email, tipo.id_subarea)
        _mov(st, ctx, "creacion", alta, ag_ini, ed=ver.inicial, dj={"tipo": "subarea", "id": dest},
             mj={"datos_iniciales": datos})
        _mov(st, ctx, "numeracion", alta + timedelta(seconds=1), ag_ini,
             mj={"numero_expediente": numero, "correlativo": correlativo, "anio": alta.year})
        if ver.inicial in ver.con_requisitos:
            await svc_aprob.instanciar_aprobaciones_de_estado(db, id_tramite, tipo.id_version, ver.inicial)
        pasos = _pasos_a_realizar(plan, ver, 0, alta, ahora, forzar=False)
        await _aplicar_pasos(db, ctx, ver, st, pasos, rnd, None, aplicar=True)
        terminado = ver.estados.get(st.estado, {}).get("es_final", False)
        if terminado and len(pasos) == len(plan.camino):
            if _sellar_resultado(ctx, ver, st, plan.resultado, plan.camino[-1], plan.fin, plan.sello_min,
                                 rnd, ahora, None):
                out["aprobados" if st.resultado == "aprobado" else "rechazados"] += 1
                par = _envio_encuesta(rnd, ctx, st, st.ultimo, ahora)
                if par:
                    out["encuestas"] += await _escribir_encuesta(db, par, id_tramite)
        out["movimientos"] += len(st.movs)
        await _guardar(db, st, ctx)
        out["tramites"] += 1
        out["por_tipo"][tipo.codigo] = out["por_tipo"].get(tipo.codigo, 0) + 1
        out["terminados" if terminado else "pendientes"] += 1
    await db.commit()
    return out


_SQL_TRAMITES_ABIERTOS = """
    SELECT t.id_tramite, t.numero_expediente, t.id_tipo_tramite_version, t.id_municipio, t.fecha_alta,
           t.id_tipo_tramite_estado_actual, t.fecha_entrada_estado_actual, t.destinatario_actual_tipo,
           t.id_subarea_actual, t.id_equipo_actual, t.id_agente_actual, t.id_agente_tomado_por, t.tomado_en,
           t.resultado, t.iniciador_tipo, t.id_ciudadano_iniciador, t.id_usuario_alta, c.email,
           v.id_tipo_tramite, e.es_final,
           (SELECT COUNT(*) FROM tramite_movimiento m WHERE m.id_tramite = t.id_tramite
             AND m.tipo = 'transicion' AND m.activo) AS n_trans,
           (SELECT COALESCE(MAX(m.orden_secuencial), 0) FROM tramite_movimiento m WHERE m.id_tramite = t.id_tramite) AS orden,
           (SELECT MAX(m.fecha_alta) FROM tramite_movimiento m WHERE m.id_tramite = t.id_tramite) AS ultimo,
           (SELECT m.fecha_alta FROM tramite_movimiento m WHERE m.id_tramite = t.id_tramite AND m.tipo = 'transicion'
             AND m.activo ORDER BY m.orden_secuencial DESC LIMIT 1) AS t_ultima_trans,
           (SELECT m.id_tipo_tramite_transicion FROM tramite_movimiento m WHERE m.id_tramite = t.id_tramite
             AND m.tipo = 'transicion' AND m.activo ORDER BY m.orden_secuencial DESC LIMIT 1) AS id_ultima_trans
      FROM tramite t
      JOIN tipo_tramite_version v ON v.id_tipo_tramite_version = t.id_tipo_tramite_version
      JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
      LEFT JOIN ciudadanos c ON c.id_ciudadano = t.id_ciudadano_iniciador
     WHERE t.activo AND t.resultado = 'pendiente' AND t.fecha_archivado IS NULL
       AND t.fecha_alta <= CAST(:ahora AS timestamptz) AND {filtro}
     ORDER BY t.id_tramite
"""


async def _avanzar(db: AsyncSession, ctx: _Ctx, filas: list, rnd: random.Random, ahora: datetime, *,
                   aplicar: bool, forzar: bool) -> dict:
    out = {"evaluados": len(filas), "transiciones": 0, "terminados": 0, "resultados_sellados": 0,
           "aprobados": 0, "rechazados": 0, "dentro_sla": 0, "fuera_sla": 0, "encuestas": 0,
           "sin_camino": 0, "no_demo": 0, "omitidos_piso_futuro": 0}
    for f in filas:
        tipo = ctx.tipos.get(f.id_tipo_tramite)
        ver = await _version(db, ctx, f.id_tipo_tramite_version)
        piso = max(f.ultimo or f.fecha_alta, f.fecha_alta)
        if piso > ahora:
            out["omitidos_piso_futuro"] += 1
            continue
        es_demo = f.id_usuario_alta == ctx.uid
        out["no_demo"] += 0 if es_demo else 1
        if tipo is None:  # tipo dado de baja: el expediente igual se cierra con su version
            sla = SLA_DEFAULT
            id_sub_tipo = None
            plan_tipo = _Tipo(f.id_tipo_tramite, "", "", "", "-", False, False, 4, [], f.id_tipo_tramite_version,
                              None, sla, f.id_municipio, "", PESO_OTRO)
        else:
            plan_tipo, id_sub_tipo = tipo, tipo.id_subarea
        plan = _plan_tramite(f.id_tramite, f.fecha_alta, plan_tipo, ver)
        dest_tipo = f.destinatario_actual_tipo
        dest_id = f.id_subarea_actual or f.id_equipo_actual or f.id_agente_actual
        st = _Estado(f.id_tramite, f.id_tipo_tramite_version, f.id_municipio, f.id_tipo_tramite_estado_actual,
                     dest_tipo, dest_id, f.id_agente_tomado_por, f.tomado_en, int(f.orden or 0),
                     f.fecha_entrada_estado_actual, f.resultado, piso, f.iniciador_tipo,
                     f.id_ciudadano_iniciador, f.email, id_sub_tipo)
        nota = None if es_demo else "Cierre de atraso de datos de prueba."
        k = int(f.n_trans or 0)
        if f.es_final:
            # Ya termino: solo falta el resultado.
            if plan is None:
                clase = "aprobado"
            else:
                clase = plan.resultado
            ultima = None
            if f.id_ultima_trans:
                for lista in ver.trans_por_origen.values():
                    for tr in lista:
                        if tr["id_tipo_tramite_transicion"] == f.id_ultima_trans:
                            ultima = tr
            t_fin = f.t_ultima_trans or f.fecha_entrada_estado_actual
            sello = plan.sello_min if plan else 60.0
            if forzar and t_fin + timedelta(minutes=sello) > ahora:
                sello = max(0.5, (ahora - t_fin).total_seconds() / 60 - 1)
            if ultima is None and forzar:
                ultima = {"tipo_accion": None}
            sellado = _sellar_resultado(ctx, ver, st, clase, ultima, max(t_fin, piso), sello, rnd, ahora, nota)
            if sellado:
                out["resultados_sellados"] += 1
                out["aprobados" if st.resultado == "aprobado" else "rechazados"] += 1
                if aplicar:
                    if es_demo:
                        par = _envio_encuesta(rnd, ctx, st, st.ultimo, ahora)
                        if par:
                            out["encuestas"] += await _escribir_encuesta(db, par, f.id_tramite)
                    await _guardar(db, st, ctx)
            continue
        if plan is None:
            out["sin_camino"] += 1
            continue
        esperado = plan.camino[k - 1]["id_estado_destino"] if 0 < k <= len(plan.camino) else ver.inicial
        if k > len(plan.camino) or esperado != f.id_tipo_tramite_estado_actual:
            plan = _plan_desde_estado(plan, ver, f.id_tipo_tramite_estado_actual, piso)
            k = 0
            if plan is None:
                out["sin_camino"] += 1
                continue
        pasos = _pasos_a_realizar(plan, ver, k, piso, ahora, forzar)
        if not pasos:
            continue
        await _aplicar_pasos(db, ctx, ver, st, pasos, rnd, nota, aplicar)
        out["transiciones"] += len(pasos)
        terminado = ver.estados.get(st.estado, {}).get("es_final", False)
        if terminado:
            out["terminados"] += 1
            ok = demo_sla.dentro_sla(f.fecha_alta, st.entrada, plan_tipo.sla)
            out["dentro_sla" if ok else "fuera_sla"] += 1
            sello = plan.sello_min
            if forzar and st.entrada + timedelta(minutes=sello) > ahora:
                sello = max(0.5, (ahora - st.entrada).total_seconds() / 60 - 1)
            if _sellar_resultado(ctx, ver, st, plan.resultado, pasos[-1][2], st.entrada, sello, rnd, ahora, nota):
                out["resultados_sellados"] += 1
                out["aprobados" if st.resultado == "aprobado" else "rechazados"] += 1
                if aplicar and es_demo:
                    par = _envio_encuesta(rnd, ctx, st, st.ultimo, ahora)
                    if par:
                        out["encuestas"] += await _escribir_encuesta(db, par, f.id_tramite)
        if aplicar:
            await _guardar(db, st, ctx)
    return out


async def avanzar_pendientes_tramites(db: AsyncSession, semilla: int | None = None,
                                      ahora: datetime | None = None) -> dict:
    """Cron: aplica el plan de los tramites demo abiertos de la ventana reciente
    (transiciones con las fechas del plan, resultado, encuesta). Idempotente."""
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(UTC)
    ctx = await _cargar_ctx(db, rnd, crear_pools=False)
    if ctx is None:
        return {"detalle": "sin usuario generador: nada que avanzar"}
    r = await db.execute(text(_SQL_TRAMITES_ABIERTOS.format(
        filtro="t.id_usuario_alta = :uid AND t.fecha_alta >= CAST(:ventana AS timestamptz)")),
        {"uid": ctx.uid, "ahora": ahora, "ventana": ahora - timedelta(days=VENTANA_AVANCE_DIAS)})
    out = await _avanzar(db, ctx, r.fetchall(), rnd, ahora, aplicar=True, forzar=False)
    await db.commit()
    return out


async def cerrar_atraso_tramites(db: AsyncSession, dias: int = 21, aplicar: bool = False,
                                 incluir_no_demo: bool = False, semilla: int | None = None,
                                 ahora: datetime | None = None) -> dict:
    """Cierre del atraso: tramites abiertos (resultado pendiente, no archivados) con
    alta de hace mas de `dias` -> recorren el circuito hasta un estado final y
    sellan su resultado; los que ya estan en un estado final con resultado
    pendiente solo sellan el resultado. Demo salvo `incluir_no_demo` (los de
    seed/QA, con la nota "cierre de atraso de datos de prueba", sin encuesta).
    Sin mails (todo SQL). Dry-run si aplicar=False (devuelve conteos y la lista de
    expedientes que no son demo). Commitea si aplica."""
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(UTC)
    ctx = await _cargar_ctx(db, rnd, crear_pools=False)
    if ctx is None:
        return {"detalle": "sin usuario generador: nada que cerrar"}
    filtro_demo = "TRUE" if incluir_no_demo else "t.id_usuario_alta = :uid"
    r = await db.execute(text(_SQL_TRAMITES_ABIERTOS.format(
        filtro=f"({filtro_demo}) AND t.fecha_alta < CAST(:limite AS timestamptz)")),
        {"uid": ctx.uid, "ahora": ahora, "limite": ahora - timedelta(days=dias)})
    filas = r.fetchall()
    out = await _avanzar(db, ctx, filas, rnd, ahora, aplicar=aplicar, forzar=True)
    out["no_demo_detalle"] = [
        {"numero": f.numero_expediente, "alta": f.fecha_alta.date().isoformat(), "en_estado_final": f.es_final}
        for f in filas if f.id_usuario_alta != ctx.uid][:60]
    if aplicar:
        await db.commit()
    return out
