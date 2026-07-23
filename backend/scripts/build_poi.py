#!/usr/bin/env python
"""Genera `poi_valle_aburra.json` con POIs reales del Valle de Aburrá vía Overpass (E09 · T09.7.2, STRETCH).

Una sola query Overpass (bbox del Valle de Aburrá, `out center tags`) para las 6 categorías no-metro,
más una pasada por nombre/brand para cadenas de supermercado. Normaliza a `{categoria,nombre,brand,lat,lon}`
usando los slugs congelados de `geo_const.CERCANIA_KEYS`, deduplica por `(lat,lon)` a 5 decimales y escribe
`_meta.conteos` por categoría. Cachea la respuesta cruda en `_overpass_raw.json` (gitignored). Reintento con
backoff ante 429/504 y rota entre espejos de Overpass. Solo stdlib.

Uso (desde backend/):  python scripts/build_poi.py
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "rag", "data")
_UA = "Aquamarine/1.0 (E09 geo build)"
_BBOX = "6.06,-75.70,6.48,-75.28"  # sur,oeste,norte,este (Valle de Aburrá)
_ESPEJOS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# Query Overpass: cada statement mapea a un slug de CERCANIA_KEYS (ver _clasificar).
_QUERY = f"""[out:json][timeout:180];
(
  nwr["shop"="supermarket"]({_BBOX});
  nwr["shop"="mall"]({_BBOX});
  nwr["shop"="convenience"]["brand"~"D1|Ara|Justo|Bueno|isimo",i]({_BBOX});
  nwr["shop"]["name"~"D1|Ara|Éxito|Exito|Carulla|Jumbo|Euro|Consumo",i]({_BBOX});
  nwr["amenity"="school"]({_BBOX});
  nwr["amenity"="university"]({_BBOX});
  nwr["amenity"="college"]({_BBOX});
  nwr["leisure"="park"]({_BBOX});
  nwr["amenity"="hospital"]({_BBOX});
  nwr["amenity"="clinic"]({_BBOX});
);
out center tags;
"""


def _clasificar(tags: dict) -> str | None:
    """Tags OSM → slug de CERCANIA_KEYS (o None). Todo elemento devuelto por la query cae en una
    de las categorías pedidas; un `shop` no-mall es supermercado o una cadena (D1/Ara/Éxito…)."""
    if tags.get("shop") == "mall":
        return "centro_comercial"
    if tags.get("shop"):
        return "supermercado"
    amen = tags.get("amenity")
    if amen == "school":
        return "colegio"
    if amen in ("university", "college"):
        return "universidad"
    if amen in ("hospital", "clinic"):
        return "clinica"
    if tags.get("leisure") == "park":
        return "parque"
    return None


def _overpass() -> dict:
    data = urllib.parse.urlencode({"data": _QUERY}).encode()
    ultimo = None
    for intento in range(4):
        espejo = _ESPEJOS[intento % len(_ESPEJOS)]
        try:
            req = urllib.request.Request(espejo, data=data, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=200) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code in (429, 504, 503):
                espera = 5 * (intento + 1) ** 2
                print(f"[build_poi] {espejo} HTTP {e.code}; retry en {espera}s…")
                time.sleep(espera)
            else:
                raise
        except Exception as e:  # timeout / red
            ultimo = e
            print(f"[build_poi] {espejo} {type(e).__name__}; probando otro espejo…")
            time.sleep(5)
    raise RuntimeError(f"Overpass no respondió tras reintentos: {ultimo}")


def _coords(el: dict):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center") or {}
    return c.get("lat"), c.get("lon")


def main() -> None:
    crudo = _overpass()
    with open(os.path.join(_DATA_DIR, "_overpass_raw.json"), "w", encoding="utf-8") as f:
        json.dump(crudo, f, ensure_ascii=False)

    vistos: set = set()
    pois: list[dict] = []
    for el in crudo.get("elements", []):
        cat = _clasificar(el.get("tags", {}))
        if not cat:
            continue
        lat, lon = _coords(el)
        if lat is None or lon is None:
            continue
        clave = (cat, round(lat, 5), round(lon, 5))
        if clave in vistos:
            continue
        vistos.add(clave)
        tags = el["tags"]
        pois.append({"categoria": cat, "nombre": tags.get("name", ""),
                     "brand": tags.get("brand", ""), "lat": round(lat, 6), "lon": round(lon, 6)})

    conteos: dict[str, int] = {}
    for p in pois:
        conteos[p["categoria"]] = conteos.get(p["categoria"], 0) + 1
    pois.sort(key=lambda p: (p["categoria"], p["nombre"]))

    doc = {"_meta": {"fuente": "OpenStreetMap / Overpass", "bbox": _BBOX,
                     "convencion_coords": "lat/lon", "total": len(pois), "conteos": conteos,
                     "generado_por": "scripts/build_poi.py (E09·T09.7.2)"},
           "pois": pois}
    with open(os.path.join(_DATA_DIR, "poi_valle_aburra.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[build_poi] OK · {len(pois)} POIs → poi_valle_aburra.json")
    for c in sorted(conteos):
        print(f"    {c:18} {conteos[c]}")


if __name__ == "__main__":
    main()
