"""Punto de entrada de la API de Aquamarine (E00 → E07).

App FastAPI con CORS abierto (solo desarrollo) y lifespan que arranca el
barrido periódico de notificaciones/reasignación (sweep_loop, E07).
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.asesores import router as asesores_router
from app.api.chat import router as chat_router
from app.api.geo import router as geo_router
from app.api.insights import router as insights_router
from app.api.leads import router as leads_router
from app.api.mensajes import router as mensajes_router
from app.api.metrics import router as metrics_router
from app.api.rag import router as rag_router
from app.core.config import settings
from app.services.sweep import sweep_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(sweep_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Aquamarine API", lifespan=lifespan)

# CORS abierto solo para desarrollo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Healthcheck: el frontend lo consulta al cargar `/chat`."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# Routers de feature.
app.include_router(rag_router)
app.include_router(geo_router)
app.include_router(leads_router)
app.include_router(mensajes_router)
app.include_router(metrics_router)
app.include_router(asesores_router)
app.include_router(chat_router)
app.include_router(insights_router)
