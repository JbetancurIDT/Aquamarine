Rol: eres el DEV de Aquamarine (lee AGENTES.md). Refinamiento de E09. Rama nueva
`feat/geo-cercania-nombrada` (desde la rama con E09 integrado). Editas código; NO edites Obsidian/.

CONTEXTO (de una conversación real): (1) el lead se enfocó en UNA casa (Laureles) y en cada pregunta
de seguimiento el agente **volvía a mostrar 3 tarjetas** (la de Laureles + 2 apartamentos que ya no
venían al caso). (2) Al preguntar "¿qué hay cerca?" y "¿qué colegios?", Aqua respondió vago ("colegios
reconocidos del sector") y **no supo nombrar ninguno** — porque hoy solo tiene la DISTANCIA a la
categoría (`dist_<cat>_m`), no los NOMBRES. Los datos SÍ tienen los nombres (Éxito, Carulla, UPB… en
`poi_valle_aburra.json`); falta exponerlos.

Son 2 arreglos. Mecánica ya verificada: las tarjetas del chat = lo que `buscar_inmuebles` devuelve EN
ESE turno (el frontend las adjunta por mensaje; el orquestador resetea `inmuebles` cada turno). O sea:
si Aqua no re-busca en general, no salen tarjetas de más.

──────────────────────────────────────────────────────────────────────────
ARREGLO A — no re-listar cuando el lead ya se enfocó en UNA propiedad (solo PROMPT)
──────────────────────────────────────────────────────────────────────────
En backend/app/agent/prompts.py agrega (ajusta al tono; sin fechas/IDs):

  ### Seguimiento de UNA propiedad (no re-listar)
  Cuando el lead elige o pregunta por UNA propiedad ya mostrada ("me gusta la de Laureles", "¿qué tan
  lejos queda de la UPB?", "¿qué hay cerca?"), estás en modo SEGUIMIENTO de ESA propiedad:
  - NO vuelvas a correr `buscar_inmuebles` como búsqueda general (sin `codigo`): traería otras opciones
    que ya no vienen al caso y llenan el chat de tarjetas irrelevantes.
  - Si necesitas datos de esa propiedad, búscala por su `codigo` (devuelve solo esa → una sola ficha).
  - Para lo que hay alrededor, usa `lugares_cerca` con su `codigo`.
  - Solo vuelve a hacer una búsqueda general si el lead PIDE explícitamente ver otras opciones/comparar
    o si cambia lo que busca.

──────────────────────────────────────────────────────────────────────────
ARREGLO B — tool `lugares_cerca`: nombres reales + distancia, omitiendo vacías
──────────────────────────────────────────────────────────────────────────
1) geo.py — nueva función pura (usa `cargar_pois()` + `cargar_metro()` como categoría "metro"):
   `lugares_cerca(lat, lon, categoria=None, top=3, radios=None) -> dict[str, list[dict]]`
   - Por cada categoría (o solo `categoria` si se pide), calcula haversine desde (lat,lon) a cada POI,
     filtra dentro del radio de esa categoría (usa radios sensatos, p.ej. súper/colegio/parque 1.5 km,
     C.C./clínica 2.5 km, universidad 3 km, metro 1.5 km), ordena asc y toma `top`.
   - Etiqueta de cada POI: `nombre` si existe; si no, `brand`; si ninguno, el nombre genérico de la
     categoría ("Supermercado", "Colegio"…). Dedup por (etiqueta, coords redondeadas).
   - Devuelve `{cat: [{"nombre": etiqueta, "dist_m": int}, …]}` **OMITIENDO** las categorías sin nada
     en el radio. (Los inmuebles fuera del Valle no tienen POIs → devuelve casi vacío = honesto.)

2) tools.py — nueva tool `LUGARES_CERCA_TOOL` + `ejecutar_lugares_cerca(args)`:
   - Schema: `codigo` (requerido, el de la ficha ya mostrada) + `categoria` opcional (enum de las 7,
     para "¿qué colegios?"). Descripción: "Lista los lugares REALES (con nombre y distancia aprox.)
     alrededor de un inmueble. Úsala cuando pregunten qué hay cerca/alrededor o por una categoría.
     Devuelve solo las categorías con algo en el radio; omite las vacías. NO inventes: si no está aquí,
     no existe."
   - Executor: `obtener_inmueble_por_codigo(codigo)` → coords; si no hay ficha/coords, texto honesto
     ("no tengo la ubicación de ese inmueble"). Llama `geo.lugares_cerca(...)` y formatea para Claude,
     por categoría con "~" en las distancias (m si <1000, km si ≥1000). **Devuelve (texto, [])** — sin
     inmuebles, para NO generar tarjetas.

3) orchestrator.py — registra la tool y generaliza el dispatch:
   - Agrega `LUGARES_CERCA_TOOL` a `tools=[...]`.
   - Cambia el `if name == "buscar_inmuebles"` por un registro
     `{"buscar_inmuebles": ejecutar_buscar_inmuebles, "lugares_cerca": ejecutar_lugares_cerca}` y
     despacha por nombre. `buscar_inmuebles` sigue aportando inmuebles (tarjetas); `lugares_cerca` no.

4) prompts.py — regla de uso:
   ### "¿Qué hay cerca / alrededor?" → lugares_cerca, con NOMBRES
   Cuando pregunten qué hay cerca de una propiedad, o por una categoría ("¿qué colegios?", "¿supermercados?"),
   LLAMA `lugares_cerca` con el `codigo` del inmueble y lista lo que devuelva, por categoría, con el
   NOMBRE real y la distancia aproximada. Ej: "Cerca tienes: Supermercados — Éxito (~400 m), Carulla
   (~900 m); Universidad — UPB (~500 m)."
   - OMITE las categorías que la herramienta no devuelva (si no hay centro comercial, no lo menciones).
   - NUNCA menciones "colegios reconocidos del sector" ni nombres genéricos sin haberlos obtenido de la
     herramienta. Si no está en `lugares_cerca`, para ti NO existe → dilo con honestidad.
   - Distancias APROXIMADAS (la ubicación es el centroide del barrio): usa "~".

TESTS (backend/tests/, sin red ni SDK): `lugares_cerca` con POIs sintéticos (orden por distancia, top-N,
omite categorías vacías, etiqueta nombre>brand>genérico); `ejecutar_lugares_cerca` con Chroma mockeado
(inmueble con/sin coords); el dispatch del orquestador enruta ambas tools. Deja el suite en verde.

VERIFICACIÓN (describe o corre): (A) el lead se enfoca en la casa de Laureles y pregunta seguimiento →
0-1 tarjetas (no 3). (B) "¿qué hay cerca?"/"¿qué colegios?" → nombres reales con distancia (Éxito ~400 m,
UPB ~500 m…), omitiendo lo que no hay, sin inventar. Entrégame un resumen + confirma los 2 escenarios.
