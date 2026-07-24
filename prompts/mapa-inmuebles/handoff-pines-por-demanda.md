Rol: eres el DEV de Aquamarine (lee AGENTES.md). Mejora del feature MAPA (rama feat/mapa-inmuebles).
Editas código; NO edites Obsidian/. Requisito: la pantalla /mapa base ya existe y funciona.

Objetivo: pintar los pines del mapa de **colores según la DEMANDA de leads en la zona de cada
propiedad** → el mapa se vuelve un **mapa de calor de demanda sobre el inventario** (pin caliente =
muchos leads buscando esa zona). Sirve para ver de un vistazo dónde hay interés vs. dónde hay inventario.

GROUND TRUTH de datos (verificado en Postgres; NO inventes rangos):
- Hay ~28 leads. La zona/ciudad de interés de un lead vive en su `perfil` JSONB: `perfil->>'zona'`,
  `perfil->>'ciudad'`. NO hay columna zona ni FK a inmueble.
- Máximo de leads por zona = **5** (El Poblado); la mayoría 1-2. Por ciudad: Medellín 18, Envigado 6.
- Por eso los rangos son 0-5, NO 0-50.

QUÉ ES "leads en la ubicación": para cada propiedad, el número de leads cuyo interés cae en la zona de
esa propiedad. Reusa la tolerancia que YA existe: `app.rag.search._cumple_ubicacion(meta, lugar)` y
`_norm`. Un lead cuenta para una propiedad si `_cumple_ubicacion(prop_meta, lead_zona)` es True; si el
lead no tiene zona, cuenta por ciudad (`_norm(lead_ciudad) == _norm(prop_ciudad)`). Un mismo lead puede
contar para varias propiedades de la misma zona (correcto: "5 leads buscan en esta zona").

BACKEND
- Enriquecer `GET /rag/inmuebles/mapa` (backend/app/api/rag.py) para que cada inmueble incluya
  `leads_zona: int`. El endpoint gana una sesión de BD (`db: Session = Depends(get_db)` — mira cómo lo
  hacen los endpoints de leads/metrics).
- Pon la lógica en un helper reutilizable (p.ej. `app/services/` o junto a métricas): consulta los leads
  del tenant (id, perfil), extrae (zona, ciudad) de cada perfil, y para cada propiedad cuenta los matches
  con `_cumple_ubicacion`/ciudad. Filtra valores basura de zona que no son ubicaciones (p.ej.
  "cerca del metro") dejándolos sin match (no rompen nada: simplemente no suman por zona).
- Test en backend/tests/: con leads sembrados (perfil con zona/ciudad) el endpoint devuelve el
  `leads_zona` correcto por propiedad (mock de Chroma como en los otros tests). Deja todo en verde.

FRONTEND (frontend/src/pages/MapaPage.tsx)
- Cambia el `<Marker>` por defecto por un `<CircleMarker>` de react-leaflet (círculo vectorial, color
  100% controlable, sin assets). Centro en `[latitud, longitud]`, `radius` ~9 (opcional: escala suave
  con la cantidad, p.ej. 7 + leads_zona), `pathOptions={{ fillColor, color:'#ffffff', weight:1.5,
  fillOpacity:0.85 }}`. Mantén el `<Popup>` con `<PropertyCard>` + `<Cercania>`.
- `MapaInmueble` gana `leads_zona: number`.
- Función `colorPorDemanda(n)` con los buckets REALES (rampa de calor secuencial; rojo = más demanda):
    0        → '#cbd5e1'  (gris · sin demanda)
    1–2      → '#fbbf24'  (ámbar · demanda baja)
    3–4      → '#f97316'  (naranja · demanda media)
    5 o más  → '#dc2626'  (rojo · alta demanda)
- En el `<Popup>`, agrega una línea: "**{leads_zona}** leads buscan en {zona}" (o "Sin leads en esta
  zona" si 0), con la paleta de marca.
- **Leyenda** fija sobre el mapa (esquina inferior-derecha, cajita con `--card`/`--line`): 4 filas
  color→rango ("0 · sin demanda", "1–2", "3–4", "5+ · alta demanda"). Es imprescindible para que se
  entienda.
- Actualiza el sub-head: "{n} propiedades · color = leads buscando en la zona".

Notas:
- Es una escala SECUENCIAL de magnitud (no categorías al azar): rojo = más demanda. Si el dueño la
  quiere invertida o por ciudad en vez de zona, es un cambio de una función — déjalo fácil de tocar.
- Las coords siguen siendo el centroide del barrio (varias propiedades de la misma zona se agrupan y
  compartirán color/valor: correcto, es la demanda de esa zona).

Mantenlo enfocado (colores + leyenda + popup). Al terminar: corre back + front, confírmame que los
pines salen coloreados, la leyenda se ve, el popup muestra el conteo de leads, y los tests en verde.
