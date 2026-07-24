"""Rutas para el mapa interactivo (feat/mapa-interactivo-rutas).

`GET /geo/ruta`: geometría (siguiendo calles) + tiempo aprox. entre dos puntos, vía
**OpenRouteService** (OSM, sin Google). Si no hay `ORS_API_KEY` o ORS falla, cae a una ruta en
**línea recta** con tiempo estimado (`aprox=true`) — así el mapa SIEMPRE funciona para la demo.
"""

import json
import urllib.request

from fastapi import APIRouter

from app.core.config import settings
from app.rag.geo import haversine_m

router = APIRouter(prefix="/geo", tags=["geo"])

_PERFIL = {"caminando": "foot-walking", "carro": "driving-car"}
_VEL_M_POR_MIN = {"caminando": 80.0, "carro": 420.0}  # estimación urbana para el fallback recto
_CACHE_RUTAS: dict = {}  # (coords redondeadas, perfil) → respuesta REAL de ORS (el fallback no se cachea)
_CACHE_MAX = 2000        # tope defensivo (el endpoint acepta coords arbitrarias): evita crecer sin fin


def _modo_efectivo(from_lat, from_lon, to_lat, to_lon, modo: str) -> str:
    """Resuelve `modo=auto` a caminando/carro según la distancia; deja pasar los explícitos.

    Normaliza a minúsculas para tolerar 'Caminando'/'Carro'; cualquier valor desconocido → auto.
    """
    modo = (modo or "auto").strip().lower()
    if modo in ("caminando", "carro"):
        return modo
    return "caminando" if haversine_m(from_lat, from_lon, to_lat, to_lon) < settings.GEO_MODO_UMBRAL_M else "carro"


def _ors_directions(perfil, from_lat, from_lon, to_lat, to_lon):
    """POST a OpenRouteService. Devuelve (geometry[[lat,lon]], duration_s, distance_m) o None si
    no hay key / falla / respuesta inesperada (el caller usará el fallback recto)."""
    if not settings.ORS_API_KEY:
        return None
    url = f"{settings.ORS_URL}/{perfil}/geojson"
    cuerpo = json.dumps({"coordinates": [[from_lon, from_lat], [to_lon, to_lat]]}).encode("utf-8")
    req = urllib.request.Request(
        url, data=cuerpo,
        headers={"Authorization": settings.ORS_API_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        feat = data["features"][0]
        coords = feat["geometry"]["coordinates"]        # [lon, lat] → Leaflet quiere [lat, lon]
        geometry = [[c[1], c[0]] for c in coords]
        summ = feat["properties"]["summary"]
        return geometry, summ["duration"], summ["distance"]
    except Exception:
        return None


def _osrm_route(from_lat, from_lon, to_lat, to_lon):
    """Ruteo por CALLES vía **OSRM público** (perfil driving, SIN key). Devuelve
    (geometry[[lat,lon]], duration_s, distance_m) o None si `code != "Ok"` / falla / timeout."""
    url = (f"{settings.OSRM_URL}/route/v1/driving/"
           f"{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": settings.NOMINATIM_USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        r0 = data["routes"][0]
        coords = r0["geometry"]["coordinates"]        # [lon, lat] → Leaflet quiere [lat, lon]
        geometry = [[c[1], c[0]] for c in coords]
        return geometry, r0["duration"], r0["distance"]
    except Exception:
        return None


def _resolver_ruta(modo_ef, perfil, from_lat, from_lon, to_lat, to_lon) -> dict:
    """Cadena de ruteo: ORS (con key, perfil real) → OSRM público (calles, sin key) → línea recta."""
    # 1) ORS — perfil peatonal/carro real (solo si hay ORS_API_KEY).
    r = _ors_directions(perfil, from_lat, from_lon, to_lat, to_lon)
    if r is not None:
        geometry, dur_s, dist_m = r
        return {"geometry": geometry, "duration_min": round(dur_s / 60, 1),
                "distance_m": round(dist_m), "modo": modo_ef, "aprox": False}

    # 2) OSRM público — sigue las calles sin key (perfil driving). Para `caminando` reusa la geometría
    #    y la distancia ruteadas, pero estima el tiempo a pie (para peatonal exacto haría falta ORS/OSRM-foot).
    r = _osrm_route(from_lat, from_lon, to_lat, to_lon)
    if r is not None:
        geometry, dur_s, dist_m = r
        dur_min = dist_m / _VEL_M_POR_MIN["caminando"] if modo_ef == "caminando" else dur_s / 60
        return {"geometry": geometry, "duration_min": round(dur_min, 1),
                "distance_m": round(dist_m), "modo": modo_ef, "aprox": False}

    # 3) Línea recta — último recurso (la demo nunca se rompe).
    dist = haversine_m(from_lat, from_lon, to_lat, to_lon)
    dur_min = dist / _VEL_M_POR_MIN.get(modo_ef, 420.0)
    return {"geometry": [[from_lat, from_lon], [to_lat, to_lon]],
            "duration_min": round(dur_min, 1), "distance_m": round(dist), "modo": modo_ef, "aprox": True}


@router.get("/ruta")
def ruta(from_lat: float, from_lon: float, to_lat: float, to_lon: float, modo: str = "auto") -> dict:
    """Ruta (geometría por calles + tiempo) entre dos puntos. `modo`: auto | caminando | carro."""
    modo_ef = _modo_efectivo(from_lat, from_lon, to_lat, to_lon, modo)
    perfil = _PERFIL.get(modo_ef, "driving-car")
    clave = (round(from_lat, 5), round(from_lon, 5), round(to_lat, 5), round(to_lon, 5), perfil)
    if clave in _CACHE_RUTAS:
        return _CACHE_RUTAS[clave]

    out = _resolver_ruta(modo_ef, perfil, from_lat, from_lon, to_lat, to_lon)
    # Cachea SOLO rutas RUTEADAS (ORS u OSRM, aprox=False): un fallo transitorio no debe quedar fijo
    # como línea recta para siempre, y la recta es barata (haversine) → no vale la pena cachearla.
    if not out["aprox"]:
        if len(_CACHE_RUTAS) >= _CACHE_MAX:
            _CACHE_RUTAS.pop(next(iter(_CACHE_RUTAS)))  # evicción FIFO defensiva
        _CACHE_RUTAS[clave] = out
    return out
