Rol: eres el DEV de Aquamarine (lee AGENTES.md en la raíz). Estás en la rama feat/e09-geo.
Editas código; NO edites nada bajo Obsidian/ (el cerebro). Excepción de docs: SÍ puedes crear
geo.md en la raíz del repo y añadir su fila a CLAUDE.md (son docs del producto, no cerebro).

Requisito: Handoffs 1 y 2 hechos y auditados (enriquecimiento + búsqueda + tool + prompt listos).

Entorno: Chroma en localhost:8002. Usa backend/.venv/bin/python y backend/.venv/bin/pytest.
Los tests mockean red y SDK (no gastan APIs).

Sigue la épica (sección Sprint 6):
  "Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md"

TAREA DE ESTE HANDOFF — SOLO Sprint 6 (tareas T09.6.1 tests, T09.6.2 docs), siguiendo el Criterio
y el "Prompt sugerido" de cada tarea.

Guardarraíles:
- Tests OFFLINE: mockea get_chroma_client y el SDK; sin red ni gasto de APIs. Sigue el estilo de
  backend/tests/test_rag_search.py + conftest.py.
- Cubre: haversine (±0.5%, simetría, cero); distancias_por_categoria omite categorías vacías/None;
  InmuebleIn.metadata omite dist_* None y emite int; cerca_de → $lte correcto en el where; clave
  ausente excluye; radio_km sobrescribe y respeta el piso 1500; honestidad sin metro; backfill de
  seed_geo idempotente que NO pierde titulo/precio/imagenes.
- Los 145 tests actuales + los nuevos DEBEN quedar verdes. Reporta el conteo final.
- geo.md en la raíz con: qué resuelve; cómo funciona (enriquecimiento offline + consulta por
  categoría + fallback por nombre propio si ya existe); tabla categoría→dist_*_m; fuentes
  (GTFS/OSM/Nominatim); precisión y límites honestos (centroide de barrio, radio mínimo, cobertura
  OSM parcial, ciudades sin metro); cómo correrlo (scripts/seed_geo.py, pytest) y config.
- Añade la fila de geo.md a la tabla "Documentación por feature" de CLAUDE.md.

VERIFICACIÓN OBSERVABLE (en tu resumen): la salida de pytest con el conteo total en verde, y la
ruta del geo.md creado con sus secciones.

Al terminar: resumen + PARA. Con esto el CORE v1 de E09 queda cerrado.
