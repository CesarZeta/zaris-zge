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
from app.api.routes.agenda import router as agenda_router
from app.api.routes.admin_tablas import router as admin_tablas_router
from app.api.routes.reclamos import router as reclamos_router
from app.api.routes.ordenes_trabajo import router as ot_router
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
        "https://cesarzeta.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Rutas
app.include_router(auth_router)
app.include_router(buc_router)
app.include_router(agenda_router)
app.include_router(admin_tablas_router, prefix="/api/v1/admin")
app.include_router(reclamos_router)
app.include_router(ot_router)


# Health check
@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "module": "BUC"
    }
