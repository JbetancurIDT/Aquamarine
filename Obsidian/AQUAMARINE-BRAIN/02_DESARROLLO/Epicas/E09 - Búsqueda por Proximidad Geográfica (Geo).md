---
tipo: epica
audiencia: dev
estado: pendiente
epica: E09
actualizado: 2026-07-22
tags: [area/desarrollo, comp/rag, comp/agente, stack/chroma, stack/claude, estado/pendiente]
---

# E09 — Búsqueda por Proximidad Geográfica (Geo)

> **En términos de negocio:** el cliente ya no solo busca "un apartamento en Envigado hasta $800M", sino con **lenguaje de la vida real**: *"una casa cerca de una estación de metro"*, *"que haya un D1 cerquita"*, *"algo cerca de la Clínica Las Américas"*. Aqua entiende la cercanía y filtra el inventario por proximidad, respondiendo con la distancia aproximada ("a pocos minutos de una estación") y con **honestidad** cuando en esa zona no hay lo que piden (p. ej. no hay metro en Rionegro o Guatapé).
> **Objetivo técnico:** enriquecer el inventario en Chroma con **distancias precalculadas** (haversine, en metros) al POI más cercano por categoría, guardadas como metadata **plana** (`dist_<cat>_m`), y enseñarle a la tool `buscar_inmuebles` a filtrar por cercanía. v1 = **distancia lineal (haversine) radial en km**, sin tiempo de viaje. Dos caminos: (a) **categorías fijas** (metro, supermercado, centro comercial, colegio, universidad, parque, clínica) vía filtro numérico en el `where` de Chroma; (b) **fallback en vivo por nombre propio** (geocode 1 vez + haversine local sobre el inventario).

## Contexto para el agente

Es una extensión del **agente de ventas Aqua** (ver [[E03 - Agente IA (Claude)]]) y del **RAG** (ver [[E01 - Ingesta RAG (Firecrawl + Chroma)]]): no es un agente nuevo. Se apoya en el patrón ya existente de filtros numéricos duros en `search.py` (`precio`/`habitaciones` → `where` de Chroma) y en que `InmuebleIn.metadata` **ya descarta claves `None`** (metadata plana sin nulos). Decisión que origina esta épica: [[Decisiones (Decision Log)]] **D21** (nueva).

### GROUND TRUTH de datos (verificado hoy sobre Chroma — condiciona todo el diseño)
- La colección `inmuebles` tiene **50 inmuebles** (tenant Aquamarine).
- **Solo 2/50 traen lat/lng y una es sintética** (`6.000123, -75.000456`, del seed) → **partimos sin coordenadas reales** (≈0).
- **Solo 3/50 traen `direccion`** (una es "N/A") → no se puede geocodificar por dirección exacta.
- **50/50 traen `zona` y `ciudad`**; 48/50 en Antioquia. Distribución: Medellín 19, Envigado 11, Rionegro 6, Santa Fe de Antioquia 2, Apartadó 2, y 1 c/u en La Ceja, Sabaneta, Girardota, El Retiro, Guatapé, Jardín, Sopetrán, San Jerónimo, + Cartagena 1 y Coveñas 1.
- **Consecuencia clave:** la geocodificación se apoya en `(zona, ciudad, departamento, "Colombia")` a granularidad de **centroide de barrio/municipio** (error de cientos de m a ~1-2 km). Solo ~**32/50** caen en el **Valle de Aburrá** (donde hay metro). El oriente (Rionegro, La Ceja, El Retiro, Guatapé), Urabá (Apartadó) y la costa (Cartagena, Coveñas) **no tienen metro** → Aqua debe responder con **honestidad**, nunca inventar cercanía.

### Decisiones de producto ya tomadas (no se cuestionan; se diseña para ellas) — [[Decisiones (Decision Log)]] D21
- **Alcance "cerca de X" = ambos:** categorías fijas **y** fallback en vivo por nombre propio.
- **Cómo se mide "cerca" en v1:** distancia lineal en km (**haversine**, radial). Sin tiempo de viaje/isócronas.
- **Fuente de POI:** 100% **OpenStreetMap/Overpass**, más el **GTFS oficial del Metro de Medellín** para estaciones. Sin Google Places. Se aceptan huecos de cobertura.
- **Cobertura:** foco Valle de Aburrá / Antioquia.
- **Sin PostGIS** (sobreingeniería a este tamaño). El cálculo es haversine puro precalculado offline.

### Principios del repo que se respetan
1. **Canales desacoplados:** el geo no sabe de dónde vino el lead.
2. **Postgres escribe / Chroma es índice de solo lectura en runtime:** las `dist_<cat>_m` se escriben **offline** (backfill `col.update`, igual que el `upsert` de ingesta), nunca en caliente.
3. **Agente como orquestador:** Aqua decide categoría vs nombre propio y compone la respuesta honesta.
4. **Multitenant:** los POI son **geografía pública** (sin `tenant_id`); las `dist_<cat>_m` viven en el inmueble, que ya lleva `tenant_id`.

## Dependencias
- **Requiere:** E01 (ingesta RAG + Chroma: colección `inmuebles`, `InmuebleIn`, `search.py`) y E03 (agente Aqua: tool `buscar_inmuebles`, system prompt, orquestador).
- **Se integra con:** E04 (el chat del lead es el surface: el lead pide cercanía en `/chat` y ve las tarjetas con la distancia).
- **Bloquea:** nada (es valor agregado; suma mucho en el pitch de lujo — "cerca del colegio de los niños", "cerca de mi EPS").

---

## Sprints y tareas

> Orden correcto: **contrato → datos → enriquecimiento → búsqueda → agente → tests/docs**. Para caber en ~0.5 día, el **CORE v1** usa **datos hardcodeados creíbles** (estaciones de metro + centroides de zona); las fuentes en vivo (Overpass/GTFS/Nominatim) y el fallback por nombre propio son **STRETCH** regenerables después. La secuencia resuelve los huecos de integración detectados en revisión (vocabulario de claves unificado, contrato de archivos, esquema de tool único, radio honesto).

### Sprint 1 — Contrato compartido [CORE]
Fuente única de verdad de nombres de clave/categoría. **Desbloquea a todos los sprints** (sin esto, enriquecimiento y búsqueda divergen y el filtro nunca matchea → "no hay nada cerca" siendo mentira).

- [ ] **T09.1.1** — `geo_const.py`: vocabulario congelado de categorías y claves.
  - **Objetivo:** una sola definición de los 7 slugs de categoría, sus claves de metadata y sus etiquetas legibles, importable por enriquecimiento, schema, search y tools.
  - **Archivos:** crear `backend/app/rag/geo_const.py`.
  - **Criterio:**
    - [ ] `CERCANIA_KEYS` con los **7 slugs congelados** → clave: `metro`→`dist_metro_m`, `supermercado`→`dist_super_m`, `centro_comercial`→`dist_mall_m`, `colegio`→`dist_colegio_m`, `universidad`→`dist_universidad_m`, `parque`→`dist_parque_m`, `clinica`→`dist_clinica_m`.
    - [ ] `ETIQUETA_CAT` con la frase legible por categoría ("una estación de metro", "un supermercado", …).
    - [ ] `clave_geocache(zona, ciudad)` → clave normalizada `"{zona}|{ciudad}"` (minúsculas, sin acentos, misma regla que `_norm` de `search.py`). **Sin** sufijo `antioquia|co`.
    - [ ] Se decide y documenta que **todos** los JSON/coords usan `lat`/`lon` (no `lng`), y el nombre exacto de cada archivo de datos.
  - **Prompt sugerido:** "Crea `backend/app/rag/geo_const.py` con `CERCANIA_KEYS` (7 slugs congelados metro/supermercado/centro_comercial/colegio/universidad/parque/clinica → dist_metro_m/dist_super_m/dist_mall_m/dist_colegio_m/dist_universidad_m/dist_parque_m/dist_clinica_m), `ETIQUETA_CAT` (frase legible por categoría) y `clave_geocache(zona,ciudad)` que normaliza sin acentos ni casing (misma regla que `_norm` de app/rag/search.py) y devuelve `'{zona}|{ciudad}'` sin sufijos. Esta es la ÚNICA fuente de verdad de esos nombres; nada se codifica a mano en otros archivos. Usa `lat`/`lon` como convención de coords en todo el proyecto."

### Sprint 2 — Datos hardcodeados [CORE]
Datos creíbles sin red, para que el CORE funcione en 0.5 día. Las fuentes en vivo entran en STRETCH.

- [ ] **T09.2.1** — Semilla de estaciones de metro + centroides de zona (sin red).
  - **Objetivo:** ~30 estaciones de metro/tranvía/metrocable con coords públicas y estables, y tabla `_COORDS_ZONA` (~25 pares distintos del inventario) como centroides de barrio/municipio.
  - **Archivos:** crear `backend/app/rag/data/__init__.py`, `backend/app/rag/data/metro_estaciones.json`, y la tabla `_COORDS_ZONA` embebida en el script de enriquecimiento (`backend/scripts/seed_geo.py`, ver Sprint 3) o en `backend/app/rag/data/centroides_zona.json`.
  - **Criterio:**
    - [ ] `metro_estaciones.json` con `{ "_meta": {...}, "estaciones": [{"nombre","linea","lat","lon"}] }`, **~30-40** estaciones (líneas A, B, tranvía, metrocables: p. ej. Poblado, San Antonio, Acevedo, San Javier, Oriente), orden alfabético estable.
    - [ ] `_COORDS_ZONA` con los ~25 pares distintos del inventario (El Poblado `(6.209,-75.567)`, Laureles `(6.245,-75.593)`, Belén `(6.232,-75.607)`, Envigado `(6.169,-75.582)`, Sabaneta `(6.151,-75.616)`, Itagüí `(6.172,-75.611)`, Las Palmas `(6.157,-75.530)`, Rionegro `(6.155,-75.374)`, La Ceja `(6.028,-75.432)`, El Retiro `(6.062,-75.502)`, Guatapé `(6.233,-75.159)`, Santa Fe de Antioquia `(6.557,-75.827)`, San Jerónimo `(6.443,-75.729)`, Sopetrán `(6.500,-75.746)`, Jardín `(5.598,-75.819)`, Girardota `(6.379,-75.446)`, Apartadó `(7.883,-76.628)`, Cartagena `(10.399,-75.551)`, Coveñas `(9.406,-75.680)`, …).
    - [ ] Sin llamadas de red; datos deterministas y versionados (commiteados).
  - **Prompt sugerido:** "Crea el paquete `backend/app/rag/data/` (con `__init__.py`) y `backend/app/rag/data/metro_estaciones.json` con ~30 estaciones reales del Metro de Medellín (líneas A, B, tranvía, metrocables) en formato `{'_meta':{...},'estaciones':[{'nombre','linea','lat','lon'}]}`, orden alfabético. Añade una tabla `_COORDS_ZONA` (centroides de barrio/municipio) con los pares (zona,ciudad) del inventario del seed. Sin red, todo hardcodeado y commiteado."

### Sprint 3 — Enriquecimiento (haversine → metadata) [CORE]
Rellena coords faltantes y precalcula las `dist_<cat>_m` sobre los 50 inmuebles ya en Chroma, sin re-scrapear.

- [ ] **T09.3.1** — Extender `InmuebleIn` con los 7 `dist_<cat>_m`.
  - **Objetivo:** que el esquema emita las distancias en `.metadata` respetando metadata plana sin `None`.
  - **Archivos:** editar `backend/app/schemas/inmueble.py`.
  - **Criterio:**
    - [ ] 7 campos `int | None = None` bajo el bloque `# --- Geo ---` (usar los nombres de `CERCANIA_KEYS`).
    - [ ] Las 7 claves se añaden al dict `bruto` de la property `metadata`; la comprensión final que filtra `None` **no se toca** → si una distancia es `None`, la clave se omite.
    - [ ] `.document` (texto embebido) **no cambia** (las distancias son señal numérica de filtro, no semántica).
  - **Prompt sugerido:** "En `backend/app/schemas/inmueble.py`, bajo `# --- Geo ---`, agrega 7 campos `dist_metro_m/dist_super_m/dist_mall_m/dist_colegio_m/dist_universidad_m/dist_parque_m/dist_clinica_m: int | None = None` (nombres de `app/rag/geo_const.CERCANIA_KEYS`). Añádelos al dict `bruto` de la property `metadata`. No cambies la comprensión final que descarta None ni la property `document`."

- [ ] **T09.3.2** — `geo.py`: haversine + distancias por categoría (funciones puras).
  - **Objetivo:** matemática de distancia y lectores de datos, sin dependencias externas (`math`/`json`).
  - **Archivos:** crear `backend/app/rag/geo.py`.
  - **Criterio:**
    - [ ] `haversine_m(lat1,lon1,lat2,lon2) -> float` (metros, radio 6_371_000); acierta ±0.5% contra una distancia conocida del Valle de Aburrá.
    - [ ] `dist_poi_mas_cercano_m(lat,lon,pois) -> int | None` (None si lat/lon None **o** lista vacía; si no, `round(min(...))`).
    - [ ] `distancias_por_categoria(lat,lon,pois_por_cat) -> dict[str,int]` que **nunca** incluye una clave con valor `None`.
    - [ ] Lectores `cargar_metro()`, `cargar_centroides()` desde `app/rag/data/`; reusa `clave_geocache` de `geo_const`.
  - **Prompt sugerido:** "Crea `backend/app/rag/geo.py` con `haversine_m` (math puro, radio 6_371_000), `dist_poi_mas_cercano_m(lat,lon,pois)->int|None` (None si coords None o pois vacío; si no round(min haversine)), y `distancias_por_categoria(lat,lon,pois_por_cat:dict)->dict[str,int]` que devuelve dist_<cat>_m solo para categorías con dato (jamás None). Añade lectores de los JSON de app/rag/data/ y reusa clave_geocache de geo_const. Sin dependencias externas."

- [ ] **T09.3.3** — `seed_geo.py`: backfill idempotente de coords + distancias.
  - **Objetivo:** un **único** script que rellena coords y escribe `dist_<cat>_m` en Chroma vía `col.update` (evita el backfill duplicado detectado en revisión).
  - **Archivos:** crear `backend/scripts/seed_geo.py` (patrón de `backend/scripts/seed_demo.py`).
  - **Criterio:**
    - [ ] `col.get(where={"tenant_id":{"$eq":tenant}}, include=["metadatas"])`; por inmueble **copia** su metadata (no la reconstruye desde cero → no pierde `titulo/precio/imagenes`).
    - [ ] Rellena `latitud/longitud` desde `_COORDS_ZONA` (con jitter determinista ±0.002° por `inmueble_id`) **solo si** faltan o son sintéticas (detecta el par `(6.000123,-75.000456)` y `abs(lat)<0.01 or abs(lon)<0.01`).
    - [ ] Calcula `dist_<cat>_m` con `geo.distancias_por_categoria` (estaciones de metro + POIs semilla). **Municipios sin metro no reciben `dist_metro_m`** (honestidad by design).
    - [ ] Reconstruye el dict completo (metadata previa − `dist_*` obsoletas + nuevas) y hace `col.update(ids, metadatas)` por chunks. **Verifica primero si la versión instalada de chromadb hace merge o replace** en `update` y ajústate para borrado determinista de claves.
    - [ ] **Idempotente:** dos corridas seguidas dejan idéntica metadata. Sin red. Flags `--dry-run`, `--tenant`. Imprime stats `{total, geocodificados, ya_tenian_coords, sin_coords, con_alguna_dist}`.
  - **Prompt sugerido:** "Crea `backend/scripts/seed_geo.py` (patrón de seed_demo.py). Con `get_chroma_client().get_or_create_collection(COLLECTION_NAME)` y `settings.DEFAULT_TENANT_ID`: por cada inmueble del tenant copia su metadata, rellena latitud/longitud desde `_COORDS_ZONA` (jitter determinista por inmueble_id) solo si faltan o son sintéticas (par 6.000123/-75.000456 o ≈0), calcula geo.distancias_por_categoria (estaciones de metro + POIs semilla), NO asignes dist_metro_m a municipios sin metro, reconstruye el dict completo quitando dist_* obsoletas y haz col.update por chunks. Idempotente, sin red, flags --dry-run/--tenant, imprime stats. Verifica antes si chromadb hace merge o replace en update."

- [ ] **T09.3.4** — Pin de `chromadb` en `requirements.txt`.
  - **Objetivo:** que el comportamiento merge/replace de `col.update` sea reproducible entre entornos.
  - **Archivos:** editar `backend/requirements.txt`.
  - **Criterio:** [ ] `chromadb==<versión instalada>` pinneado; test de backfill verifica que sobreviven `titulo/precio/imagenes`.
  - **Prompt sugerido:** "Pinnea `chromadb` a la versión instalada en backend/requirements.txt (`pip show chromadb`), para fijar el comportamiento de col.update."

### Sprint 4 — Búsqueda (filtro de cercanía duro) [CORE]
La cercanía es un **requisito espacial literal** del lead → filtro **duro** (no se relaja como zona/tipo).

- [ ] **T09.4.1** — `_cercania_cond` + `_radio_m` en `search.py`.
  - **Objetivo:** traducir `cerca_de` a `{"dist_<cat>_m": {"$lte": radio_m}}` en el `where` de Chroma, junto a `precio`/`habitaciones`.
  - **Archivos:** editar `backend/app/rag/search.py` (importa `CERCANIA_KEYS`/`ETIQUETA_CAT` de `geo_const`).
  - **Criterio:**
    - [ ] `buscar_inmuebles(query, {"cerca_de":"metro"})` inyecta `{"dist_metro_m":{"$lte":radio_m}}` ANDeado con `tenant_id` en `_where_duro`.
    - [ ] Inmuebles **sin** la clave (Rionegro/sin-coords) **no matchean** → honestidad gratis por la semántica de `$lte`.
    - [ ] `radio_km` del lead sobrescribe el default por categoría; **radio efectivo nunca < 1500 m** (piso honesto por el error de centroide de barrio; ver Riesgos).
    - [ ] Firma pública de `buscar_inmuebles` **sin cambios** (`cerca_de`/`radio_km` viajan dentro de `filtros`).
    - [ ] **Sin "Nivel 4 / radio ampliado ×2":** para un filtro espacial duro, **vacío + mensaje honesto** es la respuesta correcta (no se ensancha el radio en silencio).
  - **Prompt sugerido:** "En backend/app/rag/search.py importa CERCANIA_KEYS/ETIQUETA_CAT de app/rag/geo_const. Agrega `_radio_m(filtros,cat)` (radio_km del lead o default por categoría: metro/super/parque/colegio=1.5, mall/clinica=2.5, universidad=3.0; piso duro 1500 m) y `_cercania_cond(filtros)` que devuelve `{'dist_<cat>_m':{'\$lte':radio_m}}` o None si no soportada. Extiende `_where_duro` para ANDear la cercanía. Es filtro DURO: no se relaja en la escalera zona/tipo/precio; inmuebles sin la clave no matchean. NO agregues nivel de radio ampliado."

### Sprint 5 — Agente (tool + prompt) [CORE]
Aqua aprende a mapear frases a categorías y a hablar de distancia aproximada con honestidad.

- [ ] **T09.5.1** — Tool `cerca_de`/`radio_km` + distancia en el texto.
  - **Objetivo:** que Claude ponga la categoría en `filtros.cerca_de` y que la línea del inmueble muestre "a ~600 m de una estación de metro".
  - **Archivos:** editar `backend/app/agent/tools.py`.
  - **Criterio:**
    - [ ] `input_schema.filtros` gana `cerca_de` (enum de 7 slugs de `CERCANIA_KEYS`) y `radio_km` (number), con descripciones que enseñen el mapeo de frases ("estación/tranvía/metrocable"→metro; "D1/Ara/Éxito/Carulla/Jumbo/mercado"→supermercado; "mall/C.C."→centro_comercial; "clínica/hospital/EPS"→clinica).
    - [ ] `_frase_cercania(inm, cat)` lee `dist_<cat>_m` y formatea "[A ~600 m de … — aprox.]" (m si <1000, km si ≥1000); `_formatear_linea` la concatena.
    - [ ] Encabezado **honesto** cuando se pidió `cerca_de` y la tool vino **vacía**: instruye a Aqua a NO afirmar "no existe nada" y a ofrecer ampliar distancia / cambiar de zona / quitar el requisito (recordando que el metro solo cubre el Valle de Aburrá).
  - **Prompt sugerido:** "En backend/app/agent/tools.py añade a filtros.properties `cerca_de` (enum: metro,supermercado,centro_comercial,colegio,universidad,parque,clinica) y `radio_km` (number), con descripción que enseñe el mapeo de frases (D1/Ara/Éxito→supermercado, estación/tranvía→metro, etc.). Agrega `_frase_cercania(inm,cat)` (importa CERCANIA_KEYS/ETIQUETA_CAT de geo_const) y pásale la categoría a `_formatear_linea`. Cuando cerca_de esté presente y no haya resultados, devuelve un texto honesto que NO afirme que no existe nada y ofrezca ampliar/cambiar zona/quitar requisito."

- [ ] **T09.5.2** — System prompt: vocabulario, honestidad y distancia aproximada.
  - **Objetivo:** enseñar a Aqua las 7 categorías + sinónimos, el matiz de distancia aproximada y la honestidad geográfica dura.
  - **Archivos:** editar `backend/app/agent/prompts.py`.
  - **Criterio:**
    - [ ] Nueva sección "## Búsqueda por cercanía" con las 7 categorías y sus disparadores (incl. cadenas de súper).
    - [ ] Regla de distancia **aproximada**: "a **unos ~600 m** de la estación", "a **pocos minutos** de un Éxito"; **prohibido** cifras exactas ("a 340 m"), "caminando" o "a X cuadras".
    - [ ] Honestidad geográfica **dura**: el **metro solo existe en el Valle de Aburrá**; si piden "cerca del metro" en Rionegro/La Ceja/El Retiro/Guatapé/Cartagena/Coveñas → decirlo con calidez, no inventar.
    - [ ] Regla: `cerca_de` + tool vacía ≠ "no existe"; ofrecer alternativas.
    - [ ] Sin fechas ni IDs (no invalida el prompt caching). Los tests de contenido del prompt (si existen) siguen verdes.
  - **Prompt sugerido:** "Inserta en backend/app/agent/prompts.py una sección '## Búsqueda por cercanía' que enseñe a Aqua a usar filtros.cerca_de con las 7 categorías y sus sinónimos (D1/Ara/Éxito/Carulla/Jumbo→supermercado; estación/tranvía/metrocable→metro; clínica/hospital/EPS→clinica), a comunicar SIEMPRE la distancia como aproximada ('~600 m', 'pocos minutos', nunca cifra exacta ni 'caminando'/'cuadras'), y la regla dura de honestidad: el metro solo cubre el Valle de Aburrá; si la zona no lo tiene, decirlo con calidez y no inventar. Sin fechas ni IDs para no invalidar la caché."

### Sprint 6 — Tests + documentación [CORE]
- [ ] **T09.6.1** — Tests offline (Chroma mockeado, sin red ni SDK).
  - **Objetivo:** blindar el CORE sin gastar APIs; los **145 tests actuales siguen verdes**.
  - **Archivos:** crear `backend/tests/test_geo.py` (y `test_geo_categoria.py` si conviene separar), estilo de `backend/tests/test_rag_search.py` + `conftest.py`.
  - **Criterio:**
    - [ ] `haversine_m` determinista ±0.5% contra una distancia conocida; simétrica; punto consigo mismo = 0.
    - [ ] `distancias_por_categoria` **no** emite claves para categorías vacías ni con lat/lon None.
    - [ ] `InmuebleIn.metadata` omite `dist_*` None y emite los presentes como `int`; `.document` no cambia (regresión).
    - [ ] `cerca_de="metro"` produce el `$lte` correcto en el `where`; inmueble **sin** `dist_metro_m` no aparece; `radio_km` sobrescribe default y respeta el piso 1500 m.
    - [ ] `test_categoria_sin_metro_es_honesto`: inmuebles del oriente (sin `dist_metro_m`) no se devuelven como "cerca del metro"; el texto habilita la respuesta honesta.
    - [ ] Backfill (`seed_geo`) con `col.get` mockeado (uno con coords, uno sin): el primero recibe `dist_*`, el segundo no; segunda corrida idempotente; no pierde `titulo/precio/imagenes`.
  - **Prompt sugerido:** "Crea backend/tests/test_geo.py (estilo test_rag_search.py: monkeypatch de get_chroma_client, helper _pack, sin red ni SDK). Cubre: haversine ±0.5% + simetría + cero; distancias_por_categoria omite vacías/None; InmuebleIn.metadata omite dist_* None y emite int; cerca_de→\$lte correcto en el where; clave ausente excluye; radio_km sobrescribe y respeta piso 1500; honestidad sin metro; backfill de seed_geo idempotente que no pierde metadata."

- [ ] **T09.6.2** — `geo.md` + fila en `CLAUDE.md`.
  - **Objetivo:** documentar el feature según la convención de docs por feature.
  - **Archivos:** crear `geo.md` (raíz del repo del producto); editar `CLAUDE.md` (tabla "Documentación por feature").
  - **Criterio:**
    - [ ] `geo.md` con: qué resuelve, cómo funciona (enriquecimiento offline + consulta categoría + fallback nombre-propio), tabla de categorías→`dist_*_m`, fuentes (GTFS/OSM/Nominatim), precisión y límites honestos (centroide de barrio, radio mínimo, cobertura OSM parcial, ciudades sin metro), cómo correrlo (`python scripts/seed_geo.py`, tests) y config.
    - [ ] Fila nueva en `CLAUDE.md`: `| Búsqueda por proximidad geográfica (E09) | [geo.md](geo.md) | Cercanía haversine: categorías fijas (dist_*_m en Chroma) + fallback nombre-propio; tool cerca_de |`.
  - **Prompt sugerido:** "Crea geo.md en la raíz del repo del producto con: qué resuelve, cómo funciona, tabla categoría→dist_*_m, fuentes (GTFS Metro / OSM Overpass / Nominatim), precisión y límites honestos, cómo correrlo (scripts/seed_geo.py, pytest tests/test_geo.py), config. Añade su fila a la tabla 'Documentación por feature' de CLAUDE.md."

### Sprint 7 — Datos en vivo (Overpass/GTFS/Nominatim) [STRETCH]
Reemplaza los datos hardcodeados del Sprint 2 por fuentes reales regenerables. No bloquea el CORE.

- [ ] **T09.7.1** — `build_metro.py`: estaciones desde el GTFS oficial.
  - **Objetivo:** generar `metro_estaciones.json` real (dedup por andén, filtro riel/cable).
  - **Archivos:** crear `backend/scripts/build_metro.py`.
  - **Criterio:** [ ] descarga GTFS (`METRO_GTFS_URL` por env/param, **fallback** a la lista estática del Sprint 2 si falla); lee `stops.txt` con `zipfile`+`csv`; deduplica por nombre normalizado promediando andenes; ~30-40 estaciones; orden estable; sin nuevas dependencias.
  - **Prompt sugerido:** "Crea backend/scripts/build_metro.py (stdlib: urllib/zipfile/csv/io/json). Descarga el GTFS del Metro de Medellín desde METRO_GTFS_URL (env/param, fallback a la lista estática de metro_estaciones.json si falla), lee stops.txt, deduplica estaciones por nombre normalizado (quita ' - Plataforma N','(Sur)','Norte') promediando lat/lon, y regenera app/rag/data/metro_estaciones.json. Orden alfabético. Sin nuevas dependencias."

- [ ] **T09.7.2** — `build_poi.py`: POI del Valle de Aburrá vía Overpass.
  - **Objetivo:** generar `poi_valle_aburra.json` (super, mall, colegio, universidad, parque, salud) con una sola query.
  - **Archivos:** crear `backend/scripts/build_poi.py`, `backend/app/rag/data/poi_valle_aburra.json` (+ `_overpass_raw.json` gitignored).
  - **Criterio:** [ ] una query Overpass GET (bbox `6.06,-75.70,6.48,-75.28`, `out center tags;`) para las 6 categorías vía Overpass; para cadenas usa `brand` OR `name` y deduplica por `(lat,lon)` a 5 decimales; normaliza a `{categoria,nombre,brand,lat,lon}`; `_meta.conteos` por categoría (~1.500-2.000 POI: supers≈511, salud≈263, universidades≈143); reintento backoff ante 429/504; cachea el JSON crudo.
  - **Prompt sugerido:** "Crea backend/scripts/build_poi.py (stdlib). Ejecuta una query Overpass GET (bbox 6.06,-75.70,6.48,-75.28, out center tags) para shop=supermarket→super, shop=mall→mall, amenity=school→colegio, amenity=university|college→universidad, leisure=park→parque, amenity=hospital|clinic→salud, más una pasada por brand/name de supermercado. Usa center para ways/relations, dedup por lat/lon a 5 decimales, normaliza a {categoria,nombre,brand,lat,lon}, escribe app/rag/data/poi_valle_aburra.json con _meta.conteos y cachea el JSON crudo en _overpass_raw.json (gitignored). Reintento backoff ante 429/504. Sin nuevas dependencias."

- [ ] **T09.7.3** — `build_geocache.py`: geocodificar pares (zona,ciudad) con Nominatim.
  - **Objetivo:** reemplazar `_COORDS_ZONA` hardcodeada por centroides reales de Nominatim (offline, no en caliente).
  - **Archivos:** crear `backend/scripts/build_geocache.py`, `backend/app/rag/data/geocache.json`.
  - **Criterio:** [ ] extrae de Chroma los ~15-30 pares distintos; geocodifica con Nominatim (`format=json&limit=1&countrycodes=co`, User-Agent propio, sleep ≥1.1 s), fallback a solo-ciudad; marca `granularidad` (`barrio`|`municipio`) y `valle_aburra` (bool según bbox); clave `clave_geocache(zona,ciudad)`; idempotente (no re-geocodifica pares cacheados). Documenta precisión = centroide de barrio/municipio.
  - **Prompt sugerido:** "Crea backend/scripts/build_geocache.py (stdlib). Lee de Chroma los pares distintos (zona,ciudad) del tenant, geocodifica cada uno con Nominatim ('{zona}, {ciudad}, Antioquia, Colombia', fallback '{ciudad}, ...', respetando 1 req/s y User-Agent Aquamarine/1.0), escribe app/rag/data/geocache.json con clave clave_geocache(zona,ciudad) y valor {lat,lon,granularidad,valle_aburra,query} marcando valle_aburra según bbox 6.06/-75.70/6.48/-75.28. Idempotente. Precisión = centroide de barrio/municipio."

### Sprint 8 — Fallback en vivo por nombre propio [STRETCH]
Segundo caso de uso: "cerca de la Clínica Las Américas / EAFIT / Parque Lleras". Requiere dueño del `geocode` en vivo (cacheado, rate-limit).

- [ ] **T09.8.1** — Config + `geocode_vivo` (Nominatim + caché persistente + rate-limit).
  - **Objetivo:** geocodificar un nombre propio **una vez**, con caché en `geocache.json` re-escribible, User-Agent, timeout y 1 req/s.
  - **Archivos:** editar `backend/app/core/config.py` (`NOMINATIM_URL`, `NOMINATIM_USER_AGENT`, `OVERPASS_URL`, `METRO_GTFS_URL`, `GEO_DEFAULT_RADIO_KM`); añadir `geocode_vivo(nombre)` a `backend/app/rag/geo.py`.
  - **Criterio:** [ ] `geocode_vivo(nombre) -> (lat,lon) | None`; caché persistente (los nombres populares se resuelven una vez); 1 sola geocodificación por consulta (nunca por inmueble); inyectable para tests (sin red).
  - **Prompt sugerido:** "Añade a backend/app/core/config.py las settings NOMINATIM_URL/NOMINATIM_USER_AGENT/OVERPASS_URL/METRO_GTFS_URL/GEO_DEFAULT_RADIO_KM. En backend/app/rag/geo.py agrega `geocode_vivo(nombre)->tuple[float,float]|None` que consulta Nominatim con caché persistente en geocache.json, User-Agent, timeout y rate-limit 1 req/s. Debe ser inyectable/mockeable para tests offline."

- [ ] **T09.8.2** — `buscar_por_lugar` + routing `cerca_de_lugar` en la tool.
  - **Objetivo:** rankear el inventario por haversine a un punto geocodificado; enrutarlo desde la tool.
  - **Archivos:** editar `backend/app/rag/search.py`, `backend/app/agent/tools.py`, `backend/app/agent/prompts.py`.
  - **Criterio:**
    - [ ] `buscar_por_lugar(nombre, filtros=None, k=3, radio_km=None)` devuelve dict `{estado, punto, resultados, descartados_sin_coords}` con `estado ∈ {ok, lugar_no_encontrado, sin_coords}`; usa `col.get` + `_where_duro` (respeta precio/hab); excluye sin-coords y los cuenta; ordena ascendente; marca `coincidencia="cercana"` + `motivo="a ~X km de <lugar>"`.
    - [ ] Tool: `filtros.cerca_de_lugar` (string), **excluyente** con `cerca_de`. Routing en `ejecutar_buscar_inmuebles`: `codigo` > `cerca_de_lugar` > `cerca_de` > `query/filtros`.
    - [ ] Cada `estado` produce texto honesto (lugar no ubicado → pedir referencia alterna, no negar inventario).
    - [ ] Prompt: cuándo usar `cerca_de_lugar` (nombre propio) vs `cerca_de` (categoría).
  - **Prompt sugerido:** "En backend/app/rag/search.py añade `buscar_por_lugar(nombre,filtros=None,k=3,radio_km=None)` que geocodifica con geo.geocode_vivo (inyectable), trae inmuebles con col.get + _where_duro, calcula haversine desde el punto a cada (latitud,longitud), excluye/cuenta los sin coords, ordena por distancia y devuelve {estado,punto,resultados,descartados_sin_coords} con estados ok/lugar_no_encontrado/sin_coords y motivo 'a ~X km de <lugar>'. En tools.py agrega filtros.cerca_de_lugar (excluyente con cerca_de) y enruta codigo>cerca_de_lugar>cerca_de>query, con textos honestos por estado. En prompts.py enseña a distinguir nombre propio (cerca_de_lugar) de categoría (cerca_de)."

- [ ] **T09.8.3** — Tests del fallback + conversaciones demo.
  - **Objetivo:** blindar el fallback y hacer la demo creíble.
  - **Archivos:** crear `backend/tests/test_geo_fallback.py`; editar `backend/scripts/seed_demo.py`.
  - **Criterio:**
    - [ ] Tests (geocode y Chroma `col.get` mockeados): rankea por cercanía; `lugar_no_encontrado`; inmueble sin coords excluido y contado; todo-sin-coords; respeta `precio_max`; `radio_km` recorta; handler produce texto honesto.
    - [ ] `seed_demo.py`: 2 leads que ejerciten cercanía (uno "cerca del metro"/D1 en el Valle de Aburrá con inmueble real p. ej. `9907677`; otro "cerca de EAFIT"/"Clínica Las Américas" con `9718612`) + un intercambio de honestidad "en esa zona no hay metro" (Guatapé). Revisar que `_calcular_esperados` siga cuadrando.
  - **Prompt sugerido:** "Crea backend/tests/test_geo_fallback.py (mock de geocode y col.get, sin red) cubriendo ranking por cercanía, lugar_no_encontrado, sin-coords excluido/contado, todo-sin-coords, respeto de precio, radio_km y texto honesto. En backend/scripts/seed_demo.py agrega 2 leads de cercanía (metro/D1 con 9907677; EAFIT/Clínica Las Américas con 9718612) y un intercambio honesto 'no hay metro' para Guatapé, reutilizando _msg_recomendacion/_CONV_*; ajusta _calcular_esperados si cambia el total."

### Sprint 9 — Hook de ingesta [STRETCH]
- [ ] **T09.9.1** — Enriquecimiento falla-suave en `ingest.py` (fichas nuevas nacen con geo).
  - **Objetivo:** que fichas futuras del scraping se indexen ya con coords + `dist_*`, sin degradar la ingesta core.
  - **Archivos:** editar `backend/app/rag/ingest.py`; añadir `enriquecer_inmueble(inmueble, centroides, pois)` a `backend/app/rag/geo.py`.
  - **Criterio:** [ ] carga centroides/POIs **una vez** al inicio de `ingest()`; entre validación Pydantic y upsert, llama `enriquecer_inmueble` envuelto en try/except que solo imprime `[geo-skip]` y continúa (nunca aborta ni cuenta en `MAX_ERRORES_SEGUIDOS`).
  - **Prompt sugerido:** "En backend/app/rag/ingest.py carga geo (centroides + POIs) una vez al inicio de ingest(). En el loop, entre la validación Pydantic y el upsert, llama geo.enriquecer_inmueble(inmueble,...) envuelto en try/except que solo imprime [geo-skip] y continúa. No cambies MAX_ERRORES_SEGUIDOS. Falla-suave: la ficha se indexa igual sin dist_* si algo peta."

---

## Definición de hecho (épica)

Escenario end-to-end que debe funcionar (CORE v1):

1. **Categoría — metro:** un lead abre `/chat` y escribe *"un apartamento en Envigado cerca del metro, hasta $1.200M"*. Aqua llama `buscar_inmuebles` con `filtros: {ciudad/zona, precio_max: 1200000000, cerca_de: "metro"}`, devuelve inmuebles reales del Valle de Aburrá con la **distancia aproximada** en la tarjeta ("a **~600 m** de una estación") y **excluye** los que no tienen `dist_metro_m`.
2. **Categoría — supermercado:** *"que haya un D1 cerca"* → `cerca_de: "supermercado"`; Aqua muestra opciones y, con humildad, no niega categóricamente si OSM no tiene un D1 en el radio.
3. **Honestidad geográfica:** un lead de **Guatapé/Rionegro** pide "cerca del metro" → la tool viene **vacía** y Aqua responde con calidez *"por esa zona no hay metro cercano; ¿te sirve en el área metropolitana, donde sí hay?"*, **sin inventar**.
4. **Nombre propio (STRETCH):** *"algo cerca de la Clínica Las Américas / EAFIT"* → `cerca_de_lugar`; Aqua geocodifica el lugar una vez, rankea el inventario por haversine y dice *"a ~1.8 km de EAFIT (aprox.)"*; si no ubica el lugar, pide una referencia alterna sin negar inventario.

Los **145 tests backend** actuales siguen verdes; los nuevos tests de geo pasan sin gastar APIs.

## Riesgos y decisiones abiertas

1. **Precisión de centroide vs. radio honesto (dura).** Las coords del inmueble son el **centroide administrativo del barrio/municipio** (verificado: El Poblado → error de cientos de m a ~1-2 km), y **todos los inmuebles de una misma (zona,ciudad) comparten coords → comparten `dist_metro_m`**. La proximidad afirmable es a nivel de **sector, no de unidad**. → **Radio mínimo honesto = 1.5 km (piso duro), default 2 km**; ignorar cualquier `radio_km` del lead menor. Copy de Aqua obligatorio: "en un sector con estación cerca", "a pocos minutos"; **prohibido** cifras exactas, "caminando" o "a X cuadras".
2. **Cobertura OSM parcial (D1 ~30%).** Un `dist_super_m` ausente significa "OSM no lo tiene", **no** "no hay D1". Aqua no debe negar categóricamente; el prompt lo cubre. Se aceptan huecos (decisión del dueño).
3. **Ciudades sin metro.** Rionegro, La Ceja, El Retiro, Guatapé, Apartadó, Cartagena, Coveñas → sin `dist_metro_m` **por diseño**. El `$lte` sobre clave ausente ya garantiza la exclusión; el prompt + `test_categoria_sin_metro_es_honesto` verbalizan la honestidad.
4. **Rate-limit Nominatim (1 req/s).** Solo afecta el fallback en vivo (STRETCH): mitigado con **caché persistente**, User-Agent identificable y **1 geocodificación por consulta** (nunca por inmueble). Los pares (zona,ciudad) del inventario se geocodifican **offline**.
5. **`col.update` merge vs replace en chromadb (abierta).** Verificar el comportamiento de la versión instalada antes del backfill y **pinnear `chromadb`** para reproducibilidad; test que confirme que sobrevive la metadata previa (`titulo/precio/imagenes`).
6. **Un solo backfill.** `seed_geo.py` es el **único** script que escribe coords + distancias (se descarta duplicar la lógica en otro script) para no pisarse.

## Fuera de alcance (Fase 2)
- **Tiempo de viaje / isócronas** (OpenRouteService): "a 10 min en carro del metro". Requiere routing real; queda para Fase 2.
- **Google Places** como fuente de POI (se usa 100% OSM + GTFS).
- **PostGIS** / índices espaciales (sobreingeniería a 50 inmuebles; haversine precalculado basta).
- **Ciudades fuera de Antioquia** (más allá de los pocos casos costeros ya en el inventario, que quedan sin metro por diseño).
- **`col.get` sin bounding-box:** a escala de miles de inmuebles el ranking en Python del fallback dejaría de ser instantáneo → mover a filtro por bbox en el `where` antes del haversine (nota futura, no v1).

## Documentación del feature
Al construirlo, crea `geo.md` en la raíz del repo del producto (esqueleto en T09.6.2) y enlázalo en la tabla "Documentación por feature" de `CLAUDE.md` (convención de docs por feature).

## Propuesta de entrada al Decision Log (D21)

| # | Fecha | Decisión | Por qué | Consecuencia |
|---|---|---|---|---|
| D21 | 2026-07-22 | **Búsqueda por proximidad geográfica en v1 = haversine radial en km (sin tiempo de viaje), POI 100% OSM/Overpass + GTFS del Metro, con ambos scopes (categorías fijas + fallback por nombre propio)** | El lead pide cercanía en lenguaje natural ("cerca del metro", "un D1 cerca", "cerca de la Clínica Las Américas"); haversine precalculado es instantáneo, sin costo de APIs de rutas ni PostGIS, y encaja con el patrón de filtros numéricos ya existente en Chroma. Partimos sin coords reales (2/50), así que se geocodifica por centroide de (zona,ciudad) | Nueva épica **[[E09 - Búsqueda por Proximidad Geográfica (Geo)]]**. Se enriquece el inventario con `dist_<cat>_m` (metadata plana en Chroma, se omite si no hay dato); `search.py` filtra cercanía como requisito **duro** (clave ausente = no matchea = honestidad gratis); la tool `buscar_inmuebles` gana `cerca_de`/`radio_km`. Radio mínimo honesto **1.5 km** (precisión = centroide de barrio); el metro solo cubre el Valle de Aburrá → Aqua es honesto cuando no hay. **Tiempo de viaje/isócronas (OpenRouteService), Google Places y ciudades fuera de Antioquia = Fase 2.** Doc en `geo.md` |
