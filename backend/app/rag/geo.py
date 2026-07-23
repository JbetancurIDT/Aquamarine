"""Matemática geográfica y lectores de datos para la búsqueda por cercanía (E09 · T09.3.2 · T09.8.1).

Funciones **puras** (solo `math`/`json`): haversine y distancia al POI más cercano por categoría.
Los nombres de las claves de metadata (`dist_<cat>_m`) vienen de `geo_const.CERCANIA_KEYS` — nunca
se escriben a mano aquí. La **única** función con red es `geocode_vivo` (E09·S8): geocodifica un
nombre propio una vez (Nominatim, cacheado en `geocache.json`, rate-limit 1 req/s) y es inyectable
para tests offline.

Convención de coords: `lat`/`lon` (ver `geo_const`). Los POIs son listas de dicts con esas claves.
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request

from app.rag.geo_const import (
    CERCANIA_KEYS,
    COORD_LAT_KEY,
    COORD_LON_KEY,
    DATA_CENTROIDES_FILE,
    DATA_GEOCACHE_FILE,
    DATA_METRO_FILE,
    DATA_POI_FILE,
    _norm,
)

_RADIO_TIERRA_M = 6_371_000
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
# bbox Valle de Aburrá (misma cobertura que build_poi): sur,oeste,norte,este.
_VALLE_BBOX = (6.06, -75.70, 6.48, -75.28)
_ULTIMO_GEOCODE = [0.0]  # timestamp del último request a Nominatim (rate-limit 1 req/s)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine (gran círculo) en metros entre dos puntos (grados decimales)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _RADIO_TIERRA_M * math.asin(math.sqrt(a))


def dist_poi_mas_cercano_m(lat, lon, pois) -> int | None:
    """Metros (entero) al POI más cercano de la lista. `None` si no hay coords o la lista es vacía.

    `pois` = lista de dicts con claves `lat`/`lon` (`COORD_LAT_KEY`/`COORD_LON_KEY`).
    """
    if lat is None or lon is None or not pois:
        return None
    mejor = min(
        haversine_m(lat, lon, p[COORD_LAT_KEY], p[COORD_LON_KEY]) for p in pois
    )
    return round(mejor)


def distancias_por_categoria(lat, lon, pois_por_cat: dict) -> dict[str, int]:
    """`{dist_<cat>_m: metros}` solo para categorías con dato. **Nunca** incluye una clave con `None`.

    `pois_por_cat` = `{slug_categoria: [pois]}`. Se recorre en el orden congelado de
    `CERCANIA_KEYS`; una categoría sin POIs (o sin coords) simplemente no aparece → la
    ausencia de la clave es la señal honesta de "no sabemos / no hay".
    """
    out: dict[str, int] = {}
    for slug, clave in CERCANIA_KEYS.items():
        pois = pois_por_cat.get(slug)
        if not pois:
            continue
        d = dist_poi_mas_cercano_m(lat, lon, pois)
        if d is not None:
            out[clave] = d
    return out


def _leer_json(nombre_archivo: str) -> dict:
    with open(os.path.join(_DATA_DIR, nombre_archivo), encoding="utf-8") as f:
        return json.load(f)


def cargar_metro() -> list[dict]:
    """Estaciones del Metro como lista de POIs `[{"nombre","linea","lat","lon"}]`."""
    return _leer_json(DATA_METRO_FILE)["estaciones"]


def cargar_centroides() -> dict[str, dict]:
    """Centroides por `clave_geocache(zona,ciudad)` → `{"lat","lon","metro"}`."""
    return _leer_json(DATA_CENTROIDES_FILE)["centroides"]


def cargar_pois() -> dict[str, list[dict]]:
    """POIs OSM por categoría (slug de `CERCANIA_KEYS`) → `[{"lat","lon"}]`.

    Lee `poi_valle_aburra.json` (E09·S7). Devuelve `{}` si el archivo aún no existe (CORE sin
    fuentes en vivo: el backfill solo calcula `metro` con la semilla).
    """
    if not os.path.exists(os.path.join(_DATA_DIR, DATA_POI_FILE)):
        return {}
    por_cat: dict[str, list[dict]] = {}
    for p in _leer_json(DATA_POI_FILE).get("pois", []):
        por_cat.setdefault(p["categoria"], []).append({COORD_LAT_KEY: p["lat"], COORD_LON_KEY: p["lon"]})
    return por_cat


# ---------------------------------------------------------------------------
# Fallback por nombre propio (E09 · T09.8.1) — ÚNICA función con red de este módulo.
# ---------------------------------------------------------------------------

def _en_valle(lat: float, lon: float) -> bool:
    s, o, n, e = _VALLE_BBOX
    return s <= lat <= n and o <= lon <= e


def _geocache_path() -> str:
    return os.path.join(_DATA_DIR, DATA_GEOCACHE_FILE)


def _cargar_geocache() -> tuple[dict, dict]:
    if os.path.exists(_geocache_path()):
        doc = _leer_json(DATA_GEOCACHE_FILE)
    else:
        doc = {"_meta": {"fuente": "Nominatim / OpenStreetMap", "convencion_coords": "lat/lon"},
               "geocache": {}}
    return doc, doc.setdefault("geocache", {})


def _guardar_geocache(doc: dict, cache: dict) -> None:
    doc["geocache"] = dict(sorted(cache.items()))
    doc.setdefault("_meta", {})["n"] = len(cache)
    with open(_geocache_path(), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _nominatim(nombre: str):
    """Consulta Nominatim con rate-limit 1 req/s y User-Agent propio. (lat,lon) | None."""
    from app.core.config import settings
    espera = 1.1 - (time.time() - _ULTIMO_GEOCODE[0])
    if espera > 0:
        time.sleep(espera)
    _ULTIMO_GEOCODE[0] = time.time()
    url = settings.NOMINATIM_URL + "?" + urllib.parse.urlencode(
        {"q": f"{nombre}, Colombia", "format": "json", "limit": 1, "countrycodes": "co"})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": settings.NOMINATIM_USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    if not datos:
        return None
    return float(datos[0]["lat"]), float(datos[0]["lon"])


def geocode_vivo(nombre, *, geocodificador=None) -> tuple[float, float] | None:
    """Geocodifica un nombre propio ("EAFIT", "Clínica Las Américas") **una sola vez** y lo cachea
    en `geocache.json`. Devuelve `(lat, lon)` o `None` si no se ubica.

    Se llama **una vez por consulta**, nunca por inmueble. `geocodificador` es inyectable para los
    tests (una función `nombre -> (lat,lon)|None`), de modo que la suite corre **sin red**.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        return None
    clave = "lugar:" + _norm(nombre)
    doc, cache = _cargar_geocache()
    if clave in cache:  # caché persistente: los nombres populares se resuelven una vez
        e = cache[clave]
        return (e["lat"], e["lon"]) if e.get("lat") is not None else None
    punto = (geocodificador or _nominatim)(nombre)
    if punto is not None:
        lat, lon = punto
        cache[clave] = {"lat": round(lat, 6), "lon": round(lon, 6), "granularidad": "lugar",
                        "valle_aburra": _en_valle(lat, lon), "query": nombre}
        _guardar_geocache(doc, cache)
    return punto
