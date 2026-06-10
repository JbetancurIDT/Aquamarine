"""Punto de entrada de la API de Aquamarine (E00 · T00.2.1 / T00.5.1).

App FastAPI mínima con CORS abierto (solo desarrollo) y un endpoint `/health`
que sirve como prueba de conexión end-to-end con el frontend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rag import router as rag_router
from app.core.config import settings

app = FastAPI(title="Aquamarine API")

# CORS abierto solo para desarrollo. Se restringe en E02 (backend core / auth).
# Nota: con allow_origins=["*"] no se habilitan credenciales (incompatibles con
# el comodín en navegadores); para el MVP no se usan cookies cross-origin.
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
