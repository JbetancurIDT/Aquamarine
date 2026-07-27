Rol: eres el DEV de Aquamarine (lee AGENTES.md). Tuning del agente Aqua: **preferencia de movilidad**.
Rama nueva `feat/agente-movilidad` (desde la rama estable con E09). Editas código; NO edites Obsidian/.

OBJETIVO: Aqua pregunta proactivamente (una vez, sin ser intenso) cómo se mueve el lead, y usa la
respuesta como **preferencia SUAVE** para ofrecerle algo que valore más. Reglas duras del comportamiento:
- **No bloqueante:** si el lead no responde, sigue normal (no re-preguntar, no trabar el flujo).
- **No determinante:** si responde, NO filtra ni excluye — solo REORDENA (pone primero los que encajan)
  y el agente RESALTA por qué encajan. Siempre muestra opciones dentro del presupuesto.

Clave de diseño: NO hacen falta filtros nuevos. Los datos (`parqueaderos`, `dist_metro_m`, `area_m2`,
`habitaciones`) YA vienen en la metadata que devuelve `buscar_inmuebles` → esto es un **re-ranking suave**.

── A) PERFILAMIENTO (backend/app/agent/profiler.py + schema del perfil) ──
- Captura un campo nuevo opcional `movilidad` (string libre normalizado: "carro" | "moto" | "metro" |
  "bus" | "a_pie" | "bici" | "desde_casa" | …) en el perfil extraído y persistido (`perfil.movilidad`).
- NO lo metas en los campos que "califican" al lead (`_CAMPOS_CALIFICAN` del orquestador): es preferencia,
  no un calificador. Solo se guarda y se usa para sesgar recomendaciones.

── B) SYSTEM PROMPT (backend/app/agent/prompts.py) — el corazón (texto listo para insertar, sin fechas/IDs) ──
  ### Preferencia de movilidad (pregunta proactiva y suave)
  Durante el perfilamiento, DESPUÉS de captar lo básico (tipo/zona/presupuesto), pregunta UNA sola vez,
  natural y sin insistir, cómo se mueve el lead en su día a día o al trabajo. Ej: "¿Y cómo te mueves
  normalmente — en carro, en metro, de otra forma? Así te muestro algo que te quede cómodo 🙂".
  - Es OPCIONAL y NO bloqueante: si no responde o cambia de tema, sigue normal y NO la repitas.
  - Si responde, NO es un requisito: es info EXTRA para ofrecer algo que valore más.
  Mapea la respuesta a `preferencias` (parámetro de `buscar_inmuebles`):
  - carro / moto / camioneta / vehículo → `parqueadero`
  - metro / tranvía / bus / transporte público / integrado → `cerca_metro`
  - a pie / caminando / bici / patineta → `conectado` (zona central y bien servida)
  - desde casa / teletrabajo / remoto / home office → `espacio_oficina` (más área o una habitación extra)
  - respuestas mixtas → varias preferencias.
  Pasa esas `preferencias` en las búsquedas siguientes. Al presentar, RESALTA por qué encaja con su
  movilidad ("tiene 2 parqueaderos, ideal porque andas en carro"; "queda a ~600 m del metro"). Si ninguna
  opción cumple, ofrécelas igual sin disculparte de más.
  OJO — suave ≠ filtro duro de cercanía: para la movilidad usa `preferencias:["cerca_metro"]` (suave).
  SOLO si el lead lo pone como REQUISITO explícito ("que quede cerca del metro sí o sí") usa el filtro
  duro `cerca_de:"metro"`.

── C) BÚSQUEDA + TOOL (backend/app/rag/search.py + backend/app/agent/tools.py) ──
- `buscar_inmuebles(query, filtros, k, preferencias=None)`: `preferencias` = lista de
  {parqueadero, cerca_metro, espacio_oficina, conectado}. Re-rankea los candidatos: los que cumplen MÁS
  preferencias van primero (desempata por la `relevancia` actual), luego trunca a `k`. **NUNCA excluye**
  por preferencia — solo reordena; el conteo de resultados es el mismo que sin preferencias.
- `_cumple_pref(meta, pref)` (umbrales tuneables):
  - `parqueadero` → `int(meta.get("parqueaderos") or 0) >= 1`
  - `cerca_metro` → `meta.get("dist_metro_m")` presente y `<= 1500`
  - `espacio_oficina` → `(meta.get("area_m2") or 0) >= 90` OR `(meta.get("habitaciones") or 0) >= 3`
  - `conectado` → `dist_metro_m <= 1500` OR (≥3 categorías `dist_<cat>_m <= 800`)
- Marca cada resultado con `preferencias_ok: [...]` (cuáles cumple). En `tools.py`, el texto de cada
  línea añade un "(ideal para ti: parqueadero · cerca del metro)" cuando aplique, para que Aqua resalte.
- Tool `buscar_inmuebles`: agrega `preferencias` al input_schema (array, enum de las 4), con descripción
  que deje CLARO que es SUAVE (reordena, no filtra) y que viene de la movilidad del lead.

── D) TESTS (backend/tests/, sin red ni SDK) ──
- `_cumple_pref` con metadata sintética (los 4 casos, umbrales).
- `buscar_inmuebles` con `preferencias`: los que cumplen salen primero, pero el CONTEO no baja (no
  excluye); sin `preferencias` el orden es el de hoy (no regresiona).
- profiler extrae `movilidad` a `perfil`; sin movilidad → búsqueda normal (sin preferencias).
Deja el suite en verde.

VERIFICACIÓN (describe o corre): (1) Aqua pregunta la movilidad UNA vez tras lo básico, no re-pregunta,
y si el lead la ignora sigue sin trabarse. (2) "me muevo en carro" → los inmuebles con parqueadero salen
primero y Aqua lo resalta, pero los sin parqueadero SIGUEN apareciendo. (3) "en metro" → los cercanos al
metro primero (suave, no excluye). (4) "trabajo desde casa" → prioriza los de más área / habitación extra.
Entrégame un resumen + confirma los 4 puntos.
