Rol: eres el DEV de Aquamarine. Fix visual chico del mapa interactivo (rama del mapa). Solo frontend.
NO edites Obsidian/.

PROBLEMA: la ruta animada usa champán/marrón (`#A8884E`) + pulso blanco → se confunde con las vías
beige de OpenStreetMap. Cámbiala a **azul oscuro (línea) + azul claro (flujo)**, estilo Google Maps/Waze
(contrasta bien con OSM y se lee como "ruta").

CAMBIOS (2 líneas):
1. `frontend/src/pages/MapaPropiedadPage.tsx` (~línea 129): el `<RutaAnimada>` pasa `color="#A8884E"`.
   Cámbialo a `color="#1d4ed8"` (azul oscuro).
2. `frontend/src/components/RutaAnimada.tsx` (~línea 25): `pulseColor: '#ffffff'` → `pulseColor: '#93c5fd'`
   (azul claro, el flujo). Opcional: cambia también el default del prop (`color = '#A8884E'` → `'#1d4ed8'`)
   por consistencia.

NO toques el pin de la propiedad (🏡 sigue en champán) ni los colores por categoría de los POIs.

VERIFICACIÓN: abre `/mapa/propiedad/<codigo>`, haz click en un POI → la ruta ahora fluye en azul
(oscuro con dashes celestes), clara sobre las calles de OSM. `cd frontend && npm run build` en verde.
