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
- [x] **E07 — Demo, Seed y Pulido** → [[E07 - Demo, Seed y Pulido]] — *cerrada: `seed_demo.py` realista con **inmuebles reales de Chroma**, 3 asesores dinámicos, `cerrado_perdido` y casos `atendido_por_humano`; tests e2e críticos; guion + ejemplos de demo. Pendiente menor: correr el e2e en vivo con servicios arriba.*
- [x] **E08 — Agente de Métricas (Gerencia)** → [[E08 - Agente de Métricas (Gerencia)]] — *cerrada: `/performance` (§4.4) + **burbuja "Asistente Aquamarine"** en `/dashboard` (§4.5) con Haiku + tool-use real (`insights_agent`/`insights_tools`/`/insights/ask` + `AquaChat.tsx`), presets vía `/` + texto libre, honesta fuera de alcance.*

## Hitos de la demo (lo que debe funcionar para presentar)
- [x] El cliente puede conversar con el asistente (chat web). *(E04 — chat funcional end-to-end)*
- [x] El asistente sugiere inmuebles reales y similares. *(RAG E01 + tarjetas con imagen E04; búsqueda por código exacto — R07)*
- [x] El score sube en vivo según la conversación. *(score+barra en el detalle del lead, pipeline/asesor con polling; en el chat público la temperatura se oculta a propósito)*
- [x] Al volverse caliente, el asesor recibe la notificación con el perfil. *(auto-asignación + toasts/campana en `/asesor/:id` + escalado por temperatura — E06)*
- [x] El panel muestra el embudo y las métricas. *(`/dashboard`: 8 KPIs + funnel + donut + por origen; `/performance` con SLA — E05)*
- [x] Datos seed cargados para que el panel se vea creíble. *(seed de demo ~20 leads + asesores)*

## Semáforo general
🟢 **MVP completo — listo para presentar.** Las 9 épicas (E00–E08) cerradas: RAG con inventario real,
agente Aqua, chat del lead, dashboard + pipeline + performance, handoff completo (auto-asignación,
takeover humano, notificaciones escalonadas), seed realista con inmuebles reales, y la burbuja de
métricas para gerencia. Pendiente solo de **verificación e2e en vivo** (servicios arriba) y deuda
menor (tests de frontend, validación fina de paleta). Roadmap post-MVP: multitenancy + licencias (Fase 2).
