"""Endpoints REST del RAG de inmuebles (E01 · T01.5.2 · mapa en feat/mapa-inmuebles).

- `POST /rag/reindex`: dispara la ingesta (el botón del dashboard la usará en E05).
- `GET /rag/inmuebles/buscar`: búsqueda semántica + filtros (útil para probar el índice).
- `GET /rag/inmuebles/mapa`: inmuebles con coords para pintarlos como pines en el mapa.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import tenant_actual
from app.core.config import settings
from app.core.db import get_db
from app.models.tenant import Tenant
from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client
from app.rag.geo import lugares_cerca
from app.rag.geo_const import CERCANIA_KEYS
from app.rag.ingest import ingest
from app.rag.search import buscar_inmuebles, obtener_inmueble_por_codigo
from app.services.demanda import leads_por_ubicacion

# Campos de la ficha que viajan a la página de mapa por propiedad.
_FICHA_CAMPOS = ("inmueble_id", "titulo", "tipo", "precio", "zona", "ciudad",
                 "imagen_principal", "url_fuente", "latitud", "longitud")

router = APIRouter(prefix="/rag", tags=["rag"])

# Campos que viajan al mapa por inmueble (los mínimos para el pin + el popup de PropertyCard).
_MAPA_CAMPOS = ("inmueble_id", "titulo", "tipo", "zona", "ciudad", "precio", "habitaciones",
                "banos", "area_m2", "imagen_principal", "url_fuente", "latitud", "longitud")


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


@router.get("/inmuebles/mapa")
def inmuebles_mapa(db: Session = Depends(get_db),
                   tenant: Tenant = Depends(tenant_actual)) -> dict:
    """Inmuebles del tenant CON coordenadas, para pintarlos como pines en `/mapa`.

    Cada inmueble trae las `dist_<cat>_m` que existan (para calibrar la cercanía) y `leads_zona`:
    cuántos leads del tenant buscan en su zona (mapa de calor de demanda). Las coords son el
    **centroide del barrio** (con jitter), no la dirección exacta.
    """
    col = get_chroma_client().get_or_create_collection(COLLECTION_NAME)
    res = col.get(where={"tenant_id": {"$eq": settings.DEFAULT_TENANT_ID}}, include=["metadatas"])
    con_coords = [m for m in (res.get("metadatas") or [])
                  if m.get("latitud") is not None and m.get("longitud") is not None]

    demanda = leads_por_ubicacion(db, tenant.id, con_coords)

    inmuebles = []
    for m, n in zip(con_coords, demanda):
        item = {c: m.get(c) for c in _MAPA_CAMPOS}
        for clave in CERCANIA_KEYS.values():  # solo las distancias presentes
            if m.get(clave) is not None:
                item[clave] = m[clave]
        item["leads_zona"] = n
        inmuebles.append(item)
    return {"inmuebles": inmuebles}


@router.get("/inmuebles/{codigo}/cerca")
def inmueble_cerca(codigo: str) -> dict:
    """Ficha + servicios cercanos (con coords) de UN inmueble, para el mapa interactivo por propiedad.

    Reusa `geo.lugares_cerca` (nombres reales + lat/lon por POI, omitiendo categorías vacías).
    """
    inm = obtener_inmueble_por_codigo(codigo)
    if not inm or inm.get("latitud") is None or inm.get("longitud") is None:
        raise HTTPException(status_code=404, detail="Inmueble no encontrado o sin ubicación")
    ficha = {c: inm.get(c) for c in _FICHA_CAMPOS}
    ficha["codigo"] = codigo
    lugares = lugares_cerca(inm["latitud"], inm["longitud"])
    return {"inmueble": ficha, "lugares": lugares}
