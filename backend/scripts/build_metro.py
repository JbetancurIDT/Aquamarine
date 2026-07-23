#!/usr/bin/env python
"""Regenera `metro_estaciones.json` desde el GTFS del Metro de Medellín (E09 · T09.7.1, STRETCH).

Descarga el GTFS (`METRO_GTFS_URL` por env/param; acepta un `.zip` GTFS **o** un `stops.txt` crudo),
deduplica los andenes/plataformas por nombre de estación normalizado (promediando lat/lon) y regenera
`app/rag/data/metro_estaciones.json`. **Fallback**: si la descarga o el parseo fallan, conserva la
lista estática (semilla del Sprint 2) que ya está en disco. Solo stdlib.

Uso (desde backend/):
    python scripts/build_metro.py
    METRO_GTFS_URL=https://.../gtfs.zip python scripts/build_metro.py
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.rag.geo_const import DATA_METRO_FILE  # noqa: E402

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "rag", "data")
_DEFAULT_URL = ("https://raw.githubusercontent.com/ColombiaInfo/ColombiaGTFS/master/"
                "Medellin%20-%20Metro/stops.txt")
_UA = "Aquamarine/1.0 (E09 geo build)"

# Sufijos de andén/línea a quitar para agrupar por estación: " - Plataforma N", "(Sur)", "Norte/Sur",
# y un código de línea/cable de una sola letra al final (" K", " L", " J", " H", " B", " M", " P").
_SUFIJOS = re.compile(r"\s*(-\s*plataforma\s*\d+|\(sur\)|\(norte\)|\bnorte\b|\bsur\b|\s[a-z](-[a-z])?)\s*$", re.I)


def _norm_estacion(nombre: str) -> str:
    n = (nombre or "").strip()
    prev = None
    while n and n != prev:  # quita sufijos repetidamente ("San Javier J" -> "San Javier")
        prev = n
        n = _SUFIJOS.sub("", n).strip()
    return n


_GTFS_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")

# route_type de bus (Metroplús/alimentadores): 3 y el rango extendido 700-799. Todo lo demás
# (metro 401, cable 1302, tranvía 900) es riel/cable → se conserva.
def _es_bus(route_type: str) -> bool:
    rt = (route_type or "").strip()
    return rt == "3" or (rt.isdigit() and 700 <= int(rt) <= 799)


def _descargar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _cargar_tablas(url: str) -> dict[str, list[dict]]:
    """Devuelve {archivo: filas} para stops/routes/trips/stop_times, venga como zip GTFS o como
    CSV crudo (en ese caso baja los hermanos reemplazando el nombre de archivo en la URL)."""
    data = _descargar(url)
    tablas: dict[str, list[dict]] = {}
    if data[:2] == b"PK":  # ZIP GTFS: lee cada .txt del zip
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for fname in _GTFS_FILES:
                nombre = next((n for n in z.namelist() if n.endswith(fname)), None)
                if nombre:
                    tablas[fname] = list(csv.DictReader(io.StringIO(z.read(nombre).decode("utf-8-sig"))))
    elif url.endswith("stops.txt"):  # CSV crudo: baja los hermanos
        base = url[: -len("stops.txt")]
        tablas["stops.txt"] = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        for fname in _GTFS_FILES[1:]:
            try:
                tablas[fname] = list(csv.DictReader(io.StringIO(_descargar(base + fname).decode("utf-8-sig"))))
            except Exception:
                pass  # el filtro riel/cable es best-effort si falta un hermano
    else:
        raise ValueError("la URL no es un .zip GTFS ni un stops.txt")
    return tablas


def _stops_riel_cable(tablas: dict[str, list[dict]]) -> set[str] | None:
    """stop_ids servidos por al menos una ruta que NO es bus. None si falta info para filtrar."""
    if not all(k in tablas for k in ("routes.txt", "trips.txt", "stop_times.txt")):
        return None
    tipo_por_ruta = {r["route_id"]: r.get("route_type", "") for r in tablas["routes.txt"]}
    ruta_por_trip = {t["trip_id"]: t.get("route_id", "") for t in tablas["trips.txt"]}
    buenos: set[str] = set()
    for st in tablas["stop_times.txt"]:
        rt = tipo_por_ruta.get(ruta_por_trip.get(st.get("trip_id", ""), ""), "")
        if rt and not _es_bus(rt):
            buenos.add(st.get("stop_id", ""))
    return buenos


def _estaciones_desde_gtfs(url: str) -> list[dict]:
    tablas = _cargar_tablas(url)
    riel = _stops_riel_cable(tablas)  # set de stop_ids riel/cable, o None si no se pudo filtrar
    grupos: dict[str, list[tuple[float, float]]] = {}
    for f in tablas["stops.txt"]:
        if f.get("location_type") in ("2", "3", "4"):  # entradas/nodos, no andenes
            continue
        sid = f.get("stop_id", "")
        # el parent_station de un andén hereda el filtro riel/cable del andén
        if riel is not None and sid not in riel and f.get("parent_station", "") not in riel:
            continue  # servido solo por bus (Metroplús) → fuera
        try:
            lat, lon = float(f["stop_lat"]), float(f["stop_lon"])
        except (KeyError, ValueError):
            continue
        base = _norm_estacion(f.get("stop_name", ""))
        if base:
            grupos.setdefault(base, []).append((lat, lon))
    estaciones = [
        {"nombre": nombre, "linea": "",
         "lat": round(sum(la for la, _ in pts) / len(pts), 6),
         "lon": round(sum(lo for _, lo in pts) / len(pts), 6)}
        for nombre, pts in grupos.items()
    ]
    return sorted(estaciones, key=lambda e: e["nombre"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Regenera metro_estaciones.json desde GTFS (E09·S7).")
    ap.add_argument("--url", default=os.environ.get("METRO_GTFS_URL", _DEFAULT_URL))
    args = ap.parse_args()
    destino = os.path.join(_DATA_DIR, DATA_METRO_FILE)

    try:
        estaciones = _estaciones_desde_gtfs(args.url)
        if len(estaciones) < 15:
            raise ValueError(f"muy pocas estaciones ({len(estaciones)}) — GTFS sospechoso")
        doc = {
            "_meta": {"fuente": f"GTFS Metro de Medellín ({args.url})",
                      "convencion_coords": "lat/lon", "n": len(estaciones),
                      "generado_por": "scripts/build_metro.py (E09·T09.7.1)"},
            "estaciones": estaciones,
        }
        with open(destino, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"[build_metro] OK · {len(estaciones)} estaciones desde GTFS → {DATA_METRO_FILE}")
    except Exception as exc:
        # Fallback: conserva la semilla estática ya en disco.
        try:
            with open(destino, encoding="utf-8") as fh:
                previas = json.load(fh).get("estaciones", [])
        except Exception:
            previas = []
        print(f"[build_metro] FALLBACK ({type(exc).__name__}: {exc}). "
              f"Se conserva la lista estática ({len(previas)} estaciones) en {DATA_METRO_FILE}.")


if __name__ == "__main__":
    main()
