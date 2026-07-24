Rol: eres el DEV de Aquamarine (lee AGENTES.md). Feature grande: **mapa interactivo compartible por
propiedad, con servicios cercanos y RUTAS animadas + tiempo**. Rama nueva `feat/mapa-interactivo-rutas`
(desde la rama con el mapa base y `lugares_cerca` — handoff-8 — integrados). Editas código; NO Obsidian/.
Puedes hacerlo en 2 PASADAS con checkpoint: (1) backend routing + endpoint; (2) página + animación + chat.

OBJETIVO: cuando el lead pregunta "¿qué hay cerca?", Aqua da la lista Y le ofrece un **link a un mapa
interactivo público** de esa propiedad. Ahí ve el inmueble + todos los servicios cercanos (súper,
colegios, universidades, parques, clínicas, C.C., metro); al elegir un servicio, se dibuja la **ruta
estilo Google Maps** (siguiendo calles) con el **tiempo aproximado caminando o en carro** rotulado, y la
ruta tiene una **animación de flujo** (tipo corriente eléctrica / progreso hacia el lugar) en bucle
infinito, elegante y no invasiva.

Depende de: el mapa base (`/mapa`, react-leaflet) y `geo.lugares_cerca` (handoff-8, POIs cercanos con
nombre+distancia). Extiende `lugares_cerca` para que cada POI también devuelva `lat`/`lon` (los necesita
el mapa para pintar el pin y trazar la ruta).

═══════════ PASADA 1 — BACKEND (routing + datos por propiedad) ═══════════

A) ROUTING PROXY — `GET /geo/ruta` (nuevo router `app/api/geo.py`, o dentro de rag):
   Params: `from_lat, from_lon, to_lat, to_lon, modo` (auto|caminando|carro; default auto).
   - `modo=auto` → caminando si haversine < `GEO_MODO_UMBRAL_M` (default 1800 m), si no carro.
   - Fuente de rutas: **OpenRouteService Directions** (OSM, sin Google; alineado con la decisión de
     E09). POST `https://api.openrouteservice.org/v2/directions/{perfil}/geojson` con
     `{"coordinates":[[from_lon,from_lat],[to_lon,to_lat]]}` y header `Authorization: <ORS_API_KEY>`;
     `perfil` = `foot-walking` (caminando) | `driving-car` (carro). De la respuesta saca la geometría
     (`features[0].geometry.coordinates`, en [lon,lat] → conviértela a [lat,lon] para Leaflet), la
     duración (`properties.summary.duration` seg → min) y la distancia (m).
   - **Fallback robusto (clave para la demo):** si `ORS_API_KEY` no está o ORS falla, devuelve una
     ruta en LÍNEA RECTA (`[[from],[to]]`), `distance_m` = haversine, `duration_min` estimado
     (caminando ~80 m/min, carro ~420 m/min urbano), y `aprox: true`. Así el mapa SIEMPRE funciona.
   - Cachea por (coords redondeadas, perfil) — las rutas son estáticas. Respeta límites/errores sin
     tumbar el server. Respuesta: `{geometry:[[lat,lon]…], duration_min, distance_m, modo, aprox}`.

B) DATOS POR PROPIEDAD — `GET /rag/inmuebles/{codigo}/cerca`:
   - `obtener_inmueble_por_codigo(codigo)` → coords + campos de la ficha. Si no hay/ sin coords: 404 claro.
   - Reusa `geo.lugares_cerca(lat, lon)` (extendido con lat/lon por POI) → `{cat:[{nombre,dist_m,lat,lon}]}`
     omitiendo categorías vacías.
   - Devuelve `{inmueble:{codigo,titulo,tipo,precio,zona,ciudad,imagen_principal,url_fuente,latitud,
     longitud}, lugares:{...}}`.

C) CONFIG (`app/core/config.py`): `ORS_API_KEY: str = ""` (opcional), `ORS_URL` (default el de arriba),
   `GEO_MODO_UMBRAL_M: int = 1800`. Documenta que sin key el routing cae al fallback recto.

CHECKPOINT PASADA 1: `GET /geo/ruta?...` devuelve geometría + tiempo (con o sin key → fallback);
`/rag/inmuebles/<codigo>/cerca` devuelve inmueble + lugares con coords. Tests en verde.

═══════════ PASADA 2 — FRONTEND (página pública + animación + chat) ═══════════

D) PÁGINA PÚBLICA `/mapa/propiedad/:codigo` (nueva `pages/MapaPropiedadPage.tsx` + ruta en App.tsx):
   - Pública (sin ConsolaNav; header mínimo con marca), es un link COMPARTIBLE (como /chat).
   - Fetch `/rag/inmuebles/:codigo/cerca`. Centra en la propiedad. Pin del inmueble DISTINTO (ícono de
     casa/champagne). Un pin por POI, por categoría (color o emoji: 🛒 súper, 🎓 univ, 🏫 colegio,
     🌳 parque, 🏥 clínica, 🛍️ C.C., 🚇 metro). Panel/lista lateral (o inferior en móvil) con los
     lugares por categoría (nombre + distancia), reusando la paleta de marca.
   - Interacción: al hacer click en un POI (pin o item de la lista) → fetch `/geo/ruta` de la propiedad
     a ese POI (modo auto) → dibuja la ruta ANIMADA + un rótulo en el punto medio: "~8 min a pie" /
     "~5 min en carro" (usa `aprox` para el "~"). **Una sola ruta activa a la vez** (elegir otra la
     reemplaza). Limpia la anterior.

E) ANIMACIÓN de la ruta (el requisito estrella — flowing, infinita, elegante, NO invasiva):
   - Usa **leaflet-ant-path** (`npm i leaflet-ant-path`): polyline con dashes que FLUYEN de la propiedad
     hacia el POI (lee como corriente eléctrica / progreso). Intégralo en react-leaflet con un componente
     pequeño `<RutaAnimada positions=... />` que use `useMap()` + `L.polyline.antPath(latlngs, opts)` y
     limpie en unmount/cambio.
   - Ajustes para que sea elegante y sutil (NO invasiva): `weight: 4`, `color` = champagne de marca
     (`--champ`) con `opacity` ~0.85, `dashArray: [10, 20]`, `delay: 800` (velocidad de flujo suave),
     `pulseColor` blanco tenue. Dirección propiedad→POI. Una ruta a la vez. (Fallback si el plugin da
     lío con la versión de leaflet: una `<Polyline>` normal con animación CSS `stroke-dashoffset` en
     bucle — mismo efecto de flujo.)
   - Pausa/OK a 60fps; no la hagas pesada (una sola ruta, velocidad moderada).

F) INTEGRACIÓN CON EL CHAT:
   - En `prompts.py`, tras listar los lugares (regla de `lugares_cerca`), Aqua OFRECE el mapa con un link
     markdown: "¿Quieres verlo en un mapa interactivo con las rutas? 👉 [Abrir mapa](/mapa/propiedad/{codigo})".
     Usa el `codigo` real del inmueble.
   - Verifica que el render de mensajes del chat (`components/MarkdownMessage.tsx`) muestre el link como
     clickeable (y ábrelo en pestaña nueva). Si no soporta links, agrégalo.

TESTS (backend, sin red: ORS mockeado): `/geo/ruta` con ORS mock (geometría+tiempo) Y el fallback recto
sin key (aprox=true, tiempo estimado); umbral auto caminando/carro; `/rag/inmuebles/{codigo}/cerca`
(con/sin coords). Deja el suite en verde. (Frontend: no hace falta test de la animación.)

VERIFICACIÓN: abre `/mapa/propiedad/<codigo real, p.ej. una casa de Laureles>` → se ve el inmueble +
pines de servicios + lista; al hacer click en un POI aparece la **ruta animada fluyendo** con el tiempo
("~X min a pie/en carro"); y en el chat, tras "¿qué hay cerca?", Aqua ofrece el link y abre el mapa.
Entrégame un resumen + confirma estos 3 puntos (mapa, ruta animada+tiempo, link desde el chat).

Nota infra: ORS tiene capa gratis (necesita una API key gratuita); si no la quieres aún, el fallback
recto deja todo funcionando para la demo. NO uses Google.
