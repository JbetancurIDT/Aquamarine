Rol: eres el DEV de Aquamarine (lee AGENTES.md). Refinamiento de E09 (búsqueda por cercanía). Rama
nueva `feat/geo-lugares-tolerantes` (desde la rama con E09 integrado — feat/e09-geo o master si ya lo
mergeaste). Editas código; NO edites Obsidian/.

CONTEXTO / PROBLEMA (de una conversación real): el fallback por NOMBRE PROPIO
(`filtros.cerca_de_lugar` → `search.buscar_por_lugar` → `geo.geocode_vivo` → Nominatim) es demasiado
literal. El lead tuvo que decir el nombre EXACTO del mapa: falló con "el mirador de la piedra del
peñol" y solo funcionó al decir "Mirador del Peñol". Además NO desambigua homónimos (ej. "La América"
= el barrio en Medellín vs. la "Plaza de Mercado La América") ni usa el contexto de la conversación.

OBJETIVO: que Aqua reconozca lugares aunque el lead los diga aproximados/coloquiales, **desambigüe** los
nombres ambiguos (con contexto o preguntando), y **cualifique con la región**. Es ~80% PROMPT
ENGINEERING (la inteligencia va en Aqua) + ~20% robustez del geocoder (red de seguridad).

── A) SYSTEM PROMPT — el corazón (backend/app/agent/prompts.py) ──
En la sección "## Búsqueda por cercanía", agrega una subsección para el nombre propio. Texto listo
para insertar (ajústalo al tono/formato existente, SIN fechas ni IDs para no invalidar el caché):

  ### Cuando piden cerca de un LUGAR con nombre propio
  Para "cerca de <lugar>" (un sitio con nombre: un mirador, una clínica, una universidad, un parque,
  una plaza, un centro comercial), usa `filtros.cerca_de_lugar`. ANTES de llamar la herramienta:
  1. **Traduce el nombre coloquial al nombre OFICIAL que usaría un mapa**, con tu conocimiento del
     lugar; corrige muletillas y typos. Ej: "la piedra del peñol" / "la roca" / "el mirador de la
     piedra del peñol" → **"Mirador del Peñol"**. "el aeropuerto de rionegro" → "Aeropuerto José
     María Córdova".
  3. **Cualifícalo con el municipio/ciudad y el departamento** que sepas por la conversación o por el
     propio lugar: pasa **"Mirador del Peñol, El Peñol, Antioquia"**, no solo "mirador". Así el mapa lo
     ubica bien y no lo confunde con un homónimo de otra región.
  3. **Si el nombre es AMBIGUO** (puede ser dos cosas distintas: un barrio y una plaza de mercado, un
     centro comercial y un sector, o hay homónimos), NO adivines:
     - Primero resuélvelo con el CONTEXTO ya dado por el lead. Ej: "una casa por el **sector Estadio**
       cerca de La América" → por el sector Estadio, se refiere a la **Plaza de Mercado La América**
       (no al barrio) → pasa "Plaza de Mercado La América, Medellín".
     - Si el contexto no alcanza, haz UNA pregunta corta ofreciendo las opciones probables: "¿Te
       refieres al barrio La América o a la Plaza de Mercado La América?". Solo con la respuesta llamas
       la herramienta.
  4. Ante la duda de si un nombre es único, **prefiere preguntar** una referencia más precisa antes que
     ubicar un lugar equivocado.
  Si la herramienta responde que no ubicó el lugar, pide con calidez otra referencia cercana (municipio,
  barrio, vereda o un punto conocido) y reintenta re-cualificando con lo que sepas.

── B) TOOL (backend/app/agent/tools.py) ──
Actualiza la descripción de `filtros.cerca_de_lugar`: debe dejar claro que Aqua pasa el **nombre
OFICIAL de mapa, cualificado con ciudad/departamento y ya desambiguado** (no las palabras crudas del
lead). Incluye 1-2 ejemplos ("Mirador del Peñol, El Peñol, Antioquia").

── C) GEOCODER (backend/app/rag/geo.py · `_nominatim` / `geocode_vivo`) — robustez, SIN romper la caché,
el rate-limit 1 req/s, ni la inyección para tests ──
- Región sin duplicar: si el nombre ya trae país/departamento no le encimes otro; mantén
  `countrycodes=co`; añade ", Colombia" solo si no viene país.
- Sube `limit` a ~5 + `addressdetails=1`; toma el de mayor `importance` (Nominatim ya ordena).
- FALLBACK de una pasada: si la query completa da 0 resultados, reintenta UNA vez con una versión
  simplificada (quita conectores/muletillas: "de la", "del", "el", "cerca de", "sector"; deja el núcleo
  del nombre). Respeta el rate-limit y la caché.
- (Opcional, no obligatorio) además del mejor punto, expón los candidatos (display_name/type) para una
  futura desambiguación programática; si lo agregas, NO cambies el contrato de `geocode_vivo` que usan
  hoy `buscar_por_lugar` y los tests.

── D) TESTS (backend/tests/, sin red: geocodificador inyectado/mock) ──
- Un nombre coloquial ya cualificado por Aqua resuelve; el fallback de simplificación se dispara cuando
  la query completa da 0; el rate-limit y la caché siguen intactos; los tests de contenido del prompt
  (si existen) siguen verdes. Deja TODO el suite en verde.

VERIFICACIÓN (descríbela; o córrela si tienes ANTHROPIC_API_KEY): los 2 escenarios del transcript:
1. "una finca cerca de la piedra del peñol / el mirador de la piedra" → Aqua pasa "Mirador del Peñol,
   El Peñol, Antioquia" y lo ubica (ya no falla).
2. "cerca de La América" sin contexto → Aqua PREGUNTA barrio vs. plaza de mercado; CON contexto
   ("sector Estadio") → asume la Plaza de Mercado La América y no pregunta.

Mantenlo enfocado en estos 4 puntos. Al terminar, entrégame un resumen + confirma los 2 escenarios.
