# Feature: Búsqueda por proximidad geográfica (Geo)

> Doc de feature (convención del repo). Índice en [CLAUDE.md](CLAUDE.md); aquí el detalle.
> Épica de origen: `Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md`.
> **Estado:** CORE v1 (categorías fijas) construido y en verde. Fuentes en vivo y el fallback por
> nombre propio son STRETCH (ver §Roadmap). Extiende el RAG ([scraper.md](scraper.md)) y el agente
> Aqua ([agent.md](agent.md)); no es un agente nuevo.

## Qué resuelve
El cliente busca con **lenguaje de la vida real**: *"un apartamento en Envigado cerca del metro"*,
*"que haya un D1 cerquita"*, *"algo cerca de la Clínica Las Américas"*. Aqua entiende la cercanía,
**filtra el inventario por proximidad** y responde con la distancia **aproximada** ("a ~600 m de una
estación") y con **honestidad** cuando en esa zona no hay lo pedido (p. ej. no hay metro en Rionegro
o Guatapé). v1 = **distancia lineal (haversine) radial en km**, sin tiempo de viaje.

## Cómo funciona
1. **Enriquecimiento offline (backfill).** `scripts/seed_geo.py` recorre los inmuebles ya indexados
   en Chroma, rellena `latitud`/`longitud` faltantes o sintéticas por el **centroide** de su
   `(zona, ciudad)` (con jitter determinista por `inmueble_id`) y precalcula, por haversine, la
   distancia al POI más cercano de cada categoría, guardándola como metadata **plana** `dist_<cat>_m`.
   Escribe **solo el delta** con `col.update` (Chroma es índice de solo-lectura en runtime; el
   enriquecimiento nunca ocurre en caliente). Es **idempotente** y no re-scrapea.
2. **Consulta por categoría (runtime).** La tool `buscar_inmuebles` gana `filtros.cerca_de` (una de 7
   categorías) y `filtros.radio_km`. `search.py` traduce eso a un filtro **DURO** en el `where` de
   Chroma: `{"dist_<cat>_m": {"$lte": radio_m}}`, ANDeado con `tenant_id`/`precio`. Un inmueble **sin**
   la clave (municipio sin metro, sin coords) **no matchea** por la semántica de `$lte` → honestidad
   gratis. La cercanía **no se relaja** en la escalera zona/tipo/precio.
3. **Respuesta del agente.** El system prompt enseña a Aqua a mapear frases → categoría, a comunicar
   la distancia **siempre aproximada** ("a ~600 m", "a pocos minutos"; **nunca** cifras exactas,
   "caminando" ni "cuadras") y la honestidad dura: el metro solo cubre el Valle de Aburrá; si no hay,
   lo dice con calidez y ofrece alternativas (ampliar distancia, cambiar de zona, quitar el requisito).

## Categorías y claves de metadata
Fuente única de verdad: `app/rag/geo_const.py` (`CERCANIA_KEYS`). Nada de claves a mano en otros archivos.

| Categoría (`cerca_de`) | Clave en Chroma | Radio default | Disparadores (frases) |
|---|---|---|---|
| `metro` | `dist_metro_m` | 1.5 km | estación, metro, tranvía, metrocable |
| `supermercado` | `dist_super_m` | 1.5 km | D1, Ara, Éxito, Carulla, Jumbo, mercado, tienda |
| `centro_comercial` | `dist_mall_m` | 2.5 km | mall, C.C., centro comercial |
| `colegio` | `dist_colegio_m` | 1.5 km | colegio, escuela |
| `universidad` | `dist_universidad_m` | 3.0 km | universidad, EAFIT, UPB |
| `parque` | `dist_parque_m` | 1.5 km | parque, zona verde |
| `clinica` | `dist_clinica_m` | 2.5 km | clínica, hospital, EPS, centro médico |

`radio_km` del lead **sobrescribe** el default, pero solo **hacia arriba**: el radio efectivo nunca
baja del **piso duro de 1.5 km** (ver Precisión).

## Fuentes de datos
- **Metro de Medellín** (`app/rag/data/metro_estaciones.json`): estaciones de líneas A/B, tranvía y
  metrocables. En CORE v1 es una **semilla hardcodeada** (coords públicas); regenerable desde el
  **GTFS oficial** en STRETCH.
- **Centroides de barrio/municipio** (`app/rag/data/centroides_zona.json`): un centroide por cada
  `(zona, ciudad)` del inventario, con bandera `metro`. En CORE v1 es semilla hardcodeada; regenerable
  con **Nominatim** en STRETCH.
- **POI de categorías** (super, mall, colegio, universidad, parque, clínica): en CORE v1 solo se
  precalcula `metro`; el resto se poblará desde **OpenStreetMap/Overpass** en STRETCH. Decisión de
  producto: **100% OSM + GTFS**, sin Google Places.

## Precisión y límites honestos
- **Centroide de barrio, no de unidad.** Las coords del inmueble son el centroide administrativo de su
  `(zona, ciudad)` (error de cientos de m a ~1-2 km); **todos los inmuebles de una misma zona comparten
  coords → comparten `dist_<cat>_m`**. La proximidad afirmable es a nivel de **sector**, por eso el
  **radio mínimo honesto es 1.5 km** y Aqua **nunca** da cifras exactas.
- **Ciudades sin metro.** Rionegro, La Ceja, El Retiro, Guatapé, Apartadó, Cartagena, Coveñas, etc.
  **no reciben `dist_metro_m`** (por diseño). El `$lte` sobre clave ausente ya garantiza la exclusión.
- **Cobertura OSM parcial (STRETCH).** Un `dist_super_m` ausente significará "OSM no lo tiene", **no**
  "no hay D1"; el prompt evita que Aqua niegue categóricamente.
- **Fuera de alcance (Fase 2):** tiempo de viaje / isócronas (rutas reales), PostGIS, ciudades fuera de
  Antioquia más allá de los pocos casos costeros ya en el inventario.

## Cómo correrlo
```bash
docker compose up -d                                   # Chroma (:8002) ya con los inmuebles indexados
cd backend
.venv/bin/python scripts/seed_geo.py                   # backfill idempotente (coords + dist_metro_m)
.venv/bin/python scripts/seed_geo.py --dry-run         # reporta el delta sin escribir
# En runtime, POST /chat: "apartamento en Envigado cerca del metro, hasta 1.200M" → Aqua usa cerca_de
```

## Tests (offline, sin red ni SDK)
`backend/tests/test_geo.py` (estilo `test_rag_search.py`): haversine (±0.5%, simetría, cero);
`distancias_por_categoria` omite categorías vacías/None; `InmuebleIn.metadata` omite `dist_*` None y
emite `int` (y `document` no cambia); `cerca_de` → `$lte` correcto en el `where`; **clave ausente
excluye**; `radio_km` sobrescribe y respeta el piso 1.5 km; honestidad sin metro; y el backfill de
`seed_geo` **idempotente que no pierde `titulo`/`precio`/`imagenes`** (colección falsa que replica el
MERGE de chromadb 1.5.9).
```bash
cd backend && .venv/bin/python -m pytest -q            # 167 tests en verde (145 previos + 22 de geo)
```

## Config
- `chromadb==1.5.9` **pinneado** en `backend/requirements.txt`: el backfill depende de que `col.update`
  haga **MERGE** (claves omitidas se conservan; valor `None` elimina la clave).
- Sin variables de entorno nuevas en CORE v1. En STRETCH se añadirán `METRO_GTFS_URL`, `OVERPASS_URL`,
  `NOMINATIM_URL`/`NOMINATIM_USER_AGENT`, `GEO_DEFAULT_RADIO_KM`.

## Archivos
`app/rag/geo_const.py` (vocabulario: `CERCANIA_KEYS`/`ETIQUETA_CAT`/`clave_geocache`),
`app/rag/geo.py` (haversine + distancias + lectores), `app/rag/data/{metro_estaciones,centroides_zona}.json`,
`app/rag/search.py` (`_radio_m`/`_cercania_cond` + `where` duro), `app/agent/tools.py`
(`cerca_de`/`radio_km` + `_frase_cercania`), `app/agent/prompts.py` (sección "Búsqueda por cercanía"),
`app/schemas/inmueble.py` (7 campos `dist_*_m`), `scripts/seed_geo.py` (backfill), `tests/test_geo.py`.

## Roadmap (STRETCH, no bloquea el CORE)
- **Datos en vivo** (`build_metro.py`/`build_poi.py`/`build_geocache.py`): regenerar la semilla desde
  GTFS/Overpass/Nominatim; poblar las 6 categorías no-metro.
- **Fallback por nombre propio** (`cerca_de_lugar`): "cerca de EAFIT / la Clínica Las Américas" →
  geocode en vivo (cacheado, 1 req/s) + ranking por haversine sobre el inventario.
- **Hook de ingesta:** que las fichas nuevas nazcan con coords + `dist_*` (enriquecimiento falla-suave).
