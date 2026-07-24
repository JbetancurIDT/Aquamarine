---
tipo: epica
audiencia: dev
estado: completado
epica: E05
actualizado: 2026-07-24
tags: [area/desarrollo, comp/dashboard, comp/crm, stack/react, estado/completado]
---

# E05 — CRM Pipeline y Dashboard

> **En términos de negocio:** el panel donde Claudia (y sus asesores) ven todos sus clientes en un solo lugar: en qué paso del embudo van, qué tan listos están, de dónde vinieron, y los números del negocio. Es el "un solo lugar claro" que ella pidió, en vez de tener todo regado.
> **Objetivo técnico:** vistas React que consumen la API de E02: tablero de pipeline (tipo kanban), detalle de lead con conversación, y dashboard de métricas.

## Contexto para el agente
Consume `GET /leads` (filtros), `GET /leads/{id}`, `GET /metrics/overview`, `PATCH /leads/{id}/estado`. Estados del pipeline en [[Modelo de Datos]]. Métricas objetivo: volumen por origen/temperatura, tiempo de respuesta, conversión, conteo por estado, inmuebles más consultados.

## Dependencias
- **Requiere:** E02 (API), idealmente datos de E03/E07.
- **Bloquea:** demo.

## Etapas y tareas

### Etapa 5.1 — Tablero de pipeline (kanban)
- [ ] **T05.1.1** — Vista kanban con columnas por estado y tarjetas de lead.
  - **Criterio:** columnas (nuevo, contactado, calificado, negociando, cerrado, descartado); cada tarjeta muestra nombre, temperatura (color), origen y score.
  - **Prompt sugerido:** "Crea una vista Kanban en React+TS para /dashboard que liste leads por estado en columnas. Cada tarjeta muestra nombre, badge de temperatura (caliente=rojo, tibio=amarillo, frío=azul), origen y score. Datos desde GET /leads. Permite mover una tarjeta de estado (PATCH /leads/{id}/estado)."

### Etapa 5.2 — Detalle del lead
- [ ] **T05.2.1** — Panel de detalle con perfil, conversación y score.
  - **Criterio:** al clicar una tarjeta, se ve el perfil (tipo/zona/presupuesto/plazo), el historial de conversación y el score/temperatura.
  - **Prompt sugerido:** "Crea un panel/modal de detalle de lead que muestre el perfil estructurado, el timeline de la conversación (lead/agente/asesor) y el score con su temperatura. Datos desde GET /leads/{id}."

### Etapa 5.3 — Dashboard de métricas
- [ ] **T05.3.1** — Tarjetas KPI + gráficas de volumen, temperatura y conversión.
  - **Criterio:** muestra tiempo de primera respuesta, leads por origen, distribución por temperatura, embudo de conversión.
  - **Prompt sugerido:** "Crea un dashboard de métricas en React que consuma GET /metrics/overview y muestre: tarjetas KPI (tiempo de primera respuesta, total leads, % calificados), un gráfico de barras de leads por origen, un donut de distribución por temperatura, y un embudo de conversión lead→cita→negociación. Usa recharts."
- [ ] **T05.3.2** — Panel de inmuebles más consultados (mapa de calor de demanda).
  - **Criterio:** lista/visual de los inmuebles o zonas más buscados por los leads.

### Etapa 5.4 — Acciones de gestión
- [ ] **T05.4.1** — Botón de re-indexar inventario (conecta con `POST /rag/reindex` de E01).
  - **Criterio:** desde el dashboard se puede refrescar el inventario y se ve feedback de cuántos inmuebles cargó.

### Etapa 5.5 — Performance de asesores
- [ ] **T05.5.1** — Vista de desempeño por asesor (comparativa + detalle).
  - **Criterio:** tabla comparativa ordenable (1ª respuesta, conversión, leads, valor) con semáforo ok/risk/under vs meta y promedio de equipo; detalle por asesor con gauge de score y métricas auditables. Métricas: [[E08 - Agente de Métricas (Gerencia)]]. Diseño: [[Diseño UI (referencia)]] §4.4.

## Definición de hecho (épica)
Claudia abre `/dashboard`, ve sus leads en el embudo, entra al detalle de uno, revisa la conversación y el score, y consulta las métricas del negocio en vivo.

## Diseño (UI) — ver [[Diseño UI (referencia)]] §4.2–4.4
Consola **interna**. Dashboard de gerencia (8 KPIs incl. 1ª respuesta y conversión; funnel; donut por temperatura; por origen; demanda por zona; top inmuebles; seguimiento urgente). Kanban por **estado del embudo** (no por temperatura) + panel lateral `LeadDetail` con timeline. La burbuja **Analyst** (E08) flota sobre esta vista. Nota: el dashboard pide un par de métricas extra a las de E02 (pipeline ponderado, negocios ganados, % calificados) → **ampliar `/metrics/overview`**.
