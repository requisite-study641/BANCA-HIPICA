"""
Banca Hípica P2P — aplicación FastAPI (punto de entrada).

Ejecutar desde la RAÍZ del proyecto:
    uvicorn backend.main:app --reload  (desarrollo)
    gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:$PORT main:app  (producción)

Sirve la API JSON bajo /... y el frontend móvil estático en la raíz (/).
"""

import os
import logging
import logging.config
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Importación de routers y base de datos local del proyecto
from backend import database, auth, duel_types, races, duels, payments, audit

# Configuración de logging estructurado para producción
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "access": {
            "format": '%(asctime)s - %(name)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("banca-hipica")

app = FastAPI(
    title="Banca Hípica P2P",
    description=(
        "Aplicación web móvil modular de apuestas P2P en carreras de caballos. "
        "Comisión fija del 5% para la casa, escrow por duelo y resolución "
        "exclusiva del administrador."
    ),
    version="1.0.0",
)

# Configuración de CORS segura para producción y desarrollo
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de seguridad para producción (TrustedHostMiddleware opcional mediante variables de entorno)
allowed_hosts_env = os.getenv("ALLOWED_HOSTS", "*")
if allowed_hosts_env != "*":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in allowed_hosts_env.split(",")]
    )

# Middleware para limitar el tamaño de las solicitudes (protección contra payloads grandes - máx 10 MB)
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_int = int(content_length)
            if content_length_int > MAX_REQUEST_SIZE:
                logger.warning(
                    f"Request too large: {content_length_int} bytes from {request.client.host}:{request.client.port}"
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"El tamaño de la solicitud excede el límite permitido de {MAX_REQUEST_SIZE // 1024 // 1024} MB"},
                )
        except ValueError:
            pass
    response = await call_next(request)
    return response

# Manejadores de excepciones personalizados (evitan filtrar trazas internas al cliente)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()} - {request.url}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Error de validación en los datos proporcionados"},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"},
    )

@app.on_event("startup")
def on_startup() -> None:
    """Crea tablas y siembra datos iniciales (admin + tipos de duelo + banco)."""
    database.seed_initial_data()


# ─────────────────────────── Routers de la API ───────────────────────────
app.include_router(auth.router)
app.include_router(duel_types.router)
app.include_router(races.router)
app.include_router(duels.router)
app.include_router(payments.router)
app.include_router(audit.router)


@app.get("/health", tags=["system"])
def health():
    """Sonda de estado del servicio."""
    return {"status": "ok", "app": "banca-hipica-p2p", "fee_percentage": 0.05}


# ─────────────────────── Frontend móvil (estático) ───────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")