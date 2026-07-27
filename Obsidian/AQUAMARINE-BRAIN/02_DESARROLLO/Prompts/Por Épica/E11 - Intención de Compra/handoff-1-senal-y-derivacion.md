Rol: eres el DEV de Aquamarine (lee `Obsidian/AGENTES.md`). Feature nuevo: **clasificación de intención de compra** del lead — comprador vs curioso ("lolo"). Rama nueva `feat/e11-intencion` (desde `master`, que ya trae E09/E10). Editas código; **NUNCA** edites `Obsidian/**`. El detalle completo por tarea vive en la épica `Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E11 - Clasificación de Intención de Compra (Comprador vs Curioso).md` y en la decisión [[Decisiones (Decision Log)]] **D26**; este prompt es autosuficiente.

OBJETIVO DE ESTE HANDOFF (Etapas 11.1 + 11.2 + 11.3 = el motor de clasificación + su rastro histórico): Aqua clasifica la intención de cada lead cada turno y la persiste; los leads viejos se clasifican con una función determinista de fallback + un backfill idempotente; y cada cambio de intención deja un evento de auditoría para poder investigar la evolución en el tiempo.

REGLA DE ORO (D26): la intención es un **eje NUEVO e INDEPENDIENTE**. En v1 **NO** toca el scoring/temperatura → **`scoring.py` no se edita**. Aqua **infiere** la intención del tono/contenido; **NO interroga** al lead ("¿en serio vas a comprar?").

RÚBRICA (fuente de verdad del significado):
- `comprador` = da **presupuesto** + **plazo** corto/medio; **o** pide **visita/cita** o hablar con un **asesor**; **o** se enfoca en un **inmueble concreto** con urgencia alta.
- `curioso` ("lolo") = **solo** pregunta precio/info general; **sin** presupuesto; plazo "largo" ("solo estoy mirando"); sin contacto ni visita.
- `explorando` = intermedio (algunas señales, p. ej. zona+tipo, pero sin compromiso).

── A) SEÑAL EN EL PROFILER (backend/app/agent/profiler.py) — T11.1.1 ──
- Añade a `PerfilExtraido` el campo `intencion: Literal["comprador","explorando","curioso"] | None = None` y refléjalo en el `input_schema` de la tool de extracción con una **descripción que enseñe la rúbrica** de arriba.
- Agrega `'intencion'` **y** `'interes_urgencia'` a `_CAMPOS_PERFIL` para que ambos se persistan en `lead.perfil` (patrón idéntico a `plazo`/`movilidad`). OJO: hoy `interes_urgencia` **se extrae pero se descarta** (no está en `_CAMPOS_PERFIL`) — esto lo rescata. `fusionar_perfil` no debe pisar con `None`.
- Extiende `_EXTRACTION_SYSTEM` con la regla de mapeo señales→intención: precio-solo / sin-presupuesto / "solo mirando" → `curioso`; presupuesto+plazo corto/medio / visita / asesor → `comprador`; intermedio → `explorando`.

── B) DERIVACIÓN DE FALLBACK (backend/app/agent/intencion.py — NUEVO) — T11.2.1 ──
- Crea `derivar_intencion(perfil: dict, temperatura: str) -> str` (valores comprador/explorando/curioso), **pura, sin red ni SDK**, misma rúbrica que D26:
  - `comprador` si `temperatura` caliente, **o** (`presupuesto` presente y `plazo in {corto, medio}`), **o** `inmueble_interes` presente.
  - `curioso` si `temperatura` fría **y** sin `presupuesto` **y** `plazo == "largo"`.
  - `explorando` en el resto.
- Determinista; es el fallback para leads sin `perfil.intencion` (los viejos) y para la métrica del handoff 2.

── C) BACKFILL (backend/scripts/backfill_intencion.py — NUEVO) — T11.2.2 ──
- Patrón de `seed_geo.py`/`seed_demo.py`. Recorre `Lead` del tenant; si `perfil` no tiene `intencion`, la deriva con `derivar_intencion(perfil, temperatura)`, **mergea** en `perfil` (sin pisar otras claves) y persiste. Idempotente. Flags `--dry-run` / `--tenant`. Imprime stats `{total, ya_tenian, derivados, por_intencion}`. Emite el evento de la sección D por cada lead derivado.

── D) EVENTO DE AUDITORÍA (backend/app/services/lead_service.py + seam en backend/app/agent/orchestrator.py) — T11.3.1 ──
- Nuevo `tipo` de evento **`intencion_clasificada`** con `payload = {"intencion", "zona", "ciudad", "inmueble_interes"}` (zona/ciudad/propiedad para poder re-segmentar el pasado).
- Helper `registrar_intencion(db, lead, intencion)` en `lead_service.py`: si `intencion` **difiere** de la que está en `perfil`, actualiza `perfil['intencion']` y emite el `Evento`. **Solo emite al cambiar** (nada de un evento por turno). Respeta el patrón del repo: el evento lo emite **`lead_service`**, no el router.
- Llama `registrar_intencion` desde el bloque **post-turno** de `orchestrator.responder()`, **después** de `fusionar_perfil`.

── E) TESTS (backend/tests/, sin red ni SDK) ──
- profiler: con `PerfilExtraido` mockeado, un "¿cuánto vale?" pelado → `curioso`; presupuesto+plazo corto → `comprador`.
- `derivar_intencion`: tabla de casos límite (comprador / curioso / explorando).
- evento: un cambio de intención emite exactamente 1 `intencion_clasificada`; sin cambio, no emite.
- Los ~228 tests previos siguen verdes.

VERIFICACIÓN (corre o describe): (1) chat "¿cuánto cuesta ese apto del Poblado?" y nada más → `perfil.intencion == "curioso"` sin que Aqua interrogue; (2) "busco en Envigado hasta $800M, me mudo en 2 meses, ¿lo puedo visitar?" → `comprador`; (3) `python backend/scripts/backfill_intencion.py --dry-run` imprime stats coherentes y es idempotente; (4) un cambio de intención emite un solo evento `intencion_clasificada` con zona/propiedad en el payload; (5) `scoring.py` sin tocar.

PARA aquí. Entrégame un resumen (archivos tocados + resultado de tests + los 5 puntos de verificación) y **repórtame para el cerebro**: los campos nuevos `perfil.intencion` + `perfil.interes_urgencia` y el evento `intencion_clasificada` — los registro yo en `Modelo de Datos.md`. **No sigas con el handoff 2** hasta que el Planner audite este.
