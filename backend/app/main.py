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
from app.api.routes.turnos import router as turnos_router
from app.api.routes.turnos_publico import router as turnos_publico_router
from app.api.routes.admin_tablas import router as admin_tablas_router
from app.api.routes.admin_permisos import router as admin_permisos_router
from app.api.routes.reclamos import router as reclamos_router
from app.api.routes.reclamo_adjuntos import router as reclamo_adjuntos_router
from app.api.routes.ordenes_trabajo import router as ot_router
from app.api.routes.geo import router as geo_router
from app.api.routes.activos import router as activos_router
from app.api.routes.config_identidad import router as config_identidad_router
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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Rutas
app.include_router(auth_router)
app.include_router(buc_router)
app.include_router(agenda_v2_router)
app.include_router(agenda_publico_router)
# Orden: los routers especificos (/agenda/espacios, /agenda/disponibilidad)
# DESPUES del general /agenda. FastAPI matchea por orden de registro y
# /agenda/{path} no es greedy, asi que el orden es indiferente aca — pero
# mantenemos especificos despues por convencion.
app.include_router(agenda_espacios_router)
app.include_router(agenda_disponibilidad_router)
# turnos_publico ANTES de turnos: /turnos/publico/* lo atraparia /turnos/{id_turno} (int) -> 422
app.include_router(turnos_publico_router)
app.include_router(turnos_router)
# IMPORTANTE: admin_permisos_router debe registrarse ANTES de admin_tablas_router.
# admin_tablas usa /api/v1/admin/{tabla} y /api/v1/admin/{tabla}/{id}, que sin un
# orden explicito atrapan rutas como /api/v1/admin/permisos/* como si {tabla}='permisos'.
app.include_router(admin_permisos_router)
app.include_router(admin_tablas_router, prefix="/api/v1/admin")
app.include_router(reclamos_router)
app.include_router(reclamo_adjuntos_router)
app.include_router(ot_router)
app.include_router(geo_router)
app.include_router(activos_router)
app.include_router(config_identidad_router)


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
