Rol: eres el DEV de Aquamarine (lee AGENTES.md en la raíz). Estás en la rama feat/e09-geo.
Editas código; NO edites nada bajo Obsidian/ (el cerebro).

Requisito: CORE (Handoffs 1-3) completo y auditado. Esto es STRETCH: reemplaza los datos
HARDCODEADOS del Sprint 2 por fuentes en vivo, regenerables.

Entorno: Chroma en localhost:8002. Usa backend/.venv/bin/python. Este handoff SÍ usa RED
(Overpass / GTFS del Metro / Nominatim).

Sigue la épica (sección Sprint 7):
  "Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md"

TAREA DE ESTE HANDOFF — SOLO Sprint 7 (T09.7.1 build_metro, T09.7.2 build_poi, T09.7.3 build_geocache).

Guardarraíles:
- SOLO stdlib (urllib/zipfile/csv/io/json); NO agregues dependencias nuevas.
- build_metro.py: descarga el GTFS del Metro (METRO_GTFS_URL por env/param), dedup por andén;
  FALLBACK a la lista estática del Sprint 2 si la descarga falla.
- build_poi.py: UNA query Overpass GET con el bbox del Valle de Aburrá (6.06,-75.70,6.48,-75.28),
  `out center tags`; normaliza a {categoria,nombre,brand,lat,lon}; dedup por lat/lon; cachea el
  JSON crudo (gitignored); reintento con backoff ante 429/504.
- build_geocache.py: geocodifica los pares (zona,ciudad) distintos con Nominatim (1 req/s,
  User-Agent propio, countrycodes=co); marca granularidad y valle_aburra; idempotente.
- Regenera los JSON de app/rag/data/. DESPUÉS vuelve a correr seed_geo.py (backfill) para
  recomputar dist_* con los POI reales. No rompas los tests.

VERIFICACIÓN OBSERVABLE: conteos reales de POI por categoría (build_poi), nº de estaciones
(build_metro), nº de pares geocodificados (build_geocache), y un dist_metro_m de un inmueble de
Medellín recomputado con datos reales vs el hardcodeado.

Al terminar: resumen + PARA.
