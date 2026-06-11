---
tipo: epica
audiencia: dev
estado: completado
epica: E03
actualizado: 2026-06-10
tags: [area/desarrollo, comp/agente, stack/claude, comp/rag, estado/completado]
---

# E03 — Agente IA (Claude)

> **En términos de negocio:** el corazón del producto. El asistente que conversa con el cliente como una persona, entiende qué busca, le muestra inmuebles reales (o parecidos), y va midiendo qué tan listo está para comprar. Nunca suena robótico, porque en el mercado de lujo la confianza es todo.
> **Objetivo técnico:** orquestador sobre Claude API con system prompt de dominio, tool de búsqueda RAG, perfilamiento incremental, scoring caliente/tibio/frío, y persistencia en Postgres.

## Contexto para el agente
Es la pieza que une E01 (Chroma) y E02 (Postgres). Reglas de negocio de Claudia (del transcript): tono humano y cálido, NADA de formularios, entender la necesidad real antes de mandar opciones, no abrumar con "todo el mercado", filtrar y ofrecer lo pertinente. El handoff humano es protagonista cuando el lead es caliente (mercado de patrimonio/confianza). Las 4 dimensiones de calificación (de la propuesta): tipo de inmueble, zona, presupuesto, plazo de decisión. **Idiomas objetivo del agente: español e inglés** (el francés queda fuera del target de este MVP).

> El agente se llama **Aqua** — ver [[Aqua — el nombre del agente]] (historia del nombre + tono) y el diseño del chat en [[Diseño UI (referencia)]] §4.1. Vive **dentro del backend** (`app/agent/`). **Modelo:** `claude-sonnet-4-6` (configurable por `ANTHROPIC_MODEL`; subir a `claude-opus-4-8` para la demo). No-streaming en el MVP.

## Dependencias
- **Requiere:** E01 (búsqueda), E02 (persistencia).
- **Bloquea:** E04 (el chat lo consume), E06 (dispara handoff).

## Etapas y tareas

### Etapa 3.1 — System prompt de dominio
- [x] **T03.1.1** — Redactar el system prompt del agente inmobiliario de lujo.
  - **Criterio:** define personalidad cálida y humana, reglas (no formularios, no abrumar, entender antes de ofrecer), las 4 dimensiones a perfilar, y cuándo escalar a asesor.
  - **Prompt sugerido:** "Crea backend/app/agent/prompts.py con SYSTEM_PROMPT para un agente inmobiliario de lujo colombiano. Debe: usar tono cálido y humano (nada robótico, sin formularios), perfilar gradualmente tipo de inmueble/zona/presupuesto/plazo a través de conversación natural, ofrecer inmuebles solo cuando entienda la necesidad, recomendar similares si el cliente duda, y nunca abrumar con muchas opciones. Incluye reglas para reconocer cuándo un lead está listo para pasar a un asesor humano."
- [x] **T03.1.2** — Detección de idioma (**es/en**) y respuesta en el idioma del lead.
  - **Criterio:** si el lead escribe en inglés, el agente responde en inglés; en cualquier otro caso, en español.
  - **Alcance (MVP):** los idiomas objetivo del agente son **español e inglés**. El **francés NO está dentro del target de este MVP** — aunque el campo `idioma` del lead pueda registrarlo como dato, el agente no se compromete a conversar en francés. (Ampliar idiomas queda como mejora futura.)

### Etapa 3.2 — Tool de búsqueda (RAG)
- [x] **T03.2.1** — Definir y registrar la tool `buscar_inmuebles` para Claude (tool use).
  - **Criterio:** Claude puede invocar la tool con {query, filtros}; el backend ejecuta `buscar_inmuebles` de E01 y devuelve resultados.
  - **Prompt sugerido:** "En backend/app/agent/tools.py define la tool de Claude 'buscar_inmuebles' (schema con query y filtros opcionales: zona, ciudad, precio_max, habitaciones, tipo). Implementa el handler que llama a app/rag/search.buscar_inmuebles y devuelve los resultados formateados para que Claude los presente al cliente de forma natural."

### Etapa 3.3 — Loop conversacional
- [x] **T03.3.1** — Orquestador que maneja el turno: recibe mensaje, llama a Claude con historial + tools, ejecuta tool si aplica, devuelve respuesta.
  - **Criterio:** maneja el ciclo tool-use de Claude (mensaje → tool_use → tool_result → respuesta final).
  - **Prompt sugerido:** "Crea backend/app/agent/orchestrator.py con responder(lead_id, mensaje_usuario) que: carga el historial del lead desde Postgres, llama a Claude API con el system prompt + historial + tools, maneja el ciclo de tool use (ejecuta buscar_inmuebles cuando Claude lo pida), persiste los mensajes (lead y agente) y devuelve la respuesta final. Usa el SDK de Anthropic."

### Etapa 3.4 — Perfilamiento y scoring
- [x] **T03.4.1** — Extraer/actualizar el `perfil` del lead tras cada turno.
  - **Criterio:** el `perfil` jsonb se va completando (tipo, zona, presupuesto, plazo) a medida que el lead habla.
  - **Prompt sugerido:** "Agrega al orquestador un paso que, tras cada turno, actualice el perfil del lead en Postgres extrayendo de la conversación: tipo de inmueble, zona/ciudad, rango de presupuesto, plazo de decisión, y notas. Usa Claude para extraer estructurado solo lo nuevo/confirmado, sin sobrescribir con nulos."
- [x] **T03.4.2** — Calcular el score y la temperatura.
  - **Criterio:** caliente = zona específica + presupuesto definido + plazo < 3 meses; tibio = 1–2 criterios; frío = exploratorio. Score 0–100 persistido + evento.
  - **Prompt sugerido:** "Crea app/agent/scoring.py con calcular_score(perfil, señales_conversacion) -> (score:int, temperatura:str). Reglas: caliente si tiene zona específica + presupuesto definido + plazo menor a 3 meses; tibio si cumple 1-2; frío si es exploratorio. Integra el cálculo en el orquestador para que actualice lead.score y lead.temperatura vía lead_service y emita evento score_actualizado."

### Etapa 3.5 — Nurturing (esqueleto)
- [x] **T03.5.1** — Marcar leads tibios/fríos para seguimiento y dejar el gancho de reactivación.
  - **Criterio:** un lead tibio queda en estado de nurturing con una nota de próximo contacto (la ejecución programada queda como roadmap; en el MVP basta dejarlo modelado y visible en el dashboard).

## Definición de hecho (épica)
Enviando mensajes al orquestador, el agente conversa con tono humano, busca inmuebles reales cuando corresponde, va completando el perfil y actualizando score/temperatura, y todo queda en Postgres. Al volverse caliente, queda listo para el handoff (E06).

> [!success] E03 cerrada — 2026-06-10
> **Aqua** funciona end-to-end. Archivos en `app/agent/`: `prompts.py` (system prompt de lujo, es/en, prompt caching), `tools.py` (`buscar_inmuebles` → E01), `orchestrator.py` (loop manual de tool use + post-turno), `profiler.py` (extracción estructurada del perfil con `claude-haiku-4-5`), `scoring.py` (híbrido), `handoff.py` (mínimo, idempotente). Endpoint **`POST /chat`** (`app/api/chat.py`).
> - **El agente es la 1ª capa (D15):** `/chat` con `lead_id` opcional → **crea el lead** (origen de la URL, puede null) y devuelve `lead_id` + `temperatura`.
> - **Scoring híbrido:** completitud del perfil (tipo/zona/presupuesto/plazo/hab) + bonus de urgencia + foco en un inmueble específico → score 0–100 + temperatura; caliente por regla núcleo (zona+presupuesto+plazo<3m) **o** urgencia+inmueble **o** score≥70.
> - **Estados:** nuevo→contactado (1er turno); →calificado al volverse caliente. Nurturing (esqueleto) marca tibios/fríos.
> - **Handoff por solicitud** ("quiero un humano"): handoff inmediato; si no alcanzó a calificar → `temperatura="desconocido"` + `score=null`. El handoff mínimo (asignar asesor + evento `handoff` + estado) **adelanta parte de [[E06 - Handoff Asesor|T06.1.2]]**; la notificación/UI/impersonación quedan para E06.
> - **Verificado:** **52 tests pytest en verde** (offline, sin gastar API). Smoke real con key: a cargo del usuario. Modelos: `claude-sonnet-4-6` (conversación) + `claude-haiku-4-5` (extracción). Detalle del feature: `Aquamarine Project/agent.md`.

> ✅ **E03 cerrada (2026-06-10).** Aqua sobre Claude (Sonnet 4.6 conversación + Haiku 4.5 extracción): system
> prompt + tool `buscar_inmuebles` + loop manual de tool use; `/chat` unificado que **crea el lead**;
> perfilamiento estructurado (`profiler.py`, idioma es/en), scoring híbrido (`scoring.py`), el agente mueve el
> estado del pipeline (nuevo→contactado→calificado) y activa el flag de `handoff` al volverse caliente;
> nurturing como esqueleto. **42 tests pytest en verde** (SDK de Anthropic mockeado, sin gastar API).
> Detalle: `Aquamarine Project/agent.md`. El handoff REAL (asignar asesor) es E06.
