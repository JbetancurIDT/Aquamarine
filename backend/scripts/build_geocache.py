#!/usr/bin/env python
"""Geocodifica los pares (zona, ciudad) del inventario con Nominatim (E09 · T09.7.3, STRETCH).

Reemplaza los centroides hardcodeados por centroides reales de Nominatim, **offline** (nunca en
caliente). Lee de Chroma los pares distintos, geocodifica cada uno (`{zona}, {ciudad}, Antioquia,
Colombia`, con fallback a solo-ciudad), respeta **1 req/s** y un User-Agent propio, marca
`granularidad` (barrio|municipio) y `valle_aburra` (según bbox), y escribe `geocache.json` con clave
`clave_geocache(zona,ciudad)`. **Idempotente**: no re-geocodifica pares ya cacheados. Solo stdlib.

Precisión = centroide de barrio/municipio (cientos de m a ~1-2 km). Uso:  python scripts/build_geocache.py
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings  # noqa: E402
from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client  # noqa: E402
from app.rag.geo_const import clave_geocache  # noqa: E402

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "rag", "data")
_GEOCACHE = os.path.join(_DATA_DIR, "geocache.json")
_UA = "Aquamarine/1.0 (E09 geo build; contacto: dev@aquamarine.example)"
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
# bbox Valle de Aburrá: sur,oeste,norte,este = 6.06,-75.70,6.48,-75.28
_SUR, _OESTE, _NORTE, _ESTE = 6.06, -75.70, 6.48, -75.28


def _en_valle(lat: float, lon: float) -> bool:
    return _SUR <= lat <= _NORTE and _OESTE <= lon <= _ESTE


def _geocodificar(q: str):
    url = _NOMINATIM + "?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1, "countrycodes": "co"})
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = json.loads(r.read().decode("utf-8"))
    if not datos:
        return None
    return float(datos[0]["lat"]), float(datos[0]["lon"])


def _pares_distintos(tenant: str) -> list[tuple[str, tuple]]:
    col = get_chroma_client().get_or_create_collection(COLLECTION_NAME)
    metas = col.get(where={"tenant_id": {"$eq": tenant}}, include=["metadatas"])["metadatas"]
    pares = {}
    for m in metas:
        z, c, d = m.get("zona"), m.get("ciudad"), m.get("departamento")
        pares.setdefault(clave_geocache(z, c), (z, c, d))
    return sorted(pares.items())  # [(clave, (zona, ciudad, departamento))]


def _consultas(zona, ciudad, depto) -> list[tuple[str, str]]:
    """(query, granularidad) en orden de intento. Usa el departamento REAL (no todo es Antioquia:
    hay Cartagena/Bolívar y Coveñas/Sucre en el inventario)."""
    depto = depto or "Antioquia"
    qs = []
    if zona:
        qs.append((f"{zona}, {ciudad}, {depto}, Colombia", "barrio"))
    qs.append((f"{ciudad}, {depto}, Colombia", "municipio"))
    qs.append((f"{ciudad}, Colombia", "municipio"))  # último recurso sin departamento
    return qs


def main() -> None:
    tenant = settings.DEFAULT_TENANT_ID
    cache = {}
    if os.path.exists(_GEOCACHE):
        with open(_GEOCACHE, encoding="utf-8") as f:
            cache = json.load(f).get("geocache", {})

    pares = _pares_distintos(tenant)
    nuevos = ok = falló = 0
    for clave, (zona, ciudad, depto) in pares:
        if clave in cache:  # idempotente
            continue
        nuevos += 1
        res, gran, usada = None, None, None
        for q, g in _consultas(zona, ciudad, depto):
            try:
                res = _geocodificar(q)
            except Exception as e:
                print(f"[build_geocache] error en {q!r}: {type(e).__name__}: {e}")
                res = None
            time.sleep(1.1)  # rate-limit Nominatim (1 req/s)
            if res is not None:
                gran, usada = g, q
                break
        if res is None:
            falló += 1
            print(f"[build_geocache] sin resultado: {clave!r}")
            continue
        lat, lon = res
        cache[clave] = {"lat": round(lat, 6), "lon": round(lon, 6), "granularidad": gran,
                        "valle_aburra": _en_valle(lat, lon), "query": usada}
        ok += 1

    doc = {"_meta": {"fuente": "Nominatim / OpenStreetMap", "convencion_coords": "lat/lon",
                     "clave": "clave_geocache(zona, ciudad)", "n": len(cache),
                     "precision": "centroide de barrio/municipio (cientos de m a ~1-2 km)",
                     "generado_por": "scripts/build_geocache.py (E09·T09.7.3)"},
           "geocache": dict(sorted(cache.items()))}
    with open(_GEOCACHE, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    en_valle = sum(1 for v in cache.values() if v["valle_aburra"])
    print(f"[build_geocache] OK · {len(cache)} pares en cache ({nuevos} nuevos, {ok} geocodificados, "
          f"{falló} fallidos) · {en_valle} en Valle de Aburrá → geocache.json")


if __name__ == "__main__":
    main()
