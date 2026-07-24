# Feature: Mapa de inmuebles

> Doc de feature (convención del repo). Índice en [CLAUDE.md](CLAUDE.md); aquí el detalle.
> Feature de consola interna. Depende solo de que los inmuebles tengan `latitud`/`longitud` en
> Chroma (los tienen tras el backfill de [geo.md](geo.md)); no del código de E09.

## Qué es / para qué
Una pantalla **`/mapa`** de la consola interna que muestra **todo el inventario** como **pines sobre
un mapa de OpenStreetMap**. Al hacer click en un pin, un **popup** con la previsualización de la
imagen + datos del inmueble (reusando `PropertyCard`) y, si existen, sus **distancias por cercanía**
("Metro ~600 m · Súper ~300 m…"). Sirve para ver el inventario en el territorio y **calibrar a ojo la
búsqueda por proximidad** de E09.

## Cómo funciona
- **Backend — `GET /rag/inmuebles/mapa`** (`app/api/rag.py`): lee de Chroma
  `col.get(where={"tenant_id": …}, include=["metadatas"])`, incluye **solo** los inmuebles con
  `latitud` y `longitud`, y devuelve por cada uno `{inmueble_id, titulo, tipo, zona, ciudad, precio,
  habitaciones, banos, area_m2, imagen_principal, url_fuente, latitud, longitud}` **+ las
  `dist_<cat>_m` que existan** (vocabulario de `geo_const.CERCANIA_KEYS`). No recibe filtros (v1).
- **Frontend — `frontend/src/pages/MapaPage.tsx`** (ruta `/mapa` en `App.tsx`, link "Mapa" en
  `ConsolaNav`): al montar hace `apiClient.get('/rag/inmuebles/mapa')` y pinta un `<Marker>` por
  inmueble sobre un `<MapContainer>` (Leaflet) centrado en Medellín (~6.24, -75.58, zoom 12) con un
  `<TileLayer>` OSM. El `<Popup>` **reusa `<PropertyCard>`** para que se vea igual que en el resto de
  la app, y añade la línea de cercanías aproximadas.

## Stack
- **Leaflet** + **react-leaflet** (`leaflet`, `react-leaflet`, `@types/leaflet`), tiles de
  **OpenStreetMap** (sin API key). Se importa `leaflet/dist/leaflet.css`.
- **Fix de íconos de marker con Vite:** los assets (`marker-icon`, `marker-icon-2x`, `marker-shadow`)
  se importan con `?url` y se registran vía `L.Icon.Default.mergeOptions({...})`, si no los pines
  salen rotos (bug clásico de Leaflet con bundlers).
- Estilo consistente con la consola: header + `<ConsolaNav active="/mapa" />`, paleta de marca
  (`--champ`, `--ink`, `--card`, `--line`, `--gray`…) y fuente Newsreader en el título. Un pequeño
  override en `index.css` (`.mapa-popup`) deja que la `PropertyCard` mande dentro del popup.

## Precisión (importante)
Las coordenadas son el **centroide del barrio/municipio** (con jitter determinista por inmueble),
**no la dirección exacta** — el inventario no trae direcciones exactas. Por eso propiedades del mismo
barrio quedan **agrupadas cerca**. Es esperado y correcto (no es un bug a "arreglar").

## Cómo correrlo
```bash
docker compose up -d                                   # Chroma (:8002) con el inventario indexado
cd backend && .venv/bin/uvicorn app.main:app --reload  # API :8000 (GET /rag/inmuebles/mapa)
cd frontend && npm install && npm run dev              # :5173 → abrir /mapa
```

## Tests
`backend/tests/test_rag_mapa.py` (TestClient, Chroma mockeado): el endpoint devuelve solo los
inmuebles con coords e incluye las `dist_*` presentes; caso vacío. El frontend se valida con
`npm run build` (tsc estricto) y a ojo en `/mapa`.

## Archivos
`app/api/rag.py` (endpoint), `tests/test_rag_mapa.py`, `frontend/src/pages/MapaPage.tsx`,
`frontend/src/App.tsx` (ruta), `frontend/src/components/ConsolaNav.tsx` (link), `frontend/src/index.css`
(`.mapa-popup`), `frontend/package.json` (leaflet/react-leaflet). Reusa `components/PropertyCard.tsx`.

## Mapa interactivo por propiedad + rutas (`/mapa/propiedad/:codigo`)
Página **pública y compartible** (link que ofrece Aqua en el chat tras "¿qué hay cerca?"): muestra el
inmueble + los servicios cercanos como pines por categoría; al hacer click en un servicio se dibuja la
**ruta por calles** con una **animación de flujo** (leaflet-ant-path) y el **tiempo aproximado** ("~8 min a pie").
- **Datos:** `GET /rag/inmuebles/{codigo}/cerca` → ficha + `lugares_cerca` (nombre + distancia + lat/lon por POI).
- **Rutas:** `GET /geo/ruta?from_lat&from_lon&to_lat&to_lon&modo` (`auto|caminando|carro`) devuelve
  `{geometry:[[lat,lon]…], duration_min, distance_m, modo, aprox}`. **Cadena de ruteo:**
  1. **ORS** (OpenRouteService) si hay `ORS_API_KEY` — perfiles peatonal/carro reales.
  2. **OSRM público** (`OSRM_URL`, sin key) — ruta por calles; perfil driving. `caminando` reusa la
     geometría/distancia ruteadas pero estima el tiempo a pie.
  3. **Línea recta** (`aprox=true`) — solo si ORS y OSRM fallan.
  Solo se cachean las rutas **ruteadas** (aprox=false); la recta no (un fallo transitorio no queda fijo).
- **Frontend:** `pages/MapaPropiedadPage.tsx` + `components/RutaAnimada.tsx` (leaflet-ant-path). Config
  `ORS_API_KEY`/`ORS_URL`/`OSRM_URL`/`GEO_MODO_UMBRAL_M`. Tests: `tests/test_rutas.py` (ORS/OSRM/recta mockeados).

> [!note] Fuentes de ruteo (infra)
> El **demo público de OSRM** (`router.project-osrm.org`) es para pruebas/demo (tiene límites de uso, no
> producción pesada) y solo tiene perfil **carro**. Para rutas **peatonales reales** o sin límites: setea una
> `ORS_API_KEY` (capa gratis de OpenRouteService) o monta un **OSRM self-hosted** (swappea `OSRM_URL`). La
> línea recta queda solo como último recurso. 100% OSM, sin Google.

## Pendiente / roadmap
- Sin filtros por ahora (por tipo/zona/precio/cercanía) — se agregan después.
- Podría clusterizar pines o colorearlos por temperatura/tipo; y dibujar un radio al calibrar cercanía.
- Tiempo peatonal EXACTO (hoy estimado sobre OSRM-carro): requiere ORS con key o un OSRM perfil foot.
