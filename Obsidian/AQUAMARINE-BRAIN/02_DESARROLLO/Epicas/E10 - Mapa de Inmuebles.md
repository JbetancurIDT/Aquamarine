---
tipo: epica
audiencia: dev
estado: completado
epica: E10
actualizado: 2026-07-24
tags: [area/desarrollo, comp/frontend, comp/rag, stack/react, estado/completado]
---

# E10 — Mapa de Inmuebles

> **En términos de negocio:** hasta ahora el inventario se veía como una **lista**. Con el mapa, Claudia y sus asesores ven **dónde** está cada propiedad sobre el territorio real, y el cliente recibe un **mapa compartible** de la propiedad que le interesa con lo que tiene alrededor (colegios, súper, clínicas, metro) y **cómo llegar** ("~8 min a pie al parque"). Además, un **mapa de calor de demanda** muestra en qué zonas están pidiendo más los leads, para orientar dónde conseguir inventario. Es el mismo dato de cercanía de [[E09 - Búsqueda por Proximidad Geográfica (Geo)]], pero **visual**.
> **Objetivo técnico:** dos superficies de mapa sobre **Leaflet + OpenStreetMap** (sin API key ni Google), alimentadas por las coordenadas que E09 dejó en Chroma (centroide de barrio): (a) una pantalla interna `/mapa` con todo el inventario como pines + heatmap de demanda; (b) una página **pública** `/mapa/propiedad/:codigo` con la propiedad, sus POIs cercanos y **rutas por calles** (cadena ORS→OSRM→recta). Se apoya en el mismo vocabulario `geo_const.CERCANIA_KEYS` y no acopla la búsqueda al ruteo.

> [!success] Estado: COMPLETADA y en `master` (2026-07-24)
> Las dos superficies (consola `/mapa` + pública `/mapa/propiedad/:codigo`) y el heatmap de demanda están **shipped y mergeados a `master`**. Decisiones: [[Decisiones (Decision Log)]] **D22** (mapa como épica propia) y **D23** (rutas ORS→OSRM→recta). Doc de feature en `mapa.md`. **Pendiente menor:** verificación visual (eyeball) del mapa y la ruta animada por el usuario; documentar el heatmap en `mapa.md` (tarea del Dev).

## Contexto para el agente
No es un agente nuevo ni toca a Aqua salvo por un **enlace** que ofrece en el chat (`[Abrir mapa](/mapa/propiedad/CODIGO)` / tarjeta `[[MAPA:codigo]]`). Depende **solo** de que los inmuebles tengan `latitud`/`longitud` en Chroma — que los tienen tras el backfill de E09 ([[E09 - Búsqueda por Proximidad Geográfica (Geo)]] / `geo.md`), **no** del código de búsqueda de E09. Reusa `PropertyCard`, la paleta de marca y `geo_const.CERCANIA_KEYS`.

### Principios del repo que se respetan
1. **Chroma es índice de solo lectura en runtime:** el mapa solo hace `col.get` (lee); las coords/distancias se escribieron offline en E09.
2. **100% OSM, sin Google:** tiles OpenStreetMap; ruteo ORS/OSRM (ambos OSM), línea recta como último recurso.
3. **Multitenant:** el endpoint filtra por `tenant_id`; los POIs son geografía pública.
4. **La búsqueda no depende del ruteo:** las rutas son solo visualización de la página por propiedad.

## Dependencias
- **Requiere:** E01 (Chroma + `PropertyCard`), E09 (coords + `dist_<cat>_m` + `lugares_cerca`).
- **Se integra con:** E04 (Aqua ofrece el enlace/tarjeta de mapa en el chat).
- **Bloquea:** nada (valor agregado de presentación).

---

## Sprints y tareas

### Sprint 1 — Mapa del inventario (`/mapa`) [CORE]
- [x] **T10.1.1** — Endpoint `GET /rag/inmuebles/mapa` + pantalla `/mapa`.
  - **Archivos:** `backend/app/api/rag.py`, `backend/tests/test_rag_mapa.py`, `frontend/src/pages/MapaPage.tsx`, `frontend/src/App.tsx`, `frontend/src/components/ConsolaNav.tsx`, `frontend/src/index.css`.
  - **Criterio:**
    - [x] `GET /rag/inmuebles/mapa` lee Chroma (`col.get`, filtro `tenant_id`), incluye **solo** inmuebles con `latitud`/`longitud` y devuelve ficha + las `dist_<cat>_m` presentes (vocabulario `geo_const.CERCANIA_KEYS`).
    - [x] `MapaPage.tsx`: `<MapContainer>` (Leaflet) centrado en Medellín + `<TileLayer>` OSM; un pin por inmueble con `<Popup>` que **reusa `PropertyCard`** + línea de cercanías aproximadas.
    - [x] Fix de íconos de marker con Vite (`?url` + `L.Icon.Default.mergeOptions`). Tests `test_rag_mapa.py` (solo-con-coords, incluye `dist_*`, caso vacío).

### Sprint 2 — Heatmap de demanda [CORE]
- [x] **T10.2.1** — Rampa de calor por demanda de leads por zona.
  - **Archivos:** `backend/app/api/rag.py` (campo `leads_zona`), `frontend/src/pages/MapaPage.tsx` (`CircleMarker` + leyenda).
  - **Criterio:**
    - [x] El endpoint agrega `leads_zona` por inmueble (conteo de leads cuya ubicación pedida cae en la zona, con match tolerante por área).
    - [x] `MapaPage.tsx` colorea un `CircleMarker` secuencial (gris→ámbar→naranja→rojo, rangos 0/1-2/3-4/5+) con **leyenda**.
    - [x] Nota honesta: la demanda es "por área" (tolerante), así que zonas grandes (p. ej. El Poblado) absorben más; los buckets 5+ lo reflejan.

### Sprint 3 — Mapa por propiedad + rutas (`/mapa/propiedad/:codigo`) [CORE]
- [x] **T10.3.1** — Página pública compartible con POIs y rutas por calles.
  - **Archivos:** `backend/app/api/rag.py` (`GET /rag/inmuebles/{codigo}/cerca`), `backend/app/api/geo.py` (`GET /geo/ruta`), `backend/app/core/config.py` (`ORS_API_KEY`/`ORS_URL`/`OSRM_URL`/`GEO_MODO_UMBRAL_M`), `backend/tests/test_rutas.py`, `frontend/src/pages/MapaPropiedadPage.tsx`, `frontend/src/components/RutaAnimada.tsx`, `backend/app/agent/prompts.py` (Aqua ofrece el enlace).
  - **Criterio:**
    - [x] `GET /rag/inmuebles/{codigo}/cerca` → ficha + `lugares_cerca` (nombre + distancia + lat/lon por POI).
    - [x] `GET /geo/ruta?from&to&modo` (`auto|caminando|carro`) → `{geometry, duration_min, distance_m, modo, aprox}` con cadena **ORS→OSRM público→línea recta**; **solo se cachean rutas ruteadas** (aprox=false).
    - [x] `MapaPropiedadPage.tsx` pinta pines por categoría; click en POI → **ruta animada** (`RutaAnimada`, leaflet-ant-path) + tiempo aproximado. Tests `test_rutas.py` (ORS/OSRM/recta mockeados).
    - [x] Aqua ofrece `[Abrir mapa](/mapa/propiedad/CODIGO)` / tarjeta `[[MAPA:codigo]]` en el chat.

---

## Definición de hecho (épica)
1. **Inventario en el territorio:** `/mapa` pinta todos los inmuebles con coords; el popup reusa `PropertyCard` y muestra cercanías aproximadas.
2. **Demanda visible:** los pines se colorean por `leads_zona` con leyenda (rojo = alta demanda).
3. **Propiedad compartible:** `/mapa/propiedad/:codigo` público muestra POIs cercanos y **traza la ruta por calles** al hacer click, con tiempo aproximado; funciona **sin `ORS_API_KEY`** (vía OSRM público) y cae a línea recta solo si ambos ruteadores fallan.
4. **Honestidad de precisión:** coords = centroide de barrio (con jitter); propiedades del mismo barrio quedan agrupadas — es esperado, no un bug.

Tests: `test_rag_mapa.py` + `test_rutas.py` (dentro de los ~228 backend en verde). Frontend validado con `npm run build` (tsc estricto) y a ojo.

## Fuera de alcance / roadmap
- Filtros en `/mapa` (tipo/zona/precio/cercanía) — hoy muestra todo.
- Clusterizar pines o dibujar el radio de cercanía al calibrar.
- **Tiempo peatonal exacto:** hoy se estima sobre OSRM-carro; requiere ORS con key o un OSRM perfil *foot* (misma frontera de Fase 2 que D21/D23).
- OSRM/ORS **self-hosted** para producción (el demo público de OSRM tiene límites y solo perfil carro).

## Decisiones asociadas — [[Decisiones (Decision Log)]]
- **D22** — Mapa como superficie propia de producto (esta épica) + endpoints `GET /rag/inmuebles/mapa` y `/{codigo}/cerca`.
- **D23** — Rutas solo en la página por propiedad, cadena de fallback ORS→OSRM→recta.

## Documentación del feature
`mapa.md` en la raíz del repo del producto (enlazado en la tabla "Documentación por feature" de `CLAUDE.md`). **Nota:** `mapa.md` aún no documenta el heatmap de demanda (`leads_zona`) — pendiente de que el Dev lo añada.
