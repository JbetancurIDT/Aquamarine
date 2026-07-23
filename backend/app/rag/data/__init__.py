"""Datos geográficos versionados de E09 (sin red, deterministas).

- `metro_estaciones.json` — estaciones del Metro de Medellín (líneas A/B, tranvía, metrocables).
- `centroides_zona.json` — centroide (lat/lon) de cada (zona, ciudad) del inventario, con
  bandera `metro` (True solo en municipios cubiertos por el sistema Metro del Valle de Aburrá).

Convención de coords: `lat`/`lon` (ver `app.rag.geo_const`). Los lectores viven en `app.rag.geo`.
En E09·S7 (STRETCH) estos archivos se regeneran desde GTFS/Overpass/Nominatim; aquí son semilla.
"""
