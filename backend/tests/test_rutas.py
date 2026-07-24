"""Tests del backend del mapa interactivo (feat/mapa-interactivo-rutas), sin red.

`/geo/ruta`: ORS mockeado (geometría+tiempo) y el fallback recto sin key; umbral auto caminando/carro.
`/rag/inmuebles/{codigo}/cerca`: ficha + lugares (con/sin coords).
"""

import app.api.geo as geo_api
import app.api.rag as rag_mod


def test_ruta_fallback_recto_sin_key(client, monkeypatch):
    geo_api._CACHE_RUTAS.clear()
    monkeypatch.setattr(geo_api.settings, "ORS_API_KEY", "")     # sin key ORS
    monkeypatch.setattr(geo_api, "_osrm_route", lambda *a: None)  # y OSRM caído → línea recta
    r = client.get("/geo/ruta", params={"from_lat": 6.20, "from_lon": -75.58,
                                        "to_lat": 6.21, "to_lon": -75.57, "modo": "carro"})
    assert r.status_code == 200
    d = r.json()
    assert d["aprox"] is True
    assert d["geometry"] == [[6.20, -75.58], [6.21, -75.57]]  # recta: solo extremos
    assert d["distance_m"] > 0 and d["duration_min"] > 0 and d["modo"] == "carro"


def test_ruta_osrm_sigue_calles(client, monkeypatch):
    """Sin ORS key, OSRM público rutea por CALLES: geometría multi-punto y aprox=false."""
    geo_api._CACHE_RUTAS.clear()
    monkeypatch.setattr(geo_api, "_ors_directions", lambda *a: None)  # sin ORS key
    geom = [[6.20, -75.58], [6.201, -75.579], [6.203, -75.576], [6.21, -75.57]]
    monkeypatch.setattr(geo_api, "_osrm_route", lambda *a: (geom, 480.0, 2000.0))
    d = client.get("/geo/ruta", params={"from_lat": 6.20, "from_lon": -75.58, "to_lat": 6.21,
                                        "to_lon": -75.57, "modo": "carro"}).json()
    assert d["aprox"] is False and len(d["geometry"]) == 4      # multi-punto, no recta
    assert d["duration_min"] == 8.0 and d["distance_m"] == 2000  # 480 s → 8 min (carro, OSRM)


def test_ruta_osrm_caminando_estima_tiempo_a_pie(client, monkeypatch):
    """modo=caminando sobre OSRM: usa la geometría/distancia ruteadas pero el tiempo a pie."""
    geo_api._CACHE_RUTAS.clear()
    monkeypatch.setattr(geo_api, "_ors_directions", lambda *a: None)
    monkeypatch.setattr(geo_api, "_osrm_route",
                        lambda *a: ([[6.20, -75.58], [6.205, -75.575], [6.21, -75.57]], 480.0, 1600.0))
    d = client.get("/geo/ruta", params={"from_lat": 6.20, "from_lon": -75.58, "to_lat": 6.21,
                                        "to_lon": -75.57, "modo": "caminando"}).json()
    assert d["aprox"] is False and len(d["geometry"]) == 3
    assert d["duration_min"] == 20.0   # 1600 m / 80 m/min = 20 min a pie (NO los 8 min de carro)


def test_ruta_recta_solo_si_ors_y_osrm_fallan(client, monkeypatch):
    geo_api._CACHE_RUTAS.clear()
    monkeypatch.setattr(geo_api, "_ors_directions", lambda *a: None)
    monkeypatch.setattr(geo_api, "_osrm_route", lambda *a: None)
    d = client.get("/geo/ruta", params={"from_lat": 6.20, "from_lon": -75.58, "to_lat": 6.21,
                                        "to_lon": -75.57, "modo": "carro"}).json()
    assert d["aprox"] is True and len(d["geometry"]) == 2  # último recurso: línea recta


def test_ruta_ors_ok(client, monkeypatch):
    geo_api._CACHE_RUTAS.clear()
    monkeypatch.setattr(
        geo_api, "_ors_directions",
        lambda perfil, a, b, c, d: ([[6.20, -75.58], [6.205, -75.575], [6.21, -75.57]], 600.0, 1500.0))
    r = client.get("/geo/ruta", params={"from_lat": 6.20, "from_lon": -75.58, "to_lat": 6.21,
                                        "to_lon": -75.57, "modo": "caminando"})
    d = r.json()
    assert d["aprox"] is False
    assert d["duration_min"] == 10.0 and d["distance_m"] == 1500      # 600 s → 10 min
    assert len(d["geometry"]) == 3 and d["geometry"][0] == [6.20, -75.58]
    assert d["modo"] == "caminando"


def test_modo_auto_umbral(monkeypatch):
    monkeypatch.setattr(geo_api.settings, "GEO_MODO_UMBRAL_M", 1800)
    assert geo_api._modo_efectivo(6.20, -75.58, 6.201, -75.581, "auto") == "caminando"   # ~157 m
    assert geo_api._modo_efectivo(6.20, -75.58, 6.24, -75.60, "auto") == "carro"          # ~5 km
    assert geo_api._modo_efectivo(6.20, -75.58, 6.24, -75.60, "caminando") == "caminando"  # explícito manda


def test_modo_case_insensitive_y_desconocido():
    assert geo_api._modo_efectivo(6.20, -75.58, 6.24, -75.60, "Caminando") == "caminando"  # ~5 km, explícito
    assert geo_api._modo_efectivo(6.20, -75.58, 6.24, -75.60, "bici") == "carro"            # ~5 km, desconocido → auto → carro
    assert geo_api._modo_efectivo(6.20, -75.58, 6.201, -75.581, "bici") == "caminando"      # ~157 m, desconocido → auto → caminando


def test_ruta_fallback_no_se_cachea_y_reintenta_ors(client, monkeypatch):
    """Un fallo transitorio de ORS (fallback recto) NO se cachea → la próxima vez reintenta ORS."""
    geo_api._CACHE_RUTAS.clear()
    params = {"from_lat": 6.20, "from_lon": -75.58, "to_lat": 6.21, "to_lon": -75.57, "modo": "caminando"}
    monkeypatch.setattr(geo_api, "_osrm_route", lambda *a: None)               # OSRM también caído
    monkeypatch.setattr(geo_api, "_ors_directions", lambda *a: None)           # ORS caído
    r1 = client.get("/geo/ruta", params=params).json()
    assert r1["aprox"] is True and not geo_api._CACHE_RUTAS                     # fallback NO cacheado
    monkeypatch.setattr(geo_api, "_ors_directions",
                        lambda *a: ([[6.20, -75.58], [6.21, -75.57]], 300.0, 800.0))  # ORS se recupera
    r2 = client.get("/geo/ruta", params=params).json()
    assert r2["aprox"] is False and r2["duration_min"] == 5.0                   # reintentó (no sirvió la recta)


def test_inmueble_cerca(client, monkeypatch):
    monkeypatch.setattr(rag_mod, "obtener_inmueble_por_codigo",
                        lambda c: {"inmueble_id": c, "titulo": "Apto", "tipo": "apartamento",
                                   "precio": 900_000_000, "zona": "Poblado", "ciudad": "Medellín",
                                   "imagen_principal": "http://img", "url_fuente": "http://u",
                                   "latitud": 6.20, "longitud": -75.58})
    monkeypatch.setattr(rag_mod, "lugares_cerca",
                        lambda lat, lon: {"supermercado": [{"nombre": "Éxito", "dist_m": 400,
                                                            "lat": 6.201, "lon": -75.581}]})
    r = client.get("/rag/inmuebles/9907677/cerca")
    assert r.status_code == 200
    j = r.json()
    assert j["inmueble"]["codigo"] == "9907677" and j["inmueble"]["latitud"] == 6.20
    poi = j["lugares"]["supermercado"][0]
    assert poi["nombre"] == "Éxito" and poi["lat"] == 6.201 and poi["dist_m"] == 400


def test_inmueble_cerca_sin_coords_404(client, monkeypatch):
    monkeypatch.setattr(rag_mod, "obtener_inmueble_por_codigo", lambda c: {"inmueble_id": c})  # sin coords
    assert client.get("/rag/inmuebles/X/cerca").status_code == 404
