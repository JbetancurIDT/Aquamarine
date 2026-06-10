"""Test offline de `_construir_where` (E01 · §4.1). NO toca Chroma ni gasta créditos.

Verifica la traducción de filtros amigables a la sintaxis `where` de Chroma.

Uso:
    cd backend && .venv/bin/python scripts/test_search_where.py
"""

import sys
from pathlib import Path

# Permite ejecutar el script directamente: inserta la raíz de backend/ en sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.search import _construir_where  # noqa: E402

T = "aquamarine"


def main() -> int:
    # 1) Sin filtros → solo tenant_id (condición única, sin $and).
    w = _construir_where(None, T)
    assert w == {"tenant_id": {"$eq": T}}, w
    print("[1] sin filtros -> solo tenant_id -> OK")

    # 2) precio_max + ciudad → $and de [tenant, ciudad, precio $lte].
    w = _construir_where({"precio_max": 1000000000, "ciudad": "Medellín"}, T)
    assert w == {"$and": [
        {"tenant_id": {"$eq": T}},
        {"ciudad": {"$eq": "Medellín"}},
        {"precio": {"$lte": 1000000000}},
    ]}, w
    print("[2] precio_max + ciudad -> $and con $lte -> OK")

    # 3) tipo se normaliza a minúsculas; es_lujo bool; habitaciones $gte.
    w = _construir_where({"tipo": "Apartamento", "es_lujo": True, "habitaciones": 3}, T)
    cond = w["$and"]
    assert {"tenant_id": {"$eq": T}} in cond
    assert {"tipo": {"$eq": "apartamento"}} in cond
    assert {"es_lujo": {"$eq": True}} in cond
    assert {"habitaciones": {"$gte": 3}} in cond
    print("[3] tipo lower + es_lujo bool + habitaciones $gte -> OK")

    # 4) precio_min y precio_max juntos → $gte y $lte.
    w = _construir_where({"precio_min": 500, "precio_max": 2000}, T)
    cond = w["$and"]
    assert {"precio": {"$gte": 500}} in cond
    assert {"precio": {"$lte": 2000}} in cond
    print("[4] precio_min + precio_max -> $gte y $lte -> OK")

    # 5) None/'' no agregan condición (precio_max=None ignorado, ciudad None, zona '').
    w = _construir_where({"ciudad": None, "zona": "", "precio_max": None}, T)
    assert w == {"tenant_id": {"$eq": T}}, w
    print("[5] None/'' no agregan condición -> solo tenant -> OK")

    print("\n[OFFLINE] _construir_where OK ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
