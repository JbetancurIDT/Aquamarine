Rol: eres el DEV de Aquamarine (lee AGENTES.md en la raíz). Feature nuevo: **pantalla de MAPA de
inmuebles**. Editas código; NO edites nada bajo Obsidian/.

Rama: `feat/mapa-inmuebles` (créala desde `master` cuando E09 esté mergeado, o desde `feat/e09-geo`
si arrancas antes). El mapa solo depende de que los inmuebles tengan `latitud`/`longitud` en Chroma
—que ya los tienen tras el backfill de E09—, no del código de E09.

Objetivo: una pantalla `/mapa` que muestre TODAS las propiedades del inventario como **pines sobre un
mapa de OpenStreetMap**, integrada a la consola interna (nav + paleta de marca). Al hacer click en un
pin, un **popup con la previsualización de la imagen** + datos del inmueble. Sirve para ver el
inventario en el territorio y **calibrar la búsqueda por cercanía**.

Entorno: Chroma en localhost:8002 (colección `inmuebles`, ~50 inmuebles con `latitud`/`longitud` e
`imagen_principal`). Backend FastAPI :8000, frontend React+TS (Vite) :5173. Usa `backend/.venv`.

BACKEND
- Nuevo endpoint `GET /rag/inmuebles/mapa` en `backend/app/api/rag.py`. Devuelve todos los inmuebles
  del tenant que tengan coords: lista de {inmueble_id, titulo, tipo, zona, ciudad, precio, habitaciones,
  banos, area_m2, imagen_principal, url_fuente, latitud, longitud, **y las `dist_<cat>_m` que existan**}.
  Sácalos de Chroma: `get_chroma_client()` + `col.get(where={"tenant_id":{"$eq":settings.DEFAULT_TENANT_ID}},
  include=["metadatas"])`; incluye SOLO los que tengan latitud y longitud. Reusa el patrón del router
  existente (`app/api/rag.py`).
- Test mínimo del endpoint (TestClient) en `backend/tests/`, al estilo de los existentes. Deja todo en verde.

FRONTEND
- Instala `leaflet` + `react-leaflet` (`npm i leaflet react-leaflet`) e importa `'leaflet/dist/leaflet.css'`.
- Arregla el bug clásico de íconos de marker de Leaflet con Vite (los pines salen rotos): configura
  `L.Icon.Default` con los assets de `leaflet/dist/images` (marker-icon, marker-icon-2x, marker-shadow)
  importados con `?url`, o `L.Icon.Default.mergeOptions({...})`.
- Nueva página `frontend/src/pages/MapaPage.tsx` + ruta `/mapa` en `App.tsx`. Sigue el layout de las
  otras pantallas de consola: header con título + `<ConsolaNav active="/mapa" />`, con la **paleta de
  marca** (variables CSS `--champ`, `--ink`, `--card`, `--line`, `--gray`…) y la fuente Newsreader para
  el título. Mira DashboardPage/PipelinePage como referencia de estilo.
- Agrega el link a la nav: en `frontend/src/components/ConsolaNav.tsx` añade `{ to: '/mapa', label: 'Mapa' }`
  al arreglo `LINKS`.
- Datos: al montar, `apiClient.get('/rag/inmuebles/mapa')` (usa el cliente axios de `src/api/client.ts`).
  Tipa la respuesta extendiendo el `type Inmueble` de `PropertyCard.tsx` con `latitud`/`longitud`/`dist_*`.
- Mapa: `<MapContainer>` centrado en Medellín (~6.24, -75.58), zoom ~12, con `<TileLayer>` OSM
  (`url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"`, attribution "© OpenStreetMap contributors").
- Un `<Marker>` por inmueble en `[latitud, longitud]`. En su `<Popup>`, **REUSA el componente
  `<PropertyCard inmueble={...} />`** (`frontend/src/components/PropertyCard.tsx`) para la previsualización
  de imagen + título + precio + zona + link a la ficha → el popup queda consistente con el resto de la app.
- BONUS (útil para el objetivo de calibración): si el inmueble trae `dist_<cat>_m`, muéstralas en el
  popup ("Metro ~600 m · Súper ~300 m · Colegio ~200 m"), aproximadas (m si <1000, km si ≥1000). Así se
  ve a simple vista qué tan cerca está de cada categoría.

Nota de datos: las coords son el **CENTROIDE del barrio** (con jitter determinista), NO la dirección
exacta → propiedades del mismo barrio quedarán agrupadas cerca. Es esperado (no hay direcciones
exactas en el inventario). No lo "arregles".

DOC (convención del repo): crea `mapa.md` en la raíz (qué es, el endpoint, la ruta `/mapa`, el stack
Leaflet/OSM, y la nota de precisión por centroide) y añade su fila a la tabla "Documentación por
feature" de `CLAUDE.md`.

Mantenlo enfocado: una pantalla sólida y consistente con la consola, **sin filtros por ahora** (se
agregan después). Al terminar: corre back + front y confírmame que `/mapa` muestra ~50 pines, que el
popup muestra la imagen vía `PropertyCard`, que el link "Mapa" aparece en la nav, y que los tests están
en verde.
