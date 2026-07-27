---
tipo: epica
audiencia: dev
estado: pendiente
epica: E11
actualizado: 2026-07-24
tags: [area/desarrollo, comp/agente, comp/crm, comp/dashboard, stack/claude, estado/pendiente]
---

# E11 — Clasificación de Intención de Compra (Comprador vs Curioso / "Lolo")

> **En términos de negocio:** no todos los que escriben quieren comprar. Muchos son **curiosos** ("lolos"/"cales" en Colombia): preguntan el precio o piden info por curiosidad, sin intención real de compra. Claudia quiere **medir cuántos de los que escriben son compradores reales vs curiosos**, y **en qué zonas o propiedades** pasa más — para no gastar el equipo en curiosos, entender la demanda real y leer el mercado ("el 70% de los que preguntan por El Poblado solo están mirando"). Es la promesa comercial *"su equipo no pierde tiempo con curiosos"* hecha dato.
> **Objetivo técnico:** un **eje nuevo e independiente** de clasificación del lead — `perfil.intencion ∈ {comprador, explorando, curioso}` — que **Aqua infiere** en cada turno (igual que ya infiere `plazo`/`movilidad`), con **derivación de fallback** para los leads históricos, un **evento de auditoría** para investigar la evolución en el tiempo, y una **métrica de % segmentada por zona y por propiedad** (reutilizando la infra de cercanía/demanda ya existente) expuesta a la gerencia vía el agente de insights + un tile en el dashboard.

> [!note] Estado: PLANEADA (2026-07-24) · post-MVP
> Épica **planeada, sin construir**. Decisión de origen: [[Decisiones (Decision Log)]] **D26**. Diseño aprobado por el dueño (señal inferida + fallback histórico · clasificación en lead + evento + métrica al vuelo · rúbrica por defecto · segmentación por zona **y** propiedad). Ejecuta el DEV siguiendo los prompts por tarea. Feature doc a crear: `intencion.md` (raíz).

## Contexto para el agente

No es un agente nuevo: es una **extensión del perfilamiento/scoring de Aqua** ([[E03 - Agente IA (Claude)]]) + una **métrica nueva para gerencia** ([[E08 - Agente de Métricas (Gerencia)]]). Se apoya en piezas que ya existen:

- El **profiler** (`backend/app/agent/profiler.py`) ya extrae un perfil estructurado por turno y persiste un subconjunto en `lead.perfil` (JSONB) vía `_CAMPOS_PERFIL`. Ya extrae `interes_urgencia` (alta/media/baja) — la señal más directa de "curioso vs serio" — **pero hoy la descarta** (no está en `_CAMPOS_PERFIL`).
- El **scoring** (`backend/app/agent/scoring.py`) calcula `(score, temperatura)`; **NO se toca en v1** (ver Fuera de alcance).
- La **segmentación por zona ya existe y es reutilizable:** `services/demanda.py` (`leads_por_ubicacion`) + `rag/search.py` (`_cumple_ubicacion`, match tolerante) + `perfil.zona`/`perfil.ciudad`. La propiedad de interés vive en `perfil.inmueble_interes`.
- Las **métricas se calculan al vuelo en Python** desde filas de `leads` con el patrón `Rate {pct,num,den}` (`api/metrics.py`); el **agente de insights** suma una tool con un edit de 3 pasos en `agent/insights_tools.py`.

### Rúbrica de clasificación (fuente de verdad del significado) — [[Decisiones (Decision Log)]] D26
- **`comprador`** (intención real): da **presupuesto** y **plazo** corto/medio; **o** pide **visita/cita** o hablar con un **asesor**; **o** se enfoca en un **inmueble concreto** (`inmueble_interes`) con urgencia alta.
- **`curioso`** ("lolo"): **solo** pregunta precio/info general; **sin** presupuesto; `plazo == "largo"` ("solo estoy mirando"); sin contacto; no quiere visita.
- **`explorando`** (intermedio): tiene algunas señales (p. ej. zona + tipo) pero no está comprometido; ni claramente comprador ni claramente curioso.
- El **titular** del reporte es binario para la gerencia: **% comprador vs % curioso** (`explorando` se muestra aparte y puede sumarse al numerador o no, según se lea).

### Principios del repo que se respetan
1. **Aqua es honesta y no invasiva:** infiere la intención del tono/contenido; **no** interroga al lead ("¿en serio vas a comprar?").
2. **Postgres escribe / Chroma solo lee:** `intencion` vive en `lead.perfil` (Postgres); la segmentación por zona usa `perfil.zona`/`ciudad` (Postgres), no Chroma.
3. **Multitenant:** todo scoped por `tenant_id` (como `demanda.py`/`metrics.py`).
4. **Sin contadores denormalizados:** el % se calcula al vuelo desde los leads; el histórico se reconstruye desde `eventos`.

## Dependencias
- **Requiere:** E02 (leads/eventos/`lead_service`), E03 (profiler + scoring + orquestador), E05/E08 (métricas + agente de insights + dashboard).
- **Se integra con:** E09/E10 (reutiliza `_cumple_ubicacion`/`leads_por_ubicacion` y las claves `perfil.zona`/`inmueble_interes`).
- **Bloquea:** nada (valor analítico agregado).

---

## Sprints y tareas

> Orden: **captura de la señal → derivación histórica → auditoría → métrica → surface (insights/dashboard) → tests/docs**. Las Etapas 1-4 son backend puro; la 5 toca el frontend; la 6 blinda y documenta.

### Etapa 11.1 — Señal de intención (captura por Aqua)
- [ ] **T11.1.1** — Extender el profiler con `intencion` + persistir `interes_urgencia`.
  - **Objetivo:** que Aqua clasifique la intención cada turno y quede en `perfil.intencion`; y dejar de tirar `interes_urgencia`.
  - **Archivos:** editar `backend/app/agent/profiler.py`.
  - **Criterio:**
    - [ ] `PerfilExtraido` gana `intencion: Literal["comprador","explorando","curioso"] | None` y su tool schema lo incluye con una **descripción que enseñe la rúbrica** (D26).
    - [ ] `_CAMPOS_PERFIL` incluye **`intencion`** e **`interes_urgencia`** → ambos se persisten en `lead.perfil` (patrón idéntico a `plazo`/`movilidad`); `fusionar_perfil` no pisa con `None`.
    - [ ] El system prompt de extracción (`_EXTRACTION_SYSTEM`) explica cómo mapear señales → intención (precio-solo/sin-presupuesto/"solo mirando" → curioso; presupuesto+plazo/visita/asesor → comprador; intermedio → explorando).
    - [ ] Tests con `PerfilExtraido` mockeado: un chat "¿cuánto vale?" sin más → `curioso`; uno con presupuesto+plazo corto → `comprador`.
  - **Prompt sugerido:** «En `backend/app/agent/profiler.py`: (1) añade a `PerfilExtraido` el campo `intencion: Literal['comprador','explorando','curioso'] | None = None` y refléjalo en el `input_schema` de la tool de extracción con una descripción que enseñe la rúbrica: curioso = solo pregunta precio/info, sin presupuesto, "solo mirando" (plazo largo), sin contacto; comprador = da presupuesto y plazo corto/medio, o pide visita/asesor, o se enfoca en un inmueble con urgencia; explorando = intermedio. (2) Agrega `'intencion'` y `'interes_urgencia'` a `_CAMPOS_PERFIL` para que se persistan en `lead.perfil`. (3) Extiende `_EXTRACTION_SYSTEM` con la regla de mapeo. No cambies el scoring. Añade tests que verifiquen que un "¿cuánto cuesta?" pelado sale `curioso` y uno con presupuesto+plazo corto sale `comprador`.»

### Etapa 11.2 — Derivación histórica (fallback) + backfill
- [ ] **T11.2.1** — `derivar_intencion(lead|perfil, temperatura)` pura (fallback determinista).
  - **Objetivo:** clasificar leads que no tienen `perfil.intencion` (los viejos) a partir de lo ya guardado, con la misma rúbrica.
  - **Archivos:** crear `backend/app/agent/intencion.py` (o añadir a `scoring.py`), función pura + tests.
  - **Criterio:**
    - [ ] `derivar_intencion(perfil, temperatura) -> "comprador"|"explorando"|"curioso"` sin red ni SDK: `comprador` si `temperatura in {caliente}` o (`presupuesto` y `plazo in {corto,medio}`) o `inmueble_interes` presente; `curioso` si `frio` y (sin presupuesto y `plazo=="largo"`); `explorando` en el resto.
    - [ ] Determinista y alineada con la rúbrica de D26; tests de casos límite.
  - **Prompt sugerido:** «Crea `backend/app/agent/intencion.py` con `derivar_intencion(perfil: dict, temperatura: str) -> str` (valores comprador/explorando/curioso) siguiendo la rúbrica de D26, sin red. Reglas: comprador si temperatura caliente, o presupuesto+plazo(corto|medio), o inmueble_interes; curioso si frio y sin presupuesto y plazo=="largo"; explorando en el resto. Tests puros de la tabla de casos.»
- [ ] **T11.2.2** — Script `backfill_intencion.py` idempotente.
  - **Objetivo:** poblar `perfil.intencion` en los leads existentes para tener muestra desde el día 1.
  - **Archivos:** crear `backend/scripts/backfill_intencion.py` (patrón de `seed_geo.py`/`seed_demo.py`).
  - **Criterio:**
    - [ ] Recorre `Lead` del tenant; si `perfil` no tiene `intencion`, la deriva con `derivar_intencion` y la guarda (merge de `perfil`, sin pisar otras claves). Idempotente; flags `--dry-run`/`--tenant`; imprime stats `{total, ya_tenian, derivados, por_intencion}`.
    - [ ] Emite el evento de auditoría (T11.3.1) por cada lead derivado.
  - **Prompt sugerido:** «Crea `backend/scripts/backfill_intencion.py` (patrón seed_demo). Por cada Lead del tenant sin `perfil['intencion']`, calcula `derivar_intencion(perfil, temperatura)`, mergea en `perfil` y persiste; emite el evento `intencion_clasificada`. Idempotente, `--dry-run`/`--tenant`, imprime stats.»

### Etapa 11.3 — Evento de auditoría (series de tiempo)
- [ ] **T11.3.1** — Emitir `intencion_clasificada` en `lead_service` cuando la intención se asigna/cambia.
  - **Objetivo:** dejar rastro histórico para investigar la **evolución** del ratio (no solo la foto actual), con la zona/propiedad en el payload para poder re-segmentar el pasado.
  - **Archivos:** editar `backend/app/services/lead_service.py` (helper que emite el evento) y el seam post-turno en `backend/app/agent/orchestrator.py` (llamarlo tras fusionar el perfil).
  - **Criterio:**
    - [ ] Nuevo `tipo` de evento **`intencion_clasificada`** con `payload = {"intencion", "zona", "ciudad", "inmueble_interes"}`.
    - [ ] Se emite **solo cuando cambia** (evita ruido por turno); el evento lo emite `lead_service`, **no** el router (respeta el patrón: solo `lead_service`/`handoff` emiten eventos).
    - [ ] Tests: cambio de intención emite 1 evento; sin cambio no emite.
  - **Prompt sugerido:** «Añade a `backend/app/services/lead_service.py` un helper `registrar_intencion(db, lead, intencion)` que, si difiere de la actual en `perfil`, actualiza `perfil['intencion']` y emite un `Evento(tipo='intencion_clasificada', payload={intencion, zona, ciudad, inmueble_interes})`. Llámalo desde el bloque post-turno de `orchestrator.responder()` tras `fusionar_perfil`. Solo emite al cambiar. Tests de emisión/no-emisión.»

### Etapa 11.4 — Métrica segmentada (% comprador vs curioso por zona/propiedad)
- [ ] **T11.4.1** — Endpoint `GET /metrics/intencion` (al vuelo, tolerante, tenant-scoped).
  - **Objetivo:** el dato central: % de intención global + desglose por zona y por propiedad.
  - **Archivos:** editar `backend/app/api/metrics.py` + `backend/app/schemas/metrics.py`.
  - **Criterio:**
    - [ ] Carga `Lead` del tenant (patrón `metrics.py`); para cada lead usa `perfil['intencion']` **o**, si falta, `derivar_intencion(perfil, temperatura)` como fallback (para no depender del backfill).
    - [ ] `por_intencion` global con `Rate {pct,num,den}`; `por_zona: [{zona, comprador, explorando, curioso, pct_comprador, pct_curioso}]` usando `_cumple_ubicacion`/`leads_por_ubicacion` (match tolerante, consistente con el heatmap); `por_propiedad` agrupando por `perfil['inmueble_interes']`.
    - [ ] Ordena zonas/propiedades por volumen; scoped por `tenant_id`; tests con leads mockeados (incluye un curioso "cerca del metro" que no matchea zona real → cuenta en global, no en zona).
  - **Prompt sugerido:** «En `backend/app/api/metrics.py` agrega `GET /metrics/intencion` que carga los leads del tenant, clasifica cada uno con `perfil['intencion']` o `derivar_intencion` de fallback, y devuelve: `por_intencion` (Rate por comprador/explorando/curioso), `por_zona` (reusando `_cumple_ubicacion`/`leads_por_ubicacion` de demanda.py) y `por_propiedad` (agrupado por `perfil['inmueble_interes']`), cada uno con pct_comprador/pct_curioso. Define el schema en `schemas/metrics.py` con `Rate`. Tests: global cuenta a todos; zona usa match tolerante; un curioso sin zona real cuenta en global pero no en zona.»

### Etapa 11.5 — Surface: agente de insights + dashboard
- [ ] **T11.5.1** — Tool de insights `intencion_por_zona` (edit de 3 pasos).
  - **Objetivo:** que Claudia pregunte en lenguaje natural "¿cuántos son curiosos en El Poblado?".
  - **Archivos:** editar `backend/app/agent/insights_tools.py`.
  - **Criterio:**
    - [ ] Añadir la tool a `TOOLS` (con param opcional `zona`), un `ejecutar_intencion(db, tenant, zona=None)` que reusa la métrica de T11.4.1, y una rama en el dispatcher `ejecutar_tool`. Sin tocar `insights_agent.py` ni `api/insights.py`.
  - **Prompt sugerido:** «En `backend/app/agent/insights_tools.py` agrega la tool `intencion_por_zona` (3 pasos: dict en `TOOLS` con param opcional zona; executor `ejecutar_intencion(db, tenant, zona=None)` que reusa la lógica de `GET /metrics/intencion`; rama en `ejecutar_tool`). Devuelve % comprador/curioso global o de la zona pedida. No toques insights_agent.py.»
- [ ] **T11.5.2** — Tile "Compradores vs Curiosos" en el dashboard.
  - **Objetivo:** mostrar el % y el top de zonas/propiedades con más curiosos.
  - **Archivos:** editar `frontend/src/pages/DashboardPage.tsx` (+ componente/tile nuevo, `api/` si aplica).
  - **Criterio:**
    - [ ] Tile con el % comprador vs curioso (barra/donut) + top zonas por % de curiosos; consume `GET /metrics/intencion`; respeta paleta de marca y `tsc` estricto (`npm run build` verde).
  - **Prompt sugerido:** «En `frontend/src/pages/DashboardPage.tsx` agrega un tile "Compradores vs Curiosos" que consuma `GET /metrics/intencion`: muestra % comprador/explorando/curioso (donut o barra) y un top de zonas por % de curiosos. Paleta de marca, responsive, `npm run build` verde.»

### Etapa 11.6 — Tests + documentación
- [ ] **T11.6.1** — Suite de tests del feature.
  - **Archivos:** crear `backend/tests/test_intencion.py`.
  - **Criterio:** [ ] cubre profiler→`intencion`, `derivar_intencion` (tabla de casos), emisión de `intencion_clasificada` al cambiar, y `GET /metrics/intencion` (global + por zona tolerante + por propiedad). Todo offline; los ~228 tests previos siguen verdes.
  - **Prompt sugerido:** «Crea `backend/tests/test_intencion.py` (sin red/SDK) cubriendo: extracción de `intencion` por el profiler, `derivar_intencion` por casos, evento `intencion_clasificada` (emite al cambiar, no si igual), y `/metrics/intencion` (global, por zona con match tolerante, por propiedad).»
- [ ] **T11.6.2** — `intencion.md` + `CLAUDE.md` + `Modelo de Datos.md`.
  - **Archivos:** crear `intencion.md` (raíz); editar `CLAUDE.md` (tabla de features). **Reportar al Planner** para que actualice `Modelo de Datos.md` (Obsidian).
  - **Criterio:**
    - [ ] `intencion.md`: qué resuelve, la rúbrica, cómo se infiere/deriva, el evento, la métrica segmentada, cómo correr el backfill y los tests.
    - [ ] Fila nueva en la tabla "Documentación por feature" de `CLAUDE.md`.
    - [ ] **Para el Planner (no lo toca el Dev):** en `Modelo de Datos.md` documentar `perfil.intencion` + `perfil.interes_urgencia`, el `eventos.tipo = intencion_clasificada`, y la métrica derivada; citar D26; bump `actualizado`.
  - **Prompt sugerido:** «Crea `intencion.md` en la raíz (qué resuelve, rúbrica, inferencia+derivación, evento, métrica por zona/propiedad, backfill, tests) y añádelo a la tabla de features de `CLAUDE.md`. Reporta al Planner el cambio para `Modelo de Datos.md`.»

---

## Definición de hecho (épica)
Escenario end-to-end:
1. **Curioso detectado:** un lead escribe *"¿cuánto vale ese apartamento del Poblado?"* y nada más → Aqua lo clasifica `perfil.intencion = "curioso"`, sin interrogarlo; se emite `intencion_clasificada`.
2. **Comprador detectado:** *"busco algo en Envigado hasta $800M, me mudo en 2 meses, ¿puedo visitarlo?"* → `intencion = "comprador"`.
3. **Investigación:** `GET /metrics/intencion` devuelve, p. ej., `comprador 32% · explorando 28% · curioso 40%`, con el desglose por zona (El Poblado 55% curiosos) y por propiedad; el histórico se puede reconstruir desde `eventos`.
4. **Gerencia:** Claudia pregunta en el dashboard *"¿en qué zonas hay más curiosos?"* y el agente de insights responde con datos reales; el tile lo muestra.

Los ~228 tests backend siguen verdes; los nuevos de intención pasan sin gastar APIs.

## Fuera de alcance (Fase 2)
- **Alimentar la `intencion` al scoring/temperatura.** En v1 es un **eje independiente**; re-ponderar la temperatura con la intención se evalúa después (evita desestabilizar el pipeline probado).
- **Nurturing ejecutable** de curiosos (campañas/reactivación programada) — hoy solo se marca; la ejecución sigue siendo el esqueleto de T03.5.1.
- **Drill-down UI** por propiedad (lista de leads curiosos de una propiedad) y export.
- **Score de "calidad de curioso"** (curioso que podría madurar) — señal futura.

## Decisión asociada — [[Decisiones (Decision Log)]] **D26**
El origen y el alcance de esta épica se registran en D26 (2026-07-24).

## Documentación del feature
Al construirlo, crea `intencion.md` en la raíz y enlázalo en la tabla "Documentación por feature" de `CLAUDE.md`; el Planner actualiza `Modelo de Datos.md`.
