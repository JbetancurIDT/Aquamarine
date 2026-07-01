"""Test offline de `_where_duro` (E01 · §4.1 · endurecido E09). NO toca Chroma ni gasta créditos.

Verifica que el `where` de Chroma lleve SOLO filtros numéricos/confiables y que `tipo`/`zona`/
`ciudad` ya NO se filtren con igualdad exacta (la causa de los 0 resultados — ahora son post-filtro
tolerante en Python). Este archivo es un script manual; también lo recoge pytest.

Uso:
    cd backend && .venv/bin/python scripts/test_search_where.py
"""

import sys
from pathlib import Path

# Permite ejecutar el script directamente: inserta la raíz de backend/ en sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.search import _where_duro  # noqa: E402

T = "aquamarine"


def test_where_duro_offline() -> None:
    """Recogible por pytest: agrupa todas las aserciones del contrato de `_where_duro`."""
    # 1) Sin filtros → solo tenant_id (condición única, sin $and).
    w = _where_duro(None, T)
    assert w == {"tenant_id": {"$eq": T}}, w

    # 2) tipo/zona/ciudad NO entran al where (son post-filtro tolerante), aunque se pasen.
    w = _where_duro({"tipo": "casa campestre", "zona": "Las Palmas", "ciudad": "Envigado"}, T)
    assert w == {"tenant_id": {"$eq": T}}, w  # ninguno de esos tres filtra en Chroma

    # 3) precio_max + tipo_negocio → $and con $lte y tipo_negocio normalizado; sin tipo/zona.
    w = _where_duro({"precio_max": 1_000_000_000, "tipo_negocio": "Venta",
                     "tipo": "apartamento", "zona": "Poblado"}, T)
    cond = w["$and"]
    assert {"tenant_id": {"$eq": T}} in cond
    assert {"precio": {"$lte": 1_000_000_000}} in cond
    assert {"tipo_negocio": {"$eq": "venta"}} in cond
    assert not any("tipo" in c and "tipo_negocio" not in c for c in cond)  # no hay {"tipo": ...}
    assert not any("zona" in c for c in cond)

    # 4) numéricos: precio_min/max ($gte/$lte), habitaciones/banos ($gte), es_lujo (bool).
    w = _where_duro({"precio_min": 500, "precio_max": 2000, "habitaciones": 4,
                     "banos": 2, "es_lujo": True}, T)
    cond = w["$and"]
    assert {"precio": {"$gte": 500}} in cond
    assert {"precio": {"$lte": 2000}} in cond
    assert {"habitaciones": {"$gte": 4}} in cond
    assert {"banos": {"$gte": 2}} in cond
    assert {"es_lujo": {"$eq": True}} in cond

    # 5) None/'' no agregan condición.
    w = _where_duro({"ciudad": None, "zona": "", "precio_max": None}, T)
    assert w == {"tenant_id": {"$eq": T}}, w


def main() -> int:
    test_where_duro_offline()
    print("[OFFLINE] _where_duro OK ✅ (numéricos sí, tipo/zona/ciudad NO)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
