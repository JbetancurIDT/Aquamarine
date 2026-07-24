"""Tests offline de la búsqueda por proximidad geográfica (E09 · T09.6.1).

Sin red ni SDK: la matemática (`geo`) es pura; el esquema (`InmuebleIn`) es puro; la búsqueda
se prueba mockeando `app.rag.search.get_chroma_client` (estilo `test_rag_search.py`); y el
backfill (`scripts/seed_geo.py`) usa una colección FALSA con estado que replica el comportamiento
de chromadb 1.5.9 (`col.update` hace MERGE; una clave con valor `None` se elimina).
"""

from unittest.mock import MagicMock

import scripts.seed_geo as seed_geo
import app.rag.ingest as ingest_mod
from app.agent.tools import ejecutar_buscar_inmuebles
import app.agent.tools as tools_mod
from app.core.config import settings
from app.rag import geo
from app.rag import search as search_mod
from app.rag.geo import (
    dist_poi_mas_cercano_m,
    distancias_por_categoria,
    haversine_m,
)
from app.rag.geo_const import CERCANIA_KEYS, clave_geocache
from app.rag.search import _cercania_cond, _radio_m, buscar_inmuebles
from app.schemas.inmueble import InmuebleIn

T = settings.DEFAULT_TENANT_ID


# ---------------------------------------------------------------------------
# haversine_m — precisión, simetría, cero
# ---------------------------------------------------------------------------

def test_haversine_punto_consigo_mismo_es_cero():
    assert haversine_m(6.2, -75.5, 6.2, -75.5) == 0.0


def test_haversine_simetrica():
    a = haversine_m(6.2470, -75.5688, 6.2124, -75.5779)
    b = haversine_m(6.2124, -75.5779, 6.2470, -75.5688)
    assert a == b


def test_haversine_precision_un_grado():
    """1° de latitud ≈ 111.195 km (gran círculo). Debe acertar ±0.5%."""
    d = haversine_m(0.0, 0.0, 1.0, 0.0)
    assert abs(d - 111_195) / 111_195 < 0.005


def test_haversine_escala_valle_aburra():
    """San Antonio ↔ Poblado (línea A) ≈ 3.9-4.0 km."""
    d = haversine_m(6.2470, -75.5688, 6.2124, -75.5779)
    assert 3_800 < d < 4_100


# ---------------------------------------------------------------------------
# dist_poi_mas_cercano_m / distancias_por_categoria
# ---------------------------------------------------------------------------

def test_dist_poi_none_si_no_hay_coords():
    assert dist_poi_mas_cercano_m(None, -75.5, [{"lat": 6.2, "lon": -75.5}]) is None
    assert dist_poi_mas_cercano_m(6.2, None, [{"lat": 6.2, "lon": -75.5}]) is None


def test_dist_poi_none_si_lista_vacia():
    assert dist_poi_mas_cercano_m(6.2, -75.5, []) is None


def test_dist_poi_devuelve_el_mas_cercano_como_int():
    pois = [{"lat": 6.30, "lon": -75.50}, {"lat": 6.205, "lon": -75.502}]
    d = dist_poi_mas_cercano_m(6.2, -75.5, pois)
    assert isinstance(d, int)
    # el 2º POI está a ~600 m; el 1º a ~11 km → gana el 2º
    assert d < 1_000


def test_distancias_por_categoria_omite_vacias_y_none():
    # categoría con lista vacía → no aparece
    assert distancias_por_categoria(6.2, -75.5, {"metro": []}) == {}
    # sin coords → dist None → no aparece
    assert distancias_por_categoria(None, None, {"metro": [{"lat": 6.2, "lon": -75.5}]}) == {}


def test_distancias_por_categoria_usa_claves_canonicas():
    out = distancias_por_categoria(6.2, -75.5, {"metro": [{"lat": 6.205, "lon": -75.502}]})
    assert set(out) == {CERCANIA_KEYS["metro"]}  # 'dist_metro_m'
    assert isinstance(out["dist_metro_m"], int)


def test_cargar_datos_semilla_validos():
    """Los archivos de datos versionados existen y son coherentes (sin red)."""
    estaciones = geo.cargar_metro()
    centroides = geo.cargar_centroides()
    assert len(estaciones) >= 30 and all("lat" in e and "lon" in e for e in estaciones)
    assert clave_geocache("Poblado", "Medellín") in centroides
    assert centroides[clave_geocache("Poblado", "Medellín")]["metro"] is True
    # un municipio sin metro está marcado como tal
    assert centroides[clave_geocache("Guatape", "Guatapé")]["metro"] is False


# ---------------------------------------------------------------------------
# InmuebleIn.metadata — dist_* planas (omite None, emite int), document intacto
# ---------------------------------------------------------------------------

_BASE_INM = dict(inmueble_id="x1", tenant_id=T, titulo="Apto de prueba",
                 ciudad="Medellín", zona="Poblado", tipo="apartamento",
                 url_fuente="http://x", descripcion="Con vista")


def test_metadata_omite_dist_none():
    md = InmuebleIn(**_BASE_INM).metadata
    assert not any(k.startswith("dist_") for k in md)


def test_metadata_emite_dist_int_y_omite_las_none():
    md = InmuebleIn(**_BASE_INM, dist_metro_m=640).metadata
    assert md["dist_metro_m"] == 640 and isinstance(md["dist_metro_m"], int)
    assert "dist_super_m" not in md  # None → omitida


def test_document_no_cambia_con_dist():
    """Las distancias son señal numérica de filtro, NO semántica → no tocan el `document`."""
    sin = InmuebleIn(**_BASE_INM).document
    con = InmuebleIn(**_BASE_INM, dist_metro_m=640, dist_super_m=300).document
    assert sin == con


# ---------------------------------------------------------------------------
# search: _radio_m / _cercania_cond / where duro
# ---------------------------------------------------------------------------

def test_radio_m_default_y_piso_y_override():
    assert _radio_m({"cerca_de": "metro"}, "metro") == 1500        # default 1.5 km
    assert _radio_m({"radio_km": 0.5}, "metro") == 1500            # bajo el piso → 1500
    assert _radio_m({"radio_km": 3}, "metro") == 3000             # amplía
    assert _radio_m({}, "universidad") == 3000                    # default categoría
    assert _radio_m({}, "centro_comercial") == 2500


def test_cercania_cond():
    assert _cercania_cond({"cerca_de": "metro"}) == {"dist_metro_m": {"$lte": 1500}}
    assert _cercania_cond({}) is None
    assert _cercania_cond({"cerca_de": "no_existe"}) is None


def _pack(candidatos):
    metas = [c for c, _ in candidatos]
    return {"ids": [[m["inmueble_id"] for m in metas]],
            "metadatas": [metas], "distances": [[d for _, d in candidatos]]}


def _lte_conds(where):
    """Extrae (clave, tope) de cada {clave:{'$lte':tope}} del where (maneja $and)."""
    out = []
    if not where:
        return out
    if "$and" in where:
        for c in where["$and"]:
            out += _lte_conds(c)
    else:
        for k, v in where.items():
            if isinstance(v, dict) and "$lte" in v:
                out.append((k, v["$lte"]))
    return out


def _mock_chroma_where(monkeypatch, pool):
    """col.query filtra el pool respetando el `$lte` del where (mini-Chroma para cercanía)."""
    col = MagicMock()

    def _q(**kw):
        where = kw.get("where")
        sel = [(m, d) for (m, d) in pool
               if all(m.get(k) is not None and m[k] <= tope for k, tope in _lte_conds(where))]
        return _pack(sel)

    col.query.side_effect = _q
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(search_mod, "get_chroma_client", lambda: chroma)
    return col


def _mock_chroma(monkeypatch, candidatos):
    col = MagicMock()
    col.query.return_value = _pack(candidatos)
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(search_mod, "get_chroma_client", lambda: chroma)
    return col


def _inm(id_, zona, ciudad, *, dist=0.2, **extra):
    return {"inmueble_id": id_, "tenant_id": T, "titulo": f"Inmueble {id_}", "tipo": "apartamento",
            "zona": zona, "ciudad": ciudad, "precio": 900_000_000, "habitaciones": 3,
            "banos": 2, "estado": "disponible", **extra}, dist


def test_where_inyecta_lte_de_cercania(monkeypatch):
    col = _mock_chroma(monkeypatch, [_inm("A", "Poblado", "Medellín", dist_metro_m=800)])
    buscar_inmuebles("apartamento", {"cerca_de": "metro"}, k=3)
    where = col.query.call_args.kwargs["where"]
    assert ("dist_metro_m", 1500) in _lte_conds(where)


def test_radio_km_amplia_el_where(monkeypatch):
    col = _mock_chroma(monkeypatch, [_inm("A", "Poblado", "Medellín", dist_metro_m=800)])
    buscar_inmuebles("apartamento", {"cerca_de": "metro", "radio_km": 5}, k=3)
    assert ("dist_metro_m", 5000) in _lte_conds(col.query.call_args.kwargs["where"])


def test_clave_ausente_excluye(monkeypatch):
    """Inmueble SIN dist_metro_m (municipio sin metro) NO aparece; uno metro-cercano sí."""
    metro = _inm("M1", "Poblado", "Medellín", dist_metro_m=800)
    guatape = _inm("G1", "Guatape", "Antioquia")  # sin dist_metro_m
    _mock_chroma_where(monkeypatch, [metro, guatape])
    ids = [r["inmueble_id"] for r in buscar_inmuebles("inmueble", {"cerca_de": "metro"}, k=5)]
    assert "M1" in ids and "G1" not in ids


def test_categoria_sin_metro_es_honesto(monkeypatch):
    """Solo inmuebles sin metro en el pool → búsqueda vacía → texto honesto (no 'no existe')."""
    guatape = _inm("G1", "Guatape", "Antioquia")
    rionegro = _inm("R1", "Llanogrande", "Rionegro")
    _mock_chroma_where(monkeypatch, [guatape, rionegro])
    assert buscar_inmuebles("inmueble", {"cerca_de": "metro"}, k=5) == []
    # el handler produce un mensaje honesto que habilita la respuesta del agente
    texto, inms = ejecutar_buscar_inmuebles({"query": "inmueble", "filtros": {"cerca_de": "metro"}})
    assert inms == []
    assert "no existe" in texto.lower() and "valle de aburr" in texto.lower()


def test_frase_cercania_en_el_texto(monkeypatch):
    """Con cerca_de, la línea del inmueble muestra la distancia aproximada."""
    monkeypatch.setattr(
        tools_mod, "buscar_inmuebles",
        lambda query, filtros, k=3, preferencias=None: [{
            "inmueble_id": "9740978", "titulo": "Apto Poblado", "tipo": "apartamento",
            "zona": "Poblado", "ciudad": "Medellín", "precio": 900_000_000,
            "habitaciones": 3, "banos": 2, "coincidencia": "exacta", "dist_metro_m": 640,
        }],
    )
    texto, _ = ejecutar_buscar_inmuebles({"query": "apto", "filtros": {"cerca_de": "metro"}})
    assert "de una estación de metro — aprox." in texto and "~" in texto
    assert "640" not in texto  # nunca la cifra exacta


# ---------------------------------------------------------------------------
# seed_geo: backfill idempotente que preserva titulo/precio/imagenes
# ---------------------------------------------------------------------------

class _FakeCol:
    """Colección FALSA con estado: replica el MERGE de chromadb 1.5.9 (None elimina la clave)."""

    def __init__(self, store):
        self.store = store
        self.updates = []

    def get(self, where=None, include=None):
        ids = list(self.store)
        return {"ids": ids, "metadatas": [dict(self.store[i]) for i in ids]}

    def update(self, ids=None, metadatas=None):
        for i, delta in zip(ids, metadatas):
            self.updates.append((i, dict(delta)))
            m = self.store[i]
            for k, v in delta.items():
                if v is None:
                    m.pop(k, None)   # MERGE: None borra la clave
                else:
                    m[k] = v


def _mock_seed_env(monkeypatch, store, pois=None):
    fake = _FakeCol(store)
    client = MagicMock()
    client.get_or_create_collection.return_value = fake
    monkeypatch.setattr(seed_geo, "get_chroma_client", lambda: client)
    monkeypatch.setattr(geo, "cargar_metro", lambda: [{"lat": 6.2124, "lon": -75.5779}])
    monkeypatch.setattr(geo, "cargar_centroides", lambda: {
        "poblado|medellin": {"lat": 6.209, "lon": -75.567, "metro": True},
        "guatape|guatape": {"lat": 6.233, "lon": -75.159, "metro": False},
    })
    monkeypatch.setattr(geo, "cargar_pois", lambda: pois or {})  # sin POIs por defecto (CORE)
    return fake


def _store_demo():
    return {
        # metro-servido, coord sintética → geocodifica + dist_metro_m
        "A": {"inmueble_id": "A", "tenant_id": T, "zona": "Poblado", "ciudad": "Medellín",
              "titulo": "Apto A", "precio": 900_000_000, "imagenes": '["u1"]',
              "latitud": 6.000123, "longitud": -75.000456},
        # sin metro, sin coords → geocodifica pero SIN dist_metro_m
        "B": {"inmueble_id": "B", "tenant_id": T, "zona": "Guatape", "ciudad": "Guatapé",
              "titulo": "Finca B", "precio": 800_000_000, "imagenes": '["u2"]'},
    }


def test_backfill_asigna_dist_solo_a_metro_y_preserva_metadata(monkeypatch):
    store = _store_demo()
    _mock_seed_env(monkeypatch, store)
    stats = seed_geo.backfill(T)

    assert "dist_metro_m" in store["A"] and isinstance(store["A"]["dist_metro_m"], int)
    assert "dist_metro_m" not in store["B"]          # Guatapé no tiene metro → honestidad
    assert store["A"]["latitud"] != 6.000123          # coord sintética corregida
    # titulo/precio/imagenes intactos (MERGE: el delta nunca los toca)
    for k in ("A", "B"):
        assert store[k]["titulo"] and store[k]["precio"] and store[k]["imagenes"]
    assert stats["con_alguna_dist"] == 1 and stats["actualizados"] == 2


def test_backfill_idempotente(monkeypatch):
    store = _store_demo()
    fake = _mock_seed_env(monkeypatch, store)
    seed_geo.backfill(T)               # 1ª corrida
    snapshot = {i: dict(m) for i, m in store.items()}
    fake.updates.clear()

    stats2 = seed_geo.backfill(T)       # 2ª corrida: no debe cambiar nada
    assert stats2["actualizados"] == 0
    assert fake.updates == []
    assert store == snapshot


def test_backfill_pois_solo_dentro_del_valle(monkeypatch):
    """Con POIs OSM reales: un inmueble del Valle recibe dist_super_m; uno fuera del bbox no
    (no tenemos cobertura → honestidad "OSM no lo tiene" ≠ "no hay")."""
    store = _store_demo()
    # supermercado cerca del centroide de Poblado (dentro del bbox) y otro cerca de Guatapé (fuera)
    pois = {"supermercado": [{"lat": 6.210, "lon": -75.568}, {"lat": 6.234, "lon": -75.160}]}
    _mock_seed_env(monkeypatch, store, pois=pois)
    seed_geo.backfill(T)
    assert "dist_super_m" in store["A"] and isinstance(store["A"]["dist_super_m"], int)  # Poblado (Valle)
    assert "dist_super_m" not in store["B"]  # Guatapé fuera del bbox → sin dist_super_m


# ---------------------------------------------------------------------------
# enriquecer_inmueble + hook de ingesta (E09 · T09.9.1)
# ---------------------------------------------------------------------------

def test_enriquecer_inmueble_rellena_coords_y_dist():
    inm = InmuebleIn(**_BASE_INM)  # Poblado, Medellín, sin coords
    centroides = {"poblado|medellin": {"lat": 6.209, "lon": -75.567, "metro": True}}
    pois = {"metro": [{"lat": 6.2124, "lon": -75.5779}], "supermercado": [{"lat": 6.210, "lon": -75.568}]}
    geo.enriquecer_inmueble(inm, centroides, pois)
    assert inm.latitud is not None and inm.longitud is not None       # coord desde el centroide
    assert isinstance(inm.dist_metro_m, int) and isinstance(inm.dist_super_m, int)
    assert "dist_metro_m" in inm.metadata and "dist_super_m" in inm.metadata


def _mock_ingest_env(monkeypatch, inmueble, capturas):
    monkeypatch.setattr(ingest_mod, "extract_property", lambda url: {"raw": True})
    monkeypatch.setattr(ingest_mod, "to_inmueble", lambda raw, url: inmueble)
    col = MagicMock()
    col.upsert.side_effect = lambda ids, documents, metadatas: capturas.append(metadatas[0])
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(ingest_mod, "get_chroma_client", lambda: chroma)
    monkeypatch.setattr(geo, "cargar_centroides",
                        lambda: {"poblado|medellin": {"lat": 6.209, "lon": -75.567, "metro": True}})
    monkeypatch.setattr(geo, "cargar_metro", lambda: [{"lat": 6.2124, "lon": -75.5779}])
    monkeypatch.setattr(geo, "cargar_pois", lambda: {"supermercado": [{"lat": 6.210, "lon": -75.568}]})


def test_ingest_indexa_ficha_nueva_con_dist(monkeypatch):
    """Una ficha nueva se indexa YA con dist_* poblado (coords desde el centroide)."""
    inm = InmuebleIn(inmueble_id="NEW1", tenant_id=T, titulo="Apto nuevo", ciudad="Medellín",
                     zona="Poblado", tipo="apartamento", url_fuente="http://x")
    capt: list[dict] = []
    _mock_ingest_env(monkeypatch, inm, capt)
    resumen = ingest_mod.ingest(urls=["http://x"], index=True)
    assert resumen["indexadas"] == 1
    md = capt[0]
    assert isinstance(md.get("dist_metro_m"), int) and isinstance(md.get("dist_super_m"), int)
    assert md.get("latitud") is not None


def test_ingest_geo_falla_suave(monkeypatch):
    """Si el enriquecimiento peta, la ficha se indexa IGUAL (sin dist_*), sin abortar la ingesta."""
    inm = InmuebleIn(inmueble_id="NEW2", tenant_id=T, titulo="Apto", ciudad="Medellín",
                     zona="Poblado", tipo="apartamento", url_fuente="http://x")
    capt: list[dict] = []
    _mock_ingest_env(monkeypatch, inm, capt)

    def _boom(*a, **k):
        raise RuntimeError("geo caído")

    monkeypatch.setattr(geo, "enriquecer_inmueble", _boom)
    resumen = ingest_mod.ingest(urls=["http://x"], index=True)  # no debe lanzar
    assert resumen["indexadas"] == 1
    assert "dist_metro_m" not in capt[0]  # sin dist_*: el enriquecimiento falló pero se indexó
