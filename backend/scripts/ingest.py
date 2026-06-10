"""CLI de la ingesta RAG (E01 · T01.5.1).

Envoltorio delgado sobre `app.rag.ingest.ingest`: la lógica vive en el módulo
importable para que también la reutilice el endpoint `POST /rag/reindex`.

Uso:
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

from app.rag.firecrawl_client import BASE_URL_DEFECTO  # noqa: E402
from app.rag.ingest import ingest  # noqa: E402


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
