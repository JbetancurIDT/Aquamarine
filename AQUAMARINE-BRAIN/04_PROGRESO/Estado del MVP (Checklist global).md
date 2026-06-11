---
tipo: log
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-11
tags: [area/proyecto, progreso, checklist]
---

# Estado del MVP (Checklist global)

> Vista rápida del avance. La comercial puede leer esto para saber "qué ya está hecho" sin entrar al detalle técnico.

## Progreso por épica
- [x] **E00 — Setup y Fundaciones** → [[E00 - Setup y Fundaciones]]
- [x] **E01 — Ingesta RAG** → [[E01 - Ingesta RAG (Firecrawl + Chroma)]]
- [x] **E02 — Backend Core** → [[E02 - Backend Core (FastAPI + Postgres)]]
- [x] **E03 — Agente IA** → [[E03 - Agente IA (Claude)]]
- [x] **E04 — Chatbot Frontend** → [[E04 - Chatbot Frontend (React)]] — *cerrada: chat cableado a `POST /chat`, tarjetas con imagen real, temperatura oculta al lead, bloque de handoff, doc `chat.md`. Falta solo validar paleta vs [[Diseño UI (referencia)]] y tests de front.*
- [x] **E05 — CRM Pipeline y Dashboard** → [[E05 - CRM Pipeline y Dashboard]] — *cerrada: `/dashboard` con 8 KPIs + funnel + donut + por origen (tasas auditables), `/pipeline` Kanban con drag + asignación, modal de detalle centrado, scrollbar de marca, y `/performance` (tabla comparativa de asesores con semáforo SLA). Propiedades = mock.*
- [x] **E06 — Handoff Asesor** → [[E06 - Handoff Asesor]] — *cerrada: auto-asignación por menor cola + cap, disponibilidad del asesor, takeover humano (apaga IA + despedida), chat en vivo asesor↔cliente (polling), notificaciones escalonadas por temperatura + reasignación automática (barrido), vista `/asesor/:id` con bandeja + "En vivo · sin asignar".*
- [/] **E07 — Demo, Seed y Pulido** → [[E07 - Demo, Seed y Pulido]] — *seed de demo (~20 leads) + seed de asesores hechos. Falta guion de demo, pulido y checklist end-to-end.*
- [/] **E08 — Agente de Métricas (Gerencia)** → [[E08 - Agente de Métricas (Gerencia)]] — *adelantado: `/performance` + métricas por asesor reales ya existen (§4.4). Falta la burbuja Analyst conversacional (§4.5).*

## Hitos de la demo (lo que debe funcionar para presentar)
- [x] El cliente puede conversar con el asistente (chat web). *(E04 — chat funcional end-to-end)*
- [x] El asistente sugiere inmuebles reales y similares. *(RAG E01 + tarjetas con imagen E04; búsqueda por código exacto — R07)*
- [x] El score sube en vivo según la conversación. *(score+barra en el detalle del lead, pipeline/asesor con polling; en el chat público la temperatura se oculta a propósito)*
- [x] Al volverse caliente, el asesor recibe la notificación con el perfil. *(auto-asignación + toasts/campana en `/asesor/:id` + escalado por temperatura — E06)*
- [x] El panel muestra el embudo y las métricas. *(`/dashboard`: 8 KPIs + funnel + donut + por origen; `/performance` con SLA — E05)*
- [x] Datos seed cargados para que el panel se vea creíble. *(seed de demo ~20 leads + asesores)*

## Semáforo general
🟢 **Demo-able.** Back E01–E03 + chat (E04) + dashboard/pipeline/performance (E05) + handoff completo con auto-asignación balanceada, takeover humano que apaga la IA, chat en vivo y notificaciones escalonadas + reasignación (E06). Bloqueante R08 (`LeadOut.score`) **resuelto**. Falta: guion/pulido de demo (E07) y la burbuja Analyst conversacional (E08, §4.5).
