"""Endpoints REST del RAG de inmuebles (E01 · T01.5.2).

- `POST /rag/reindex`: dispara la ingesta (el botón del dashboard la usará en E05).
- `GET /rag/inmuebles/buscar`: búsqueda semántica + filtros (útil para probar el índice).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.rag.ingest import ingest
from app.rag.search import buscar_inmuebles

router = APIRouter(prefix="/rag", tags=["rag"])


class ReindexRequest(BaseModel):
    base_url: str | None = None
    urls: list[str] | None = None
    limit: int | None = None


@router.post("/reindex")
def reindex(req: ReindexRequest) -> dict:
    """Dispara la ingesta (el botón del dashboard la usará en E05). Devuelve el resumen.

    Nota de diseño: un reindex de todo el sitio es lento (créditos + tiempo), por eso
    acepta `limit`/`urls` para acotarlo. Para el MVP es síncrono.
    """
    # TODO: si el dashboard lo necesita, mover a background/cola (un barrido completo
    # tarda y bloquearía la petición HTTP).
    return ingest(base_url=req.base_url, urls=req.urls, limit=req.limit, index=True)


@router.get("/inmuebles/buscar")
def buscar(q: str, ciudad: str | None = None, zona: str | None = None, tipo: str | None = None,
           precio_max: int | None = None, habitaciones: int | None = None,
           es_lujo: bool | None = None, k: int = 5) -> dict:
    """Busca inmuebles por similitud semántica (`q`) + filtros opcionales de metadata."""
    filtros = {"ciudad": ciudad, "zona": zona, "tipo": tipo, "precio_max": precio_max,
               "habitaciones": habitaciones, "es_lujo": es_lujo}
    return {"resultados": buscar_inmuebles(q, filtros, k)}
