"""Orquestación de la ingesta RAG (E01 · T01.5.1).

Pipeline re-ejecutable: (map →) extract → normalizar/validar → upsert en Chroma.
Idempotente: re-correr no duplica (upsert por `inmueble_id`).

Lógica **importable**: la usan tanto el CLI `scripts/ingest.py` como el endpoint
`POST /rag/reindex` (`app/api/rag.py`).
"""

from app.rag import geo
from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client
from app.rag.firecrawl_client import (
    BASE_URL_DEFECTO,
    extract_property,
    map_properties,
    to_inmueble,
)


def _cargar_geo():
    """Carga centroides + POIs (metro incluido) UNA vez para el enriquecimiento de la ingesta.
    Falla-suave: si la data geo no está, devuelve None y la ingesta indexa sin `dist_*`."""
    try:
        centroides = geo.cargar_centroides()
        pois = {"metro": geo.cargar_metro(), **geo.cargar_pois()}
        return centroides, pois
    except Exception as exc:  # data geo ausente/corrupta → no degradar la ingesta core
        print(f"[geo-skip]   no se pudo cargar la data geo ({exc}); se indexa sin dist_*")
        return None

# Si se acumulan tantos errores SEGUIDOS, abortamos el barrido: es un fallo sistémico
# (API key inválida, sin créditos, Chroma caído o sin red), no vale recorrer cientos
# de fichas en vano.
MAX_ERRORES_SEGUIDOS = 5


def ingest(base_url=None, urls=None, limit=None, index=True) -> dict:
    """Corre el pipeline de ingesta y devuelve un resumen.

    Args:
        base_url: raíz del sitio a mapear (si no se pasan `urls`).
        urls: lista explícita de URLs de fichas (tiene prioridad sobre el map).
        limit: máximo de fichas a procesar (para pruebas acotadas).
        index: si True, hace upsert en Chroma; si False, solo extrae y valida.

    Returns:
        dict con {procesadas, indexadas, descartadas, errores, ids}.
    """
    if urls:
        lista = list(urls)
    else:
        lista = map_properties(base_url or BASE_URL_DEFECTO)

    if limit is not None:
        lista = lista[:limit]

    resumen = {"procesadas": 0, "indexadas": 0, "descartadas": 0, "errores": 0, "ids": []}

    coleccion = None
    if index:
        coleccion = get_chroma_client().get_or_create_collection(COLLECTION_NAME)

    geo_ctx = _cargar_geo()  # (centroides, pois) o None — una sola vez (E09·S9)
    errores_seguidos = 0  # se resetea con cada ficha procesada con éxito

    for url in lista:
        resumen["procesadas"] += 1

        # 1) Extracción estructurada con Firecrawl.
        try:
            raw = extract_property(url)
        except Exception as exc:
            print(f"[error]      {url} -> {exc}")
            resumen["errores"] += 1
            errores_seguidos += 1
            if errores_seguidos >= MAX_ERRORES_SEGUIDOS:
                print(
                    f"[abortado]   {errores_seguidos} errores seguidos — "
                    "¿key/créditos/red? Se detiene el barrido."
                )
                break
            continue

        # 2) Normalización + validación Pydantic (descarta sin romper si no valida).
        #    Una descarta NO es fallo sistémico (el scrape funcionó) → no toca la racha.
        try:
            inmueble = to_inmueble(raw, url)
        except Exception as exc:
            print(f"[descartada] {url} -> {exc}")
            resumen["descartadas"] += 1
            continue

        # 2b) Enriquecimiento geo (E09·S9): la ficha nace con coords + dist_*. **Falla-suave**:
        #     nunca aborta ni cuenta en la racha de errores; si algo peta, se indexa igual sin dist_*.
        if geo_ctx is not None:
            try:
                geo.enriquecer_inmueble(inmueble, *geo_ctx)
            except Exception as exc:
                print(f"[geo-skip]   {inmueble.inmueble_id} -> {exc}")

        # 3) Indexado idempotente (upsert por inmueble_id). Chroma es remoto: protegemos
        #    el upsert para que un timeout/5xx no aborte todo el barrido.
        if index:
            try:
                coleccion.upsert(
                    ids=[inmueble.inmueble_id],
                    documents=[inmueble.document],
                    metadatas=[inmueble.metadata],
                )
            except Exception as exc:
                print(f"[error-idx]  {inmueble.inmueble_id} ({url}) -> {exc}")
                resumen["errores"] += 1
                errores_seguidos += 1
                if errores_seguidos >= MAX_ERRORES_SEGUIDOS:
                    print(
                        f"[abortado]   {errores_seguidos} errores seguidos — "
                        "¿Chroma caído/red? Se detiene el barrido."
                    )
                    break
                continue
            resumen["indexadas"] += 1
            resumen["ids"].append(inmueble.inmueble_id)
            errores_seguidos = 0
            print(f"[ok]         {inmueble.inmueble_id} · {inmueble.titulo}")
        else:
            resumen["ids"].append(inmueble.inmueble_id)
            errores_seguidos = 0
            print(f"[ok·sin-idx] {inmueble.inmueble_id} · {inmueble.titulo}")
            # Sin indexar imprimimos el InmuebleIn completo para inspección manual.
            for clave, valor in inmueble.model_dump().items():
                print(f"               {clave}: {valor}")

    return resumen
