#!/usr/bin/env python
"""Backfill geográfico idempotente (E09 · T09.3.3).

Rellena coordenadas faltantes/sintéticas y precalcula las distancias `dist_<cat>_m` sobre los
inmuebles **ya indexados** en Chroma, **sin re-scrapear**. Es el ÚNICO script que escribe
coords + distancias (para no pisarse con otro backfill).

Cómo funciona, por inmueble del tenant:
  1. Lee su metadata actual con `col.get(... include=["metadatas"])` (no la reconstruye desde
     cero → conserva titulo/precio/imagenes/etc.).
  2. Resuelve coords: si faltan o son **sintéticas** (par 6.000123/-75.000456) o ≈0, las toma del
     centroide de su (zona, ciudad) con un **jitter determinista** por `inmueble_id` (±0.002°);
     si ya tenía coords reales, las respeta.
  3. Calcula `dist_metro_m` con haversine a la estación más cercana **solo** si su municipio tiene
     Metro (bandera `metro` del centroide); los municipios sin metro (Rionegro, La Ceja, El Retiro,
     Guatapé, Apartadó, Cartagena, Coveñas…) **no reciben** la clave → honestidad by design.
  4. Escribe **solo el delta** con `col.update` (chromadb 1.5.9 hace MERGE; una clave con valor
     `None` se ELIMINA — así se borran distancias obsoletas de forma determinista). No toca las
     demás claves.

Idempotente: una segunda corrida no produce ningún cambio (0 updates). Sin red.

Uso (desde backend/):
    python scripts/seed_geo.py
    python scripts/seed_geo.py --dry-run
    python scripts/seed_geo.py --tenant aquamarine
"""

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.rag import geo
from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client
from app.rag.geo_const import clave_geocache

# Par sintético que dejó el seed original (una coord "de mentira" a corregir).
_COORD_SINTETICA = (6.000123, -75.000456)
_JITTER_GRADOS = 0.002  # ±0.002° ≈ ±220 m: desempata inmuebles que comparten centroide.
_CHUNK = 100


def _es_sintetica_o_cero(lat, lon) -> bool:
    """True si la coord es la sintética del seed o ≈0 (placeholder), es decir NO confiable."""
    if lat is None or lon is None:
        return True
    if abs(lat - _COORD_SINTETICA[0]) < 1e-6 and abs(lon - _COORD_SINTETICA[1]) < 1e-6:
        return True
    return abs(lat) < 0.01 or abs(lon) < 0.01


def _jitter(lat: float, lon: float, inmueble_id: str) -> tuple[float, float]:
    """Desplazamiento determinista (±_JITTER_GRADOS) derivado del inmueble_id. Estable entre corridas."""
    h = hashlib.sha256(str(inmueble_id).encode("utf-8")).digest()
    dlat = ((h[0] << 8 | h[1]) / 65535 * 2 - 1) * _JITTER_GRADOS
    dlon = ((h[2] << 8 | h[3]) / 65535 * 2 - 1) * _JITTER_GRADOS
    return round(lat + dlat, 6), round(lon + dlon, 6)


def backfill(tenant: str, dry_run: bool = False) -> dict:
    estaciones = geo.cargar_metro()
    centroides = geo.cargar_centroides()
    col = get_chroma_client().get_or_create_collection(COLLECTION_NAME)

    res = col.get(where={"tenant_id": {"$eq": tenant}}, include=["metadatas"])
    ids = res.get("ids") or []
    metas = res.get("metadatas") or []

    stats = {"total": len(ids), "geocodificados": 0, "ya_tenian_coords": 0,
             "sin_coords": 0, "con_alguna_dist": 0, "actualizados": 0}

    upd_ids: list[str] = []
    upd_metas: list[dict] = []

    for _id, meta in zip(ids, metas):
        clave = clave_geocache(meta.get("zona"), meta.get("ciudad"))
        centroide = centroides.get(clave)

        lat, lon = meta.get("latitud"), meta.get("longitud")
        necesita_coords = _es_sintetica_o_cero(lat, lon)

        delta: dict = {}
        if necesita_coords and centroide:
            lat, lon = _jitter(centroide["lat"], centroide["lon"], _id)
            delta["latitud"], delta["longitud"] = lat, lon
            stats["geocodificados"] += 1
        elif not necesita_coords:
            stats["ya_tenian_coords"] += 1
        else:  # necesita coords pero no hay centroide para su (zona,ciudad)
            lat, lon = None, None
            stats["sin_coords"] += 1

        # POIs por categoría: solo metro (CORE); solo si el municipio tiene metro y hay coords.
        pois_por_cat: dict = {}
        if centroide and centroide.get("metro") and lat is not None:
            pois_por_cat["metro"] = estaciones

        nuevas_dist = geo.distancias_por_categoria(lat, lon, pois_por_cat)
        if nuevas_dist:
            stats["con_alguna_dist"] += 1

        # Delta de distancias: setea las nuevas; borra (None) las dist_* obsoletas que ya no aplican.
        prev_dist = {k for k in meta if k.startswith("dist_")}
        for k, v in nuevas_dist.items():
            if meta.get(k) != v:
                delta[k] = v
        for k in prev_dist - set(nuevas_dist):
            delta[k] = None  # None => Chroma elimina la clave (merge semantics, verificado)

        if delta:
            upd_ids.append(_id)
            upd_metas.append(delta)
            stats["actualizados"] += 1

    if upd_ids and not dry_run:
        for i in range(0, len(upd_ids), _CHUNK):
            col.update(ids=upd_ids[i:i + _CHUNK], metadatas=upd_metas[i:i + _CHUNK])

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill geográfico idempotente (E09).")
    ap.add_argument("--tenant", default=settings.DEFAULT_TENANT_ID)
    ap.add_argument("--dry-run", action="store_true", help="No escribe; solo reporta el delta.")
    args = ap.parse_args()

    stats = backfill(args.tenant, dry_run=args.dry_run)
    modo = "DRY-RUN (sin escribir)" if args.dry_run else "aplicado"
    print(f"[seed_geo] tenant={args.tenant} · {modo}")
    print(f"  total inmuebles     : {stats['total']}")
    print(f"  geocodificados      : {stats['geocodificados']}  (coords faltantes/sintéticas → centroide)")
    print(f"  ya tenían coords    : {stats['ya_tenian_coords']}")
    print(f"  sin centroide       : {stats['sin_coords']}")
    print(f"  con alguna dist_*   : {stats['con_alguna_dist']}")
    print(f"  actualizados (delta): {stats['actualizados']}")


if __name__ == "__main__":
    main()
