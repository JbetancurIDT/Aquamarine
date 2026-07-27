Rol: eres el DEV de Aquamarine (lee AGENTES.md en la raíz). Estás en la rama feat/e09-geo.
Puedes editar código; NO edites nada bajo Obsidian/ (el cerebro es read-only para ti).

Entorno: Chroma corre en Docker en localhost:8002 (colección `inmuebles`, 50 inmuebles del
tenant Aquamarine). Usa el venv del backend: backend/.venv/bin/python y backend/.venv/bin/pytest.
Postgres está en localhost:5432 (no lo necesitas para este handoff).

Vas a construir el feature E09 (búsqueda por proximidad geográfica). Lee PRIMERO la épica
completa y síguela al pie de la letra:
  "Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md"
Interioriza las decisiones (haversine radial en km; 100% OSM; radio honesto mínimo 1.5 km;
cercanía = filtro DURO; metadata plana sin None) y el GROUND TRUTH de datos (50 inmuebles,
~0 coords reales, se geocodifica por centroide de zona+ciudad).

TAREA DE ESTE HANDOFF — SOLO Sprints 1, 2 y 3 (tareas T09.1.1 → T09.3.4), en orden, siguiendo
el Criterio y el "Prompt sugerido" de cada tarea. NO construyas todavía la búsqueda (Sprint 4)
ni la tool/prompt (Sprint 5). PARA al terminar el Sprint 3.

Guardarraíles (no negociables):
- `geo_const.py` es la ÚNICA fuente de verdad de los nombres de categoría/clave; el schema y el
  enriquecimiento DEBEN importarla (cero strings de clave escritos a mano en otro archivo).
- Sprint 2 usa datos HARDCODEADOS y sin red (estaciones de metro + centroides de zona); las
  fuentes en vivo son Sprint 7 (no las hagas ahora).
- El backfill (`seed_geo.py`) NO re-scrapea: copia la metadata existente, rellena lat/lon solo
  si faltan o son sintéticas (detecta el par 6.000123/-75.000456), calcula dist_<cat>_m con
  haversine, y hace col.update. ANTES verifica si tu versión de chromadb hace merge o replace
  en update y pinéala en backend/requirements.txt.
- Municipios SIN metro (Rionegro, La Ceja, El Retiro, Guatapé, Apartadó, Cartagena, Coveñas)
  NO reciben dist_metro_m (por diseño = honestidad).
- Es idempotente: dos corridas seguidas dejan la metadata idéntica. No pierdas titulo/precio/imagenes.
- Los 145 tests actuales siguen verdes (corre backend/.venv/bin/pytest).

VERIFICACIÓN OBSERVABLE (inclúyela en tu resumen final): corre seed_geo.py contra Chroma y
muéstrame que (a) 3-4 inmuebles del Valle de Aburrá —Medellín/Envigado— ya tienen dist_metro_m
con valores plausibles, (b) el inmueble 9515664 (Santa Fe, coord falsa) quedó corregido, y
(c) una segunda corrida deja la metadata idéntica (idempotencia).

Al terminar: entrégame un resumen (archivos creados/tocados + comandos con los que verificaste)
y PARA. No sigas al Sprint 4.
