"""Tests del fallback por nombre propio `cerca_de_lugar` (E09 · T09.8.3).

Sin red: se mockean `geo.geocode_vivo` (el geocode) y `search.get_chroma_client` (col.get con un
mini-Chroma que respeta el `where` de precio/habitaciones)."""

from unittest.mock import MagicMock

from app.agent.tools import ejecutar_buscar_inmuebles
from app.core.config import settings
from app.rag import geo as geo_mod
from app.rag import search as search_mod
from app.rag.search import buscar_por_lugar

T = settings.DEFAULT_TENANT_ID
EAFIT = (6.2006, -75.5783)  # El Poblado, Medellín


def _inm(id_, lat, lon, precio=900_000_000, hab=3, **extra):
    m = {"inmueble_id": id_, "tenant_id": T, "titulo": f"Inmueble {id_}", "tipo": "apartamento",
         "zona": "Z", "ciudad": "Medellín", "precio": precio, "habitaciones": hab, "banos": 2,
         "estado": "disponible", **extra}
    if lat is not None:
        m["latitud"] = lat
    if lon is not None:
        m["longitud"] = lon
    return m


def _passes(m, where):
    if not where:
        return True
    if "$and" in where:
        return all(_passes(m, c) for c in where["$and"])
    for k, cond in where.items():
        v = m.get(k)
        if "$eq" in cond and v != cond["$eq"]:
            return False
        if "$lte" in cond and (v is None or v > cond["$lte"]):
            return False
        if "$gte" in cond and (v is None or v < cond["$gte"]):
            return False
    return True


def _mock_col_get(monkeypatch, pool):
    col = MagicMock()

    def _get(where=None, include=None, ids=None):
        sel = [m for m in pool if _passes(m, where)]
        return {"ids": [m["inmueble_id"] for m in sel], "metadatas": sel}

    col.get.side_effect = _get
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(search_mod, "get_chroma_client", lambda: chroma)
    return col


def _mock_geocode(monkeypatch, punto):
    monkeypatch.setattr(geo_mod, "geocode_vivo", lambda nombre, **kw: punto)


# --- buscar_por_lugar ---

def test_rankea_por_cercania(monkeypatch):
    _mock_geocode(monkeypatch, EAFIT)
    lejos = _inm("LEJOS", 6.30, -75.55)     # ~11 km
    cerca = _inm("CERCA", 6.202, -75.578)   # ~200 m
    _mock_col_get(monkeypatch, [lejos, cerca])
    res = buscar_por_lugar("EAFIT", {}, k=3)
    assert res["estado"] == "ok"
    assert [r["inmueble_id"] for r in res["resultados"]] == ["CERCA", "LEJOS"]
    assert res["resultados"][0]["coincidencia"] == "cercana"
    assert "EAFIT" in res["resultados"][0]["motivo"] and "~" in res["resultados"][0]["motivo"]


def test_lugar_no_encontrado(monkeypatch):
    _mock_geocode(monkeypatch, None)
    _mock_col_get(monkeypatch, [_inm("A", 6.2, -75.57)])
    res = buscar_por_lugar("Lugar Inexistente XYZ", {})
    assert res["estado"] == "lugar_no_encontrado" and res["resultados"] == []


def test_sin_coords_excluido_y_contado(monkeypatch):
    _mock_geocode(monkeypatch, EAFIT)
    _mock_col_get(monkeypatch, [_inm("SIN", None, None), _inm("CON", 6.202, -75.578)])
    res = buscar_por_lugar("EAFIT", {})
    assert [r["inmueble_id"] for r in res["resultados"]] == ["CON"]
    assert res["descartados_sin_coords"] == 1


def test_todo_sin_coords(monkeypatch):
    _mock_geocode(monkeypatch, EAFIT)
    _mock_col_get(monkeypatch, [_inm("A", None, None), _inm("B", None, None)])
    res = buscar_por_lugar("EAFIT", {})
    assert res["estado"] == "sin_coords" and res["descartados_sin_coords"] == 2


def test_respeta_precio_max(monkeypatch):
    _mock_geocode(monkeypatch, EAFIT)
    caro = _inm("CARO", 6.201, -75.578, precio=5_000_000_000)   # cerca pero fuera de presupuesto
    barato = _inm("BARATO", 6.30, -75.55, precio=500_000_000)
    _mock_col_get(monkeypatch, [caro, barato])
    res = buscar_por_lugar("EAFIT", {"precio_max": 1_000_000_000})
    assert [r["inmueble_id"] for r in res["resultados"]] == ["BARATO"]  # CARO excluido por el where


def test_radio_km_recorta(monkeypatch):
    _mock_geocode(monkeypatch, EAFIT)
    cerca = _inm("CERCA", 6.201, -75.578)   # ~200 m
    lejos = _inm("LEJOS", 6.30, -75.55)     # ~11 km
    _mock_col_get(monkeypatch, [cerca, lejos])
    res = buscar_por_lugar("EAFIT", {}, radio_km=1.0)
    assert [r["inmueble_id"] for r in res["resultados"]] == ["CERCA"]  # LEJOS fuera de 1 km


# --- handler (routing + texto honesto) ---

def test_handler_ok_muestra_distancia_aproximada(monkeypatch):
    _mock_geocode(monkeypatch, EAFIT)
    _mock_col_get(monkeypatch, [_inm("CERCA", 6.201, -75.578)])
    texto, inms = ejecutar_buscar_inmuebles({"query": "", "filtros": {"cerca_de_lugar": "EAFIT"}})
    assert len(inms) == 1
    assert "más cercanos a “EAFIT”" in texto
    assert "de EAFIT (aprox.)" in texto and "~" in texto


def test_handler_lugar_no_encontrado_pide_referencia(monkeypatch):
    _mock_geocode(monkeypatch, None)
    _mock_col_get(monkeypatch, [_inm("A", 6.2, -75.57)])
    texto, inms = ejecutar_buscar_inmuebles({"query": "", "filtros": {"cerca_de_lugar": "XYZ inexistente"}})
    assert inms == []
    assert "referencia alterna" in texto.lower()


def test_routing_lugar_tiene_prioridad_sobre_categoria(monkeypatch):
    """Con cerca_de_lugar presente, se enruta al fallback por lugar (no a la búsqueda por categoría)."""
    _mock_geocode(monkeypatch, EAFIT)
    _mock_col_get(monkeypatch, [_inm("CERCA", 6.201, -75.578)])
    texto, inms = ejecutar_buscar_inmuebles(
        {"query": "apto", "filtros": {"cerca_de_lugar": "EAFIT", "cerca_de": "metro"}})
    assert "más cercanos a “EAFIT”" in texto  # ganó cerca_de_lugar
