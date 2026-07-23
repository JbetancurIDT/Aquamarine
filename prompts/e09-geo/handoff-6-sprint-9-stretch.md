Rol: eres el DEV de Aquamarine (lee AGENTES.md en la raíz). Estás en la rama feat/e09-geo.
Editas código; NO edites nada bajo Obsidian/ (el cerebro).

Requisito: CORE (Handoffs 1-3) completo; idealmente H4 (POI reales) para que las fichas nuevas
nazcan con datos reales. STRETCH: engancha el enriquecimiento a la ingesta.

Entorno: Chroma en localhost:8002. Usa backend/.venv/bin/python y backend/.venv/bin/pytest.

Sigue la épica (sección Sprint 9):
  "Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md"

TAREA DE ESTE HANDOFF — SOLO Sprint 9 (T09.9.1: enriquecer_inmueble en geo.py + hook en ingest.py).

Guardarraíles:
- Carga los centroides/POIs UNA vez al inicio de ingest().
- Entre la validación Pydantic y el upsert, llama geo.enriquecer_inmueble(inmueble, ...) envuelto
  en try/except que SOLO imprime [geo-skip] y continúa. Falla-suave: la ficha se indexa igual sin
  dist_* si algo peta.
- NO cambies MAX_ERRORES_SEGUIDOS ni la lógica de aborto de la ingesta.
- No rompas los tests; agrega uno que verifique que una ficha nueva se indexa con dist_* poblado
  (con Chroma/red mockeados).

VERIFICACIÓN OBSERVABLE: una ingesta/test de una ficha nueva la indexa con dist_* poblado; si el
enriquecimiento falla, la ficha se indexa igual (falla-suave).

Al terminar: resumen. Con esto E09 queda completo (CORE + STRETCH).
