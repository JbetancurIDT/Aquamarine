# Dashboard gerente + Pipeline Kanban — feature doc (E05 · ext. E07)

## Qué hace
Capa interna de CRM con varias vistas:
- `/dashboard` — panel de **gerencia/métricas**: 8 KPIs, funnel, donut, por-origen + (E07) bloque de
  **inventario** (mock) y resumen de **equipo de asesores**.
- `/pipeline` — **Kanban operativo**: 6 columnas por estado, drag-and-drop, asignación de asesor.
- `/asesores` — **índice de asesores**: tarjetas (iniciales + disponibilidad + carga) que enlazan al
  tablero de cada asesor (`/asesor/:id`); atajo de navegación para no tener que conocer el UUID.
- `/asesor/:asesorId` — bandeja del asesor; en E07 gana **en-vivo**, **disponibilidad** y **campana**.
- `/performance` — (E07) tabla de **performance por asesor** con semáforos de SLA.

> Los features E07 (takeover, barrido, en-vivo, performance, métricas por asesor) se documentan en
> **[handoff.md](handoff.md)**; aquí solo el dashboard de gerencia y el Kanban.
>
> El nav interno (Chat / Dashboard / Pipeline / Performance / Asesores) está unificado en el componente
> `components/ConsolaNav.tsx` (lo usan dashboard, pipeline, performance y asesores).

---

## Rutas frontend

| Ruta | Componente | Rol |
|---|---|---|
| `/dashboard` | `DashboardPage.tsx` | Gerencia: KPIs + funnel + donut + por-origen |
| `/pipeline` | `PipelinePage.tsx` | Kanban: 6 columnas + modal detalle + asignar asesor |
| `/asesores` | `AsesoresPage.tsx` | Índice de asesores en tarjetas (nombre + disponibilidad + carga) → enlaza a `/asesor/:id` |
| `/asesor/:id` | `AsesorPage.tsx` | Kanban del asesor: 4 columnas (calificado→negociando→ganado/perdido) + modal detalle |

---

## Backend: endpoints E05

| Endpoint | Descripción |
|---|---|
| `GET /metrics/overview` | Resumen completo del embudo + 8 KPIs (con filtros opcionales) |
| `PATCH /leads/{id}/asesor` | Asigna o desasigna asesor al lead (emite `asesor_asignado`) |
| `PATCH /leads/{id}/estado` | Cambia estado (ya existía; usado para drag-and-drop Kanban) |

---

## Fórmulas exactas de cada métrica (GET /metrics/overview)

> Convención §5: cada porcentaje se devuelve como `{ pct, num, den }` para auditoría.

### Pipeline y rangos

| Estado | Rank en embudo |
|---|---|
| nuevo | 0 |
| contactado | 1 |
| calificado | 2 |
| negociando | 3 |
| cerrado_ganado | 4 |

`cerrado_perdido` / `descartado` → rank efectivo = 2 (calificado) en el funnel.  
Esto evita que leads que no cerraron inflen la conversión hacia abajo.

### valor_lead (COP)

```
valor_lead = perfil.presupuesto_max  si disponible
           ?? null                    si no hay
```

### Fórmulas de KPIs

| KPI | Fórmula |
|---|---|
| **Total leads** | N (del tenant, tras filtros) |
| **Leads calientes** | #{temperatura == "caliente"} / N |
| **% calificados** | #{temperatura != "desconocido"} / N |
| **1ª respuesta** | promedio (seg) entre `lead.creado_en` y primer mensaje `rol="agente"` |
| **Funnel acumulado** | `funnel[i] = #{rank_efectivo(lead.estado) >= i}` para las 5 etapas en orden |
| **% paso previo** | `funnel[i] / funnel[i-1]` |
| **Lead → cita** | `funnel[calificado] / N` |
| **Cita → negociación** | `funnel[negociando] / funnel[calificado]` |
| **Pipeline ponderado** | `Σ (valor_lead × peso(estado))` sobre leads ABIERTOS |
| **Negocios ganados** | `#{estado == "cerrado_ganado"}` + `Σ valor_lead de esos` |

### Pesos del pipeline ponderado

| Estado | Peso |
|---|---|
| nuevo | 0.10 |
| contactado | 0.25 |
| calificado | 0.50 |
| negociando | 0.75 |
| cerrado_* / descartado | 0 (excluidos) |

### Filtros del endpoint

Query params opcionales: `asesor_id`, `origen`, `temperatura`, `zona` (= `perfil.zona`).  
Si no se pasa, no filtra. Filtran el conjunto de leads **antes** de calcular todas las métricas.

---

## Seed de demo (`scripts/seed_demo.py`)

Crea/asegura el tenant + asesores del tenant (Valentina Ruiz, Juana Páez, Mateo Ángel) + **22 leads**
con perfiles realistas de Medellín/Antioquia, conversaciones completas (incluyendo handoff y mensajes
de asesor en negociando/cerrado) e inmuebles reales de Chroma. **Idempotente** (borra y recrea
leads marcados con `perfil.demo=true`). 2 leads en inglés (extranjeros).

```bash
# Desde backend/
python scripts/seed_demo.py
```

### Distribución del seed (22 leads)

| Dimensión | Distribución |
|---|---|
| Temperatura | 6 caliente · 7 tibio · 7 frio · 2 desconocido |
| Estado | 3 nuevo · 5 contactado · 6 calificado · 4 negociando · 2 cerrado_ganado · 2 cerrado_perdido |
| Perfiles | Medellín (El Poblado, Patio Bonito, Las Palmas…) · Envigado · Guatapé · Cartagena |
| Conversaciones | negociando: 3 roles (lead/IA/asesor) · cerrado_ganado: cierre · cerrado_perdido: salida |

### Valores esperados del seed (para validar el dashboard 1:1)

> **Nota:** `cerrado_perdido` cuenta como rank=2 (calificado) en el funnel, igual que en la API.
> Estos números asumen una BD con solo los 22 leads de demo (sin leads pre-existentes).

| Métrica | Valor esperado |
|---|---|
| Total leads | 22 |
| % calificados | 90.9% (20/22) |
| Leads calientes | 27.3% (6/22) |
| Funnel | 22 → 19 → 14 → 6 → 2 |
| % paso previo | — / 86.4% / 73.7% / 42.9% / 33.3% |
| Lead → cita | 63.6% (14/22) |
| Cita → negociación | 42.9% (6/14) |
| Pipeline ponderado | $22,657.5 M COP (22,657,500,000 COP) |
| Negocios ganados | 2 · valor cerrado $5,760 M COP |
| 1ª respuesta | 30.0 s |

---

---

## Asistente Aqua — Burbuja de chat en `/dashboard` (E08)

FAB (`✦ Asistente`) fijo abajo-derecha en `/dashboard`. Abre un panel flotante (380×520 px,
animación suave, paleta de lujo) donde Claudia pregunta en lenguaje natural.

### Comportamiento
- **Chips sugeridos** (4 preguntas comunes) cuando el hilo está vacío.
- **Input con `/` menu**: escribir `/` despliega los 8 presets filtrables por texto; elegir uno
  envía esa pregunta directamente. También acepta texto libre (Enter envía).
- **Indicador "escribiendo…"**: 3 puntos animados mientras Haiku procesa (< 2 s típico).
- **Markdown formateado**: las respuestas de Aqua (negritas, listas, enlaces y **tablas** GFM) se
  renderizan con el componente compartido `components/MarkdownMessage.tsx` (react-markdown + remark-gfm,
  sin HTML crudo). Las tablas anchas hacen scroll horizontal dentro de la burbuja (`scrollbar-brand`).
  El mismo componente formatea las respuestas de Aqua en el chat del cliente (`/chat`) y en los timelines.
  **Alcance:** el Markdown se aplica solo al texto de la **IA (`rol='agente'`/`aqua`)**; el texto tecleado
  por el **lead** y por el **asesor humano** se muestra en texto plano (`whitespace-pre-wrap`), para no
  reinterpretar sus pulsaciones literales (`-`, `#`, `|`…) como formato.
- **Ante pregunta fuera de alcance**: Aqua se disculpa, dice que pronto podrá responder eso y
  agradece — **nunca inventa cifras**.

### Backend (E08)
| Componente | Ruta | Descripción |
|---|---|---|
| `POST /insights/ask` | `app/api/insights.py` | Body `{pregunta}` → `{respuesta, datos}` |
| Agente | `app/agent/insights_agent.py` | Loop tool-use sobre Claude Haiku 4.5, máx 3 vueltas |
| Tools | `app/agent/insights_tools.py` | 4 tools read-only que reutilizan helpers de `metrics.py` |

### 4 herramientas del agente
| Tool | Qué devuelve |
|---|---|
| `metricas_generales` | Total leads, calientes, conversión, pipeline ponderado, negocios ganados |
| `performance_asesores` | Por asesor: asignados, en cola, tomados, ganados, conversión, tiempos |
| `resumen_mensual` | Leads nuevos + valor cerrado por mes (últimos 12 meses) |
| `distribucion_leads` | Distribución por temperatura, origen y estado |

---

## PATCH /leads/{id}/asesor

Body: `{ "asesor_id": "<uuid>" | null }`  
- `null` → desasigna el asesor.  
- Valida que el asesor exista y sea del mismo tenant → 404 si no.  
- Emite evento `asesor_asignado` con `{ asesor_id, anterior }`.  
- Devuelve `LeadOut`.

---

## Pipeline Kanban (`/pipeline`)

- **6 columnas**: Nuevo · Contactado · Calificado · Negociando · Cerrado·ganado · Cerrado·perdido.
- **Drag & drop** HTML5 nativo: soltar una card en otra columna → `PATCH /leads/{id}/estado` + update optimista.
- **Modal de detalle** (`LeadDetailModal`): centrado (`min(900px,94vw)`, `max-h-[88vh]`), cierra con ✕/backdrop/Esc.
  - Columna izquierda: Score IA (barra), asesor select (`PATCH /leads/{id}/asesor`), acciones rápidas, perfil, metadata.
  - Columna derecha: timeline de conversación con scroll independiente.
  - Acciones rápidas: botones de transición de estado (gerente = todas; asesor = según `transicionesPermitidas`).
  - Polling 4.5 s del lead abierto.

## Vista asesor (`/asesor/:id`)

- **4 columnas**: Nuevo handoff (calificado) · En gestión (negociando) · Cerrado·ganado · Cerrado·perdido.
- **Leads filtrados**: solo los del asesor (`GET /asesores/{id}/leads`).
- **Drag restringido**: el asesor puede arrastrar hacia `negociando`, `cerrado_ganado`, `cerrado_perdido`; no puede regresar a estados anteriores.
- **Modal de detalle**: mismo `LeadDetailModal` con `transicionesPermitidas=['negociando','cerrado_ganado','cerrado_perdido']`.
- Polling lista 5 s.

## Componentes compartidos

| Componente | Ruta | Descripción |
|---|---|---|
| `KanbanBoard` | `src/components/KanbanBoard.tsx` | Board + columnas + cards parametrizable. Props: `columnas`, `leads`, `asesores`, `selectedId`, `onCardClick`, `onMoverEstado`, `estadosPermitidos?`. |
| `LeadDetailModal` | `src/components/LeadDetailModal.tsx` | Modal centrado con 2 columnas (datos + timeline). Props: `leadId`, `asesores`, `onClose`, `onMoverEstado`, `onAsignarAsesor`, `transicionesPermitidas?`. |
| `Scrollable` | `src/components/Scrollable.tsx` | Wrapper `overflow-auto` + `.scrollbar-brand[-thin]`. |

---

## Polling en tiempo real

| Vista | Intervalo | Qué refresca |
|---|---|---|
| `/dashboard` | 6 s | Métricas completas |
| `/pipeline` (lista) | 5 s | Lista de leads |
| `/pipeline` (modal) | 4.5 s | Lead abierto (`LeadDetailModal`) |
| `/asesor/:id` (lista) | 5 s | Lista de leads del asesor |
| `/asesor/:id` (modal) | 4.5 s | Lead abierto (`LeadDetailModal`) |

Todos los intervalos se limpian en el `cleanup` del `useEffect` correspondiente.

---

## Paleta / diseño

Variables CSS usadas: `--ink`, `--champ`, `--champ-bg`, `--champ-soft`, `--hot`, `--hot-bg`,
`--warm`, `--warm-bg`, `--cold`, `--cold-bg`, `--gray`, `--gray-soft`, `--line`, `--line-soft`,
`--card`, `--bg`, `--charcoal`.  
Fuente serif: `Newsreader` (valores grandes / títulos de KPI).
