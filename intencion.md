# Intención de compra — Comprador vs Curioso ("lolo") · E11

> **En términos de negocio:** no todos los que escriben quieren comprar. Muchos son **curiosos**
> ("lolos"): preguntan precio o piden info por curiosidad, sin intención real. Este feature mide
> **cuántos son compradores vs curiosos** para que el equipo no gaste tiempo con curiosos y para
> leer la demanda real. Es la promesa *"su equipo no pierde tiempo con curiosos"* hecha dato.

> [!note] Estado — **Feature completo** (handoffs 1–3)
> Construido: la **señal** (Aqua infiere `perfil.intencion` cada turno), la **derivación de
> fallback** determinista, el **backfill** idempotente, el **evento de auditoría**
> `intencion_clasificada`, la **métrica segmentada** `GET /metrics/intencion` (% por zona y
> propiedad, al vuelo), la **tool de insights** `intencion_por_zona`, el **tile** del dashboard
> y la **suite de tests** offline. Falta solo que el Planner registre `perfil.intencion` /
> `perfil.interes_urgencia` / `eventos.tipo=intencion_clasificada` en `Modelo de Datos.md`.
> Decisión de origen: **D26**. Épica: `E11` (en la vault). Regla de oro: es un **eje NUEVO e
> independiente** — en v1 **NO** toca el scoring/temperatura (`scoring.py` no se edita).

## Qué es

Un eje de clasificación del lead, ortogonal al scoring/temperatura:

```
perfil.intencion ∈ { "comprador", "explorando", "curioso" }
```

Aqua **infiere** la intención del tono/contenido de la conversación (nunca interroga al lead
"¿en serio vas a comprar?"). Los leads históricos —sin la señal— se clasifican con una función
determinista de fallback. Cada **cambio** de intención deja un evento para reconstruir la
evolución en el tiempo.

## Rúbrica (fuente de verdad del significado — D26)

| Intención | Señales |
|---|---|
| **`comprador`** | Da **presupuesto** + **plazo** corto/medio; **o** pide **visita/cita** o hablar con un **asesor**; **o** se enfoca en un **inmueble concreto** con urgencia. |
| **`curioso`** ("lolo") | **Solo** pregunta precio/info general; **sin** presupuesto; plazo **largo** ("solo estoy mirando"); sin contacto ni visita. |
| **`explorando`** | Intermedio: algunas señales (p. ej. zona + tipo) pero sin compromiso. |

## Cómo se infiere (en vivo) — `backend/app/agent/profiler.py`

- `PerfilExtraido` gana el campo `intencion: Literal["comprador","explorando","curioso"] | None`.
- La tool de extracción (`extraer_perfil_cliente`) incluye `intencion` en su `input_schema` con
  una **descripción que enseña la rúbrica**, y `_EXTRACTION_SYSTEM` explica el mapeo señales→intención.
- `interes_urgencia` (que antes **se extraía y se descartaba**) ahora **se persiste** en `lead.perfil`
  (se añadió a `_CAMPOS_PERFIL`) para el análisis.
- **Nota de diseño:** `intencion` **NO** está en `_CAMPOS_PERFIL`. Su persistencia la hace
  `lead_service.registrar_intencion` (único escritor de `perfil['intencion']`). Si `fusionar_perfil`
  la pre-escribiera, el evento de auditoría —que se emite **solo al cambiar**— nunca vería un cambio.
  Aun así `perfil['intencion']` queda persistida cada turno.

## Derivación de fallback (histórico) — `backend/app/agent/intencion.py`

```python
derivar_intencion(perfil: dict, temperatura: str) -> "comprador" | "explorando" | "curioso"
```

Pura, determinista, sin red ni SDK. Misma rúbrica de D26:
- `comprador` si `temperatura == "caliente"`, **o** `presupuesto` + `plazo ∈ {corto, medio}`, **o** `inmueble_interes` presente.
- `curioso` si `temperatura == "frio"` **y** sin `presupuesto` **y** `plazo == "largo"`.
- `explorando` en el resto.

Es el fallback para leads sin `perfil.intencion` (los viejos) y —en el handoff 2— para la métrica al vuelo.

## Evento de auditoría — `backend/app/services/lead_service.py`

`registrar_intencion(db, lead, intencion)`:
- Si `intencion` **difiere** de la guardada en `perfil`, fija `perfil['intencion']` y emite un
  `Evento(tipo="intencion_clasificada")`. **Solo emite al cambiar** (nada de un evento por turno).
- Payload: `{"intencion", "zona", "ciudad", "inmueble_interes"}` — zona/ciudad/propiedad para
  poder **re-segmentar el pasado** desde `eventos`.
- Lo llama el orquestador (`orchestrator.responder`) en el bloque post-turno, **después** de
  `fusionar_perfil` (para que el payload lleve la zona/propiedad ya actualizada). Patrón del repo:
  el evento lo emite `lead_service`, no el router.

## Backfill idempotente — `backend/scripts/backfill_intencion.py`

Puebla `perfil.intencion` en los leads existentes (para tener muestra desde el día 1):

```bash
# desde backend/
python scripts/backfill_intencion.py            # aplica
python scripts/backfill_intencion.py --dry-run  # no escribe; solo reporta
python scripts/backfill_intencion.py --tenant "Aquamarine Group"
```

Por cada `Lead` del tenant sin `intencion`: la deriva con `derivar_intencion`, mergea en `perfil`
(sin pisar otras claves) y emite el evento (vía `registrar_intencion`). **Idempotente**: una
segunda corrida no deriva nada. Imprime stats `{total, ya_tenian, derivados, por_intencion}`.

## Métrica segmentada — `GET /metrics/intencion` (`backend/app/api/metrics.py`)

Tenant-scoped, **al vuelo** (patrón `metrics.py`: carga `Lead` del tenant y agrega en Python;
sin contadores denormalizados). Cada lead se clasifica con `perfil['intencion']` **o**, si falta,
`derivar_intencion(perfil, temperatura)` como fallback (no depende del backfill). Devuelve:
- `por_intencion`: global, `Rate {pct,num,den}` por comprador / explorando / curioso.
- `por_zona`: `[{zona, comprador, explorando, curioso, total, pct_comprador, pct_curioso}]`. Las
  zonas salen del **inventario** (Chroma); un lead se asigna a una zona por **match tolerante contra
  la zona** (`_cumple_ubicacion({"zona": …})`, acentos/tokens ≥4). Un lead sin zona real
  (p. ej. "cerca del metro") o de ciudad ("Medellín") cuenta en el global pero **no** en zona.
- `por_propiedad`: agrupado por `perfil['inmueble_interes']` (con título del inventario si existe).
- Zonas y propiedades ordenadas por volumen.

> [!warning] Semántica de `por_zona` (para el Planner)
> El match tolerante permite que un lead cuente en **varias etiquetas de zona solapadas** de la misma
> familia (p. ej. "Poblado" / "El Poblado - Milla De Oro" / "Poblado Campestre" comparten los leads de
> "El Poblado"). Es la semántica del heatmap ("demanda relevante a esta zona"), **no** una partición.
> Se corrigió el sangrado peor (matchear solo la zona, no título/ciudad) para que barrios no
> relacionados no hereden demanda ajena; colapsar familias de zona a una sola fila es una decisión de
> producto pendiente.

## Surface: insights + dashboard

- **Tool de insights** `intencion_por_zona` (`backend/app/agent/insights_tools.py`): param opcional
  `zona`; `ejecutar_intencion(db, tenant, zona=None)` reusa `calcular_intencion` (misma lógica del
  endpoint). Responde en lenguaje natural "¿cuántos son curiosos en El Poblado?".
- **Tile "Compradores vs Curiosos"** (`frontend/src/pages/DashboardPage.tsx`): barra apilada del %
  global (comprador/explorando/curioso) + top de zonas por % de curiosos. Consume `GET /metrics/intencion`.

## Tests — `backend/tests/test_intencion.py`

Todo offline (sin red/SDK): captura de `intencion` por el profiler, tabla de casos de
`derivar_intencion`, emisión de `intencion_clasificada` (emite al cambiar, no si es igual, no si es
`None`), el seam del orquestador (payload fusionado; curioso no exige datos extra), el backfill
(deriva + idempotente + dry-run) y la **métrica** (`_intencion_metrics` puro: global + zona tolerante
+ propiedad; endpoint con Chroma mockeado; tool de insights con/sin zona).
`python -m pytest tests/test_intencion.py`.

## Fuera de alcance (roadmap)
- **Alimentar la intención al scoring/temperatura** — Fase 2 (en v1 es un eje independiente).
- **Colapsar familias de zona** a una sola fila en `por_zona` (decisión de producto — ver aviso arriba).
- **Drill-down UI** por propiedad (lista de leads curiosos) y export.
