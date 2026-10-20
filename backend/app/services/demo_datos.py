# -*- coding: utf-8 -*-
"""Generador de datos demo para los tableros BI (municipio ficticio San Andres).

Crea reclamos + historial + encuestas CSAT (+ vecinos nuevos si el pool es
chico) con distribuciones derivadas del set de referencia de gestion municipal
(demo_datos_ref.py). Lo consumen:

  - POST /api/v1/demo/poblar (routes/demo_datos.py) — carga inicial por rango
    y refresco semanal via GitHub Actions (X-Dispatcher-Token) o admin JWT.
  - backend/seed_demo_bi.py — driver local.
  - Hermano: app/services/demo_atencion.py (turnos + colero + Guardia + eventos,
    2026-09-19): mismo usuario generador, mismos vecinos demo, mismo endpoint y
    cron (body.modulos). Sus encuestas de turnos las madura avanzar_pendientes.

Disenio PARAMETRIZADO (pre-IT-01 multi-tenant): los catalogos (tipos, subareas,
estados, localidades, plantilla de encuesta) se resuelven por NOMBRE en runtime
contra la DB del entorno — nunca por id, que diverge entre local y prod.
Todo lo insertado queda atribuido al usuario 'generador.demo' (se crea INACTIVO
si no existe): identificar/borrar/migrar a un tenant = filtrar por ese
id_usuario_alta.

ALCANCE MULTI-TENANT (definicion de Cesar 2026-08-30): el generador y su cron
aplican datos SOLO al municipio DEMO (San Andres). Al implementar IT-01 este
modulo debe recibir/derivar el id_municipio del tenant demo y quedar acotado a
el — JAMAS generar datos en tenants reales.

REGLA CRITICA: jamas crear encuesta_envio en estado 'pendiente' — el dispatcher
horario de encuestas MANDA MAIL a los pendientes. Solo estados 'enviada',
'completada' o 'expirada'.
"""
from __future__ import annotations

import logging
import math
import random
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import demo_datos_ref as ref
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
# Auditoria POSTERIOR al cierre (mig 112): un resuelto puede estar 'En auditoria'
# (pendiente del auditor) o 'Auditado'; para encuestas y tiempos sigue siendo un
# resuelto (su fecha_cierre es la del primer cierre).
ESTADOS_GESTION_CERRADA_OK = (ESTADO_RESUELTO, ESTADO_EN_AUDITORIA, ESTADO_AUDITADO)
TASA_AUDITORIA = 0.08      # fraccion de resueltos que la supervision manda a auditar
TASA_OBSERVADA = 0.20      # fraccion de auditorias que terminan observadas (con retrabajo)
OBSERVACIONES_AUDITORIA = [
    "quedó un desnivel en el borde de la reparación",
    "faltó señalizar la zona intervenida",
    "el trabajo no cubre todo el tramo reclamado",
    "la reparación cedió a los pocos días",
    "quedaron restos de material sobre la vereda",
]

CANALES = [("telefono", 40), ("web", 22), ("app_movil", 15), ("presencial", 10),
           ("whatsapp", 8), ("oficio", 3), ("otro", 2)]
PRIORIDADES = [("Media", 70), ("Alta", 15), ("Baja", 15)]
FUENTES_GEO = [("pin_manual", 45), ("geocoding_osm", 35), ("gps_dispositivo", 20)]
# Distribucion de score 1-5 derivada del export de encuestas de referencia
# (Q1: 5=50.5% 4=17.5% 3=6.6% 2=7.4% 1=18.0% de las respondidas).
SCORES = [(5, 505), (4, 175), (3, 66), (2, 74), (1, 180)]

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


@dataclass
class _Catalogos:
    tipos_por_nombre: dict[str, tuple[int, int, str]] = field(default_factory=dict)
    tipos_por_subarea: dict[int, list[int]] = field(default_factory=dict)
    tipo_info: dict[int, tuple[str, int]] = field(default_factory=dict)
    subareas_por_nombre: dict[str, int] = field(default_factory=dict)
    estados_fk: dict[str, int] = field(default_factory=dict)
    # (nombre normalizado, partido normalizado) -> id_localidad
    localidades: dict[tuple[str, str], int] = field(default_factory=dict)
    limite: dict | None = None  # GeoJSON Polygon del municipio (mig 111)
    id_plantilla_reclamos: int | None = None
    # estado_ot para las OT de auditoria demo (mig 112): En gestion = pendiente, Terminada = cerrada.
    id_estado_ot_gestion: int | None = None
    id_estado_ot_terminada: int | None = None
    # Poblacion ponderada de tipos ya resuelta contra el catalogo del entorno:
    # entradas ('tipo', id_tipo) o ('subarea', id_subarea), con su peso.
    poblacion_tipos: list[tuple[tuple[str, int], int]] = field(default_factory=list)
    poblacion_localidades: list[tuple[tuple[int, str, float, float, int], int]] = field(default_factory=list)


async def _cargar_catalogos(db: AsyncSession) -> _Catalogos:
    cat = _Catalogos()
    r = await db.execute(text(
        "SELECT t.id_tipo_reclamo, t.nombre, t.id_subarea FROM tipo_reclamo t "
        "JOIN subarea s ON s.id_subarea = t.id_subarea WHERE t.activo AND s.activo"
    ))
    for fila in r.fetchall():
        cat.tipos_por_nombre[_norm(fila.nombre)] = (fila.id_tipo_reclamo, fila.id_subarea, fila.nombre)
        cat.tipos_por_subarea.setdefault(fila.id_subarea, []).append(fila.id_tipo_reclamo)
        cat.tipo_info[fila.id_tipo_reclamo] = (fila.nombre, fila.id_subarea)

    r = await db.execute(text("SELECT id_subarea, nombre FROM subarea WHERE activo"))
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
    cat.limite = await leer_limite(db)

    r = await db.execute(text(
        "SELECT id_encuesta_plantilla FROM encuesta_plantilla "
        "WHERE tipo = 'reclamos' AND activo ORDER BY id_encuesta_plantilla LIMIT 1"
    ))
    fila = r.fetchone()
    cat.id_plantilla_reclamos = fila.id_encuesta_plantilla if fila else None

    r = await db.execute(text("SELECT id_estado_ot, nombre FROM estado_ot WHERE activo AND nombre IN ('En gestión', 'Terminada')"))
    for fila in r.fetchall():
        if fila.nombre == "Terminada":
            cat.id_estado_ot_terminada = fila.id_estado_ot
        else:
            cat.id_estado_ot_gestion = fila.id_estado_ot

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
    r = await db.execute(text("SELECT id_usuario FROM usuarios WHERE username = :u"),
                         {"u": USERNAME_GENERADOR})
    fila = r.fetchone()
    if fila:
        return fila.id_usuario
    if not crear:
        return None
    from app.core.auth import hash_password
    import secrets as stdlib_secrets
    # id_municipio y buc_acceso son NOT NULL sin default en local (drift §24).
    r = await db.execute(text("""
        INSERT INTO usuarios (nombre, username, password_hash, nivel_acceso, activo,
                              buc_acceso, email, id_municipio)
        VALUES ('Generador de datos demo', :u, :h, 5, FALSE, FALSE, :e,
                (SELECT MIN(id_municipio) FROM usuarios WHERE id_municipio IS NOT NULL))
        RETURNING id_usuario
    """), {"u": USERNAME_GENERADOR, "h": hash_password(stdlib_secrets.token_urlsafe(24)),
           "e": EMAIL_GENERADOR})
    return r.fetchone().id_usuario


async def _asegurar_vecinos(db: AsyncSession, cat: _Catalogos, uid: int,
                            objetivo_nuevos: int, rnd: random.Random) -> list[tuple[int, str]]:
    """Devuelve el pool [(id_ciudadano, email)] creando vecinos demo si faltan.

    Los nombres se RECOMBINAN (apellido de una fila del set de referencia,
    nombre de otra): nunca se reproduce un par real. DNI/CUIL sinteticos.
    """
    ya_demo = (await db.execute(text(
        "SELECT COUNT(*) AS n FROM ciudadanos WHERE email LIKE :d"),
        {"d": f"%@{DOMINIO_VECINO_DEMO}"})).fetchone().n
    a_crear = max(0, objetivo_nuevos - ya_demo)

    if a_crear:
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
                "uid": uid,
            })
        # ren_chk/email_chk/emp_chk/activo: NOT NULL sin default en local (drift §24).
        await db.execute(text("""
            INSERT INTO ciudadanos
                (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                 id_nacionalidad, calle, altura, localidad, provincia,
                 latitud, longitud, telefono, email, fecha_alta, id_usuario_alta,
                 ren_chk, email_chk, emp_chk, activo)
            VALUES (:doc_tipo, :doc_nro, :cuil, :nombre, :apellido, :sexo, :fecha_nac,
                    :id_nacionalidad, :calle, :altura, :localidad, :provincia,
                    :latitud, :longitud, :telefono, :email, :fecha_alta, :uid,
                    FALSE, FALSE, FALSE, TRUE)
        """), filas)

    r = await db.execute(text(
        "SELECT id_ciudadano, email FROM ciudadanos WHERE activo AND email LIKE '%@%'"))
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


def _armar_reclamo(rnd: random.Random, cat: _Catalogos, pool: list[tuple[int, str]],
                   desde: date, dias: int, ahora: datetime) -> dict:
    id_tipo = _resolver_tipo(rnd, cat)
    tipo_nombre, id_subarea = cat.tipo_info[id_tipo]
    id_loc, loc_nombre, lat0, lon0, radio = _elegir_localidad(rnd, cat)
    lat, lon = _ubicar(rnd, cat, lat0, lon0, radio)

    dia = desde + timedelta(days=rnd.randrange(dias))
    # Horario comercial AR (UTC-3) con algo de dispersion: 11-21 UTC.
    fecha_alta = datetime(dia.year, dia.month, dia.day,
                          rnd.randint(11, 21), rnd.randint(0, 59), rnd.randint(0, 59),
                          tzinfo=timezone.utc)

    canal = _elegir(rnd, CANALES)
    fuente = "gps_dispositivo" if canal == "app_movil" else _elegir(rnd, FUENTES_GEO)
    direccion = f"{rnd.choice(CALLES)} {rnd.randint(100, 5900)}, {loc_nombre}"
    frase = rnd.choice(FRASES).format(tipo=tipo_nombre, tipo_lower=tipo_nombre[0].lower() + tipo_nombre[1:],
                                      dir=direccion) + rnd.choice(COLETILLAS)

    # Demora de resolucion: lognormal mediana ~3 dias, p90 ~14 (set de referencia);
    # un 3% queda "trabado" con demoras varias veces mayores (cola larga real).
    demora_dias = min(rnd.lognormvariate(math.log(3), 1.15), 60.0)
    if rnd.random() < 0.03:
        demora_dias = min(demora_dias * 8, 140.0)
    cierre = fecha_alta + timedelta(days=demora_dias, hours=rnd.uniform(0, 10))

    id_ciudadano, email = rnd.choice(pool)
    edad_dias = (ahora - fecha_alta).days

    reclamo = {
        "id_tipo_reclamo": id_tipo, "id_subarea": id_subarea,
        "id_ciudadano": id_ciudadano, "email": email,
        "id_localidad": id_loc, "localidad_nombre": loc_nombre,
        "latitud": lat, "longitud": lon, "direccion": direccion,
        "descripcion": frase,
        "prioridad": _elegir(rnd, PRIORIDADES),
        "canal_origen": canal, "fuente_geolocalizacion": fuente,
        "fecha_alta": fecha_alta,
        "fecha_primer_asignacion": None, "fecha_cierre": None,
        "auditoria": False, "subreclamo": False,
        "fecha_inicio_auditoria": None, "fecha_fin_auditoria": None,
        "resultado_auditoria": None, "id_reclamo_origen_auditoria": None,
    }

    if cierre <= ahora:
        # Cerrado: 96% Resuelto, 4% Cancelado. Auditoria POSTERIOR al cierre (mig
        # 112): ~8% de los resueltos la supervision los manda a auditar 1-10 dias
        # despues del cierre y el auditor cierra 1-7 dias mas tarde (80% aprobada /
        # 20% observada, que genera un reclamo de retrabajo). fecha_cierre no cambia.
        if rnd.random() < 0.96:
            reclamo["estado"] = ESTADO_RESUELTO
            if rnd.random() < TASA_AUDITORIA:
                inicio = cierre + timedelta(days=rnd.uniform(1, 10))
                if inicio <= ahora:
                    reclamo["auditoria"] = True
                    reclamo["fecha_inicio_auditoria"] = inicio
                    fin = inicio + timedelta(days=rnd.uniform(1, 7))
                    if fin <= ahora:
                        reclamo["estado"] = ESTADO_AUDITADO
                        reclamo["fecha_fin_auditoria"] = fin
                        reclamo["resultado_auditoria"] = "observado" if rnd.random() < TASA_OBSERVADA else "aprobado"
                    else:
                        reclamo["estado"] = ESTADO_EN_AUDITORIA
        else:
            reclamo["estado"] = ESTADO_CANCELADO
        reclamo["fecha_cierre"] = cierre
        if reclamo["estado"] != ESTADO_CANCELADO or rnd.random() < 0.5:
            reclamo["fecha_primer_asignacion"] = fecha_alta + timedelta(days=demora_dias * rnd.uniform(0.1, 0.4))
        reclamo["subreclamo"] = demora_dias >= 4 and rnd.random() < 0.04
    else:
        if edad_dias < 4:
            estado = _elegir(rnd, [(ESTADO_SIN_ASIGNAR, 55), (ESTADO_EN_GESTION, 40), (ESTADO_EN_ESPERA, 5)])
        elif edad_dias < 14:
            estado = _elegir(rnd, [(ESTADO_SIN_ASIGNAR, 25), (ESTADO_EN_GESTION, 60), (ESTADO_EN_ESPERA, 15)])
        else:
            estado = _elegir(rnd, [(ESTADO_SIN_ASIGNAR, 15), (ESTADO_EN_GESTION, 60), (ESTADO_EN_ESPERA, 25)])
        reclamo["subreclamo"] = rnd.random() < 0.04
        if reclamo["subreclamo"]:
            estado = ESTADO_EN_ESPERA
        reclamo["estado"] = estado
        if estado != ESTADO_SIN_ASIGNAR:
            reclamo["fecha_primer_asignacion"] = fecha_alta + timedelta(
                hours=rnd.uniform(2, 72 if edad_dias > 3 else max(4, edad_dias * 24)))
    return reclamo


def _armar_retrabajo(rnd: random.Random, rec: dict, id_origen: int, nro_origen: str | None,
                     ahora: datetime) -> dict:
    """Reclamo NUEVO de retrabajo que nace de una auditoria observada (mig 112):
    mismo vecino/tipo/direccion/geo, canal 'oficio', alta = cierre de la
    auditoria. Su estado depende de la edad (puede estar ya resuelto)."""
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


_SQL_INSERT_RECLAMO = text("""
    INSERT INTO reclamos
        (id_ciudadano, id_tipo_reclamo, descripcion, prioridad, estado, id_estado_fk,
         direccion, latitud, longitud, id_localidad, canal_origen,
         fuente_geolocalizacion, fecha_alta, fecha_modificacion,
         fecha_primer_asignacion, fecha_cierre, id_usuario_alta, id_reclamo_padre,
         observaciones, fecha_inicio_auditoria, fecha_fin_auditoria, resultado_auditoria,
         id_reclamo_origen_auditoria)
    VALUES (:id_ciudadano, :id_tipo_reclamo, :descripcion, :prioridad, :estado, :id_estado_fk,
            :direccion, :latitud, :longitud, :id_localidad, :canal_origen,
            :fuente_geolocalizacion, :fecha_alta, :fecha_alta,
            :fecha_primer_asignacion, :fecha_cierre, :uid, :id_reclamo_padre,
            NULL, :fecha_inicio_auditoria, :fecha_fin_auditoria, :resultado_auditoria,
            :id_reclamo_origen_auditoria)
    RETURNING id_reclamo, nro_reclamo
""")

# OT de auditoria (mig 112): pendiente = En gestion sin cierre; cerrada = Terminada con resultado.
_SQL_INSERT_OT_AUDITORIA = text("""
    INSERT INTO ordenes_trabajo
        (id_reclamo, id_estado, es_auditoria, resultado_auditoria, observaciones,
         observaciones_auditoria, id_supervisor_asigna, fecha_creacion, fecha_cierre,
         activo, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
    VALUES (:id_reclamo, :id_estado, TRUE, :resultado, 'Control de calidad (demo)',
            :obs_aud, :uid, CAST(:inicio AS timestamptz), CAST(:fin AS timestamptz),
            TRUE, CAST(:inicio AS timestamptz),
            COALESCE(CAST(:fin AS timestamptz), CAST(:inicio AS timestamptz)), :uid, :uid)
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
    INSERT INTO reclamo_historial (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
    VALUES (:id_reclamo, :accion, :estado_anterior, :estado_nuevo, :nota, :fecha, :uid)
""")

_SQL_INSERT_ENVIO = text("""
    INSERT INTO encuesta_envio
        (id_plantilla, id_ciudadano, id_reclamo, email_destino_snapshot,
         fecha_envio, fecha_apertura, fecha_completada, fecha_expiracion,
         estado, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta)
    VALUES (:id_plantilla, :id_ciudadano, :id_reclamo, :email,
            :fecha_envio, :fecha_apertura, :fecha_completada, :fecha_expiracion,
            :estado, :id_subarea, :fecha_envio, :fecha_envio, :uid)
    RETURNING id_encuesta_envio
""")

_SQL_INSERT_RESPUESTA = text("""
    INSERT INTO encuesta_respuesta
        (id_envio, clasificacion_inicial, rama_seguida, tiempo_completado_seg,
         solicita_contacto, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta)
    VALUES (:id_envio, :clasificacion, :rama, :tiempo, FALSE, :id_subarea, :fecha, :fecha, :uid)
""")


def _historial_de(reclamo: dict, id_reclamo: int, uid: int, rnd: random.Random,
                  es_subreclamo: bool) -> list[dict]:
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
            filas.append({"id_reclamo": id_reclamo, "accion": "Enviado a auditoría",
                          "estado_anterior": ESTADO_RESUELTO, "estado_nuevo": ESTADO_EN_AUDITORIA,
                          "nota": "Control de calidad (demo)", "fecha": reclamo["fecha_inicio_auditoria"], "uid": uid})
            if reclamo.get("fecha_fin_auditoria"):
                aprobada = reclamo.get("resultado_auditoria") == "aprobado"
                filas.append({"id_reclamo": id_reclamo,
                              "accion": "Auditoría aprobada" if aprobada else "Auditoría observada",
                              "estado_anterior": ESTADO_EN_AUDITORIA, "estado_nuevo": ESTADO_AUDITADO,
                              "nota": "Trabajo verificado por el auditor" if aprobada else "Se generó un reclamo de retrabajo",
                              "fecha": reclamo["fecha_fin_auditoria"], "uid": uid})
    elif estado == ESTADO_CANCELADO:
        filas.append({"id_reclamo": id_reclamo, "accion": "Reclamo cancelado",
                      "estado_anterior": ESTADO_EN_GESTION if asig else ESTADO_SIN_ASIGNAR,
                      "estado_nuevo": ESTADO_CANCELADO, "nota": "Cancelado (demo)",
                      "fecha": cierre, "uid": uid})
    return filas


def _armar_envio(rnd: random.Random, reclamo: dict, ahora: datetime,
                 id_plantilla: int, uid: int) -> tuple[dict, dict | None] | None:
    """Envio de encuesta para un reclamo RESUELTO (o None). Nunca 'pendiente'."""
    if rnd.random() > 0.85:
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


async def generar_periodo(db: AsyncSession, desde: date, hasta: date,
                          min_mensual: int = 300, max_mensual: int = 500,
                          vecinos_nuevos: int = 250,
                          semilla: int | None = None) -> dict:
    """Genera reclamos demo (con historial y encuestas) en [desde, hasta].

    El volumen se sortea en [min_mensual, max_mensual] y se escala por la
    fraccion de mes que cubre el rango. Commitea al final.
    """
    rnd = random.Random(semilla)
    ahora = datetime.now(timezone.utc)
    uid = await _usuario_generador(db)
    cat = await _cargar_catalogos(db)
    if not cat.poblacion_tipos or not cat.poblacion_localidades:
        raise RuntimeError("Catalogo sin tipos/localidades matcheables: no se puede generar demo")
    pool = await _asegurar_vecinos(db, cat, uid, vecinos_nuevos, rnd)

    dias = (hasta - desde).days + 1
    objetivo = max(1, round(rnd.randint(min_mensual, max_mensual) * dias / 30.44))

    reclamos = [_armar_reclamo(rnd, cat, pool, desde, dias, ahora) for _ in range(objetivo)]
    reclamos.sort(key=lambda x: x["fecha_alta"])  # nro_reclamo correlativo a la fecha

    historial: list[dict] = []
    respuestas: list[dict] = []
    n_sub = n_envios = n_auditorias = n_retrabajos = 0
    por_estado: dict[str, int] = {}

    async def _insertar(rec: dict, id_padre: int | None, es_sub: bool) -> int:
        fila = (await db.execute(_SQL_INSERT_RECLAMO, {
            "id_ciudadano": rec["id_ciudadano"], "id_tipo_reclamo": rec["id_tipo_reclamo"],
            "descripcion": rec["descripcion"], "prioridad": rec["prioridad"],
            "estado": rec["estado"], "id_estado_fk": cat.estados_fk.get(rec["estado"]),
            "direccion": rec["direccion"], "latitud": rec["latitud"], "longitud": rec["longitud"],
            "id_localidad": rec["id_localidad"], "canal_origen": rec["canal_origen"],
            "fuente_geolocalizacion": rec["fuente_geolocalizacion"],
            "fecha_alta": rec["fecha_alta"],
            "fecha_primer_asignacion": rec["fecha_primer_asignacion"],
            "fecha_cierre": rec["fecha_cierre"], "uid": uid, "id_reclamo_padre": id_padre,
            "fecha_inicio_auditoria": rec.get("fecha_inicio_auditoria"),
            "fecha_fin_auditoria": rec.get("fecha_fin_auditoria"),
            "resultado_auditoria": rec.get("resultado_auditoria"),
            "id_reclamo_origen_auditoria": rec.get("id_reclamo_origen_auditoria"),
        })).fetchone()
        rec["_nro"] = fila.nro_reclamo
        historial.extend(_historial_de(rec, fila.id_reclamo, uid, rnd, es_sub))
        return fila.id_reclamo

    async def _insertar_ot_auditoria(rec: dict, id_reclamo: int) -> None:
        """OT es_auditoria espejo de la auditoria del reclamo (mig 112)."""
        cerrada = rec.get("fecha_fin_auditoria") is not None
        id_estado = cat.id_estado_ot_terminada if cerrada else cat.id_estado_ot_gestion
        if id_estado is None:
            return
        resultado = None
        if cerrada:
            resultado = "aprobada" if rec.get("resultado_auditoria") == "aprobado" else "observada"
        await db.execute(_SQL_INSERT_OT_AUDITORIA, {
            "id_reclamo": id_reclamo, "id_estado": id_estado, "resultado": resultado,
            "obs_aud": ("Trabajo verificado" if resultado == "aprobada"
                        else rnd.choice(OBSERVACIONES_AUDITORIA) if resultado else None),
            "uid": uid, "inicio": rec["fecha_inicio_auditoria"], "fin": rec.get("fecha_fin_auditoria"),
        })

    for rec in reclamos:
        id_reclamo = await _insertar(rec, None, False)
        por_estado[rec["estado"]] = por_estado.get(rec["estado"], 0) + 1

        if rec["subreclamo"]:
            hijo = dict(rec)
            hijo["id_tipo_reclamo"] = _resolver_tipo(rnd, cat)
            hijo["descripcion"] = f"Subreclamo derivado: {cat.tipo_info[hijo['id_tipo_reclamo']][0]}. {rec['direccion']}."
            nombre_h, sub_h = cat.tipo_info[hijo["id_tipo_reclamo"]]
            hijo["id_subarea"] = sub_h
            hijo["fecha_alta"] = min(rec["fecha_alta"] + timedelta(hours=rnd.uniform(4, 48)),
                                     ahora - timedelta(hours=1))
            hijo["subreclamo"] = False
            hijo["fecha_primer_asignacion"] = min(
                hijo["fecha_alta"] + timedelta(hours=rnd.uniform(1, 24)), ahora)
            if rec["fecha_cierre"]:
                hijo["fecha_cierre"] = rec["fecha_cierre"] - timedelta(hours=rnd.uniform(1, 12))
                if hijo["fecha_cierre"] <= hijo["fecha_alta"]:
                    hijo["fecha_cierre"] = min(hijo["fecha_alta"] + timedelta(hours=2), ahora)
                hijo["estado"] = ESTADO_RESUELTO
                hijo["auditoria"] = False
            else:
                hijo["estado"] = ESTADO_EN_GESTION
                hijo["fecha_cierre"] = None
            await _insertar(hijo, id_reclamo, True)
            n_sub += 1

        # Auditoria posterior (mig 112): OT de auditoria + retrabajo si fue observada.
        if rec["auditoria"]:
            await _insertar_ot_auditoria(rec, id_reclamo)
            n_auditorias += 1
            if rec.get("resultado_auditoria") == "observado":
                retrabajo = _armar_retrabajo(rnd, rec, id_reclamo, rec.get("_nro"), ahora)
                await _insertar(retrabajo, None, False)
                por_estado[retrabajo["estado"]] = por_estado.get(retrabajo["estado"], 0) + 1
                n_retrabajos += 1

        # La encuesta se dispara en el PRIMER cierre: un reclamo auditado tambien la tuvo.
        if rec["estado"] in ESTADOS_GESTION_CERRADA_OK and cat.id_plantilla_reclamos:
            par = _armar_envio(rnd, rec, ahora, cat.id_plantilla_reclamos, uid)
            if par:
                envio, respuesta = par
                envio["id_reclamo"] = id_reclamo
                fila = (await db.execute(_SQL_INSERT_ENVIO, envio)).fetchone()
                n_envios += 1
                if respuesta:
                    respuesta["id_envio"] = fila.id_encuesta_envio
                    respuestas.append(respuesta)

    if historial:
        await db.execute(_SQL_INSERT_HISTORIAL, historial)
    if respuestas:
        await db.execute(_SQL_INSERT_RESPUESTA, respuestas)
    await db.commit()

    return {"reclamos": len(reclamos), "subreclamos": n_sub, "por_estado": por_estado,
            "auditorias": n_auditorias, "retrabajos": n_retrabajos,
            "encuestas_enviadas": n_envios, "encuestas_respondidas": len(respuestas),
            "pool_vecinos": len(pool), "desde": str(desde), "hasta": str(hasta)}


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
        ORDER BY r.id_reclamo
    """), {"uid": uid})
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
            })).fetchone()
            historial.extend(_historial_de(retrabajo, fila.id_reclamo, uid, rnd, False))

    if aplicar and historial:
        await db.execute(_SQL_INSERT_HISTORIAL, historial)
    return conteo


async def avanzar_pendientes(db: AsyncSession, semilla: int | None = None) -> dict:
    """Envejece SOLO los datos demo (atribuidos al usuario generador): asigna,
    resuelve, cancela y madura encuestas. Pensado para el cron semanal."""
    rnd = random.Random(semilla)
    ahora = datetime.now(timezone.utc)
    uid = await _usuario_generador(db, crear=False)
    if uid is None:
        return {"detalle": "sin usuario generador: nada que avanzar"}
    cat = await _cargar_catalogos(db)

    r = await db.execute(text("""
        SELECT r.id_reclamo, r.estado, r.fecha_alta, r.id_ciudadano, r.id_tipo_reclamo,
               r.fecha_primer_asignacion, r.id_reclamo_origen_auditoria, c.email
        FROM reclamos r JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        WHERE r.activo AND r.id_usuario_alta = :uid
          AND r.estado IN ('Sin asignar', 'En gestión', 'En espera')
          AND NOT EXISTS (SELECT 1 FROM reclamos h WHERE h.id_reclamo_padre = r.id_reclamo
                          AND h.activo AND h.estado NOT IN ('Resuelto', 'Cancelado', 'En auditoría', 'Auditado'))
    """), {"uid": uid})
    pendientes = r.fetchall()

    historial: list[dict] = []
    respuestas: list[dict] = []
    movidos = {"a_gestion": 0, "a_resuelto": 0, "a_cancelado": 0, "a_espera": 0}

    async def _update(id_reclamo: int, estado: str, asig, cierre) -> None:
        await db.execute(text("""
            UPDATE reclamos SET estado = :estado, id_estado_fk = :fk,
                   fecha_primer_asignacion = COALESCE(fecha_primer_asignacion, :asig),
                   fecha_cierre = :cierre, fecha_modificacion = :ahora,
                   id_usuario_modificacion = :uid
            WHERE id_reclamo = :id
        """), {"estado": estado, "fk": cat.estados_fk.get(estado), "asig": asig,
               "cierre": cierre, "ahora": ahora, "uid": uid, "id": id_reclamo})

    for p in pendientes:
        azar = rnd.random()
        piso = p.fecha_alta + timedelta(hours=1)  # nada puede pasar antes del alta
        if p.estado == ESTADO_SIN_ASIGNAR:
            if azar < 0.45:
                asig = max(ahora - timedelta(hours=rnd.uniform(1, 96)), piso)
                await _update(p.id_reclamo, ESTADO_EN_GESTION, asig, None)
                historial.append({"id_reclamo": p.id_reclamo, "accion": f"Cambio de estado a {ESTADO_EN_GESTION}",
                                  "estado_anterior": ESTADO_SIN_ASIGNAR, "estado_nuevo": ESTADO_EN_GESTION,
                                  "nota": None, "fecha": asig, "uid": uid})
                movidos["a_gestion"] += 1
            elif azar < 0.49:
                cierre = max(ahora - timedelta(hours=rnd.uniform(0, 48)), piso)
                await _update(p.id_reclamo, ESTADO_CANCELADO, None, cierre)
                historial.append({"id_reclamo": p.id_reclamo, "accion": "Reclamo cancelado",
                                  "estado_anterior": ESTADO_SIN_ASIGNAR, "estado_nuevo": ESTADO_CANCELADO,
                                  "nota": "Cancelado (demo)", "fecha": cierre, "uid": uid})
                movidos["a_cancelado"] += 1
        elif p.estado == ESTADO_EN_GESTION:
            if azar < 0.40:
                cierre = max(ahora - timedelta(hours=rnd.uniform(0, 72)), piso)
                await _update(p.id_reclamo, ESTADO_RESUELTO, None, cierre)
                historial.append({"id_reclamo": p.id_reclamo, "accion": f"Cambio de estado a {ESTADO_RESUELTO}",
                                  "estado_anterior": ESTADO_EN_GESTION, "estado_nuevo": ESTADO_RESUELTO,
                                  "nota": None, "fecha": cierre, "uid": uid})
                movidos["a_resuelto"] += 1
                # Un retrabajo de auditoria (mig 112) es interno: el vecino no lo ve ni se lo encuesta.
                if cat.id_plantilla_reclamos and p.id_reclamo_origen_auditoria is None and rnd.random() < 0.85:
                    fecha_envio = min(cierre + timedelta(days=1), ahora - timedelta(minutes=5))
                    envio = {"id_plantilla": cat.id_plantilla_reclamos, "id_ciudadano": p.id_ciudadano,
                             "id_reclamo": p.id_reclamo, "email": p.email,
                             "fecha_envio": fecha_envio, "fecha_apertura": None, "fecha_completada": None,
                             "fecha_expiracion": fecha_envio + timedelta(days=15),
                             "estado": "enviada", "id_subarea": cat.tipo_info[p.id_tipo_reclamo][1],
                             "uid": uid}
                    await db.execute(_SQL_INSERT_ENVIO, envio)
            elif azar < 0.45:
                await _update(p.id_reclamo, ESTADO_EN_ESPERA, None, None)
                historial.append({"id_reclamo": p.id_reclamo, "accion": f"Cambio de estado a {ESTADO_EN_ESPERA}",
                                  "estado_anterior": ESTADO_EN_GESTION, "estado_nuevo": ESTADO_EN_ESPERA,
                                  "nota": None, "fecha": ahora, "uid": uid})
                movidos["a_espera"] += 1
        else:  # En espera
            if azar < 0.30:
                await _update(p.id_reclamo, ESTADO_EN_GESTION, p.fecha_primer_asignacion or ahora, None)
                historial.append({"id_reclamo": p.id_reclamo, "accion": f"Cambio de estado a {ESTADO_EN_GESTION}",
                                  "estado_anterior": ESTADO_EN_ESPERA, "estado_nuevo": ESTADO_EN_GESTION,
                                  "nota": None, "fecha": ahora, "uid": uid})
                movidos["a_gestion"] += 1

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
              AND r.fecha_inicio_auditoria < :limite
        """), {"uid": uid, "limite": ahora - timedelta(days=1)})
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
            SELECT r.id_reclamo, r.fecha_cierre FROM reclamos r
            WHERE r.activo AND r.id_usuario_alta = :uid AND r.estado = 'Resuelto'
              AND r.fecha_inicio_auditoria IS NULL AND r.id_reclamo_origen_auditoria IS NULL
              AND r.fecha_cierre > :desde
        """), {"uid": uid, "desde": ahora - timedelta(days=30)})
        for p in r.fetchall():
            if rnd.random() >= 0.03:
                continue
            inicio = min(max(ahora - timedelta(hours=rnd.uniform(0, 72)), p.fecha_cierre + timedelta(hours=1)), ahora)
            await db.execute(_SQL_ENVIAR_AUDITORIA, {
                "id": p.id_reclamo, "fk": cat.estados_fk.get(ESTADO_EN_AUDITORIA), "inicio": inicio, "uid": uid})
            await db.execute(_SQL_INSERT_OT_AUDITORIA, {
                "id_reclamo": p.id_reclamo, "id_estado": cat.id_estado_ot_gestion, "resultado": None,
                "obs_aud": None, "uid": uid, "inicio": inicio, "fin": None})
            historial.append({"id_reclamo": p.id_reclamo, "accion": "Enviado a auditoría",
                              "estado_anterior": ESTADO_RESUELTO, "estado_nuevo": ESTADO_EN_AUDITORIA,
                              "nota": "Control de calidad (demo)", "fecha": inicio, "uid": uid})
            movidos["a_auditoria"] += 1

    # Maduracion de encuestas demo: expirar vencidas y responder ~35% de las vivas.
    await db.execute(text("""
        UPDATE encuesta_envio SET estado = 'expirada', fecha_modificacion = :ahora
        WHERE estado = 'enviada' AND fecha_expiracion < :ahora AND id_usuario_alta = :uid
    """), {"ahora": ahora, "uid": uid})
    r = await db.execute(text("""
        SELECT ev.id_encuesta_envio, ev.id_subarea, ev.fecha_envio
        FROM encuesta_envio ev
        WHERE ev.estado = 'enviada' AND ev.id_usuario_alta = :uid
    """), {"uid": uid})
    n_resp = 0
    for ev in r.fetchall():
        if rnd.random() < 0.35:
            apertura = ev.fecha_envio + timedelta(hours=rnd.uniform(1, 96))
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
