"""Orquestación de la ingesta RAG (E01 · T01.5.1).

Pipeline re-ejecutable: (map →) extract → normalizar/validar → upsert en Chroma.
Idempotente: re-correr no duplica (upsert por `inmueble_id`).

Uso (CLI):
    python scripts/ingest.py --no-index --url "<URL_DE_UNA_FICHA>"   # prueba 1 ficha, sin indexar
    python scripts/ingest.py --url "<URL_DE_UNA_FICHA>"              # indexa 1 ficha
    python scripts/ingest.py --limit 5                               # mapea el sitio e indexa 5
    python scripts/ingest.py                                         # mapea TODO el sitio e indexa

Control de costo: la extracción gasta créditos de Firecrawl (≈1 por ficha). Empieza
con --url o --limit antes de correr el sitio completo.
"""

import argparse
import sys
from pathlib import Path

# Permite ejecutar el script directamente: inserta la raíz de backend/ en sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client  # noqa: E402
from app.rag.firecrawl_client import (  # noqa: E402
    BASE_URL_DEFECTO,
    extract_property,
    map_properties,
    to_inmueble,
)

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta RAG de inmuebles (Firecrawl → Chroma)")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de fichas a procesar")
    parser.add_argument("--no-index", action="store_true", help="No indexa en Chroma (solo extrae/valida)")
    parser.add_argument("--url", default=None, help="Procesa una sola URL (en vez de mapear el sitio)")
    parser.add_argument("--base-url", default=None, help=f"Raíz del sitio a mapear (def: {BASE_URL_DEFECTO})")
    args = parser.parse_args()

    urls = [args.url] if args.url else None
    resumen = ingest(
        base_url=args.base_url,
        urls=urls,
        limit=args.limit,
        index=not args.no_index,
    )

    print("\n== RESUMEN ==")
    print(
        f"procesadas={resumen['procesadas']} · indexadas={resumen['indexadas']} · "
        f"descartadas={resumen['descartadas']} · errores={resumen['errores']}"
    )
    print(f"ids: {resumen['ids']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
