"""Matemática geográfica y lectores de datos para la búsqueda por cercanía (E09 · T09.3.2).

Funciones **puras** (solo `math`/`json`, sin red ni dependencias externas): distancia haversine
en metros y la distancia al POI más cercano por categoría. Los nombres de las claves de metadata
(`dist_<cat>_m`) vienen de `geo_const.CERCANIA_KEYS` — nunca se escriben a mano aquí.

Convención de coords: `lat`/`lon` (ver `geo_const`). Los POIs son listas de dicts con esas claves.
"""

import json
import math
import os

from app.rag.geo_const import (
    CERCANIA_KEYS,
    COORD_LAT_KEY,
    COORD_LON_KEY,
    DATA_CENTROIDES_FILE,
    DATA_METRO_FILE,
)

_RADIO_TIERRA_M = 6_371_000
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


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
