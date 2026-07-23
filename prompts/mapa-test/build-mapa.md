Rol: eres el DEV de Aquamarine. Esto es una HERRAMIENTA INTERNA DE TESTING (no es parte de la
demo del cliente): prioriza que funcione rápido y simple, sin sobre-ingeniería. Trabaja en una
rama nueva `feat/mapa-test` (o sobre feat/e09-geo si prefieres). Puedes editar código; NO edites Obsidian/.

Objetivo: una pantalla nueva **/mapa** que muestre TODAS las propiedades del inventario como pines
sobre un mapa de OpenStreetMap, y que al hacer click en un pin abra un popup con una previsualización
de la imagen + título + precio + zona/ciudad + id + link a la ficha.

Entorno: Chroma en localhost:8002 (colección `inmuebles`, ~50 inmuebles del tenant, ya con
latitud/longitud e imagen_principal). Backend FastAPI en :8000, frontend React+TS (Vite) en :5173.
Usa backend/.venv para el backend.

BACKEND:
- Nuevo endpoint `GET /rag/inmuebles/mapa` en `backend/app/api/rag.py`. Devuelve todos los inmuebles
  del tenant que tengan coords: lista de {inmueble_id, titulo, precio, tipo, zona, ciudad, latitud,
  longitud, imagen_principal, url_fuente}. Sácalos de Chroma con `get_chroma_client()` +
  `col.get(where={"tenant_id": {"$eq": settings.DEFAULT_TENANT_ID}}, include=["metadatas"])`; incluye
  solo los que tengan latitud y longitud. Sin auth (herramienta interna, como la impersonación de asesor).

FRONTEND:
- Instala `leaflet` y `react-leaflet` (`npm i leaflet react-leaflet`). Importa el CSS de leaflet.
- Tiles OSM estándar: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` con atribución
  "© OpenStreetMap contributors". Sin API key.
- Nueva ruta `/mapa` (agrégala en `App.tsx`, junto a /chat, /dashboard, etc.). Centra el mapa en
  Medellín (~6.24, -75.58), zoom ~12. Al cargar, llama al endpoint y pinta un `<Marker>` por inmueble
  en (latitud, longitud).
- En el `<Popup>` de cada marker: `<img>` con `imagen_principal` (con fallback `onError` a un
  placeholder), el título, el precio formateado (COP), zona, ciudad, id, y un link a `url_fuente`
  (abrir en nueva pestaña).
- IMPORTANTE: arregla el bug clásico de los íconos de marker de Leaflet con bundlers (los pines
  salen rotos): configura `L.Icon.Default` con los assets de leaflet (import de
  `leaflet/dist/images/marker-icon.png` etc., o `L.Icon.Default.mergeOptions`).

Nota de datos: las coordenadas son el CENTROIDE del barrio (con jitter determinista), NO la dirección
exacta → varias propiedades del mismo barrio quedarán agrupadas cerca. Es esperado (no hay direcciones
exactas en el inventario). No intentes "arreglarlo".

Mantenlo SIMPLE: una sola pantalla funcional, sin filtros ni capas extra por ahora. Al terminar, corre
back + front y confírmame que en /mapa se ven ~50 pines y que al hacer click aparece la imagen en el popup.
