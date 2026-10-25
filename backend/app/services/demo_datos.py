# -*- coding: utf-8 -*-
"""Generador de datos demo para los tableros BI (municipio ficticio San Andres).

Crea reclamos + historial + OT operativas + encuestas CSAT (+ vecinos nuevos si
el pool es chico) con distribuciones derivadas del set de referencia de gestion
municipal (demo_datos_ref.py). Lo consumen:

  - POST /api/v1/demo/poblar (routes/demo_datos.py) — cron DIARIO de GitHub
    Actions (X-Dispatcher-Token) o admin JWT; tambien el modo `cerrar_atraso`.
  - backend/seed_demo_bi.py — driver local.
  - Hermanos: app/services/demo_atencion.py (turnos + colero + Guardia + eventos,
    2026-09-19) y app/services/demo_tramites.py (expedientes, 2026-10-21):
    mismo usuario generador, mismos vecinos demo, mismo endpoint y cron.

CIERRES SLA-AWARE (decision de Cesar 2026-10-21, app/services/demo_sla.py): cada
reclamo tiene un PLAN determinista calculado desde su id + fecha de alta + SLA
del tipo (demora, si cae dentro o fuera del SLA, asignacion, espera,
cancelacion). Cada mes una fraccion p entre 60 % y 85 % cierra dentro del SLA.
El generador aplica el plan hasta "ahora" y avanzar_pendientes lo sigue
aplicando dias despues con las MISMAS fechas: lo que queda pendiente es lo de
las ultimas ~3 semanas cuyo cierre planificado todavia no llego (~10 %); nada
dura mas de 20 dias, asi que lo viejo siempre queda cerrado.

OT OPERATIVAS (2026-10-21): todo reclamo que pasa por "En gestion" tiene su OT
(no es_auditoria) asignada con la regla del producto (agente nivel 4 no auditor
de la gestion o cuadrilla segun tipo_reclamo.asignacion_a, menor carga y
rotacion). Los reclamos NO se agendan: ninguna OT demo crea ocupacion.

IDEMPOTENCIA POR DIA: un dia que ya tiene reclamos demo (no subreclamos ni
retrabajos) se saltea, asi el cron diario y un dispatch manual sobre el mismo
rango no duplican (incidente 2026-08-31).

Disenio PARAMETRIZADO (pre-IT-01 multi-tenant): los catalogos (tipos, subareas,
estados, localidades, plantilla de encuesta) se resuelven por NOMBRE en runtime
contra la DB del entorno — nunca por id, que diverge entre local y prod.
Todo lo insertado queda atribuido al usuario 'generador.demo' (se crea INACTIVO
si no existe): identificar/borrar/migrar a un tenant = filtrar por ese
id_usuario_alta.

ALCANCE MULTI-TENANT (definicion de Cesar 2026-08-30): el generador y su cron
aplican datos SOLO al municipio DEMO (San Andres). Desde IT-01 F2 el municipio
demo es el de las direcciones sin prefijo (municipio_demo: `direccion_base`; F4 lo
cambia por municipios.estado = 'demo'): todo catalogo, agente y vecino se lee de
ese municipio y todo INSERT lo lleva (las filas hijas, el de su reclamo). JAMAS
generar datos en tenants reales.

REGLA CRITICA: jamas crear encuesta_envio en estado 'pendiente' — el dispatcher
horario de encuestas MANDA MAIL a los pendientes. Solo estados 'enviada',
'completada' o 'expirada'. Ningun paso llama a servicios de notificacion: todo
se escribe por SQL (sin mails ni push).
"""
from __future__ import annotations

import calendar
import logging
import math
import random
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import autoasignacion
from app.services import demo_datos_ref as ref
from app.services import demo_sla
from app.services.geo_limite import leer_limite, punto_en_limite

logger = logging.getLogger(__name__)

USERNAME_GENERADOR = "generador.demo"
EMAIL_GENERADOR = "generador.demo@vecinos-demo.zaris.com.ar"
DOMINIO_VECINO_DEMO = "vecinos-demo.zaris.com.ar"

ESTADO_SIN_ASIGNAR = "Sin asignar"
ESTADO_EN_GESTION = "En gestión"
ESTADO_EN_ESPERA = "En espera"
ESTADO_EN_AUDITORIA = "En auditoría"
ESTADO_AUDITADO = "Auditado"
ESTADO_RESUELTO = "Resuelto"
ESTADO_CANCELADO = "Cancelado"
ESTADOS_PENDIENTES = (ESTADO_SIN_ASIGNAR, ESTADO_EN_GESTION, ESTADO_EN_ESPERA)
# Auditoria POSTERIOR al cierre (mig 112): un resuelto puede estar 'En auditoria'
# (pendiente del auditor) o 'Auditado'; para encuestas y tiempos sigue siendo un
# resuelto (su fecha_cierre es la del primer cierre).
ESTADOS_GESTION_CERRADA_OK = (ESTADO_RESUELTO, ESTADO_EN_AUDITORIA, ESTADO_AUDITADO)
TASA_AUDITORIA = 0.08      # fraccion de resueltos que la supervision manda a auditar
TASA_OBSERVADA = 0.20      # fraccion de auditorias que terminan observadas (con retrabajo)
TASA_CANCELADO = 0.04      # fraccion de reclamos que se cancelan
TASA_SUBRECLAMO = 0.04     # fraccion de reclamos largos (>= 4 dias) con un subreclamo
TASA_ENCUESTA = 0.85       # fraccion de resueltos con encuesta enviada
SLA_DEFAULT_RECLAMO = 5    # tipo sin SLA: duracion objetivo en dias (el BI no lo cuenta en % SLA)
# avanzar_pendientes (cron) solo mira los reclamos demo de los ultimos N dias: con el
# tope de 20 dias del plan, nada generado por esta version queda afuera; lo pendiente
# mas viejo (datos anteriores) es el "atraso" y se cierra con cerrar_atraso_reclamos.
VENTANA_AVANCE_DIAS = 30

OBSERVACIONES_AUDITORIA = [
    "quedó un desnivel en el borde de la reparación",
    "faltó señalizar la zona intervenida",
    "el trabajo no cubre todo el tramo reclamado",
    "la reparación cedió a los pocos días",
    "quedaron restos de material sobre la vereda",
]
# Texto de resolucion que ve el vecino (reclamos.resolucion, mig 117) y cierre de la OT.
RESOLUCIONES = [
    "Se realizó el trabajo solicitado.",
    "La cuadrilla resolvió el inconveniente en el lugar.",
    "Se verificó el lugar y se solucionó el problema reportado.",
    "Trabajo terminado: el sector quedó en condiciones.",
    "Se atendió el reclamo y se normalizó el servicio.",
    "Intervención realizada según lo informado por el vecino.",
]
MOTIVOS_CANCELACION = [
    "Reclamo duplicado: ya había uno abierto por el mismo problema.",
    "No corresponde a la gestión municipal; se informó al vecino.",
    "El vecino informó que el problema ya estaba resuelto.",
    "No se encontró el problema en la dirección indicada.",
]

CANALES = [("telefono", 40), ("web", 22), ("app_movil", 15), ("presencial", 10),
           ("whatsapp", 8), ("oficio", 3), ("otro", 2)]
PRIORIDADES = [("Media", 70), ("Alta", 15), ("Baja", 15)]
FUENTES_GEO = [("pin_manual", 45), ("geocoding_osm", 35), ("gps_dispositivo", 20)]
# Distribucion de score 1-5 derivada del export de encuestas de referencia
# (Q1: 5=50.5% 4=17.5% 3=6.6% 2=7.4% 1=18.0% de las respondidas).
SCORES = [(5, 505), (4, 175), (3, 66), (2, 74), (1, 180)]
# Peso relativo de cada dia de la semana (lun..dom) en el volumen de reclamos.
PESO_DIA_SEMANA = (1.12, 1.12, 1.12, 1.12, 1.12, 0.72, 0.56)

CALLES = [
    "Av. Maipú", "Av. del Libertador", "Hipólito Yrigoyen", "Bartolomé Mitre",
    "Juan B. Justo", "Av. San Martín", "Belgrano", "Sarmiento", "Rivadavia",
    "Moreno", "Lavalle", "Güemes", "Pelliza", "Ugarte", "Malaver", "Laprida",
    "Alberdi", "Independencia", "Córdoba", "Tucumán", "Catamarca", "Chacabuco",
    "Ayacucho", "Zufriategui", "Melo", "Paraná", "Arenales", "Santa Fe",
    "25 de Mayo", "9 de Julio", "Italia", "España", "Francia", "Roca",
    "Las Heras", "Pueyrredón",
]

FRASES = [
    "{tipo} en {dir}. El vecino solicita intervención del municipio.",
    "Vecino informa: {tipo_lower} frente a {dir}.",
    "Se registra {tipo_lower} en la zona de {dir}. Solicita pronta respuesta.",
    "Reclamo reiterado por {tipo_lower} en {dir}; el vecino indica que ya lo había reportado.",
    "El vecino pide inspección por {tipo_lower} en {dir}.",
    "Llamado a la línea de atención por {tipo_lower} en {dir}.",
    "Reporte desde la app del vecino: {tipo_lower}. Ubicación: {dir}.",
    "{tipo} sobre {dir}, a metros de la esquina.",
]
COLETILLAS = [
    " Hay riesgo para los peatones.",
    " Afecta el ingreso a su domicilio.",
    " Sucede desde hace varios días.",
    " Pide que lo contacten al resolverlo.",
    " Es zona de tránsito escolar.",
    "",
    "",
    "",
]


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _elegir(rnd: random.Random, pares):
    vals = [p[0] for p in pares]
    pesos = [p[1] for p in pares]
    return rnd.choices(vals, weights=pesos, k=1)[0]


_NOMBRES_FEM_SIN_A = {
    "ines", "beatriz", "mercedes", "dolores", "soledad", "isabel", "raquel",
    "noemi", "mabel", "ester", "edith", "elizabeth", "carmen", "lourdes",
    "belen", "rocio", "solange", "nelida", "luz", "gisele", "denise", "nicole",
    "yael", "abril", "ailen", "maite", "milagros", "aylen", "nieves", "leonor",
}


def _sexo_de(nombre: str) -> str:
    """Heuristica simple para que el sexo del vecino demo no desentone con su
    nombre (el dato solo alimenta la ficha BUC, no ninguna visualizacion)."""
    primero = _norm(nombre.split()[0])
    if primero.endswith("a") or primero in _NOMBRES_FEM_SIN_A:
        return "MUJER"
    return "HOMBRE"


def _rama(clasificacion: int) -> str:
    if clasificacion >= 4:
        return "satisfechos"
    if clasificacion == 3:
        return "neutrales"
    return "insatisfechos"


def _cuil_valido(dni: int, sexo: str) -> str:
    """CUIL digits-only con verificador mod-11 (regla BUC: sin guiones)."""
    prefijo = "20" if sexo == "HOMBRE" else "27"
    base = f"{prefijo}{dni:08d}"
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    ver = 11 - resto
    if ver == 11:
        ver = 0
    elif ver == 10:
        # Regla AFIP: verificador 10 no existe; cambia el prefijo a 23.
        base = f"23{dni:08d}"
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        ver = 11 - resto
        if ver == 11:
            ver = 0
    return f"{base}{ver}"


def _jitter(rnd: random.Random, lat: float, lon: float, radio_m: int) -> tuple[float, float]:
    rr = radio_m * math.sqrt(rnd.random())
    ang = rnd.random() * 2 * math.pi
    dlat = (rr * math.cos(ang)) / 111_320.0
    dlon = (rr * math.sin(ang)) / (111_320.0 * math.cos(math.radians(lat)))
    return round(lat + dlat, 7), round(lon + dlon, 7)


def _ubicar(rnd: random.Random, cat: "_Catalogos", lat0: float, lon0: float,
            radio_m: int) -> tuple[float, float]:
    """Jitter alrededor del centro de la localidad, re-sorteando los puntos que
    caen fuera del contorno del municipio (rio, partido lindero). Sin contorno
    configurado (mig 111) se comporta como _jitter."""
    lat, lon = _jitter(rnd, lat0, lon0, radio_m)
    if cat.limite is None:
        return lat, lon
    for _ in range(30):
        if punto_en_limite(cat.limite, lat, lon):
            return lat, lon
        lat, lon = _jitter(rnd, lat0, lon0, radio_m)
    return round(lat0, 7), round(lon0, 7)  # centro de la localidad: siempre adentro


def _poisson(rnd: random.Random, media: float) -> int:
    """Poisson por el metodo de Knuth (media chica: decenas por dia)."""
    if media <= 0:
        return 0
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= limite:
            return k
        k += 1


def volumen_dia(rnd: random.Random, modulo: str, dia: date, minimo: int, maximo: int,
                semilla: int | None, pesos: tuple[float, ...] = PESO_DIA_SEMANA) -> int:
    """Cantidad de items de un dia. El total MENSUAL se sortea en [minimo, maximo]
    de forma determinista por (modulo, mes, semilla) — el cron diario que arma un
    mes de a un dia apunta siempre al mismo total — y se reparte por peso de dia
    de semana con ruido Poisson."""
    r = random.Random(f"zaris-demo-vol:{modulo}:{dia.year:04d}-{dia.month:02d}:{semilla}")
    total_mes = r.randint(min(minimo, maximo), max(minimo, maximo))
    dias_mes = calendar.monthrange(dia.year, dia.month)[1]
    media = total_mes / dias_mes * pesos[dia.weekday()] / (sum(pesos) / 7)
    return _poisson(rnd, media)


def dias_rango(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


@dataclass
class _Catalogos:
    tipos_por_nombre: dict[str, tuple[int, int, str]] = field(default_factory=dict)
    tipos_por_subarea: dict[int, list[int]] = field(default_factory=dict)
    tipo_info: dict[int, tuple[str, int]] = field(default_factory=dict)
    # SLA del tipo en dias (fraccion si es en horas o minutos; mig 120: sla_minutos / 1440).
    tipo_sla: dict[int, float | None] = field(default_factory=dict)
    tipo_asignacion: dict[int, str] = field(default_factory=dict)
    subareas_por_nombre: dict[str, int] = field(default_factory=dict)
    estados_fk: dict[str, int] = field(default_factory=dict)
    # (nombre normalizado, partido normalizado) -> id_localidad
    localidades: dict[tuple[str, str], int] = field(default_factory=dict)
    limite: dict | None = None  # GeoJSON Polygon del municipio (mig 111)
    id_plantilla_reclamos: int | None = None
    # estado_ot por nombre (En gestion, En espera, Pendiente, Terminada, Cancelada).
    estados_ot: dict[str, int] = field(default_factory=dict)
    id_estado_ot_gestion: int | None = None
    id_estado_ot_terminada: int | None = None
    # reclamos.resolucion (mig 117): texto de cierre que ve el vecino. Opcional.
    tiene_resolucion: bool = False
    id_municipio: int = 0  # municipio demo (municipio_demo)
    # Poblacion ponderada de tipos ya resuelta contra el catalogo del entorno:
    # entradas ('tipo', id_tipo) o ('subarea', id_subarea), con su peso.
    poblacion_tipos: list[tuple[tuple[str, int], int]] = field(default_factory=list)
    poblacion_localidades: list[tuple[tuple[int, str, float, float, int], int]] = field(default_factory=list)


async def municipio_demo(db: AsyncSession) -> int:
    """Municipio donde escribe el generador: el de las direcciones sin prefijo
    (`direccion_base`, IT-01; F4 lo cambia por municipios.estado = 'demo')."""
    id_m = await db.scalar(text("SELECT id_municipio FROM municipios WHERE direccion_base AND activo"))
    if id_m is None:
        raise RuntimeError("No hay un municipio con direccion_base: el generador demo no corre")
    return id_m


async def _cargar_catalogos(db: AsyncSession) -> _Catalogos:
    cat = _Catalogos()
    cat.id_municipio = await municipio_demo(db)
    mun = {"mun": cat.id_municipio}
    r = await db.execute(text(
        "SELECT t.id_tipo_reclamo, t.nombre, t.id_subarea, t.sla_minutos, t.asignacion_a FROM tipo_reclamo t "
        "JOIN subarea s ON s.id_subarea = t.id_subarea WHERE t.activo AND s.activo AND t.id_municipio = :mun"
    ), mun)
    for fila in r.fetchall():
        cat.tipos_por_nombre[_norm(fila.nombre)] = (fila.id_tipo_reclamo, fila.id_subarea, fila.nombre)
        cat.tipos_por_subarea.setdefault(fila.id_subarea, []).append(fila.id_tipo_reclamo)
        cat.tipo_info[fila.id_tipo_reclamo] = (fila.nombre, fila.id_subarea)
        cat.tipo_sla[fila.id_tipo_reclamo] = fila.sla_minutos / 1440.0 if fila.sla_minutos else None
        cat.tipo_asignacion[fila.id_tipo_reclamo] = fila.asignacion_a or "agente"

    r = await db.execute(text("SELECT id_subarea, nombre FROM subarea WHERE activo AND id_municipio = :mun"), mun)
    for fila in r.fetchall():
        cat.subareas_por_nombre[_norm(fila.nombre)] = fila.id_subarea

    r = await db.execute(text("SELECT id_estado_reclamo, nombre FROM estado_reclamo WHERE activo"))
    for fila in r.fetchall():
        cat.estados_fk[fila.nombre] = fila.id_estado_reclamo

    r = await db.execute(text(
        "SELECT l.id_localidad, l.nombre, p.nombre AS partido FROM localidades l "
        "JOIN partidos p ON p.id_partido = l.id_partido"
    ))
    for fila in r.fetchall():
        # Por (nombre, partido): "Villa Adelina" existe en VL y en San Isidro.
        cat.localidades.setdefault((_norm(fila.nombre), _norm(fila.partido)), fila.id_localidad)
    cat.limite = await leer_limite(db, cat.id_municipio)

    r = await db.execute(text(
        "SELECT id_encuesta_plantilla FROM encuesta_plantilla "
        "WHERE tipo = 'reclamos' AND activo AND id_municipio = :mun ORDER BY id_encuesta_plantilla LIMIT 1"
    ), mun)
    fila = r.fetchone()
    cat.id_plantilla_reclamos = fila.id_encuesta_plantilla if fila else None

    r = await db.execute(text("SELECT id_estado_ot, nombre FROM estado_ot WHERE activo"))
    for fila in r.fetchall():
        cat.estados_ot[fila.nombre] = fila.id_estado_ot
    cat.id_estado_ot_gestion = cat.estados_ot.get("En gestión")
    cat.id_estado_ot_terminada = cat.estados_ot.get("Terminada")

    cat.tiene_resolucion = bool(await db.scalar(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'reclamos' AND column_name = 'resolucion'")))

    sin_match = 0
    for tipo_ref, grupo_ref, peso in ref.TIPOS_REF:
        if tipo_ref in cat.tipos_por_nombre:
            cat.poblacion_tipos.append((("tipo", cat.tipos_por_nombre[tipo_ref][0]), peso))
        elif grupo_ref in cat.subareas_por_nombre and cat.tipos_por_subarea.get(cat.subareas_por_nombre[grupo_ref]):
            cat.poblacion_tipos.append((("subarea", cat.subareas_por_nombre[grupo_ref]), peso))
        else:
            sin_match += 1
    if sin_match:
        logger.info("demo_datos: %s tipos de referencia sin match en el catalogo (se omiten)", sin_match)

    for nombre, partido, peso, lat, lon, radio in ref.LOCALIDADES_REF:
        id_loc = cat.localidades.get((_norm(nombre), _norm(partido)))
        if id_loc:
            cat.poblacion_localidades.append(((id_loc, nombre, lat, lon, radio), peso))
    return cat


async def _usuario_generador(db: AsyncSession, crear: bool = True) -> int | None:
    id_mun = await municipio_demo(db)
    r = await db.execute(text("SELECT id_usuario FROM usuarios WHERE username = :u AND id_municipio = :mun"),
                         {"u": USERNAME_GENERADOR, "mun": id_mun})
    fila = r.fetchone()
    if fila:
        return fila.id_usuario
    if not crear:
        return None
    from app.core.auth import hash_password
    import secrets as stdlib_secrets
    # buc_acceso es NOT NULL sin default en local (drift §24).
    r = await db.execute(text("""
        INSERT INTO usuarios (nombre, username, password_hash, nivel_acceso, activo,
                              buc_acceso, email, id_municipio)
        VALUES ('Generador de datos demo', :u, :h, 5, FALSE, FALSE, :e, :mun)
        RETURNING id_usuario
    """), {"u": USERNAME_GENERADOR, "h": hash_password(stdlib_secrets.token_urlsafe(24)),
           "e": EMAIL_GENERADOR, "mun": id_mun})
    return r.fetchone().id_usuario


async def _asegurar_vecinos(db: AsyncSession, cat: _Catalogos, uid: int,
                            objetivo_nuevos: int, rnd: random.Random) -> list[tuple[int, str]]:
    """Devuelve el pool [(id_ciudadano, email)] creando vecinos demo si faltan.

    Los nombres se RECOMBINAN (apellido de una fila del set de referencia,
    nombre de otra): nunca se reproduce un par real. DNI/CUIL sinteticos.
    """
    ya_demo = (await db.execute(text(
        "SELECT COUNT(*) AS n FROM ciudadanos WHERE email LIKE :d AND id_municipio = :mun"),
        {"d": f"%@{DOMINIO_VECINO_DEMO}", "mun": cat.id_municipio})).fetchone().n
    a_crear = max(0, objetivo_nuevos - ya_demo)

    if a_crear:
        # Todo el padron: el UNIQUE global viejo de documento sigue hasta el lote de limpieza.
        existentes = {f.doc_nro for f in (await db.execute(
            text("SELECT doc_nro FROM ciudadanos"))).fetchall()}
        filas = []
        usados: set[str] = set()
        while len(filas) < a_crear:
            dni = rnd.randint(18_000_000, 45_999_999)
            if str(dni) in existentes or str(dni) in usados:
                continue
            usados.add(str(dni))
            apellido = rnd.choice(ref.APELLIDOS)
            nombre = rnd.choice(ref.NOMBRES)
            sexo = _sexo_de(nombre)
            id_loc, loc_nombre, lat0, lon0, radio = _elegir_localidad(rnd, cat)
            lat, lon = _ubicar(rnd, cat, lat0, lon0, radio)
            slug = re.sub(r"[^a-z0-9]+", ".", _norm(f"{nombre} {apellido}")).strip(".")
            filas.append({
                "doc_tipo": "DNI", "doc_nro": str(dni),
                "cuil": _cuil_valido(dni, sexo),
                "nombre": nombre, "apellido": apellido, "sexo": sexo,
                "fecha_nac": date(rnd.randint(1945, 2006), rnd.randint(1, 12), rnd.randint(1, 28)),
                "id_nacionalidad": 1,
                "calle": rnd.choice(CALLES), "altura": str(rnd.randint(100, 5900)),
                "localidad": loc_nombre, "provincia": "Buenos Aires",
                "latitud": lat, "longitud": lon,
                "telefono": f"11{rnd.randint(20_000_000, 79_999_999)}",
                "email": f"{slug}.{dni % 10000}@{DOMINIO_VECINO_DEMO}",
                "fecha_alta": datetime.now() - timedelta(days=rnd.randint(30, 720)),
                "uid": uid, "mun": cat.id_municipio,
            })
        # ren_chk/email_chk/emp_chk/activo: NOT NULL sin default en local (drift §24).
        await db.execute(text("""
            INSERT INTO ciudadanos
                (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                 id_nacionalidad, calle, altura, localidad, provincia,
                 latitud, longitud, telefono, email, fecha_alta, id_usuario_alta,
                 ren_chk, email_chk, emp_chk, activo, id_municipio)
            VALUES (:doc_tipo, :doc_nro, :cuil, :nombre, :apellido, :sexo, :fecha_nac,
                    :id_nacionalidad, :calle, :altura, :localidad, :provincia,
                    :latitud, :longitud, :telefono, :email, :fecha_alta, :uid,
                    FALSE, FALSE, FALSE, TRUE, :mun)
        """), filas)

    # Solo vecinos DEMO (2026-10-21): hasta esta fecha el pool eran todos los
    # ciudadanos con email, y un reclamo demo podia aparecer en la app de un vecino
    # real. demo_atencion ya filtraba asi.
    r = await db.execute(text(
        "SELECT id_ciudadano, email FROM ciudadanos WHERE activo AND email LIKE :d AND id_municipio = :mun "
        "ORDER BY id_ciudadano"),
        {"d": f"%@{DOMINIO_VECINO_DEMO}", "mun": cat.id_municipio})
    return [(f.id_ciudadano, f.email) for f in r.fetchall()]


def _resolver_tipo(rnd: random.Random, cat: _Catalogos) -> int:
    clase, valor = rnd.choices([p[0] for p in cat.poblacion_tipos],
                               weights=[p[1] for p in cat.poblacion_tipos], k=1)[0]
    if clase == "tipo":
        return valor
    return rnd.choice(cat.tipos_por_subarea[valor])


def _elegir_localidad(rnd: random.Random, cat: _Catalogos) -> tuple[int, str, float, float, int]:
    return rnd.choices([p[0] for p in cat.poblacion_localidades],
                       weights=[p[1] for p in cat.poblacion_localidades], k=1)[0]


async def reservar_ids(db: AsyncSession, tabla: str, pk: str, n: int) -> list[int]:
    """Reserva n ids de la secuencia de la tabla (ascendentes). El plan de cada
    item depende de su id, asi que el id tiene que conocerse ANTES del INSERT."""
    if n <= 0:
        return []
    r = await db.execute(text(
        f"SELECT nextval(pg_get_serial_sequence('{tabla}', '{pk}')) AS id FROM generate_series(1, :n)"),
        {"n": n})
    return sorted(int(f.id) for f in r.fetchall())


# ── Plan determinista de un reclamo (demo_sla) ──────────────────────────────

@dataclass
class _PlanReclamo:
    estado_final: str                       # Resuelto | Cancelado
    eventos: list[tuple[datetime, str]]     # (fecha, estado destino), en orden, sin el ingreso
    cierre: datetime                        # fecha de cierre o de cancelacion
    dentro: bool                            # el plan cae dentro del SLA
    p: float                                # fraccion objetivo del mes


def _plan_reclamo(id_reclamo: int, alta: datetime, sla: int | None) -> _PlanReclamo:
    """Plan reproducible del reclamo: el mismo (id, alta, sla) da siempre el mismo
    resultado (lo recalculan el generador y avanzar_pendientes)."""
    rnd = demo_sla.rnd_de("reclamo", id_reclamo)
    p = demo_sla.p_mes("reclamos", alta.year, alta.month)
    dentro = demo_sla.cae_dentro("reclamos", id_reclamo, p)
    sla_ef = sla or SLA_DEFAULT_RECLAMO
    dias = demo_sla.demora_dentro(rnd, sla_ef) if dentro else demo_sla.demora_fuera(rnd, sla_ef)
    # Sorteos SIEMPRE en el mismo orden (el plan tiene que ser reproducible).
    u_cancel = rnd.random()
    f_asig = rnd.uniform(0.08, 0.35)
    u_espera = rnd.random()
    e1, e2 = rnd.uniform(0.30, 0.45), rnd.uniform(0.60, 0.85)
    u_asig_cancel = rnd.random()
    f_cancel = rnd.uniform(0.15, 0.90)

    cierre = alta + timedelta(days=dias)
    span = cierre - alta
    asig = alta + max(span * f_asig, timedelta(minutes=20))
    if u_cancel < TASA_CANCELADO:
        t_c = alta + max(span * f_cancel, timedelta(minutes=30))
        eventos: list[tuple[datetime, str]] = []
        if u_asig_cancel < 0.5 and asig < t_c - timedelta(minutes=10):
            eventos.append((asig, ESTADO_EN_GESTION))
        eventos.append((t_c, ESTADO_CANCELADO))
        return _PlanReclamo(ESTADO_CANCELADO, eventos, t_c, dentro, p)
    eventos = [(asig, ESTADO_EN_GESTION)]
    if not dentro and u_espera < 0.22:
        # Episodio de espera (materiales, autorizacion) en los que se demoran.
        eventos += [(asig + (cierre - asig) * e1, ESTADO_EN_ESPERA),
                    (asig + (cierre - asig) * e2, ESTADO_EN_GESTION)]
    eventos.append((cierre, ESTADO_RESUELTO))
    return _PlanReclamo(ESTADO_RESUELTO, eventos, cierre, dentro, p)


def _plan_subreclamo(id_hijo: int, alta_hijo: datetime, sla_hijo: int | None,
                     plan_padre: _PlanReclamo) -> _PlanReclamo:
    """El subreclamo sigue su propio plan pero cierra ANTES que el padre (que lo
    espera en 'En espera'). Nunca se cancela."""
    rnd = demo_sla.rnd_de("subreclamo", id_hijo)
    propio = _plan_reclamo(id_hijo, alta_hijo, sla_hijo)
    cierre = min(propio.cierre, plan_padre.cierre - timedelta(hours=rnd.uniform(1, 12)))
    cierre = max(cierre, alta_hijo + timedelta(hours=2))
    asig = alta_hijo + min(timedelta(hours=rnd.uniform(1, 24)), (cierre - alta_hijo) / 2)
    return _PlanReclamo(ESTADO_RESUELTO, [(asig, ESTADO_EN_GESTION), (cierre, ESTADO_RESUELTO)],
                        cierre, propio.dentro, propio.p)


def _con_subreclamos(plan: _PlanReclamo, hijos: list[tuple[datetime, datetime | None]]) -> _PlanReclamo:
    """Plan del padre con subreclamos [(alta_hijo, cierre_hijo o None)]: 'En espera'
    desde el primer subreclamo y, cuando cierran todos, vuelve a 'En gestion'
    (desbloqueo) y despues se resuelve. Con alguno abierto, el plan termina en espera."""
    if not hijos or plan.estado_final != ESTADO_RESUELTO:
        return plan
    asig = next((t for t, e in plan.eventos if e == ESTADO_EN_GESTION), None)
    inicio = min(a for a, _ in hijos) + timedelta(minutes=5)
    eventos: list[tuple[datetime, str]] = []
    if asig is not None and asig < inicio:
        eventos.append((asig, ESTADO_EN_GESTION))
    eventos.append((inicio, ESTADO_EN_ESPERA))
    if any(c is None for _, c in hijos):
        return _PlanReclamo(plan.estado_final, eventos, plan.cierre, plan.dentro, plan.p)
    fin = max(c for _, c in hijos if c is not None) + timedelta(minutes=30)
    cierre = max(plan.cierre, fin + timedelta(hours=1))
    eventos += [(fin, ESTADO_EN_GESTION), (cierre, ESTADO_RESUELTO)]
    return _PlanReclamo(plan.estado_final, eventos, cierre, plan.dentro, plan.p)


# Transiciones directas que admite el FSM del reclamo (reclamos.py
# TRANSICIONES_PERMITIDAS; Sin asignar -> Resuelto existe como cierre directo sin
# OT, pero el generador siempre pasa por una OT).
_FSM_VALIDAS = {
    (ESTADO_SIN_ASIGNAR, ESTADO_EN_GESTION), (ESTADO_SIN_ASIGNAR, ESTADO_CANCELADO),
    (ESTADO_EN_GESTION, ESTADO_EN_ESPERA), (ESTADO_EN_GESTION, ESTADO_RESUELTO),
    (ESTADO_EN_GESTION, ESTADO_CANCELADO),
    (ESTADO_EN_ESPERA, ESTADO_EN_GESTION), (ESTADO_EN_ESPERA, ESTADO_CANCELADO),
}
# Camino minimo entre estados (para alcanzar el estado del plan desde el del DB).
_CAMINOS = {
    (ESTADO_SIN_ASIGNAR, ESTADO_EN_GESTION): (ESTADO_EN_GESTION,),
    (ESTADO_SIN_ASIGNAR, ESTADO_EN_ESPERA): (ESTADO_EN_GESTION, ESTADO_EN_ESPERA),
    (ESTADO_SIN_ASIGNAR, ESTADO_RESUELTO): (ESTADO_EN_GESTION, ESTADO_RESUELTO),
    (ESTADO_SIN_ASIGNAR, ESTADO_CANCELADO): (ESTADO_CANCELADO,),
    (ESTADO_EN_GESTION, ESTADO_EN_ESPERA): (ESTADO_EN_ESPERA,),
    (ESTADO_EN_GESTION, ESTADO_RESUELTO): (ESTADO_RESUELTO,),
    (ESTADO_EN_GESTION, ESTADO_CANCELADO): (ESTADO_CANCELADO,),
    (ESTADO_EN_ESPERA, ESTADO_EN_GESTION): (ESTADO_EN_GESTION,),
    (ESTADO_EN_ESPERA, ESTADO_RESUELTO): (ESTADO_EN_GESTION, ESTADO_RESUELTO),
    (ESTADO_EN_ESPERA, ESTADO_CANCELADO): (ESTADO_CANCELADO,),
}


def _realizar(estado: str, plan: _PlanReclamo, piso: datetime, ahora: datetime,
              forzar_final: bool = False) -> list[tuple[datetime, str, str]]:
    """Transiciones [(fecha, anterior, nuevo)] que llevan el reclamo desde `estado`
    (su estado en la DB, con su ultimo movimiento en `piso`) al estado que el plan
    indica para `ahora`. Fechas del plan cuando son posteriores al piso; si el DB
    va atrasado respecto del plan (datos viejos), los pasos que faltan se fechan
    pegados al piso. Todo monotono y <= ahora, respetando el FSM.

    forzar_final (cierre del atraso): el plan se da por cumplido aunque su cierre
    sea posterior a `ahora` (con el tope de 20 dias no deberia pasar)."""
    eventos = list(plan.eventos)
    if forzar_final and eventos and eventos[-1][1] not in (ESTADO_RESUELTO, ESTADO_CANCELADO):
        eventos.append((max(plan.cierre, eventos[-1][0] + timedelta(hours=1)), plan.estado_final))
    if forzar_final:
        tope = ahora - timedelta(minutes=2)
        vencidos = [(min(t, tope), e) for t, e in eventos]
    else:
        vencidos = [(t, e) for t, e in eventos if t <= ahora]
    objetivo = vencidos[-1][1] if vencidos else ESTADO_SIN_ASIGNAR
    hora_plan: dict[str, datetime] = {}
    for t, e in vencidos:
        hora_plan[e] = t  # la ULTIMA ocurrencia de cada estado

    out: list[tuple[datetime, str, str]] = []
    actual, t_prev = estado, piso

    def _paso(nuevo: str, t: datetime) -> None:
        nonlocal actual, t_prev
        t = max(t, t_prev + timedelta(minutes=1))
        out.append((t, actual, nuevo))
        actual, t_prev = nuevo, t

    for t, nuevo in vencidos:
        if t <= piso or nuevo == actual:
            continue
        if (actual, nuevo) not in _FSM_VALIDAS:
            camino = _CAMINOS.get((actual, nuevo))
            if not camino:
                continue  # el DB ya esta "adelante" del plan: no se vuelve atras
            for inter in camino[:-1]:
                _paso(inter, t_prev + timedelta(minutes=15))
        _paso(nuevo, t)
    if actual != objetivo:
        for nuevo in _CAMINOS.get((actual, objetivo), ()):
            t_plan = hora_plan.get(nuevo)
            _paso(nuevo, t_plan if t_plan and t_plan > t_prev else t_prev + timedelta(minutes=15))

    # Nada en el futuro: si un paso agregado paso de `ahora`, se comprime contra ahora.
    tope = ahora - timedelta(minutes=1)
    for i in range(len(out) - 1, -1, -1):
        t, a, n = out[i]
        lim = tope - timedelta(minutes=len(out) - 1 - i)
        if t > lim:
            out[i] = (lim, a, n)
    return out


# ── Asignacion de OT operativas ─────────────────────────────────────────────

@dataclass
class _Recurso:
    tipo: str            # 'agente' | 'equipo'
    id: int
    nombre: str
    id_subarea: int | None
    asignadas: int = 0   # OTs operativas que ya recibio (rotacion)


class _AsignadorOT:
    """A quien se asigna cada OT operativa demo. Regla del producto
    (services/autoasignacion.py::candidatos_gestion): agentes de nivel Gestion (4)
    no auditores de la gestion del tipo, o cuadrillas ('trabajo_reclamos') con
    integrantes si tipo_reclamo.asignacion_a = 'equipo'; entre ellos el que menos
    OTs recibio (rotacion por carga). Los reclamos NO se agendan (2026-10-21):
    ninguna OT demo crea ocupacion en la Agenda.

    Fallback para que ninguna OT quede sin destinatario cuando la gestion no tiene a
    nadie (la DB local casi no tiene agentes): otros niveles operativos (2-3) de la
    gestion -> nivel 4 de otra gestion de la misma secretaria -> nivel 4 de
    cualquier gestion. El resultado cuenta cada caso en `ot_por_origen`.

    Excluye a los agentes cuyo usuario tiene una suscripcion push activa (la app de
    agentes instalada en un telefono real): son personas probando el circuito real
    y no deben encontrar OTs demo en su mesa."""

    def __init__(self) -> None:
        self.ag4_sub: dict[int, list[_Recurso]] = {}
        self.ag_otros_sub: dict[int, list[_Recurso]] = {}
        self.ag4_area: dict[int, list[_Recurso]] = {}
        self.ag4_todos: list[_Recurso] = []
        self.equipos_sub: dict[int, list[_Recurso]] = {}
        self.supervisores_sub: dict[int, list[int]] = {}
        self.auto_sub: set[int] = set()
        self.area_de_sub: dict[int, int] = {}
        self.por_origen: dict[str, int] = {}

    @classmethod
    async def cargar(cls, db: AsyncSession, id_municipio: int) -> "_AsignadorOT":
        a = cls()
        mun = {"mun": id_municipio}
        tiene_push = bool(await db.scalar(text("SELECT to_regclass('public.usuario_push_subscription') IS NOT NULL")))
        filtro_push = ("AND NOT EXISTS (SELECT 1 FROM usuario_push_subscription ps "
                       "WHERE ps.id_usuario = u.id_usuario AND ps.activo)") if tiene_push else ""
        for f in (await db.execute(text("SELECT id_subarea, id_area FROM subarea WHERE id_municipio = :mun"),
                                   mun)).fetchall():
            a.area_de_sub[f.id_subarea] = f.id_area
        r = await db.execute(text(f"""
            SELECT ag.id_agente, TRIM(BOTH ', ' FROM COALESCE(ag.apellido, '') || ', ' || COALESCE(ag.nombre, '')) AS nombre,
                   ag.id_subarea, u.nivel_acceso,
                   (SELECT COUNT(*) FROM ordenes_trabajo ot
                     WHERE ot.id_agente = ag.id_agente AND NOT ot.es_auditoria) AS n_ot
              FROM agentes ag
              JOIN usuarios u ON u.id_usuario = ag.id_usuario AND u.activo
             WHERE ag.activo AND NOT ag.es_auditor AND u.nivel_acceso BETWEEN 2 AND 4
                   AND ag.id_subarea IS NOT NULL AND ag.id_municipio = :mun {filtro_push}
        """), mun)
        for f in r.fetchall():
            rec = _Recurso("agente", f.id_agente, f.nombre, f.id_subarea, int(f.n_ot or 0))
            if f.nivel_acceso == 4:
                a.ag4_sub.setdefault(f.id_subarea, []).append(rec)
                a.ag4_todos.append(rec)
                area = a.area_de_sub.get(f.id_subarea)
                if area is not None:
                    a.ag4_area.setdefault(area, []).append(rec)
            else:
                a.ag_otros_sub.setdefault(f.id_subarea, []).append(rec)
        r = await db.execute(text("""
            SELECT e.id_equipo, e.nombre, e.id_subarea,
                   (SELECT COUNT(*) FROM ordenes_trabajo ot
                     WHERE ot.id_equipo = e.id_equipo AND NOT ot.es_auditoria) AS n_ot
              FROM equipos e
             WHERE e.activo AND e.tipo_grupo = 'trabajo_reclamos' AND e.id_subarea IS NOT NULL
               AND e.id_municipio = :mun
               AND EXISTS (SELECT 1 FROM equipo_agentes ea
                             JOIN agentes ag ON ag.id_agente = ea.id_agente AND ag.activo
                             JOIN usuarios u ON u.id_usuario = ag.id_usuario AND u.activo
                            WHERE ea.id_equipo = e.id_equipo AND ea.activo AND u.nivel_acceso <= 4)
        """), mun)
        for f in r.fetchall():
            a.equipos_sub.setdefault(f.id_subarea, []).append(
                _Recurso("equipo", f.id_equipo, f"la cuadrilla {f.nombre}", f.id_subarea, int(f.n_ot or 0)))
        r = await db.execute(text("""
            SELECT DISTINCT ag.id_subarea, u.id_usuario FROM agentes ag
              JOIN usuarios u ON u.id_usuario = ag.id_usuario AND u.activo
             WHERE ag.activo AND u.nivel_acceso = 2 AND ag.id_subarea IS NOT NULL AND ag.id_municipio = :mun
        """), mun)
        for f in r.fetchall():
            a.supervisores_sub.setdefault(f.id_subarea, []).append(f.id_usuario)
        # Gestiones que asignan solas (mig 121): la asignacion general del municipio
        # prendida y la gestion sin la excepcion «asigna a mano».
        if await autoasignacion.asignacion_general_prendida(db, id_municipio):
            r = await db.execute(text(
                "SELECT id_subarea FROM subarea WHERE NOT asignacion_manual AND id_municipio = :mun"), mun)
            a.auto_sub = {f.id_subarea for f in r.fetchall()}
        return a

    @staticmethod
    def _tomar(cands: list[_Recurso], rnd: random.Random) -> _Recurso:
        minimo = min(c.asignadas for c in cands)
        elegido = rnd.choice([c for c in cands if c.asignadas == minimo])
        elegido.asignadas += 1
        return elegido

    def elegir(self, id_subarea: int | None, asignacion_a: str, rnd: random.Random) -> _Recurso | None:
        cadena: list[tuple[str, list[_Recurso] | None]] = []
        if asignacion_a == "equipo":
            cadena.append(("gestion_cuadrilla", self.equipos_sub.get(id_subarea)))
        cadena += [
            ("gestion", self.ag4_sub.get(id_subarea)),
            ("gestion_otros_niveles", self.ag_otros_sub.get(id_subarea)),
            ("secretaria", self.ag4_area.get(self.area_de_sub.get(id_subarea))),
            ("municipio", self.ag4_todos),
        ]
        for origen, cands in cadena:
            if cands:
                self.por_origen[origen] = self.por_origen.get(origen, 0) + 1
                return self._tomar(cands, rnd)
        self.por_origen["sin_candidato"] = self.por_origen.get("sin_candidato", 0) + 1
        return None

    def supervisor(self, id_subarea: int | None, rnd: random.Random) -> tuple[int | None, bool]:
        """(id_supervisor_asigna, asignacion_automatica): la gestion que asigna sola
        (mig 121) o sin supervisor -> NULL + automatica."""
        if id_subarea in self.auto_sub:
            return None, True
        sups = self.supervisores_sub.get(id_subarea)
        if sups:
            return rnd.choice(sups), False
        return None, True


_ESTADO_OT_DE_RECLAMO = {
    ESTADO_EN_GESTION: "En gestión", ESTADO_EN_ESPERA: "En espera",
    ESTADO_RESUELTO: "Terminada", ESTADO_EN_AUDITORIA: "Terminada", ESTADO_AUDITADO: "Terminada",
    ESTADO_CANCELADO: "Cancelada",
}

_SQL_INSERT_OT_OPERATIVA = text("""
    INSERT INTO ordenes_trabajo
        (id_reclamo, id_estado, id_agente, id_equipo, es_auditoria, asignacion_automatica,
         id_supervisor_asigna, fecha_creacion, fecha_cierre, observaciones, activo,
         fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion, id_municipio)
    VALUES (:id_reclamo, :id_estado, :id_agente, :id_equipo, FALSE, :auto,
            :sup, CAST(:creacion AS timestamptz), CAST(:cierre AS timestamptz), :obs, TRUE,
            CAST(:creacion AS timestamptz), CAST(:modif AS timestamptz), :uid, :uid, (SELECT id_municipio FROM reclamos WHERE id_reclamo = :id_reclamo))
    RETURNING id_ot, nro_ot
""")

_SQL_UPDATE_OT_OPERATIVA = text("""
    UPDATE ordenes_trabajo SET id_estado = :id_estado, fecha_cierre = CAST(:cierre AS timestamptz),
           observaciones = COALESCE(:obs, observaciones),
           fecha_modificacion = CAST(:modif AS timestamptz), id_usuario_modificacion = :uid
     WHERE id_ot = :id_ot
""")


def _params_ot(cat: _Catalogos, asignador: _AsignadorOT, rnd: random.Random, id_reclamo: int,
               id_tipo: int, estado_reclamo: str, creacion: datetime, cierre: datetime | None,
               modif: datetime, uid: int, obs: str | None) -> tuple[dict | None, _Recurso | None]:
    """Parametros del INSERT de la OT operativa (o None si no hay a quien asignarla)."""
    _nombre, id_sub = cat.tipo_info.get(id_tipo, (None, None))
    rec = asignador.elegir(id_sub, cat.tipo_asignacion.get(id_tipo, "agente"), rnd)
    estado_ot = cat.estados_ot.get(_ESTADO_OT_DE_RECLAMO.get(estado_reclamo, "En gestión"))
    if rec is None or estado_ot is None:
        return None, None
    sup, auto = asignador.supervisor(id_sub, rnd)
    final = estado_reclamo in (ESTADO_RESUELTO, ESTADO_EN_AUDITORIA, ESTADO_AUDITADO, ESTADO_CANCELADO)
    return {
        "id_reclamo": id_reclamo, "id_estado": estado_ot,
        "id_agente": rec.id if rec.tipo == "agente" else None,
        "id_equipo": rec.id if rec.tipo == "equipo" else None,
        "auto": auto, "sup": sup, "creacion": creacion,
        "cierre": cierre if final else None, "obs": obs, "modif": modif, "uid": uid,
    }, rec


def _texto_historial(anterior: str, nuevo: str, nro_ot: str | None, recurso: _Recurso | None,
                     resolucion: str | None, motivo_cancel: str | None,
                     por_subreclamo: bool, sufijo: str) -> tuple[str, str | None]:
    """(accion, nota) del historial para una transicion, con los textos del producto."""
    if nuevo == ESTADO_EN_GESTION and anterior == ESTADO_SIN_ASIGNAR:
        if nro_ot:
            quien = recurso.nombre if recurso else "la gestión"
            return f"OT {nro_ot} generada", f"Asignada a {quien}.{sufijo}"
        return f"Cambio de estado a {ESTADO_EN_GESTION}", sufijo.strip() or None
    if nuevo == ESTADO_EN_GESTION:
        nota = "Subreclamo resuelto: se reanuda la gestión." if por_subreclamo else "Se reanuda la gestión."
        return f"Cambio de estado a {ESTADO_EN_GESTION}", nota + sufijo
    if nuevo == ESTADO_EN_ESPERA:
        if por_subreclamo:
            return "Reclamo en espera por subreclamo", sufijo.strip() or None
        return f"Cambio de estado a {ESTADO_EN_ESPERA}", "A la espera de materiales o autorización." + sufijo
    if nuevo == ESTADO_RESUELTO:
        return "Reclamo resuelto", (resolucion or "OT operativa terminada") + sufijo
    if nuevo == ESTADO_CANCELADO:
        return "Reclamo cancelado", (motivo_cancel or "Cancelado") + sufijo
    return f"Cambio de estado a {nuevo}", sufijo.strip() or None


# ── Armado de reclamos ──────────────────────────────────────────────────────

def _armar_reclamo(rnd: random.Random, cat: _Catalogos, pool: list[tuple[int, str]],
                   dia: date, ahora: datetime) -> dict | None:
    """Datos base de un reclamo del dia (sin estado: lo decide el plan). None si la
    hora sorteada cae en el futuro respecto de `ahora`."""
    id_tipo = _resolver_tipo(rnd, cat)
    tipo_nombre, id_subarea = cat.tipo_info[id_tipo]
    id_loc, loc_nombre, lat0, lon0, radio = _elegir_localidad(rnd, cat)
    lat, lon = _ubicar(rnd, cat, lat0, lon0, radio)

    # Horario comercial AR (UTC-3) con algo de dispersion: 11-21 UTC.
    fecha_alta = datetime(dia.year, dia.month, dia.day,
                          rnd.randint(11, 21), rnd.randint(0, 59), rnd.randint(0, 59),
                          tzinfo=timezone.utc)
    canal = _elegir(rnd, CANALES)
    fuente = "gps_dispositivo" if canal == "app_movil" else _elegir(rnd, FUENTES_GEO)
    direccion = f"{rnd.choice(CALLES)} {rnd.randint(100, 5900)}, {loc_nombre}"
    frase = rnd.choice(FRASES).format(tipo=tipo_nombre, tipo_lower=tipo_nombre[0].lower() + tipo_nombre[1:],
                                      dir=direccion) + rnd.choice(COLETILLAS)
    id_ciudadano, email = rnd.choice(pool)
    prioridad = _elegir(rnd, PRIORIDADES)
    if fecha_alta > ahora - timedelta(minutes=5):
        return None  # nunca un alta en el futuro
    return {
        "id_tipo_reclamo": id_tipo, "id_subarea": id_subarea,
        "id_ciudadano": id_ciudadano, "email": email,
        "id_localidad": id_loc, "localidad_nombre": loc_nombre,
        "latitud": lat, "longitud": lon, "direccion": direccion,
        "descripcion": frase, "prioridad": prioridad,
        "canal_origen": canal, "fuente_geolocalizacion": fuente,
        "fecha_alta": fecha_alta,
        "fecha_primer_asignacion": None, "fecha_cierre": None,
        "auditoria": False, "subreclamo": False,
        "fecha_inicio_auditoria": None, "fecha_fin_auditoria": None,
        "resultado_auditoria": None, "id_reclamo_origen_auditoria": None,
    }


def _armar_retrabajo(rnd: random.Random, rec: dict, id_origen: int, nro_origen: str | None,
                     ahora: datetime) -> dict:
    """LEGACY (lo usa backfill_auditorias, ya aplicado en los dos entornos): reclamo
    NUEVO de retrabajo con su estado sorteado por edad. El generador nuevo usa
    _base_retrabajo + el plan del reclamo."""
    alta = rec["fecha_fin_auditoria"]
    obs = rnd.choice(OBSERVACIONES_AUDITORIA)
    r = dict(rec)
    r.update({
        "descripcion": f"Retrabajo por auditoría observada del reclamo {nro_origen or id_origen}: {obs}.",
        "canal_origen": "oficio", "fecha_alta": alta,
        "fecha_primer_asignacion": None, "fecha_cierre": None,
        "auditoria": False, "subreclamo": False,
        "fecha_inicio_auditoria": None, "fecha_fin_auditoria": None, "resultado_auditoria": None,
        "id_reclamo_origen_auditoria": id_origen, "_nro_origen": nro_origen,
    })
    edad = (ahora - alta).days
    if edad >= 3 and rnd.random() < 0.7:
        r["estado"] = ESTADO_RESUELTO
        r["fecha_primer_asignacion"] = alta + timedelta(hours=rnd.uniform(2, 36))
        r["fecha_cierre"] = min(alta + timedelta(days=rnd.uniform(2, max(2.5, float(edad)))),
                                ahora - timedelta(hours=1))
    elif edad >= 1 and rnd.random() < 0.6:
        r["estado"] = ESTADO_EN_GESTION
        r["fecha_primer_asignacion"] = min(alta + timedelta(hours=rnd.uniform(2, 36)), ahora)
    else:
        r["estado"] = ESTADO_SIN_ASIGNAR
    return r


def _base_retrabajo(rec: dict, id_origen: int, nro_origen: str | None, obs: str) -> dict:
    """Datos base del reclamo de retrabajo (mig 112): mismo vecino/tipo/direccion/geo,
    canal 'oficio', alta = cierre de la auditoria. El estado lo decide su plan."""
    r = dict(rec)
    r.update({
        "descripcion": f"Retrabajo por auditoría observada del reclamo {nro_origen or id_origen}: {obs}.",
        "canal_origen": "oficio", "fecha_alta": rec["fecha_fin_auditoria"],
        "fecha_primer_asignacion": None, "fecha_cierre": None,
        "auditoria": False, "subreclamo": False,
        "fecha_inicio_auditoria": None, "fecha_fin_auditoria": None, "resultado_auditoria": None,
        "id_reclamo_origen_auditoria": id_origen, "_nro_origen": nro_origen,
    })
    return r


# LEGACY (backfill_auditorias): INSERT sin id explicito.
_SQL_INSERT_RECLAMO = text("""
    INSERT INTO reclamos
        (id_ciudadano, id_tipo_reclamo, descripcion, prioridad, estado, id_estado_fk,
         direccion, latitud, longitud, id_localidad, canal_origen,
         fuente_geolocalizacion, fecha_alta, fecha_modificacion,
         fecha_primer_asignacion, fecha_cierre, id_usuario_alta, id_reclamo_padre,
         observaciones, fecha_inicio_auditoria, fecha_fin_auditoria, resultado_auditoria,
         id_reclamo_origen_auditoria, id_municipio)
    VALUES (:id_ciudadano, :id_tipo_reclamo, :descripcion, :prioridad, :estado, :id_estado_fk,
            :direccion, :latitud, :longitud, :id_localidad, :canal_origen,
            :fuente_geolocalizacion, :fecha_alta, :fecha_alta,
            :fecha_primer_asignacion, :fecha_cierre, :uid, :id_reclamo_padre,
            NULL, :fecha_inicio_auditoria, :fecha_fin_auditoria, :resultado_auditoria,
            :id_reclamo_origen_auditoria, :id_municipio)
    RETURNING id_reclamo, nro_reclamo
""")


def _sql_insert_reclamo_con_id(con_resolucion: bool):
    """INSERT con id_reclamo reservado (el plan depende del id) y, si la columna
    existe (mig 117), el texto de resolucion."""
    extra_col = ", resolucion" if con_resolucion else ""
    extra_val = ", :resolucion" if con_resolucion else ""
    return text(f"""
        INSERT INTO reclamos
            (id_reclamo, id_ciudadano, id_tipo_reclamo, descripcion, prioridad, estado, id_estado_fk,
             direccion, latitud, longitud, id_localidad, canal_origen,
             fuente_geolocalizacion, fecha_alta, fecha_modificacion,
             fecha_primer_asignacion, fecha_cierre, id_usuario_alta, id_usuario_modificacion,
             id_reclamo_padre, observaciones, fecha_inicio_auditoria, fecha_fin_auditoria,
             resultado_auditoria, id_reclamo_origen_auditoria, id_municipio{extra_col})
        VALUES (:id_reclamo, :id_ciudadano, :id_tipo_reclamo, :descripcion, :prioridad, :estado, :id_estado_fk,
                :direccion, :latitud, :longitud, :id_localidad, :canal_origen,
                :fuente_geolocalizacion, :fecha_alta, :fecha_modificacion,
                :fecha_primer_asignacion, :fecha_cierre, :uid, :uid,
                :id_reclamo_padre, NULL, :fecha_inicio_auditoria, :fecha_fin_auditoria,
                :resultado_auditoria, :id_reclamo_origen_auditoria, :id_municipio{extra_val})
        RETURNING id_reclamo, nro_reclamo
    """)


# OT de auditoria (mig 112): pendiente = En gestion sin cierre; cerrada = Terminada con resultado.
_SQL_INSERT_OT_AUDITORIA = text("""
    INSERT INTO ordenes_trabajo
        (id_reclamo, id_estado, es_auditoria, resultado_auditoria, observaciones,
         observaciones_auditoria, id_supervisor_asigna, fecha_creacion, fecha_cierre,
         activo, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion, id_municipio)
    VALUES (:id_reclamo, :id_estado, TRUE, :resultado, 'Control de calidad (demo)',
            :obs_aud, :uid, CAST(:inicio AS timestamptz), CAST(:fin AS timestamptz),
            TRUE, CAST(:inicio AS timestamptz),
            COALESCE(CAST(:fin AS timestamptz), CAST(:inicio AS timestamptz)), :uid, :uid, (SELECT id_municipio FROM reclamos WHERE id_reclamo = :id_reclamo))
""")

# Igual, con la OT operativa que audita (como POST /reclamos/{id}/auditoria).
_SQL_INSERT_OT_AUDITORIA_ORIGEN = text("""
    INSERT INTO ordenes_trabajo
        (id_reclamo, id_estado, es_auditoria, resultado_auditoria, observaciones,
         observaciones_auditoria, id_supervisor_asigna, id_ot_origen, fecha_creacion, fecha_cierre,
         activo, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion, id_municipio)
    VALUES (:id_reclamo, :id_estado, TRUE, :resultado, 'Control de calidad (demo)',
            :obs_aud, :uid, :id_ot_origen, CAST(:inicio AS timestamptz), CAST(:fin AS timestamptz),
            TRUE, CAST(:inicio AS timestamptz),
            COALESCE(CAST(:fin AS timestamptz), CAST(:inicio AS timestamptz)), :uid, :uid, (SELECT id_municipio FROM reclamos WHERE id_reclamo = :id_reclamo))
""")

_SQL_ENVIAR_AUDITORIA = text("""
    UPDATE reclamos SET estado = 'En auditoría', id_estado_fk = :fk,
           fecha_inicio_auditoria = :inicio, fecha_fin_auditoria = NULL, resultado_auditoria = NULL,
           fecha_modificacion = :inicio, id_usuario_modificacion = :uid
    WHERE id_reclamo = :id
""")

_SQL_CERRAR_AUDITORIA_RECLAMO = text("""
    UPDATE reclamos SET estado = 'Auditado', id_estado_fk = :fk, resultado_auditoria = :resultado,
           fecha_fin_auditoria = :fin, fecha_modificacion = :fin, id_usuario_modificacion = :uid
    WHERE id_reclamo = :id
""")

_SQL_CERRAR_AUDITORIA_OT = text("""
    UPDATE ordenes_trabajo SET id_estado = :id_terminada, resultado_auditoria = :resultado_ot,
           observaciones_auditoria = :obs, fecha_cierre = :fin, fecha_modificacion = :fin,
           id_usuario_modificacion = :uid
    WHERE id_reclamo = :id AND es_auditoria = TRUE AND activo = TRUE AND id_estado <> :id_terminada
""")

# Retrabajo desde un reclamo ya insertado (avanzar_pendientes): copia del auditado.
_SQL_INSERT_RETRABAJO_DESDE = text("""
    INSERT INTO reclamos
        (id_ciudadano, id_tipo_reclamo, id_area, descripcion, direccion, domicilio_reclamo,
         prioridad, estado, id_estado_fk, observaciones, latitud, longitud, id_localidad,
         id_activo, id_empresa, canal_origen, fuente_geolocalizacion,
         id_reclamo_origen_auditoria, id_municipio, activo, fecha_alta, fecha_modificacion,
         id_usuario_alta, id_usuario_modificacion)
    SELECT r.id_ciudadano, r.id_tipo_reclamo, r.id_area,
           'Retrabajo por auditoría observada del reclamo ' || COALESCE(r.nro_reclamo, r.id_reclamo::text)
               || ': ' || CAST(:obs AS text) || '.',
           r.direccion, r.domicilio_reclamo, r.prioridad, 'Sin asignar', :fk, NULL,
           r.latitud, r.longitud, r.id_localidad, r.id_activo, r.id_empresa, 'oficio',
           r.fuente_geolocalizacion, r.id_reclamo, r.id_municipio, TRUE,
           CAST(:fecha AS timestamptz), CAST(:fecha AS timestamptz), :uid, :uid
    FROM reclamos r WHERE r.id_reclamo = :id
    RETURNING id_reclamo, nro_reclamo
""")

_SQL_INSERT_HISTORIAL = text("""
    INSERT INTO reclamo_historial (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta,
                                   id_municipio)
    VALUES (:id_reclamo, :accion, :estado_anterior, :estado_nuevo, :nota, :fecha, :uid, (SELECT id_municipio FROM reclamos WHERE id_reclamo = :id_reclamo))
""")

_SQL_INSERT_ENVIO = text("""
    INSERT INTO encuesta_envio
        (id_plantilla, id_ciudadano, id_reclamo, email_destino_snapshot,
         fecha_envio, fecha_apertura, fecha_completada, fecha_expiracion,
         estado, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta, id_municipio)
    VALUES (:id_plantilla, :id_ciudadano, :id_reclamo, :email,
            :fecha_envio, :fecha_apertura, :fecha_completada, :fecha_expiracion,
            :estado, :id_subarea, :fecha_envio, :fecha_envio, :uid, (SELECT id_municipio FROM reclamos WHERE id_reclamo = :id_reclamo))
    RETURNING id_encuesta_envio
""")

_SQL_INSERT_RESPUESTA = text("""
    INSERT INTO encuesta_respuesta
        (id_envio, clasificacion_inicial, rama_seguida, tiempo_completado_seg,
         solicita_contacto, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta, id_municipio)
    VALUES (:id_envio, :clasificacion, :rama, :tiempo, FALSE, :id_subarea, :fecha, :fecha, :uid,
            (SELECT id_municipio FROM encuesta_envio WHERE id_encuesta_envio = :id_envio))
""")


def _historial_de(reclamo: dict, id_reclamo: int, uid: int, rnd: random.Random,
                  es_subreclamo: bool) -> list[dict]:
    """LEGACY (backfill_auditorias): historial reconstruido desde las fechas del dict."""
    es_retrabajo = bool(reclamo.get("id_reclamo_origen_auditoria"))
    filas = [{
        "id_reclamo": id_reclamo,
        "accion": ("Reclamo ingresado por auditoría observada" if es_retrabajo
                   else "Subreclamo ingresado" if es_subreclamo else "Reclamo ingresado"),
        "estado_anterior": None, "estado_nuevo": ESTADO_SIN_ASIGNAR,
        "nota": f"Retrabajo del reclamo {reclamo.get('_nro_origen') or reclamo['id_reclamo_origen_auditoria']}" if es_retrabajo else None,
        "fecha": reclamo["fecha_alta"], "uid": uid,
    }]
    asig = reclamo["fecha_primer_asignacion"]
    cierre = reclamo["fecha_cierre"]
    estado = reclamo["estado"]
    if asig:
        filas.append({"id_reclamo": id_reclamo, "accion": f"Cambio de estado a {ESTADO_EN_GESTION}",
                      "estado_anterior": ESTADO_SIN_ASIGNAR, "estado_nuevo": ESTADO_EN_GESTION,
                      "nota": None, "fecha": asig, "uid": uid})
    if estado == ESTADO_EN_ESPERA:
        filas.append({"id_reclamo": id_reclamo, "accion": "Reclamo en espera por subreclamo"
                      if reclamo.get("subreclamo") else f"Cambio de estado a {ESTADO_EN_ESPERA}",
                      "estado_anterior": ESTADO_EN_GESTION if asig else ESTADO_SIN_ASIGNAR,
                      "estado_nuevo": ESTADO_EN_ESPERA, "nota": None,
                      "fecha": (asig or reclamo["fecha_alta"]) + timedelta(hours=rnd.uniform(1, 24)),
                      "uid": uid})
    if estado in ESTADOS_GESTION_CERRADA_OK:
        previo = ESTADO_EN_GESTION if asig else ESTADO_SIN_ASIGNAR
        filas.append({"id_reclamo": id_reclamo, "accion": f"Cambio de estado a {ESTADO_RESUELTO}",
                      "estado_anterior": previo, "estado_nuevo": ESTADO_RESUELTO, "nota": None,
                      "fecha": cierre, "uid": uid})
        # Auditoria POSTERIOR al cierre (mig 112): envio y, si ya cerro, resultado.
        if reclamo.get("fecha_inicio_auditoria"):
            filas += _historial_auditoria(reclamo, id_reclamo, uid)
    elif estado == ESTADO_CANCELADO:
        filas.append({"id_reclamo": id_reclamo, "accion": "Reclamo cancelado",
                      "estado_anterior": ESTADO_EN_GESTION if asig else ESTADO_SIN_ASIGNAR,
                      "estado_nuevo": ESTADO_CANCELADO, "nota": "Cancelado (demo)",
                      "fecha": cierre, "uid": uid})
    return filas


def _historial_auditoria(reclamo: dict, id_reclamo: int, uid: int) -> list[dict]:
    """Pasos de la auditoria posterior al cierre (mig 112)."""
    filas = [{"id_reclamo": id_reclamo, "accion": "Enviado a auditoría",
              "estado_anterior": ESTADO_RESUELTO, "estado_nuevo": ESTADO_EN_AUDITORIA,
              "nota": "Control de calidad (demo)", "fecha": reclamo["fecha_inicio_auditoria"], "uid": uid}]
    if reclamo.get("fecha_fin_auditoria"):
        aprobada = reclamo.get("resultado_auditoria") == "aprobado"
        filas.append({"id_reclamo": id_reclamo,
                      "accion": "Auditoría aprobada" if aprobada else "Auditoría observada",
                      "estado_anterior": ESTADO_EN_AUDITORIA, "estado_nuevo": ESTADO_AUDITADO,
                      "nota": "Trabajo verificado por el auditor" if aprobada else "Se generó un reclamo de retrabajo",
                      "fecha": reclamo["fecha_fin_auditoria"], "uid": uid})
    return filas


def _armar_envio(rnd: random.Random, reclamo: dict, ahora: datetime,
                 id_plantilla: int, uid: int) -> tuple[dict, dict | None] | None:
    """Envio de encuesta para un reclamo RESUELTO (o None). Nunca 'pendiente'."""
    if rnd.random() > TASA_ENCUESTA:
        return None
    cierre = reclamo["fecha_cierre"]
    fecha_envio = cierre + timedelta(days=1, hours=rnd.uniform(0, 6))
    if fecha_envio > ahora:
        fecha_envio = ahora - timedelta(hours=1)
    expiracion = fecha_envio + timedelta(days=15)
    reciente = expiracion > ahora
    responde = rnd.random() < (0.30 if not reciente else 0.25)

    envio = {
        "id_plantilla": id_plantilla, "id_ciudadano": reclamo["id_ciudadano"],
        "email": reclamo["email"], "fecha_envio": fecha_envio,
        "fecha_apertura": None, "fecha_completada": None,
        "fecha_expiracion": expiracion,
        "estado": "enviada" if reciente else "expirada",
        "id_subarea": reclamo["id_subarea"], "uid": uid,
    }
    respuesta = None
    if responde:
        apertura = min(fecha_envio + timedelta(hours=rnd.uniform(1, 72)),
                       ahora - timedelta(minutes=30))
        completada = min(apertura + timedelta(minutes=rnd.uniform(2, 25)), ahora)
        clasificacion = _elegir(rnd, SCORES)
        envio.update({"estado": "completada", "fecha_apertura": apertura,
                      "fecha_completada": completada})
        respuesta = {"clasificacion": clasificacion, "rama": _rama(clasificacion),
                     "tiempo": rnd.randint(45, 420), "id_subarea": reclamo["id_subarea"],
                     "fecha": completada, "uid": uid}
    return envio, respuesta


async def _dias_con_reclamos_demo(db: AsyncSession, uid: int, desde: date, hasta: date,
                                  id_municipio: int) -> set[date]:
    """Dias del rango que ya tienen reclamos demo "de base" (sin contar
    subreclamos ni retrabajos, que nacen otro dia que su origen)."""
    r = await db.execute(text("""
        SELECT DISTINCT (fecha_alta AT TIME ZONE 'UTC')::date AS d FROM reclamos
         WHERE id_usuario_alta = :uid AND id_reclamo_padre IS NULL AND id_reclamo_origen_auditoria IS NULL
           AND id_municipio = :mun
           AND fecha_alta >= CAST(:d0 AS timestamptz) AND fecha_alta < CAST(:d1 AS timestamptz)
    """), {"uid": uid, "mun": id_municipio,
           "d0": datetime(desde.year, desde.month, desde.day, tzinfo=timezone.utc),
           "d1": datetime(hasta.year, hasta.month, hasta.day, tzinfo=timezone.utc) + timedelta(days=1)})
    return {f.d for f in r.fetchall()}


async def generar_periodo(db: AsyncSession, desde: date, hasta: date,
                          min_mensual: int = 300, max_mensual: int = 500,
                          vecinos_nuevos: int = 250,
                          semilla: int | None = None,
                          ahora: datetime | None = None) -> dict:
    """Genera reclamos demo (historial, OT operativas, auditorias, encuestas) en
    [desde, hasta], aplicando el plan SLA-aware de cada uno hasta `ahora`.

    Idempotente por dia: los dias que ya tienen reclamos demo se saltean. El
    volumen mensual se sortea en [min_mensual, max_mensual] por mes (determinista)
    y se reparte por dia. Nunca crea un alta posterior a `ahora`. Commitea al final.
    `ahora` solo para pruebas (simular otra fecha); default = reloj real.
    """
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(timezone.utc)
    uid = await _usuario_generador(db)
    cat = await _cargar_catalogos(db)
    if not cat.poblacion_tipos or not cat.poblacion_localidades:
        raise RuntimeError("Catalogo sin tipos/localidades matcheables: no se puede generar demo")
    pool = await _asegurar_vecinos(db, cat, uid, vecinos_nuevos, rnd)
    asignador = await _AsignadorOT.cargar(db, cat.id_municipio)
    sql_insert = _sql_insert_reclamo_con_id(cat.tiene_resolucion)

    ya = await _dias_con_reclamos_demo(db, uid, desde, hasta, cat.id_municipio)
    omitidos: list[str] = []
    base: list[dict] = []
    for dia in dias_rango(desde, hasta):
        if dia > ahora.date():
            continue
        if dia in ya:
            omitidos.append(str(dia))
            continue
        for _ in range(volumen_dia(rnd, "reclamos", dia, min_mensual, max_mensual, semilla)):
            rec = _armar_reclamo(rnd, cat, pool, dia, ahora)
            if rec:
                base.append(rec)
    base.sort(key=lambda x: x["fecha_alta"])  # nro_reclamo correlativo a la fecha
    ids = await reservar_ids(db, "reclamos", "id_reclamo", len(base))

    historial: list[dict] = []
    respuestas: list[dict] = []
    n = {"sub": 0, "envios": 0, "auditorias": 0, "retrabajos": 0, "ot": 0}
    por_estado: dict[str, int] = {}

    async def _insertar(rec: dict, id_reclamo: int, plan: _PlanReclamo, id_padre: int | None,
                        es_sub: bool, por_subreclamo: bool = False) -> tuple[int | None, str | None]:
        """Inserta el reclamo con su estado a `ahora` + OT operativa + historial.
        Devuelve (id_ot, estado)."""
        trans = _realizar(ESTADO_SIN_ASIGNAR, plan, rec["fecha_alta"], ahora)
        estado = trans[-1][2] if trans else ESTADO_SIN_ASIGNAR
        asig = next((t for t, _a, nv in trans if nv == ESTADO_EN_GESTION), None)
        cierre = trans[-1][0] if estado in (ESTADO_RESUELTO, ESTADO_CANCELADO) else None
        modif = trans[-1][0] if trans else rec["fecha_alta"]
        resolucion = rnd.choice(RESOLUCIONES) if estado == ESTADO_RESUELTO else None
        motivo = rnd.choice(MOTIVOS_CANCELACION) if estado == ESTADO_CANCELADO else None
        # Auditoria POSTERIOR al cierre (mig 112): ~8% de los resueltos (no subreclamos)
        # la supervision los manda a auditar 1-10 dias despues del cierre y el auditor
        # cierra 1-7 dias mas tarde (80% aprobada / 20% observada -> retrabajo).
        estado_db = estado
        es_retrabajo = bool(rec.get("id_reclamo_origen_auditoria"))
        if estado == ESTADO_RESUELTO and not es_sub and not es_retrabajo and rnd.random() < TASA_AUDITORIA:
            inicio = cierre + timedelta(days=rnd.uniform(1, 10))
            if inicio <= ahora:
                rec["auditoria"] = True
                rec["fecha_inicio_auditoria"] = inicio
                fin = inicio + timedelta(days=rnd.uniform(1, 7))
                estado_db = ESTADO_EN_AUDITORIA
                if fin <= ahora:
                    estado_db = ESTADO_AUDITADO
                    rec["fecha_fin_auditoria"] = fin
                    rec["resultado_auditoria"] = "observado" if rnd.random() < TASA_OBSERVADA else "aprobado"
        rec.update({"estado": estado_db, "fecha_primer_asignacion": asig, "fecha_cierre": cierre})
        params = {
            "id_reclamo": id_reclamo,
            "id_ciudadano": rec["id_ciudadano"], "id_tipo_reclamo": rec["id_tipo_reclamo"],
            "descripcion": rec["descripcion"], "prioridad": rec["prioridad"],
            "estado": estado_db, "id_estado_fk": cat.estados_fk.get(estado_db),
            "direccion": rec["direccion"], "latitud": rec["latitud"], "longitud": rec["longitud"],
            "id_localidad": rec["id_localidad"], "canal_origen": rec["canal_origen"],
            "fuente_geolocalizacion": rec["fuente_geolocalizacion"],
            "fecha_alta": rec["fecha_alta"],
            "fecha_modificacion": rec.get("fecha_fin_auditoria") or rec.get("fecha_inicio_auditoria") or modif,
            "fecha_primer_asignacion": asig, "fecha_cierre": cierre, "uid": uid,
            "id_reclamo_padre": id_padre,
            "fecha_inicio_auditoria": rec.get("fecha_inicio_auditoria"),
            "fecha_fin_auditoria": rec.get("fecha_fin_auditoria"),
            "resultado_auditoria": rec.get("resultado_auditoria"),
            "id_reclamo_origen_auditoria": rec.get("id_reclamo_origen_auditoria"),
            "id_municipio": cat.id_municipio,
        }
        if cat.tiene_resolucion:
            params["resolucion"] = resolucion
        fila = (await db.execute(sql_insert, params)).fetchone()
        rec["_nro"] = fila.nro_reclamo
        por_estado[estado_db] = por_estado.get(estado_db, 0) + 1

        id_ot = nro_ot = None
        recurso = None
        if asig is not None:
            p_ot, recurso = _params_ot(cat, asignador, rnd, id_reclamo, rec["id_tipo_reclamo"], estado,
                                       asig, cierre, modif, uid, resolucion)
            if p_ot:
                ot = (await db.execute(_SQL_INSERT_OT_OPERATIVA, p_ot)).fetchone()
                id_ot, nro_ot = ot.id_ot, ot.nro_ot or f"OT-{ot.id_ot}"
                n["ot"] += 1
        historial.append({
            "id_reclamo": id_reclamo,
            "accion": ("Reclamo ingresado por auditoría observada" if es_retrabajo
                       else "Subreclamo ingresado" if es_sub else "Reclamo ingresado"),
            "estado_anterior": None, "estado_nuevo": ESTADO_SIN_ASIGNAR,
            "nota": f"Retrabajo del reclamo {rec.get('_nro_origen') or rec['id_reclamo_origen_auditoria']}" if es_retrabajo else None,
            "fecha": rec["fecha_alta"], "uid": uid,
        })
        for t, ant, nv in trans:
            accion, nota = _texto_historial(ant, nv, nro_ot, recurso, resolucion, motivo,
                                            por_subreclamo and nv in (ESTADO_EN_ESPERA, ESTADO_EN_GESTION)
                                            and ant != ESTADO_SIN_ASIGNAR, "")
            historial.append({"id_reclamo": id_reclamo, "accion": accion, "estado_anterior": ant,
                              "estado_nuevo": nv, "nota": nota, "fecha": t, "uid": uid})
        if rec.get("fecha_inicio_auditoria"):
            historial.extend(_historial_auditoria(rec, id_reclamo, uid))
        return id_ot, estado_db

    async def _encuestar(rec: dict, id_reclamo: int) -> int:
        """Envio (y quizas respuesta) de encuesta del reclamo resuelto. Devuelve 0 o 1."""
        par = _armar_envio(rnd, rec, ahora, cat.id_plantilla_reclamos, uid)
        if not par:
            return 0
        envio, respuesta = par
        envio["id_reclamo"] = id_reclamo
        fila = (await db.execute(_SQL_INSERT_ENVIO, envio)).fetchone()
        if respuesta:
            respuesta["id_envio"] = fila.id_encuesta_envio
            respuestas.append(respuesta)
        return 1

    for rec, id_reclamo in zip(base, ids):
        sla = cat.tipo_sla.get(rec["id_tipo_reclamo"])
        plan = _plan_reclamo(id_reclamo, rec["fecha_alta"], sla)

        # Subreclamo (~4% de los que tardan 4 dias o mas): nace despues de asignado el
        # padre, que queda 'En espera' hasta que el subreclamo se resuelve.
        hijo = plan_hijo = None
        if (plan.estado_final == ESTADO_RESUELTO and plan.cierre - rec["fecha_alta"] >= timedelta(days=4)
                and rnd.random() < TASA_SUBRECLAMO):
            asig_p = plan.eventos[0][0]
            alta_h = asig_p + timedelta(hours=rnd.uniform(2, 24))
            if alta_h < plan.cierre - timedelta(days=1) and alta_h <= ahora - timedelta(minutes=5):
                hijo = dict(rec)
                hijo["id_tipo_reclamo"] = _resolver_tipo(rnd, cat)
                nombre_h, sub_h = cat.tipo_info[hijo["id_tipo_reclamo"]]
                hijo.update({"id_subarea": sub_h, "fecha_alta": alta_h,
                             "descripcion": f"Subreclamo derivado: {nombre_h}. {rec['direccion']}.",
                             "auditoria": False, "subreclamo": False})
                hijo["_id"] = (await reservar_ids(db, "reclamos", "id_reclamo", 1))[0]
                plan_hijo = _plan_subreclamo(hijo["_id"], alta_h, cat.tipo_sla.get(hijo["id_tipo_reclamo"]), plan)
                cierre_h = plan_hijo.cierre if plan_hijo.cierre <= ahora else None
                plan = _con_subreclamos(plan, [(alta_h, cierre_h)])

        id_ot, estado_db = await _insertar(rec, id_reclamo, plan, None, False, por_subreclamo=hijo is not None)
        if hijo is not None:
            await _insertar(hijo, hijo["_id"], plan_hijo, id_reclamo, True)
            n["sub"] += 1

        # Auditoria posterior (mig 112): OT de auditoria + retrabajo si fue observada.
        if rec["auditoria"]:
            cerrada = rec.get("fecha_fin_auditoria") is not None
            id_estado = cat.id_estado_ot_terminada if cerrada else cat.id_estado_ot_gestion
            if id_estado is not None:
                resultado = None
                if cerrada:
                    resultado = "aprobada" if rec.get("resultado_auditoria") == "aprobado" else "observada"
                await db.execute(_SQL_INSERT_OT_AUDITORIA_ORIGEN, {
                    "id_reclamo": id_reclamo, "id_estado": id_estado, "resultado": resultado,
                    "obs_aud": ("Trabajo verificado" if resultado == "aprobada"
                                else rnd.choice(OBSERVACIONES_AUDITORIA) if resultado else None),
                    "uid": uid, "id_ot_origen": id_ot,
                    "inicio": rec["fecha_inicio_auditoria"], "fin": rec.get("fecha_fin_auditoria"),
                })
            n["auditorias"] += 1
            if rec.get("resultado_auditoria") == "observado":
                retrabajo = _base_retrabajo(rec, id_reclamo, rec.get("_nro"), rnd.choice(OBSERVACIONES_AUDITORIA))
                id_rt = (await reservar_ids(db, "reclamos", "id_reclamo", 1))[0]
                plan_rt = _plan_reclamo(id_rt, retrabajo["fecha_alta"], sla)
                _ot_rt, estado_rt = await _insertar(retrabajo, id_rt, plan_rt, None, False)
                n["retrabajos"] += 1
                # F4: el vecino ve el retrabajo y al resolverlo se lo encuesta (sin anti-fatiga).
                if estado_rt == ESTADO_RESUELTO and cat.id_plantilla_reclamos:
                    n["envios"] += await _encuestar(retrabajo, id_rt)

        # La encuesta se dispara en el PRIMER cierre: un reclamo auditado tambien la tuvo.
        if estado_db in ESTADOS_GESTION_CERRADA_OK and cat.id_plantilla_reclamos:
            n["envios"] += await _encuestar(rec, id_reclamo)

    if historial:
        await db.execute(_SQL_INSERT_HISTORIAL, historial)
    if respuestas:
        await db.execute(_SQL_INSERT_RESPUESTA, respuestas)
    await db.commit()

    pendientes = sum(por_estado.get(e, 0) for e in ESTADOS_PENDIENTES)
    return {"reclamos": len(base), "subreclamos": n["sub"], "por_estado": por_estado,
            "pendientes": pendientes, "ot_operativas": n["ot"],
            "ot_por_origen": dict(asignador.por_origen),
            "auditorias": n["auditorias"], "retrabajos": n["retrabajos"],
            "encuestas_enviadas": n["envios"], "encuestas_respondidas": len(respuestas),
            "dias_omitidos_con_demo": len(omitidos), "pool_vecinos": len(pool),
            "desde": str(desde), "hasta": str(hasta)}


async def backfill_auditorias(db: AsyncSession, fraccion: float = TASA_AUDITORIA,
                              semilla: int | None = None, aplicar: bool = False) -> dict:
    """Una sola vez por entorno (2026-10-20, F3 de PLAN_AUDITORIA_RECLAMOS.md): sobre
    los reclamos demo YA cargados antes de la mig 112, sortea `fraccion` de los
    Resueltos sin auditoria y les aplica una auditoria POSTERIOR al cierre con las
    mismas reglas que generar_periodo (1-10 dias despues del cierre; 1-7 dias
    de revision; 80% aprobada / 20% observada con reclamo de retrabajo envejecido).
    Solo datos del usuario generador. Con aplicar=False no escribe: devuelve los
    conteos que escribiria. NO commitea: lo hace el caller.

    El sorteo (que reclamos, fechas, resultado) se decide en una primera pasada
    con `random.Random(semilla)` y SIN escribir; la escritura usa otro generador
    para sus detalles (textos, envejecimiento del retrabajo). Asi el dry-run y el
    aplicar con la misma semilla tocan EXACTAMENTE los mismos ids (el snapshot
    previo se arma con los ids del dry-run).
    """
    rnd = random.Random(semilla)
    rnd_detalle = random.Random((semilla or 0) + 7)
    ahora = datetime.now(timezone.utc)
    uid = await _usuario_generador(db, crear=False)
    if uid is None:
        return {"detalle": "sin usuario generador: nada que auditar"}
    cat = await _cargar_catalogos(db)
    if cat.id_estado_ot_gestion is None or cat.id_estado_ot_terminada is None:
        raise RuntimeError("estado_ot sin 'En gestión'/'Terminada': no se pueden crear las OT de auditoria")

    r = await db.execute(text("""
        SELECT r.id_reclamo, r.nro_reclamo, r.id_ciudadano, r.id_tipo_reclamo, r.descripcion,
               r.prioridad, r.direccion, r.latitud, r.longitud, r.id_localidad, r.canal_origen,
               r.fuente_geolocalizacion, r.fecha_alta, r.fecha_primer_asignacion, r.fecha_cierre,
               c.email
        FROM reclamos r JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        WHERE r.activo AND r.id_usuario_alta = :uid AND r.estado = 'Resuelto'
          AND r.fecha_cierre IS NOT NULL AND r.fecha_inicio_auditoria IS NULL
          AND r.id_reclamo_origen_auditoria IS NULL AND r.id_reclamo_padre IS NULL
          AND r.id_municipio = :mun
        ORDER BY r.id_reclamo
    """), {"uid": uid, "mun": cat.id_municipio})
    candidatos = r.fetchall()

    # Pasada 1: el plan, sin escribir.
    plan: list[tuple] = []
    for p in candidatos:
        if rnd.random() >= fraccion:
            continue
        inicio = p.fecha_cierre + timedelta(days=rnd.uniform(1, 10))
        if inicio > ahora:
            continue
        fin = inicio + timedelta(days=rnd.uniform(1, 7))
        cerrada = fin <= ahora
        resultado = None
        if cerrada:
            resultado = "observado" if rnd.random() < TASA_OBSERVADA else "aprobado"
        plan.append((p, inicio, fin, cerrada, resultado))

    historial: list[dict] = []
    conteo = {"candidatos": len(candidatos), "auditadas": 0, "pendientes": 0,
              "observadas": 0, "retrabajos": 0, "ids": []}
    # Pasada 2: conteos (dry-run) y, si aplicar, escritura con rnd_detalle.
    rnd = rnd_detalle
    for p, inicio, fin, cerrada, resultado in plan:
        rec = {
            "id_ciudadano": p.id_ciudadano, "id_tipo_reclamo": p.id_tipo_reclamo,
            "id_subarea": cat.tipo_info.get(p.id_tipo_reclamo, (None, None))[1],
            "email": p.email, "id_localidad": p.id_localidad,
            "latitud": p.latitud, "longitud": p.longitud, "direccion": p.direccion,
            "descripcion": p.descripcion, "prioridad": p.prioridad,
            "canal_origen": p.canal_origen, "fuente_geolocalizacion": p.fuente_geolocalizacion,
            "fecha_alta": p.fecha_alta, "fecha_primer_asignacion": p.fecha_primer_asignacion,
            "fecha_cierre": p.fecha_cierre, "estado": ESTADO_AUDITADO if cerrada else ESTADO_EN_AUDITORIA,
            "auditoria": True, "subreclamo": False,
            "fecha_inicio_auditoria": inicio, "fecha_fin_auditoria": fin if cerrada else None,
            "resultado_auditoria": resultado, "id_reclamo_origen_auditoria": None,
        }
        conteo["auditadas" if cerrada else "pendientes"] += 1
        conteo["ids"].append(p.id_reclamo)
        if resultado == "observado":
            conteo["observadas"] += 1
            conteo["retrabajos"] += 1  # cada observada genera exactamente un retrabajo
        if not aplicar:
            continue

        await db.execute(text("""
            UPDATE reclamos SET estado = :estado, id_estado_fk = :fk,
                   fecha_inicio_auditoria = :inicio, fecha_fin_auditoria = :fin,
                   resultado_auditoria = :resultado, fecha_modificacion = :mod,
                   id_usuario_modificacion = :uid
            WHERE id_reclamo = :id
        """), {"estado": rec["estado"], "fk": cat.estados_fk.get(rec["estado"]),
               "inicio": inicio, "fin": fin if cerrada else None, "resultado": resultado,
               "mod": fin if cerrada else inicio, "uid": uid, "id": p.id_reclamo})
        await db.execute(_SQL_INSERT_OT_AUDITORIA, {
            "id_reclamo": p.id_reclamo,
            "id_estado": cat.id_estado_ot_terminada if cerrada else cat.id_estado_ot_gestion,
            "resultado": ("aprobada" if resultado == "aprobado" else "observada") if cerrada else None,
            "obs_aud": ("Trabajo verificado" if resultado == "aprobado"
                        else rnd.choice(OBSERVACIONES_AUDITORIA) if cerrada else None),
            "uid": uid, "inicio": inicio, "fin": fin if cerrada else None,
        })
        # Historial: solo los pasos de auditoria (los de gestion ya existen).
        filas = _historial_de(rec, p.id_reclamo, uid, rnd, False)
        historial.extend(f for f in filas if f["estado_nuevo"] in (ESTADO_EN_AUDITORIA, ESTADO_AUDITADO))
        if resultado == "observado":
            retrabajo = _armar_retrabajo(rnd, rec, p.id_reclamo, p.nro_reclamo, ahora)
            fila = (await db.execute(_SQL_INSERT_RECLAMO, {
                "id_ciudadano": retrabajo["id_ciudadano"], "id_tipo_reclamo": retrabajo["id_tipo_reclamo"],
                "descripcion": retrabajo["descripcion"], "prioridad": retrabajo["prioridad"],
                "estado": retrabajo["estado"], "id_estado_fk": cat.estados_fk.get(retrabajo["estado"]),
                "direccion": retrabajo["direccion"], "latitud": retrabajo["latitud"],
                "longitud": retrabajo["longitud"], "id_localidad": retrabajo["id_localidad"],
                "canal_origen": retrabajo["canal_origen"],
                "fuente_geolocalizacion": retrabajo["fuente_geolocalizacion"],
                "fecha_alta": retrabajo["fecha_alta"],
                "fecha_primer_asignacion": retrabajo["fecha_primer_asignacion"],
                "fecha_cierre": retrabajo["fecha_cierre"], "uid": uid, "id_reclamo_padre": None,
                "fecha_inicio_auditoria": None, "fecha_fin_auditoria": None,
                "resultado_auditoria": None, "id_reclamo_origen_auditoria": p.id_reclamo,
                "id_municipio": cat.id_municipio,
            })).fetchone()
            historial.extend(_historial_de(retrabajo, fila.id_reclamo, uid, rnd, False))

    if aplicar and historial:
        await db.execute(_SQL_INSERT_HISTORIAL, historial)
    return conteo


# ── Avance de pendientes (cron) y cierre del atraso ─────────────────────────

_SQL_PENDIENTES = """
    SELECT r.id_reclamo, r.nro_reclamo, r.estado, r.fecha_alta, r.id_tipo_reclamo, r.id_reclamo_padre,
           r.id_ciudadano, c.email, r.id_usuario_alta, r.fecha_primer_asignacion,
           (SELECT MAX(h.fecha_alta) FROM reclamo_historial h WHERE h.id_reclamo = r.id_reclamo) AS ultimo,
           ot.id_ot, ot.nro_ot
      FROM reclamos r
      LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
      LEFT JOIN LATERAL (
            SELECT o.id_ot, o.nro_ot FROM ordenes_trabajo o
             WHERE o.id_reclamo = r.id_reclamo AND o.activo AND NOT o.es_auditoria
             ORDER BY o.id_ot DESC LIMIT 1) ot ON TRUE
     WHERE r.activo AND r.estado IN ('Sin asignar', 'En gestión', 'En espera')
       AND r.fecha_alta <= CAST(:ahora AS timestamptz)
       AND r.id_municipio = :mun
       AND {filtro}
     ORDER BY r.id_reclamo
"""


async def _avanzar_reclamos(db: AsyncSession, cat: _Catalogos, uid: int, asignador: _AsignadorOT,
                            rnd: random.Random, ahora: datetime, filas: list, *,
                            aplicar: bool, forzar_final: bool, encuestar: bool) -> dict:
    """Aplica el plan de cada reclamo pendiente hasta `ahora`: transiciones con las
    fechas del plan, OT operativa coherente (la crea si falta), historial y, si
    `encuestar`, la encuesta de los que se resuelven (solo datos demo). Con
    aplicar=False solo cuenta. Los subreclamos se procesan antes que los padres."""
    out = {"evaluados": len(filas), "a_gestion": 0, "a_espera": 0, "reanudados": 0,
           "a_resuelto": 0, "a_cancelado": 0, "cerrados_dentro_sla": 0, "cerrados_fuera_sla": 0,
           "ot_creadas": 0, "ot_actualizadas": 0, "encuestas": 0, "no_demo": 0, "omitidos_piso_futuro": 0}
    if not filas:
        return out
    sql_upd = text("""
        UPDATE reclamos SET estado = :estado, id_estado_fk = :fk,
               fecha_primer_asignacion = COALESCE(fecha_primer_asignacion, CAST(:asig AS timestamptz)),
               fecha_cierre = CAST(:cierre AS timestamptz), fecha_modificacion = CAST(:modif AS timestamptz),
               id_usuario_modificacion = :uid {res}
         WHERE id_reclamo = :id AND estado = :estado_prev
    """.format(res=", resolucion = COALESCE(:resolucion, resolucion)" if cat.tiene_resolucion else ""))

    # Padres de los subreclamos pendientes y subreclamos de los padres pendientes.
    ids = [f.id_reclamo for f in filas]
    ids_padres = sorted({f.id_reclamo_padre for f in filas if f.id_reclamo_padre})
    padres: dict[int, tuple] = {}
    if ids_padres:
        r = await db.execute(text(
            "SELECT id_reclamo, fecha_alta, id_tipo_reclamo FROM reclamos WHERE id_reclamo = ANY(:ids)"),
            {"ids": ids_padres})
        padres = {f.id_reclamo: (f.fecha_alta, f.id_tipo_reclamo) for f in r.fetchall()}
    hijos: dict[int, dict[int, list]] = {}
    r = await db.execute(text("""
        SELECT id_reclamo, id_reclamo_padre, fecha_alta, estado, fecha_cierre FROM reclamos
         WHERE activo AND id_reclamo_padre = ANY(:ids)
    """), {"ids": ids})
    for f in r.fetchall():
        hijos.setdefault(f.id_reclamo_padre, {})[f.id_reclamo] = [f.fecha_alta, f.estado, f.fecha_cierre]

    historial: list[dict] = []
    respuestas: list[dict] = []
    orden = sorted(filas, key=lambda f: (f.id_reclamo_padre is None, f.id_reclamo))  # hijos primero
    for f in orden:
        piso = max(f.ultimo or f.fecha_alta, f.fecha_alta)
        if piso > ahora:
            out["omitidos_piso_futuro"] += 1
            continue
        es_demo = f.id_usuario_alta == uid
        out["no_demo"] += 0 if es_demo else 1
        sla = cat.tipo_sla.get(f.id_tipo_reclamo)
        if f.id_reclamo_padre and f.id_reclamo_padre in padres:
            alta_p, tipo_p = padres[f.id_reclamo_padre]
            plan = _plan_subreclamo(f.id_reclamo, f.fecha_alta, sla,
                                    _plan_reclamo(f.id_reclamo_padre, alta_p, cat.tipo_sla.get(tipo_p)))
        else:
            plan = _plan_reclamo(f.id_reclamo, f.fecha_alta, sla)
            hs = hijos.get(f.id_reclamo)
            if hs:
                cerrados = ("Resuelto", "Cancelado", "En auditoría", "Auditado")
                plan = _con_subreclamos(plan, [(a, c if e in cerrados and c else None) for a, e, c in hs.values()])
        trans = _realizar(f.estado, plan, piso, ahora, forzar_final=forzar_final)
        if not trans and not (f.estado in (ESTADO_EN_GESTION, ESTADO_EN_ESPERA) and f.id_ot is None):
            continue
        estado = trans[-1][2] if trans else f.estado
        final = estado in (ESTADO_RESUELTO, ESTADO_CANCELADO)
        cierre = trans[-1][0] if final else None
        modif = trans[-1][0] if trans else piso
        asig = next((t for t, _a, nv in trans if nv == ESTADO_EN_GESTION), None)
        resolucion = rnd.choice(RESOLUCIONES) if estado == ESTADO_RESUELTO else None
        motivo = rnd.choice(MOTIVOS_CANCELACION) if estado == ESTADO_CANCELADO else None
        for _t, _a, nv in trans:
            if nv == ESTADO_EN_GESTION:
                out["reanudados" if _a == ESTADO_EN_ESPERA else "a_gestion"] += 1
            elif nv == ESTADO_EN_ESPERA:
                out["a_espera"] += 1
            elif nv == ESTADO_RESUELTO:
                out["a_resuelto"] += 1
                ok = demo_sla.dentro_sla_reclamo(f.fecha_alta, _t, sla)
                if ok is not None:
                    out["cerrados_dentro_sla" if ok else "cerrados_fuera_sla"] += 1
            elif nv == ESTADO_CANCELADO:
                out["a_cancelado"] += 1
        if f.id_reclamo_padre and f.id_reclamo_padre in hijos:
            hijos[f.id_reclamo_padre][f.id_reclamo] = [f.fecha_alta, estado, cierre]

        # OT operativa: se crea si el reclamo paso (o pasa ahora) por En gestion y no la tiene.
        id_ot, nro_ot, recurso = f.id_ot, f.nro_ot, None
        paso_por_gestion = asig is not None or f.fecha_primer_asignacion is not None \
            or f.estado in (ESTADO_EN_GESTION, ESTADO_EN_ESPERA)
        crea_ot = id_ot is None and paso_por_gestion
        if crea_ot:
            creacion = f.fecha_primer_asignacion or asig or piso
            p_ot, recurso = _params_ot(cat, asignador, rnd, f.id_reclamo, f.id_tipo_reclamo, estado,
                                       creacion, cierre, modif, uid, resolucion)
            if p_ot:
                out["ot_creadas"] += 1
                if aplicar:
                    ot = (await db.execute(_SQL_INSERT_OT_OPERATIVA, p_ot)).fetchone()
                    id_ot, nro_ot = ot.id_ot, ot.nro_ot or f"OT-{ot.id_ot}"
                else:
                    nro_ot = "OT-(nueva)"
        elif id_ot is not None and trans:
            out["ot_actualizadas"] += 1
            if aplicar:
                estado_ot = cat.estados_ot.get(_ESTADO_OT_DE_RECLAMO.get(estado, "En gestión"))
                if estado_ot is not None:
                    await db.execute(_SQL_UPDATE_OT_OPERATIVA, {
                        "id_estado": estado_ot, "cierre": cierre, "obs": resolucion,
                        "modif": modif, "uid": uid, "id_ot": id_ot})
        if not aplicar or not trans:
            continue

        params = {"estado": estado, "fk": cat.estados_fk.get(estado), "asig": asig, "cierre": cierre,
                  "modif": modif, "uid": uid, "id": f.id_reclamo, "estado_prev": f.estado}
        if cat.tiene_resolucion:
            params["resolucion"] = resolucion
        await db.execute(sql_upd, params)
        sufijo = "" if es_demo else " Cierre de atraso de datos de prueba."
        tiene_hijos = bool(hijos.get(f.id_reclamo))
        for t, ant, nv in trans:
            accion, nota = _texto_historial(ant, nv, nro_ot if crea_ot else None, recurso, resolucion, motivo,
                                            tiene_hijos and ant != ESTADO_SIN_ASIGNAR, sufijo)
            historial.append({"id_reclamo": f.id_reclamo, "accion": accion, "estado_anterior": ant,
                              "estado_nuevo": nv, "nota": nota, "fecha": t, "uid": uid})
        # Encuesta del primer cierre (solo demo, nunca 'pendiente'; no subreclamos).
        if (encuestar and es_demo and estado == ESTADO_RESUELTO and not f.id_reclamo_padre
                and cat.id_plantilla_reclamos and f.email):
            par = _armar_envio(rnd, {"fecha_cierre": cierre, "id_ciudadano": f.id_ciudadano,
                                     "email": f.email, "id_subarea": cat.tipo_info.get(f.id_tipo_reclamo, (None, None))[1]},
                               ahora, cat.id_plantilla_reclamos, uid)
            if par:
                envio, respuesta = par
                envio["id_reclamo"] = f.id_reclamo
                fila = (await db.execute(_SQL_INSERT_ENVIO, envio)).fetchone()
                out["encuestas"] += 1
                if respuesta:
                    respuesta["id_envio"] = fila.id_encuesta_envio
                    respuestas.append(respuesta)

    if aplicar and historial:
        await db.execute(_SQL_INSERT_HISTORIAL, historial)
    if aplicar and respuestas:
        await db.execute(_SQL_INSERT_RESPUESTA, respuestas)
    return out


async def avanzar_pendientes(db: AsyncSession, semilla: int | None = None,
                             ahora: datetime | None = None) -> dict:
    """Envejece SOLO los datos demo (atribuidos al usuario generador) siguiendo el
    plan de cada reclamo: asigna (con su OT), pone en espera, resuelve o cancela en
    las fechas planificadas — la misma mezcla de SLA que el generador —, manda a
    auditar / cierra auditorias y madura encuestas. Idempotente: correrlo dos veces
    el mismo dia no cambia nada mas. Pensado para el cron diario."""
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(timezone.utc)
    uid = await _usuario_generador(db, crear=False)
    if uid is None:
        return {"detalle": "sin usuario generador: nada que avanzar"}
    cat = await _cargar_catalogos(db)
    asignador = await _AsignadorOT.cargar(db, cat.id_municipio)

    # Solo la ventana reciente: lo pendiente mas viejo (datos anteriores a esta version)
    # lo cierra cerrar_atraso_reclamos, que tiene dry-run para revisarlo antes.
    r = await db.execute(text(_SQL_PENDIENTES.format(
        filtro="r.id_usuario_alta = :uid AND r.fecha_alta >= CAST(:ventana AS timestamptz)")),
        {"uid": uid, "ahora": ahora, "ventana": ahora - timedelta(days=VENTANA_AVANCE_DIAS),
         "mun": cat.id_municipio})
    pendientes = r.fetchall()
    movidos = await _avanzar_reclamos(db, cat, uid, asignador, rnd, ahora, pendientes,
                                      aplicar=True, forzar_final=False, encuestar=True)
    movidos["ot_por_origen"] = dict(asignador.por_origen)

    historial: list[dict] = []
    respuestas: list[dict] = []
    # Auditoria POSTERIOR al cierre (mig 112), solo datos demo:
    #  (a) ~60% de las auditorias pendientes de mas de un dia se cierran (80% aprobada /
    #      20% observada; la observada genera el reclamo de retrabajo);
    #  (b) ~3% de los resueltos de los ultimos 30 dias sin auditoria se mandan a auditar.
    movidos.update({"auditorias_cerradas": 0, "retrabajos": 0, "a_auditoria": 0})
    if cat.id_estado_ot_terminada is not None and cat.id_estado_ot_gestion is not None:
        r = await db.execute(text("""
            SELECT r.id_reclamo, r.nro_reclamo, r.fecha_inicio_auditoria
            FROM reclamos r
            WHERE r.activo AND r.id_usuario_alta = :uid AND r.estado = 'En auditoría'
              AND r.fecha_inicio_auditoria < :limite AND r.id_municipio = :mun
        """), {"uid": uid, "limite": ahora - timedelta(days=1), "mun": cat.id_municipio})
        for p in r.fetchall():
            if rnd.random() >= 0.60:
                continue
            aprobada = rnd.random() >= TASA_OBSERVADA
            obs = "Trabajo verificado" if aprobada else rnd.choice(OBSERVACIONES_AUDITORIA)
            fin = max(ahora - timedelta(hours=rnd.uniform(0, 48)),
                      p.fecha_inicio_auditoria + timedelta(hours=1))
            await db.execute(_SQL_CERRAR_AUDITORIA_RECLAMO, {
                "id": p.id_reclamo, "fk": cat.estados_fk.get(ESTADO_AUDITADO),
                "resultado": "aprobado" if aprobada else "observado", "fin": fin, "uid": uid})
            await db.execute(_SQL_CERRAR_AUDITORIA_OT, {
                "id": p.id_reclamo, "id_terminada": cat.id_estado_ot_terminada,
                "resultado_ot": "aprobada" if aprobada else "observada", "obs": obs, "fin": fin, "uid": uid})
            historial.append({"id_reclamo": p.id_reclamo,
                              "accion": "Auditoría aprobada" if aprobada else "Auditoría observada",
                              "estado_anterior": ESTADO_EN_AUDITORIA, "estado_nuevo": ESTADO_AUDITADO,
                              "nota": obs, "fecha": fin, "uid": uid})
            movidos["auditorias_cerradas"] += 1
            if not aprobada:
                nuevo = (await db.execute(_SQL_INSERT_RETRABAJO_DESDE, {
                    "id": p.id_reclamo, "obs": obs, "fk": cat.estados_fk.get(ESTADO_SIN_ASIGNAR),
                    "fecha": fin, "uid": uid})).fetchone()
                historial.append({"id_reclamo": nuevo.id_reclamo, "accion": "Reclamo ingresado por auditoría observada",
                                  "estado_anterior": None, "estado_nuevo": ESTADO_SIN_ASIGNAR,
                                  "nota": f"Retrabajo del reclamo {p.nro_reclamo or p.id_reclamo}",
                                  "fecha": fin, "uid": uid})
                movidos["retrabajos"] += 1

        r = await db.execute(text("""
            SELECT r.id_reclamo, r.fecha_cierre,
                   (SELECT o.id_ot FROM ordenes_trabajo o WHERE o.id_reclamo = r.id_reclamo
                     AND o.activo AND NOT o.es_auditoria ORDER BY o.id_ot DESC LIMIT 1) AS id_ot
            FROM reclamos r
            WHERE r.activo AND r.id_usuario_alta = :uid AND r.estado = 'Resuelto'
              AND r.fecha_inicio_auditoria IS NULL AND r.id_reclamo_origen_auditoria IS NULL
              AND r.fecha_cierre > :desde AND r.fecha_cierre <= :ahora AND r.id_municipio = :mun
        """), {"uid": uid, "desde": ahora - timedelta(days=30), "ahora": ahora, "mun": cat.id_municipio})
        for p in r.fetchall():
            if rnd.random() >= 0.03:
                continue
            inicio = min(max(ahora - timedelta(hours=rnd.uniform(0, 72)), p.fecha_cierre + timedelta(hours=1)), ahora)
            await db.execute(_SQL_ENVIAR_AUDITORIA, {
                "id": p.id_reclamo, "fk": cat.estados_fk.get(ESTADO_EN_AUDITORIA), "inicio": inicio, "uid": uid})
            await db.execute(_SQL_INSERT_OT_AUDITORIA_ORIGEN, {
                "id_reclamo": p.id_reclamo, "id_estado": cat.id_estado_ot_gestion, "resultado": None,
                "obs_aud": None, "uid": uid, "id_ot_origen": p.id_ot, "inicio": inicio, "fin": None})
            historial.append({"id_reclamo": p.id_reclamo, "accion": "Enviado a auditoría",
                              "estado_anterior": ESTADO_RESUELTO, "estado_nuevo": ESTADO_EN_AUDITORIA,
                              "nota": "Control de calidad (demo)", "fecha": inicio, "uid": uid})
            movidos["a_auditoria"] += 1

    # Maduracion de encuestas demo: expirar vencidas y responder ~35% de las vivas.
    await db.execute(text("""
        UPDATE encuesta_envio SET estado = 'expirada', fecha_modificacion = :ahora
        WHERE estado = 'enviada' AND fecha_expiracion < :ahora AND id_usuario_alta = :uid
          AND id_municipio = :mun
    """), {"ahora": ahora, "uid": uid, "mun": cat.id_municipio})
    r = await db.execute(text("""
        SELECT ev.id_encuesta_envio, ev.id_subarea, ev.fecha_envio
        FROM encuesta_envio ev
        WHERE ev.estado = 'enviada' AND ev.id_usuario_alta = :uid AND ev.fecha_envio <= :ahora
          AND ev.id_municipio = :mun
    """), {"uid": uid, "ahora": ahora, "mun": cat.id_municipio})
    n_resp = 0
    for ev in r.fetchall():
        if rnd.random() < 0.35:
            apertura = min(ev.fecha_envio + timedelta(hours=rnd.uniform(1, 96)), ahora - timedelta(minutes=30))
            completada = min(apertura + timedelta(minutes=rnd.uniform(2, 25)), ahora)
            clasificacion = _elegir(rnd, SCORES)
            await db.execute(text("""
                UPDATE encuesta_envio SET estado = 'completada', fecha_apertura = :ap,
                       fecha_completada = :comp, fecha_modificacion = :comp
                WHERE id_encuesta_envio = :id
            """), {"ap": apertura, "comp": completada, "id": ev.id_encuesta_envio})
            respuestas.append({"id_envio": ev.id_encuesta_envio, "clasificacion": clasificacion,
                               "rama": _rama(clasificacion), "tiempo": rnd.randint(45, 420),
                               "id_subarea": ev.id_subarea, "fecha": completada, "uid": uid})
            n_resp += 1

    if historial:
        await db.execute(_SQL_INSERT_HISTORIAL, historial)
    if respuestas:
        await db.execute(_SQL_INSERT_RESPUESTA, respuestas)
    await db.commit()
    return {"pendientes_evaluados": len(pendientes), **movidos, "encuestas_respondidas": n_resp}


async def completar_ot_historicas(db: AsyncSession, uid: int, aplicar: bool,
                                  ahora: datetime | None = None, semilla: int | None = None,
                                  excluir: set[int] | None = None) -> dict:
    """OT operativa para cada reclamo demo YA cargado que paso por 'En gestion' y no
    la tiene (los generados antes del 2026-10-21 no tenian OT operativa). Estado
    coherente con el reclamo: Terminada (resueltos, en auditoria y auditados),
    Cancelada, En gestion o En espera. Tambien liga las OT de auditoria demo a la
    OT operativa que auditan (id_ot_origen). `excluir`: reclamos que el cierre del
    atraso ya proceso (su OT se cuenta ahi; sin esto el dry-run la contaria dos
    veces). No commitea."""
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(timezone.utc)
    cat = await _cargar_catalogos(db)
    r = await db.execute(text("""
        SELECT r.id_reclamo, r.estado, r.id_tipo_reclamo, r.fecha_primer_asignacion, r.fecha_cierre,
               r.fecha_modificacion, r.fecha_alta
          FROM reclamos r
         WHERE r.activo AND r.id_usuario_alta = :uid AND r.fecha_primer_asignacion IS NOT NULL
           AND r.id_municipio = :mun
           AND r.fecha_primer_asignacion <= CAST(:ahora AS timestamptz)
           AND r.estado IN ('Resuelto', 'En auditoría', 'Auditado', 'Cancelado', 'En gestión', 'En espera')
           AND NOT EXISTS (SELECT 1 FROM ordenes_trabajo o WHERE o.id_reclamo = r.id_reclamo
                            AND o.activo AND NOT o.es_auditoria)
         ORDER BY r.id_reclamo
    """), {"uid": uid, "ahora": ahora, "mun": cat.id_municipio})
    filas = [f for f in r.fetchall() if not excluir or f.id_reclamo not in excluir]
    out = {"reclamos_sin_ot": len(filas), "ot_creadas": 0, "auditorias_ligadas": 0}
    if not filas:
        return out
    asignador = await _AsignadorOT.cargar(db, cat.id_municipio)
    lote: list[dict] = []
    for f in filas:
        cierre = f.fecha_cierre if f.estado in (ESTADO_RESUELTO, ESTADO_EN_AUDITORIA, ESTADO_AUDITADO,
                                                ESTADO_CANCELADO) else None
        creacion = f.fecha_primer_asignacion
        if cierre is not None and cierre < creacion:
            # Datos viejos con la asignacion registrada despues del cierre: la OT cierra
            # igual con la fecha del reclamo y nace un rato antes.
            creacion = max(f.fecha_alta, cierre - timedelta(hours=1))
        p_ot, _rec = _params_ot(cat, asignador, rnd, f.id_reclamo, f.id_tipo_reclamo, f.estado,
                                creacion, cierre, cierre or creacion, uid,
                                rnd.choice(RESOLUCIONES) if f.estado in ESTADOS_GESTION_CERRADA_OK else None)
        if p_ot:
            lote.append(p_ot)
    out["ot_creadas"] = len(lote)
    out["ot_por_origen"] = dict(asignador.por_origen)
    if not aplicar:
        return out
    sql_sin_returning = text(str(_SQL_INSERT_OT_OPERATIVA).replace("RETURNING id_ot, nro_ot", ""))
    for i in range(0, len(lote), 500):
        await db.execute(sql_sin_returning, lote[i:i + 500])
    r = await db.execute(text("""
        UPDATE ordenes_trabajo a SET id_ot_origen = o.id_ot
          FROM ordenes_trabajo o
         WHERE a.es_auditoria AND a.activo AND a.id_ot_origen IS NULL AND a.id_usuario_alta = :uid
           AND a.id_municipio = :mun
           AND o.id_reclamo = a.id_reclamo AND NOT o.es_auditoria AND o.activo
    """), {"uid": uid, "mun": cat.id_municipio})
    out["auditorias_ligadas"] = r.rowcount or 0
    return out


async def rebalancear_sla_historico(db: AsyncSession, uid: int, aplicar: bool,
                                    ahora: datetime | None = None,
                                    pendientes_desde: datetime | None = None) -> dict:
    """OPT-IN (cerrar_atraso con rebalancear_sla=true; decision de Cesar): los meses
    de reclamos demo generados antes del 2026-10-21 cerraron ~50-58 % dentro del SLA
    (demora sin relacion con el SLA). Para cada mes de alta SIN pendientes cuyo %
    dentro del SLA esta por DEBAJO del 60 %, adelanta el cierre de los reclamos fuera
    de SLA que hagan falta para llevarlo al p del mes (demo_sla.p_mes, el mismo
    objetivo del generador).

    Que se toca de cada reclamo elegido (solo demo, sin subreclamos ni padres de
    subreclamos): fecha_cierre = alta + demora dentro del SLA de su plan, nunca antes
    de su ultimo movimiento previo al cierre; la fila 'Resuelto' del historial y la
    fecha de cierre de su OT operativa acompanan. Encuesta y auditoria quedan donde
    estaban (despues del cierre). Los meses por encima del 85 % no se tocan (atrasar
    un cierre dejaria la encuesta antes del cierre). Idempotente. No commitea.

    `pendientes_desde`: solo los pendientes con alta posterior bloquean un mes (los
    anteriores los cierra el atraso de la misma corrida). En dry-run el % del mes se
    calcula sin esos cierres: el conteo es aproximado."""
    ahora = ahora or datetime.now(timezone.utc)
    id_mun = await municipio_demo(db)
    pendientes_desde = pendientes_desde or datetime(1900, 1, 1, tzinfo=timezone.utc)
    cerrados = "('Resuelto', 'En auditoría', 'Auditado')"
    r = await db.execute(text(f"""
        SELECT to_char(r.fecha_alta AT TIME ZONE 'UTC', 'YYYY-MM') AS mes,
               COUNT(*) FILTER (WHERE r.estado IN {cerrados} AND tr.sla_minutos IS NOT NULL AND r.fecha_cierre IS NOT NULL) AS cerrados,
               COUNT(*) FILTER (WHERE r.estado IN {cerrados} AND tr.sla_minutos IS NOT NULL AND r.fecha_cierre IS NOT NULL
                    AND r.fecha_cierre - r.fecha_alta <= make_interval(mins => tr.sla_minutos)) AS dentro,
               COUNT(*) FILTER (WHERE r.estado IN ('Sin asignar', 'En gestión', 'En espera')
                                  AND r.fecha_alta >= CAST(:pdesde AS timestamptz)) AS pendientes
          FROM reclamos r JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
         WHERE r.activo AND r.id_usuario_alta = :uid AND r.fecha_alta <= CAST(:ahora AS timestamptz)
           AND r.id_municipio = :mun
         GROUP BY 1 ORDER BY 1
    """), {"uid": uid, "ahora": ahora, "pdesde": pendientes_desde, "mun": id_mun})
    meses: dict[str, dict] = {}
    for f in r.fetchall():
        if not f.cerrados or f.pendientes:
            continue
        pct = f.dentro / f.cerrados
        if pct >= demo_sla.P_MIN:
            continue
        p = demo_sla.p_mes("reclamos", int(f.mes[:4]), int(f.mes[5:]))
        meses[f.mes] = {"antes": round(pct * 100, 1), "objetivo": round(p * 100, 1), "cerrados": f.cerrados,
                        "a_mover": max(0, math.ceil(p * f.cerrados) - f.dentro), "movidos": 0}
    out = {"meses": meses, "reclamos_adelantados": 0}
    if not meses:
        return out
    r = await db.execute(text(f"""
        SELECT r.id_reclamo, r.fecha_alta, r.fecha_cierre, tr.sla_minutos / 1440.0 AS sla_dias,
               to_char(r.fecha_alta AT TIME ZONE 'UTC', 'YYYY-MM') AS mes,
               (SELECT MAX(h.fecha_alta) FROM reclamo_historial h WHERE h.id_reclamo = r.id_reclamo
                  AND h.fecha_alta < r.fecha_cierre AND h.estado_nuevo IS DISTINCT FROM 'Resuelto') AS previo
          FROM reclamos r JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
         WHERE r.activo AND r.id_usuario_alta = :uid AND r.estado IN {cerrados} AND r.fecha_cierre IS NOT NULL
           AND tr.sla_minutos IS NOT NULL AND r.id_reclamo_padre IS NULL
           AND NOT EXISTS (SELECT 1 FROM reclamos h WHERE h.id_reclamo_padre = r.id_reclamo)
           AND r.fecha_cierre - r.fecha_alta > make_interval(mins => tr.sla_minutos)
           AND to_char(r.fecha_alta AT TIME ZONE 'UTC', 'YYYY-MM') = ANY(:meses)
           AND r.id_municipio = :mun
         ORDER BY r.id_reclamo
    """), {"uid": uid, "meses": list(meses), "mun": id_mun})
    candidatos = r.fetchall()
    # Primero los que su plan pone dentro del SLA (mismo criterio que el generador).
    candidatos.sort(key=lambda f: (not demo_sla.cae_dentro(
        "reclamos", f.id_reclamo, demo_sla.p_mes("reclamos", f.fecha_alta.year, f.fecha_alta.month)), f.id_reclamo))
    for f in candidatos:
        m = meses[f.mes]
        if m["movidos"] >= m["a_mover"]:
            continue
        rnd = demo_sla.rnd_de("reclamo", f.id_reclamo)
        nuevo = f.fecha_alta + timedelta(days=demo_sla.demora_dentro(rnd, float(f.sla_dias)))
        if f.previo is not None:
            nuevo = max(nuevo, f.previo + timedelta(minutes=5))
        if not demo_sla.dentro_sla_reclamo(f.fecha_alta, nuevo, float(f.sla_dias)) or nuevo >= f.fecha_cierre:
            continue
        m["movidos"] += 1
        out["reclamos_adelantados"] += 1
        if not aplicar:
            continue
        p = {"n": nuevo, "v": f.fecha_cierre, "id": f.id_reclamo}
        await db.execute(text("UPDATE reclamos SET fecha_cierre = :n WHERE id_reclamo = :id"), p)
        await db.execute(text("""
            UPDATE reclamo_historial SET fecha_alta = :n
             WHERE id_reclamo = :id AND estado_nuevo = 'Resuelto' AND fecha_alta = :v
        """), p)
        await db.execute(text("""
            UPDATE ordenes_trabajo SET fecha_cierre = :n
             WHERE id_reclamo = :id AND NOT es_auditoria AND activo AND fecha_cierre = :v
        """), p)
    for m in meses.values():
        m["despues"] = round((m["antes"] / 100 * m["cerrados"] + m["movidos"]) / m["cerrados"] * 100, 1)
    return out


async def cerrar_atraso_reclamos(db: AsyncSession, dias: int = 21, aplicar: bool = False,
                                 incluir_no_demo: bool = False, completar_ot: bool = True,
                                 rebalancear_sla: bool = False,
                                 semilla: int | None = None, ahora: datetime | None = None) -> dict:
    """Cierre del atraso (2026-10-21): los reclamos pendientes (Sin asignar / En
    gestion / En espera) con alta de hace mas de `dias` se cierran con su plan SLA
    (las mismas fechas que les habria dado el generador; si su historial ya va mas
    alla, pegado a su ultimo movimiento) y su OT coherente. Sus subreclamos
    pendientes tambien. Solo datos demo salvo `incluir_no_demo` (los de QA/seed:
    sin encuesta, con nota "cierre de atraso de datos de prueba"). Ningun mail ni
    push (todo SQL). Idempotente: una segunda corrida no encuentra nada.

    Con aplicar=False NO escribe: devuelve los conteos de lo que haria (y la lista
    de reclamos que NO son demo, para revisarla antes de aplicar). Commitea si aplica.
    `completar_ot` agrega la OT operativa que les falta a los reclamos demo ya
    cerrados (los generados antes de esta version no la tenian). `rebalancear_sla`
    (opt-in) lleva los meses viejos que quedaron por debajo del 60 % dentro del SLA
    a su objetivo (ver rebalancear_sla_historico)."""
    rnd = random.Random(semilla)
    ahora = ahora or datetime.now(timezone.utc)
    uid = await _usuario_generador(db, crear=False)
    if uid is None:
        return {"detalle": "sin usuario generador: nada que cerrar"}
    cat = await _cargar_catalogos(db)
    asignador = await _AsignadorOT.cargar(db, cat.id_municipio)
    limite = ahora - timedelta(days=dias)
    filtro_demo = "TRUE" if incluir_no_demo else "r.id_usuario_alta = :uid"
    filtro = (f"({filtro_demo}) AND (r.fecha_alta < CAST(:limite AS timestamptz) OR EXISTS ("
              "SELECT 1 FROM reclamos p WHERE p.id_reclamo = r.id_reclamo_padre "
              "AND p.fecha_alta < CAST(:limite AS timestamptz) AND p.estado IN ('Sin asignar', 'En gestión', 'En espera')))")
    r = await db.execute(text(_SQL_PENDIENTES.format(filtro=filtro)),
                         {"uid": uid, "ahora": ahora, "limite": limite, "mun": cat.id_municipio})
    filas = r.fetchall()
    por_estado: dict[str, int] = {}
    for f in filas:
        clave = f"{f.estado} ({'demo' if f.id_usuario_alta == uid else 'no demo'})"
        por_estado[clave] = por_estado.get(clave, 0) + 1
    res = await _avanzar_reclamos(db, cat, uid, asignador, rnd, ahora, filas,
                                  aplicar=aplicar, forzar_final=True, encuestar=True)
    res["por_estado_actual"] = por_estado
    res["ot_por_origen"] = dict(asignador.por_origen)
    res["no_demo_detalle"] = [
        {"nro": f.nro_reclamo, "estado": f.estado, "alta": f.fecha_alta.date().isoformat()}
        for f in filas if f.id_usuario_alta != uid][:60]
    # El rebalanceo va ANTES de completar las OT: las que se crean toman el cierre nuevo.
    if rebalancear_sla:
        res["rebalanceo_sla"] = await rebalancear_sla_historico(db, uid, aplicar, ahora=ahora,
                                                                pendientes_desde=limite)
    if completar_ot:
        res["ot_historicas"] = await completar_ot_historicas(db, uid, aplicar, ahora=ahora, semilla=semilla,
                                                             excluir={f.id_reclamo for f in filas})
    if aplicar:
        await db.commit()
    return res
