Rol: eres el DEV de Aquamarine. Fix visual chico del mapa interactivo. Solo frontend. NO edites Obsidian/.

OBJETIVO: QUITAR el tiempo estimado de la ruta ("~X min a pie / en carro") — dejar SOLO la ruta (la
línea animada azul). Las distancias de los POIs (ej. "~400 m") se QUEDAN: eso es distancia, no tiempo.

En `frontend/src/pages/MapaPropiedadPage.tsx`:
1. **Rótulo de tiempo en el mapa (quitar):** elimina el `<Marker>` del punto medio con el `divIcon` que
   renderiza `${tiempoLabel(ruta)}` (~líneas 131-135) y la variable `const medio = …` (~línea 91) que solo
   lo alimenta. **CONSERVA** el `<RutaAnimada positions={ruta.geometry} color="#1d4ed8" />` (la línea).
2. **Panel lateral (~línea 155):** quita el ` — ${tiempoLabel(ruta)}`. Deja "Ruta a {sel.poi.nombre}"
   (puedes conservar los estados " — calculando…" y " — no se pudo calcular la ruta" para el feedback,
   pero SIN el tiempo cuando la ruta ya cargó).
3. **Limpieza:** elimina la función `tiempoLabel` (~líneas 44-46), que queda sin uso (evita el error de
   "unused" en el build). Los campos `duration_min`/`modo` del type `Ruta` pueden quedarse (el backend los
   sigue enviando; no estorban).

NO toques: los tooltips de distancia de los POIs (`poi.nombre · aprox(poi.dist_m)`), ni la ruta animada,
ni el endpoint `/geo/ruta` (el backend sigue devolviendo el tiempo; solo dejamos de mostrarlo).

VERIFICACIÓN: click en un POI → se traza la ruta azul **sin ningún rótulo de minutos** ni en el mapa ni en
el panel; las distancias de los POIs siguen visibles. `cd frontend && npm run build` en verde (sin unused).
