Rol: eres el DEV de Aquamarine (lee AGENTES.md en la raíz). Estás en la rama feat/e09-geo.
Editas código; NO edites nada bajo Obsidian/ (el cerebro).

Requisito: CORE (Handoffs 1-3) completo; idealmente H4 (POI reales) también. STRETCH: agrega el
fallback de búsqueda por LUGAR CON NOMBRE PROPIO ("cerca de EAFIT / la Clínica Las Américas / el
Parque Lleras").

Entorno: Chroma en localhost:8002. Usa backend/.venv/bin/python y backend/.venv/bin/pytest.
Nominatim usa RED, pero los tests mockean el geocode (sin red).

Sigue la épica (sección Sprint 8):
  "Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md"

TAREA DE ESTE HANDOFF — SOLO Sprint 8 (T09.8.1 config+geocode_vivo, T09.8.2 buscar_por_lugar +
routing, T09.8.3 tests+demo).

Guardarraíles:
- geocode_vivo geocodifica el lugar UNA vez por consulta (JAMÁS por inmueble), con caché
  persistente en geocache.json, User-Agent y rate-limit 1 req/s; inyectable/mockeable para tests.
- buscar_por_lugar rankea el inventario por haversine al punto; excluye y CUENTA los sin-coords;
  devuelve estado ∈ {ok, lugar_no_encontrado, sin_coords}; motivo "a ~X km de <lugar>".
- Tool: filtros.cerca_de_lugar (string), EXCLUYENTE con cerca_de. Routing en la tool:
  codigo > cerca_de_lugar > cerca_de > query/filtros.
- Honestidad: lugar no ubicado → pedir una referencia alterna, NO negar inventario.
- prompts.py: enseña a distinguir nombre propio (cerca_de_lugar) de categoría (cerca_de).
- Tests con geocode y col.get mockeados (sin red). Los 145+ siguen verdes.
- seed_demo.py: 2 leads que ejerciten cercanía (uno metro/D1 con un inmueble real del Valle de
  Aburrá; otro EAFIT/Clínica Las Américas) + un intercambio honesto "no hay metro" (Guatapé);
  ajusta _calcular_esperados si cambia el total.

VERIFICACIÓN OBSERVABLE: "algo cerca de EAFIT" → geocode + ranking + "a ~X km de EAFIT (aprox.)";
un lugar inexistente → texto honesto; pytest verde.

Al terminar: resumen + PARA.
