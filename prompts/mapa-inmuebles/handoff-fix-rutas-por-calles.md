Rol: eres el DEV de Aquamarine (lee AGENTES.md). FIX del mapa interactivo (misma rama del mapa
interactivo, feat/mapa-interactivo-rutas). Editas código; NO edites Obsidian/.

PROBLEMA: al hacer click en un servicio (colegio, súper, universidad…) la ruta se dibuja como
**línea recta**, no como una ruta por CALLES (estilo Google Maps / Waze / DiDi). Causa raíz: el
endpoint `GET /geo/ruta` (`backend/app/api/geo.py`) solo obtiene geometría real de calles vía
**OpenRouteService**, y como NO hay `ORS_API_KEY`, cae SIEMPRE al fallback en línea recta (`aprox=true`).

OBJETIVO: que la ruta siga las CALLES **sin depender de una API key**. Es fix de BACKEND: el frontend
(`RutaAnimada`) ya dibuja/anima cualquier geometría que le llegue — NO lo toques.

FIX en `backend/app/api/geo.py` — agrega **OSRM público** como fuente de ruteo por calles sin key,
como paso intermedio entre ORS y la línea recta. Nueva cadena en `/ruta`:
  1. **ORS** (`_ors_directions`) si hay `ORS_API_KEY` — déjalo igual (perfiles caminando/carro reales).
  2. **OSRM público** (nuevo `_osrm_route`) — SIN key, ruta por calles. ← lo que arregla la demo hoy.
  3. **Línea recta** — SOLO como último recurso (si ORS y OSRM fallan).

`_osrm_route(from_lat, from_lon, to_lat, to_lon)`:
  - GET `{OSRM_URL}/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson`
    (sin auth, timeout ~15 s).
  - De la respuesta: `routes[0].geometry.coordinates` (viene en [lon,lat] → **convierte a [lat,lon]** para
    Leaflet, igual que ORS), `routes[0].duration` (seg), `routes[0].distance` (m).
  - Devuelve `(geometry, duration_s, distance_m)` o `None` si `code != "Ok"` / falla / timeout.

Uso por modo (el demo público de OSRM es perfil CARRO):
  - `modo=carro` → geometry + duration de OSRM (tiempo en carro).
  - `modo=caminando` → geometry de OSRM (sigue calles igual) + distancia real de OSRM, pero el tiempo =
    `distancia / _VEL_M_POR_MIN["caminando"]` (para ruteo peatonal EXACTO haría falta ORS con key o un
    OSRM foot; con el demo alcanza para que la línea siga las calles).
  - `aprox=false` cuando la geometría es RUTEADA (ORS u OSRM); `aprox=true` SOLO en la línea recta.
  - Cachea también las rutas de OSRM en `_CACHE_RUTAS` (misma evicción FIFO que ORS).

CONFIG (`backend/app/core/config.py`): agrega `OSRM_URL: str = "https://router.project-osrm.org"`
(swappable a un OSRM self-hosted en el futuro).

Nota infra (documéntala en `mapa.md`): el demo público de OSRM es para pruebas/demo (tiene límites de
uso, no producción pesada). Para rutas PEATONALES reales o sin límites: setea `ORS_API_KEY` (capa
gratis) o monta un OSRM propio. El fallback recto queda solo por si todo lo demás falla.

TESTS (backend, sin red — OSRM/ORS mockeados): con OSRM mock, `/geo/ruta` devuelve geometría
**multi-punto** (no 2 puntos) y `aprox=false`; sin OSRM ni ORS → línea recta `aprox=true`; `modo=caminando`
calcula el tiempo a pie sobre la distancia de OSRM. Deja el suite en verde.

VERIFICACIÓN: en el mapa, al hacer click en un POI, la ruta ahora **sigue las calles** (línea
multi-punto) con la animación fluyendo encima y el tiempo — ya no es una recta. Entrégame un resumen +
confirma que la ruta sigue calles con y sin `ORS_API_KEY`.
