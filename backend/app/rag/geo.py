"""Matemática geográfica y lectores de datos para la búsqueda por cercanía (E09 · T09.3.2 · T09.8.1).

Funciones **puras** (solo `math`/`json`): haversine y distancia al POI más cercano por categoría.
Los nombres de las claves de metadata (`dist_<cat>_m`) vienen de `geo_const.CERCANIA_KEYS` — nunca
se escriben a mano aquí. La **única** función con red es `geocode_vivo` (E09·S8): geocodifica un
nombre propio una vez (Nominatim, cacheado en `geocache.json`, rate-limit 1 req/s) y es inyectable
para tests offline.

Convención de coords: `lat`/`lon` (ver `geo_const`). Los POIs son listas de dicts con esas claves.
"""

import functools
import json
import math
import os
import threading
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
    clave_geocache,
)

_RADIO_TIERRA_M = 6_371_000
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
# bbox Valle de Aburrá (misma cobertura que build_poi): sur,oeste,norte,este.
_VALLE_BBOX = (6.06, -75.70, 6.48, -75.28)
_ULTIMO_GEOCODE = [0.0]  # timestamp del último request a Nominatim (rate-limit 1 req/s)
_GEO_LOCK = threading.Lock()  # serializa geocodes concurrentes (FastAPI corre `def` en threadpool)


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


# Los archivos de datos son estáticos por proceso (se regeneran offline con los scripts build_* y
# se recargan al reiniciar) → se memoizan. NO mutar los dicts/listas devueltos (son compartidos).
@functools.lru_cache(maxsize=1)
def cargar_metro() -> list[dict]:
    """Estaciones del Metro como lista de POIs `[{"nombre","linea","lat","lon"}]`."""
    return _leer_json(DATA_METRO_FILE)["estaciones"]


@functools.lru_cache(maxsize=1)
def cargar_centroides() -> dict[str, dict]:
    """Centroides por `clave_geocache(zona,ciudad)` → `{"lat","lon","metro"}`."""
    return _leer_json(DATA_CENTROIDES_FILE)["centroides"]


@functools.lru_cache(maxsize=1)
def cargar_pois() -> dict[str, list[dict]]:
    """POIs OSM por categoría (slug de `CERCANIA_KEYS`) → `[{"lat","lon"}]`.

    Lee `poi_valle_aburra.json` (E09·S7). Devuelve `{}` si el archivo aún no existe (CORE sin
    fuentes en vivo: el backfill solo calcula `metro` con la semilla).
    """
    if not os.path.exists(os.path.join(_DATA_DIR, DATA_POI_FILE)):
        return {}
    por_cat: dict[str, list[dict]] = {}
    for p in _leer_json(DATA_POI_FILE).get("pois", []):
        # incluye nombre/brand: el backfill solo usa lat/lon, pero lugares_cerca necesita el NOMBRE.
        por_cat.setdefault(p["categoria"], []).append(
            {COORD_LAT_KEY: p["lat"], COORD_LON_KEY: p["lon"],
             "nombre": p.get("nombre", ""), "brand": p.get("brand", "")})
    return por_cat


# Radios sensatos por categoría (m) para "qué hay cerca". Metadata plana → mismos que la búsqueda.
_RADIOS_LUGARES_M = {"metro": 1500, "supermercado": 1500, "colegio": 1500, "parque": 1500,
                     "centro_comercial": 2500, "clinica": 2500, "universidad": 3000}
# Nombre genérico cuando el POI no trae nombre ni brand.
_NOMBRE_GENERICO = {"metro": "Estación de metro", "supermercado": "Supermercado",
                    "centro_comercial": "Centro comercial", "colegio": "Colegio",
                    "universidad": "Universidad", "parque": "Parque", "clinica": "Clínica"}


def lugares_cerca(lat, lon, categoria=None, top: int = 3, radios: dict | None = None) -> dict[str, list[dict]]:
    """Lugares REALES (con nombre) alrededor de (lat,lon), por categoría (E09·H8).

    Para cada categoría (o solo `categoria` si se pide) calcula haversine a cada POI, filtra dentro
    del radio de la categoría, ordena asc, deduplica por (etiqueta, coords) y toma `top`. La etiqueta
    es `nombre` → `brand` → el genérico de la categoría. Devuelve
    `{cat: [{"nombre": etiqueta, "dist_m": int, "lat": float, "lon": float}, …]}` **omitiendo las
    categorías sin nada** en el radio (un inmueble fuera del Valle no tiene POIs → casi vacío = honesto).
    `lat`/`lon` del POI sirven para pintar el pin y trazar la ruta en el mapa interactivo.
    """
    if lat is None or lon is None:
        return {}
    radios = radios or _RADIOS_LUGARES_M
    pois = {"metro": cargar_metro(), **cargar_pois()}  # metro es una categoría más (sus POIs traen nombre)
    cats = [categoria] if categoria else list(CERCANIA_KEYS)  # orden congelado
    out: dict[str, list[dict]] = {}
    for cat in cats:
        lista = pois.get(cat)
        if not lista:
            continue
        radio = radios.get(cat, 1500)
        candidatos = []
        for p in lista:
            plat, plon = p.get(COORD_LAT_KEY), p.get(COORD_LON_KEY)
            if plat is None or plon is None:
                continue
            d = haversine_m(lat, lon, plat, plon)
            if d <= radio:
                etiqueta = (p.get("nombre") or p.get("brand") or _NOMBRE_GENERICO.get(cat, "Lugar")).strip()
                candidatos.append((round(d), etiqueta, round(plat, 6), round(plon, 6)))
        candidatos.sort(key=lambda t: t[0])
        vistos, res = set(), []
        for d, etiqueta, pla, plo in candidatos:
            # dedup por NOMBRE (conserva el más cercano): un mismo lugar mapeado como varios nodos
            # OSM (p.ej. EAFIT ×5) no debe copar el top-N ni repetirse; así entran nombres distintos.
            clave = etiqueta.lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            res.append({"nombre": etiqueta, "dist_m": d, "lat": pla, "lon": plo})  # lat/lon: mapa + ruta
            if len(res) >= top:
                break
        if res:
            out[cat] = res
    return out


# ---------------------------------------------------------------------------
# Enriquecimiento de una ficha en la ingesta (E09 · T09.9.1)
# ---------------------------------------------------------------------------

_COORD_SINTETICA = (6.000123, -75.000456)  # placeholder del seed original


def _coords_no_confiables(lat, lon) -> bool:
    """True si faltan, son ≈0, o son la coord sintética del seed (→ conviene geocodificar)."""
    if lat is None or lon is None:
        return True
    if abs(lat - _COORD_SINTETICA[0]) < 1e-6 and abs(lon - _COORD_SINTETICA[1]) < 1e-6:
        return True
    return abs(lat) < 0.01 or abs(lon) < 0.01


def enriquecer_inmueble(inmueble, centroides: dict, pois: dict):
    """Rellena coords + setea las `dist_<cat>_m` de un `InmuebleIn` **in-place** (E09·T09.9.1).

    `centroides` = salida de `cargar_centroides()`; `pois` = `{"metro": [...], "supermercado": [...], …}`
    (estaciones + POIs OSM). Reglas de honestidad (idénticas al backfill `seed_geo`):
    - coords: usa las del inmueble si son confiables; si no, el centroide de su `(zona, ciudad)`.
    - `metro`: solo si el municipio tiene metro (flag del centroide).
    - las 6 categorías OSM: solo si el inmueble cae en el bbox con cobertura de Overpass (Valle).

    Falla-suave: si no hay coords ni centroide, no toca las distancias (la ficha se indexa igual).
    Devuelve el mismo `inmueble` (mutado) por comodidad.
    """
    lat, lon = getattr(inmueble, "latitud", None), getattr(inmueble, "longitud", None)
    centro = centroides.get(clave_geocache(getattr(inmueble, "zona", None),
                                           getattr(inmueble, "ciudad", None)))
    if _coords_no_confiables(lat, lon) and centro:
        lat, lon = centro["lat"], centro["lon"]
        inmueble.latitud, inmueble.longitud = lat, lon
    if lat is None or lon is None:
        return inmueble

    pois_por_cat: dict = {}
    if centro and centro.get("metro") and pois.get("metro"):
        pois_por_cat["metro"] = pois["metro"]
    if _en_valle(lat, lon):
        for slug, lista in pois.items():
            if slug != "metro":
                pois_por_cat[slug] = lista

    for clave, val in distancias_por_categoria(lat, lon, pois_por_cat).items():
        setattr(inmueble, clave, val)  # clave == nombre del campo (dist_<cat>_m)
    return inmueble


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


# Conectores/muletillas que el fallback del geocoder quita para dejar el núcleo del nombre.
# NO se quitan los artículos sueltos "el/la/los/las": son parte de muchos topónimos colombianos
# (El Peñol, La Ceja, Las Palmas) y removerlos geocodificaría un nombre mutilado.
_CONECTORES = (" cerca de ", " de la ", " de los ", " de las ", " del ", " sector ")


def _con_region(q: str) -> str:
    """Añade ', Colombia' **solo si** la query no trae ya país (no encimar región)."""
    return q if "colombia" in q.lower() else f"{q}, Colombia"


def _simplificar(nombre: str) -> str:
    """Quita conectores/muletillas dejando el núcleo del nombre (fallback del geocoder).

    Trabaja en minúsculas (Nominatim es case-insensitive): "el mirador de la piedra del peñol"
    → "el mirador piedra peñol"; "cerca de La América" → "la américa". Conserva los artículos de
    topónimo ("La Ceja" → "la ceja").
    """
    s = f" {nombre.lower()} "
    prev = None
    while s != prev:  # repetido: "de la" puede dejar otro conector pegado
        prev = s
        for c in _CONECTORES:
            s = s.replace(c, " ")
    return " ".join(s.split())


def _consulta_nominatim(q: str) -> list:
    """Una consulta a Nominatim con **rate-limit 1 req/s** y User-Agent propio. Lista (puede ser vacía).

    Pide `limit=5` + `addressdetails=1` y deja que Nominatim ordene por `importance` (el mejor va 1º).
    Toma `_GEO_LOCK` para que geocodes concurrentes (threadpool de FastAPI) se serialicen y respeten
    el límite (lectura-espera-escritura del timestamp de forma atómica).
    """
    from app.core.config import settings
    with _GEO_LOCK:
        espera = 1.1 - (time.time() - _ULTIMO_GEOCODE[0])
        if espera > 0:
            time.sleep(espera)
        _ULTIMO_GEOCODE[0] = time.time()
        url = settings.NOMINATIM_URL + "?" + urllib.parse.urlencode(
            {"q": q, "format": "json", "limit": 5, "addressdetails": 1, "countrycodes": "co"})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": settings.NOMINATIM_USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            return []


def _nominatim(nombre: str):
    """Geocodifica con Nominatim + **fallback de simplificación** (una pasada). (lat,lon) | None.

    1) Consulta el nombre tal cual (cualificado con región si no la trae). 2) Si da 0, reintenta
    **una vez** con el nombre simplificado (sin muletillas). Toma el resultado de mayor `importance`.
    """
    datos = _consulta_nominatim(_con_region(nombre))
    if not datos:
        simp = _simplificar(nombre)
        if simp and _norm(simp) != _norm(nombre):  # solo si realmente cambió
            datos = _consulta_nominatim(_con_region(simp))
    if not datos:
        return None
    mejor = datos[0]  # Nominatim ya ordena por importance
    return float(mejor["lat"]), float(mejor["lon"])


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
