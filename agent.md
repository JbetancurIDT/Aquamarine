# Feature: Aqua — el agente de IA (Claude)

> Doc de feature (convención del repo). Índice en [CLAUDE.md](CLAUDE.md); aquí el detalle.
> Épica de origen: `../Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E03 - Agente IA (Claude).md`.
> Este doc cubre el **setup** del agente (system prompt + tool + loop + endpoint). Perfilamiento,
> scoring y nurturing vienen en tareas posteriores (T03.4.x / T03.5.x).

## Qué es / para qué
**Aqua** es el asistente conversacional cara al cliente: atiende al lead con tono cálido y humano,
entiende qué busca (sin formularios), recomienda **inmuebles reales** del inventario (RAG de E01) y
prepara el handoff a un asesor. Vive **dentro del backend** (`app/agent/`) y reusa E01 (búsqueda) y
E02 (persistencia de leads/mensajes).

## Piezas
- **`app/agent/prompts.py`** — `SYSTEM_PROMPT`: constante **estable** (sin fechas/IDs, para que el
  prompt caching funcione) con identidad/tono de Aqua, reglas de Claudia (nada de formularios, entender
  antes de ofrecer, no abrumar), las 4 dimensiones a perfilar, cuándo usar la tool y el handoff.
- **`app/agent/tools.py`** — `BUSCAR_INMUEBLES_TOOL` (schema para Claude, descripción prescriptiva) +
  `ejecutar_buscar_inmuebles(args)` → `(texto_compacto, inmuebles_crudos)`, reusando `app.rag.search`.
- **`app/agent/profiler.py`** — `PerfilExtraido` (schema) + `extraer_perfil(historial)` (una llamada de
  **extracción estructurada** con un modelo barato — solo lo confirmado, el resto `None`) +
  `fusionar_perfil(db, lead, extraido)` (persiste sin pisar datos previos con `None`). Detecta también el **idioma** (es/en).
- **`app/agent/scoring.py`** — `calcular_score(perfil, interes_urgencia, tiene_inmueble_interes)` → `(score 0–100, temperatura)`.
  Híbrido: completitud del perfil + tono/urgencia + foco en un inmueble específico.
- **`app/agent/handoff.py`** — `ejecutar_handoff_minimo(db, lead, *, sin_calificar=False)`: **idempotente**;
  asigna un asesor `disponible` del tenant (o `None` si no hay), pone el estado en `calificado` y emite el
  evento `handoff` con snapshot del lead. Adelanta parte de T06.1.2; el handoff REAL (notificación/UI) es E06.
- **`app/agent/orchestrator.py`** — `responder(db, lead, mensaje)`: persiste el mensaje del lead, arma el
  historial en formato Claude, corre el **loop manual de tool use** (máx 3 vueltas), persiste la respuesta, y
  en un **post-turno** (try/except, no rompe la respuesta): extrae+fusiona el perfil (incl. **origen deducido** e
  intención de hablar con un humano) → si `pide_humano` hace **handoff por solicitud** (sin calificar →
  `temperatura="desconocido"`, `score=None`) → si no, calcula score/temperatura, mueve el estado
  (nuevo→contactado; caliente→handoff; tibio/frío→nurturing). Devuelve `{respuesta, inmuebles, handoff, temperatura, lead_id}`.
- **`app/api/chat.py`** — `POST /chat` `{lead_id?, mensaje, origen?}` → `{respuesta, inmuebles, handoff, temperatura, lead_id}`.
  **Unificado: si no llega `lead_id`, el agente CREA el lead** (emite `lead_creado`) y devuelve su `lead_id`;
  si llega, continúa la charla (404 si no existe; mensaje vacío → 422). El `origen` lo simula la URL
  `/chat/<origen>/` (E04); `None` si no se sabe (el agente puede deducirlo). Registrado en `app/main.py`.

## Integración con Claude
- SDK oficial `anthropic`; cliente con la key **explícita** de settings
  (`anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)`).
- **Modelos configurables:** `settings.ANTHROPIC_MODEL` para la conversación (default `claude-sonnet-4-6`;
  subir a `claude-opus-4-8` para la demo) y `settings.ANTHROPIC_EXTRACTION_MODEL` para la extracción del
  perfil (default `claude-haiku-4-5`, barato para tarea mecánica). IDs sin sufijo de fecha.
- **Extracción estructurada:** `client.messages.parse(output_format=PerfilExtraido)` → el objeto validado
  llega en `block.parsed_output`.
- **Scoring/temperatura:** caliente = (zona + presupuesto + plazo<3m) **o** (urgencia alta + inmueble
  específico) **o** score≥70; tibio si score≥35; si no, frío. El agente mueve el estado del pipeline.
- **Prompt caching:** el `system` se envía como bloque con `cache_control: {"type": "ephemeral"}`; como
  el prompt es estable, se cachea y abarata las llamadas.
- **Loop de tool use:** `messages.create(... tools=[BUSCAR_INMUEBLES_TOOL])`; si `stop_reason == "tool_use"`
  se ejecuta el handler, se devuelve el `tool_result` y se vuelve a llamar hasta `end_turn` (máx 3 vueltas).
- **Idioma:** Aqua responde en el idioma del lead — **español o inglés** (el francés no entra en el MVP).

## Cómo correrlo
```bash
docker compose up -d                                   # BDs
cd backend
.venv/bin/alembic upgrade head                         # tablas (E02)
# pon ANTHROPIC_API_KEY en backend/.env  (opcional ANTHROPIC_MODEL=claude-opus-4-8 para la demo)
.venv/bin/uvicorn app.main:app --reload --port 8000    # API → http://localhost:8000/docs
# POST /chat {"mensaje":"Hola, busco un apto de lujo en El Poblado"} → devuelve lead_id; sigue con ese lead_id
```

## Tests (offline, sin gastar API)
`backend/tests/test_agent.py` mockea el cliente de Anthropic (`orchestrator._build_client`) y la búsqueda
RAG. Cubre: respuesta sin/con tool, request con `model`/`system` cache_control, scoring puro (`test_scoring.py`),
`/chat` que **crea** el lead vs. continúa, perfil+scoring integrados (caliente→calificado→handoff), y que
`fusionar_perfil` no borra datos previos con `None`.
```bash
cd backend && .venv/bin/python -m pytest -q     # 52 tests en verde (incluye E01/E02)
```

## Guardrails / pendientes
- **Costo:** cada turno gasta créditos de Anthropic (conversación + 1 extracción de perfil). Los tests no
  llaman a la API real (cliente + `extraer_perfil` mockeados); el smoke real lo corre el usuario.
- **`handoff`** se activa cuando el lead se vuelve `caliente` **o cuando pide un humano** (handoff por
  solicitud; sin calificar → `temperatura="desconocido"`). El `handoff_minimo` (asignar asesor + evento) ya
  está; el handoff REAL (notificación al asesor, UI, impersonación) se completa en **E06**.
- **Nurturing:** solo el esqueleto (marca `perfil["nurturing"]`); la reactivación programada queda en roadmap.

## Archivos
`app/agent/{prompts,tools,orchestrator,profiler,scoring,handoff}.py`, `app/api/chat.py`,
`app/core/config.py` (`ANTHROPIC_MODEL`, `ANTHROPIC_EXTRACTION_MODEL`), `app/main.py` (router),
`tests/{test_agent,test_scoring,test_handoff}.py`. Modelo/migración: `origen`/`score` nullable, temperatura `desconocido`.
