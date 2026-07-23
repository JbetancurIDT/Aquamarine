Rol: eres el DEV de Aquamarine (lee AGENTES.md en la raíz). Estás en la rama feat/e09-geo.
Puedes editar código; NO edites nada bajo Obsidian/ (el cerebro es read-only para ti).

Requisito: el Handoff 1 (Sprints 1-3) ya está hecho y auditado — los 50 inmuebles tienen
dist_<cat>_m en Chroma y existe app/rag/geo_const.py. Si el audit pidió correcciones, aplícalas
antes de empezar.

Entorno: Chroma en localhost:8002 (colección `inmuebles`). Usa backend/.venv/bin/python y
backend/.venv/bin/pytest. ANTHROPIC_API_KEY puede estar vacía: los tests mockean el SDK.

Sigue la épica al pie de la letra (sección Sprints 4 y 5):
  "Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md"

TAREA DE ESTE HANDOFF — SOLO Sprints 4 y 5 (tareas T09.4.1, T09.5.1, T09.5.2), en orden,
siguiendo el Criterio y el "Prompt sugerido" de cada tarea. PARA al terminar el Sprint 5;
NO hagas los tests/docs (Sprint 6) todavía.

Guardarraíles (no negociables):
- Importa CERCANIA_KEYS / ETIQUETA_CAT desde app/rag/geo_const (nada de claves a mano).
- La cercanía es un filtro DURO: se ANDea en el `where` de Chroma junto a tenant_id/precio,
  NO se relaja en la escalera zona/tipo/precio, y NO agregues ningún "nivel de radio ampliado".
- Inmuebles SIN la clave dist_<cat>_m no deben matchear (semántica de $lte) → honestidad gratis.
- Radio efectivo nunca menor a 1500 m (piso honesto por el centroide de barrio); radio_km del
  lead lo sobrescribe hacia arriba.
- La firma pública de buscar_inmuebles NO cambia: cerca_de/radio_km viajan dentro de `filtros`.
- La distancia SIEMPRE se comunica aproximada ("~600 m", "a pocos minutos"); PROHIBIDO cifras
  exactas, "caminando" o "a X cuadras".
- Honestidad dura: el metro solo existe en el Valle de Aburrá; cerca_de + tool vacía ≠ "no existe".
- En prompts.py no metas fechas ni IDs (no invalides el prompt caching). Los 145 tests siguen verdes.

VERIFICACIÓN OBSERVABLE (inclúyela en tu resumen):
1) Desde Python: buscar_inmuebles("apartamento", {"cerca_de":"metro","ciudad":"Envigado","precio_max":1200000000})
   devuelve inmuebles con dist_metro_m ≤ radio y con la frase de distancia; muéstrame el `where` generado.
2) Un inmueble de Rionegro/Guatapé (sin dist_metro_m) NO aparece en esa búsqueda.
3) Prueba del agente (orquestador / POST /chat, SDK mockeado o real si tienes key):
   "apartamento en Envigado cerca del metro" → Aqua llama la tool con filtros.cerca_de="metro" y
   responde con distancia aproximada; y "algo cerca del metro en Guatapé" → responde honesto (no hay).

Al terminar: entrégame un resumen (archivos tocados + cómo verificaste) y PARA. No sigas al Sprint 6.
