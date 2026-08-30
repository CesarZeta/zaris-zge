"""
ZARIS API — FastAPI Application Entry Point.
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.auth import router as auth_router
from app.api.routes.buc import router as buc_router
from app.api.routes.agenda_v2 import router as agenda_v2_router
from app.api.routes.agenda_publico import router as agenda_publico_router
from app.api.routes.agenda_espacios import router as agenda_espacios_router
from app.api.routes.agenda_disponibilidad import router as agenda_disponibilidad_router
from app.api.routes.agenda_novedades import router as agenda_novedades_router
from app.api.routes.turnos import router as turnos_router
from app.api.routes.turnos_publico import router as turnos_publico_router
from app.api.routes.admin_tablas import router as admin_tablas_router
from app.api.routes.admin_permisos import router as admin_permisos_router
from app.api.routes.reclamos import router as reclamos_router
from app.api.routes.bi import router as bi_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.reclamo_adjuntos import router as reclamo_adjuntos_router
from app.api.routes.ordenes_trabajo import router as ot_router
from app.api.routes.ot_adjuntos import router as ot_adjuntos_router
from app.api.routes.geo import router as geo_router
from app.api.routes.activos import router as activos_router
from app.api.routes.config_identidad import router as config_identidad_router
from app.api.routes.emergencias import router as emergencias_router
from app.api.routes.tramites import router as tramites_router
from app.api.routes.tramites_admin import router as tramites_admin_router
from app.api.routes.tramites_mantenimiento import router as tramites_mantenimiento_router
from app.api.routes.usuarios_mantenimiento import router as usuarios_mantenimiento_router
from app.api.routes.encuestas_admin import router as encuestas_admin_router
from app.api.routes.encuestas_admin import dispatcher_router as encuestas_dispatcher_router
from app.api.routes.encuestas_publico import router as encuestas_publico_router
from app.api.routes.notificaciones import router as notificaciones_router
from app.api.routes.publico_auth import router as publico_auth_router
from app.api.routes.publico_alta import router as publico_alta_router
from app.api.routes.publico_identidad import router as publico_identidad_router
from app.api.routes.publico_reclamos import router as publico_reclamos_router
from app.api.routes.publico_reclamos_adjuntos import router as publico_reclamos_adjuntos_router
from app.api.routes.publico_portal import router as publico_portal_router
from app.api.routes.publico_turnos_vecino import router as publico_turnos_vecino_router
from app.api.routes.publico_entradas_vecino import router as publico_entradas_vecino_router
from app.api.routes.publico_emergencias import router as publico_emergencias_router
from app.api.routes.publico_push import router as publico_push_router
from app.api.routes.publico_perfil import router as publico_perfil_router
from app.api.routes.publico_avisos import router as publico_avisos_router
from app.init_db import create_tables

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("zaris")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hook: startup/shutdown."""
    logger.info(f"Iniciando {settings.PROJECT_NAME}")
    await create_tables()
    yield
    logger.info("Cerrando aplicación")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="API para ZARIS Gestion Estatal - Modulo BUC",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8080",
        "http://localhost:8090",
        "https://cesarzeta.github.io",
        "http://zge.zaris.com.ar",
        "https://zge.zaris.com.ar",
        # App Vecinos (PWA en Vercel)
        "http://vecinos.zaris.com.ar",
        "https://vecinos.zaris.com.ar",
        "https://zaris-vecinos.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Rutas
app.include_router(auth_router)
app.include_router(buc_router)
# usuarios_mantenimiento: /usuarios/mantenimiento/integridad-cuentas (cron, sin JWT)
app.include_router(usuarios_mantenimiento_router)
app.include_router(agenda_v2_router)
app.include_router(agenda_publico_router)
# Orden: los routers especificos (/agenda/espacios, /agenda/disponibilidad)
# DESPUES del general /agenda. FastAPI matchea por orden de registro y
# /agenda/{path} no es greedy, asi que el orden es indiferente aca — pero
# mantenemos especificos despues por convencion.
app.include_router(agenda_espacios_router)
app.include_router(agenda_disponibilidad_router)
app.include_router(agenda_novedades_router)
# turnos_publico ANTES de turnos: /turnos/publico/* lo atraparia /turnos/{id_turno} (int) -> 422
app.include_router(turnos_publico_router)
app.include_router(turnos_router)
# tramites_mantenimiento: /tramites/mantenimiento/ejecutar (segmento fijo, sin
# guard JWT — auth por X-Dispatcher-Token). DEBE ir ANTES de tramites_router o
# el /{numero_o_id} greedy lo atrapa como numero_o_id='mantenimiento' (S5).
app.include_router(tramites_mantenimiento_router)
# tramites_router ANTES de admin_tablas (que tiene /{tabla} greedy).
# /tramites/* no colisiona con otros routers pero lo dejamos arriba por convención.
app.include_router(tramites_router)
# tramites_admin: CRUD del catalogo de tipos. Prefix /api/v1/admin/tramites.
# DEBE ir ANTES de admin_tablas_router (/api/v1/admin/{tabla} greedy lo atraparia).
app.include_router(tramites_admin_router)
# encuestas_admin: prefix /api/v1/admin/encuestas. ANTES de admin_tablas_router
# (/api/v1/admin/{tabla} greedy atraparia /admin/encuestas como {tabla}='encuestas').
app.include_router(encuestas_admin_router)
# dispatcher: mismo prefix pero router sin guard JWT (auth por X-Dispatcher-Token).
# Tambien ANTES de admin_tablas_router por el /{tabla} greedy.
app.include_router(encuestas_dispatcher_router)
app.include_router(notificaciones_router)
# IMPORTANTE: admin_permisos_router debe registrarse ANTES de admin_tablas_router.
# admin_tablas usa /api/v1/admin/{tabla} y /api/v1/admin/{tabla}/{id}, que sin un
# orden explicito atrapan rutas como /api/v1/admin/permisos/* como si {tabla}='permisos'.
app.include_router(admin_permisos_router)
app.include_router(admin_tablas_router, prefix="/api/v1/admin")
app.include_router(reclamos_router)
# BI: /api/v1/bi/* (agregaciones de analisis). No colisiona con otros prefijos.
app.include_router(bi_router)
# Dashboard home: /api/v1/dashboard/resumen (conteos + capas geo). Prefijo propio.
app.include_router(dashboard_router)
app.include_router(reclamo_adjuntos_router)
# ot_adjuntos ANTES de ot_router: /ot/{id_ot}/adjuntos no debe ser atrapado por
# el /{id_ot} greedy del router de OT (mismo quirk §5 de orden de routers).
app.include_router(ot_adjuntos_router)
app.include_router(ot_router)
app.include_router(geo_router)
app.include_router(activos_router)
app.include_router(config_identidad_router)
# Emergencias (COM): /api/v1/emergencias/* — prefijo propio, sin colisiones.
# Fase 3 sumara rutas con {id} greedy: las de segmento fijo deberan ir antes (§5).
app.include_router(emergencias_router)
# App Vecinos (PWA publica de ciudadanos)
app.include_router(publico_auth_router)
# Alta publica de vecinos (autoregistro desde URL publica por municipio, sin JWT, rate-limited)
app.include_router(publico_alta_router)
app.include_router(publico_identidad_router)
# Adjuntos publicos ANTES del router de reclamos publicos (su GET /{id_reclamo} es greedy, §5)
app.include_router(publico_reclamos_adjuntos_router)
app.include_router(publico_reclamos_router)
app.include_router(publico_portal_router)
# Turnos del vecino logueado (App Vecinos etapa C, scope publico)
app.include_router(publico_turnos_vecino_router)
# Entradas del vecino logueado (App Vecinos etapa D, scope publico — cartelera + QR)
app.include_router(publico_entradas_vecino_router)
# Emergencias del vecino (App Vecinos, scope publico — plan COM Fase 5)
app.include_router(publico_emergencias_router)
# Suscripciones Web Push del vecino (App Vecinos etapa E, scope publico)
app.include_router(publico_push_router)
# Perfil del vecino logueado (ficha BUC + edicion de contacto/domicilio, scope publico)
app.include_router(publico_perfil_router)
# Bandeja de avisos del vecino (mig 99, scope publico)
app.include_router(publico_avisos_router)
# Encuestas publicas (form del ciudadano, sin JWT, rate-limited por IP)
app.include_router(encuestas_publico_router)


# Health check
@app.get("/api/health", tags=["Health"])
@app.get("/health",     tags=["Health"])
@app.get("/healthz",    tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "module": "BUC"
    }
