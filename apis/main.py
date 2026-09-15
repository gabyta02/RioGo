import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.registro_routers import registrar_routers
from core.infra.conexion import engine

app = FastAPI()
logger = logging.getLogger(__name__)


@app.middleware("http")
async def registrar_tiempo_respuesta_api(request: Request, call_next):
    inicio = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        _log_api_timing(request, inicio, status_code)


def _log_api_timing(request: Request, inicio: float, status_code: int) -> None:
    path = request.url.path
    if not path.startswith("/api/v1/chatboot") and path not in {
        "/api/v1/sitios/",
    } and not path.startswith("/api/v1/ficha_sitio/"):
        return

    try:
        pool_status = engine.pool.status()
    except Exception as exc:  # pragma: no cover - diagnostico defensivo
        pool_status = f"unavailable:{exc}"

    logger.warning(
        "apis_timing method=%s path=%s status=%s duration_seconds=%.3f db_pool=\"%s\"",
        request.method,
        path,
        status_code,
        time.perf_counter() - inicio,
        pool_status,
    )


app.mount(
    "/api/v1/imagenes",
    StaticFiles(directory="fuente_datos/imagenes", check_dir=False),
    name="imagenes",
)

registrar_routers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "API funcionando"}
