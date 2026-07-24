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


# --- robustez del geocoder (E09·H7): región sin duplicar, mayor importance, fallback de simplificación ---

def test_simplificar_quita_conectores():
    # quita conectores/muletillas pero CONSERVA los artículos de topónimo (La Ceja, El Peñol…)
    assert geo_mod._simplificar("el mirador de la piedra del peñol") == "el mirador piedra peñol"
    assert geo_mod._simplificar("cerca de La América") == "la américa"
    assert geo_mod._simplificar("La Ceja") == "la ceja"  # no mutila el topónimo


def test_con_region_no_duplica_pais():
    ya = "Mirador del Peñol, El Peñol, Antioquia, Colombia"
    assert geo_mod._con_region(ya) == ya            # ya trae país → no encima
    assert geo_mod._con_region("EAFIT") == "EAFIT, Colombia"  # no trae → añade


def test_nominatim_fallback_simplifica_cuando_completa_da_cero(monkeypatch):
    llamadas = []

    def fake(q):
        llamadas.append(q)
        # la query completa (con muletillas "de la") da 0; la simplificada resuelve
        return [] if "de la" in q.lower() else [{"lat": "6.2205", "lon": "-75.1780", "importance": 0.6}]

    monkeypatch.setattr(geo_mod, "_consulta_nominatim", fake)
    assert geo_mod._nominatim("el mirador de la piedra del peñol") == (6.2205, -75.178)
    assert len(llamadas) == 2  # completa + simplificada (una sola pasada de fallback)


def test_nominatim_toma_el_de_mayor_importance(monkeypatch):
    monkeypatch.setattr(geo_mod, "_consulta_nominatim", lambda q: [
        {"lat": "6.2", "lon": "-75.5", "importance": 0.9},
        {"lat": "1.0", "lon": "1.0", "importance": 0.1},
    ])
    assert geo_mod._nominatim("EAFIT") == (6.2, -75.5)  # el 1º (Nominatim ordena por importance)


def test_nominatim_no_reconsulta_si_la_completa_resuelve(monkeypatch):
    """Si la query completa ya resuelve, NO se dispara el fallback (una sola consulta)."""
    llamadas = []

    def fake(q):
        llamadas.append(q)
        return [{"lat": "6.2", "lon": "-75.58", "importance": 0.8}]

    monkeypatch.setattr(geo_mod, "_consulta_nominatim", fake)
    assert geo_mod._nominatim("Mirador del Peñol, El Peñol, Antioquia") == (6.2, -75.58)
    assert len(llamadas) == 1  # resolvió a la primera → sin reconsulta


def test_nominatim_sin_reconsulta_redundante_si_simplificar_no_cambia(monkeypatch):
    """Un nombre sin conectores que da 0 NO se reconsulta (el guard `_norm(simp)!=_norm(nombre)`)."""
    llamadas = []
    monkeypatch.setattr(geo_mod, "_consulta_nominatim", lambda q: llamadas.append(q) or [])
    assert geo_mod._nominatim("EAFIT") is None  # 0 resultados y simplificar no cambia
    assert len(llamadas) == 1  # una sola consulta (sin reconsulta idéntica)


def test_consulta_nominatim_respeta_rate_limit(monkeypatch):
    """Ejercita el rate-limit REAL de `_consulta_nominatim`: duerme lo que falte para 1 req/s."""
    import app.rag.geo as g

    class _FakeTime:
        def __init__(self, t):
            self.t = t
            self.sleeps = []

        def time(self):
            return self.t

        def sleep(self, s):
            self.sleeps.append(s)
            self.t += s

    ft = _FakeTime(100.3)
    monkeypatch.setattr(g, "time", ft)
    old_ts = g._ULTIMO_GEOCODE[0]
    g._ULTIMO_GEOCODE[0] = 100.0  # último request hace 0.3 s → debe dormir 0.8 s

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"[]"

    monkeypatch.setattr(g.urllib.request, "urlopen", lambda req, timeout=15: _Resp())
    try:
        g._consulta_nominatim("Lugar X")
        assert len(ft.sleeps) == 1 and abs(ft.sleeps[0] - 0.8) < 1e-6
        assert abs(g._ULTIMO_GEOCODE[0] - 101.1) < 1e-6  # timestamp actualizado tras dormir
    finally:
        g._ULTIMO_GEOCODE[0] = old_ts  # no dejar un timestamp falso para otros tests


def test_geocode_vivo_cache_hit_no_geocodifica(monkeypatch):
    """La caché sigue intacta: un hit no vuelve a geocodificar ni reescribe."""
    monkeypatch.setattr(geo_mod, "_cargar_geocache",
                        lambda: ({}, {"lugar:eafit": {"lat": 6.2, "lon": -75.58}}))
    saves = []
    monkeypatch.setattr(geo_mod, "_guardar_geocache", lambda doc, cache: saves.append(1))

    def boom(_n):
        raise AssertionError("un cache hit no debe geocodificar")

    assert geo_mod.geocode_vivo("EAFIT", geocodificador=boom) == (6.2, -75.58)
    assert saves == []


def test_geocode_vivo_inyeccion_no_toca_red_y_cachea(monkeypatch):
    """La inyección para tests sigue funcionando (sin red) y persiste en caché."""
    store: dict = {}
    monkeypatch.setattr(geo_mod, "_cargar_geocache", lambda: ({}, store))
    monkeypatch.setattr(geo_mod, "_guardar_geocache", lambda doc, cache: None)
    monkeypatch.setattr(geo_mod, "_consulta_nominatim",
                        lambda q: (_ for _ in ()).throw(AssertionError("no debe tocar red")))
    assert geo_mod.geocode_vivo("Lugar Nuevo", geocodificador=lambda n: (6.1, -75.2)) == (6.1, -75.2)
    assert store["lugar:lugar nuevo"]["lat"] == 6.1  # se cacheó con la clave normalizada
