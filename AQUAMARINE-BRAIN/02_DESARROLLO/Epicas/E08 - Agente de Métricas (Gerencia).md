---
tipo: epica
audiencia: dev
estado: pendiente
epica: E08
actualizado: 2026-06-10
tags: [area/desarrollo, comp/agente, comp/dashboard, stack/claude, estado/pendiente]
---

# E08 — Agente de Métricas (Gerencia)

> **En términos de negocio:** un segundo asistente, este para **Claudia (la gerente)**. En vez de leer tablas o gráficas, le **pregunta en lenguaje natural** cómo va el negocio: "¿cuántos leads calientes hay esta semana?", "¿qué asesor va mejor?", "¿cuál es el tiempo de primera respuesta?", "¿qué zonas se están pidiendo más?". Responde con números reales y, si hace falta, una explicación corta.
> **Objetivo técnico:** un segundo agente Claude (patrón **tool use**) **de solo lectura** sobre las métricas y datos del negocio (Postgres de E02 + demanda de inmuebles de E01). Expone *tools* de métricas predefinidas (no text-to-SQL libre, para no alucinar ni exponer la BD), maneja el loop tool-use, y se sirve por un endpoint + un panel en el dashboard.

## Contexto para el agente
Es un agente **distinto** al de ventas (E03): otra audiencia (gerencia), datos **agregados**, tono **ejecutivo y conciso**, y **nunca inventa** — si no hay dato, lo dice. Reutiliza el patrón tool-use de Claude (ver [[E03 - Agente IA (Claude)]]) pero con *tools* de métricas en vez de RAG. Vive en el módulo de agentes del backend (`app/agent/`). Multitenant: solo datos del `tenant_id` actual. Las métricas objetivo están en [[Modelo de Datos]] (sección "Métricas derivadas") y se calculan desde `eventos` + `leads` (E02). Decisión que origina esta épica: [[Decisiones (Decision Log)]] **D13**.

## Dependencias
- **Requiere:** E02 (datos y métricas: `leads`, `eventos`, `asesores`, `/metrics/overview`). Se apoya en E01 (demanda de inmuebles) cuando aplique.
- **Se integra con:** E05 (el panel de Claudia es el surface natural del agente).
- **Bloquea:** nada (es valor agregado; no está en el camino crítico de la demo, pero suma mucho en el pitch).

## Etapas y tareas

### Etapa 8.1 — Herramientas de métricas (tools)
- [ ] **T08.1.1** — Definir las *tools* de métricas para Claude (solo lectura, agregadas, por `tenant_id`).
  - **Criterio:** cada tool devuelve datos **reales** del tenant (nada hardcodeado); cubren leads por estado/temperatura/origen, tiempo de primera respuesta, conversión (lead→cita→negociación), conteo por estado del pipeline, desempeño por asesor y zonas/inmuebles más consultados.
  - **Prompt sugerido:** "Crea backend/app/agent/insights_tools.py con funciones de métricas que reutilicen la lógica de E02 (lead_service / endpoint /metrics) y sus definiciones de tool para Claude (schema con parámetros como rango de fechas y asesor_id opcional). Solo lectura, siempre filtradas por tenant_id. No uses SQL libre: cada métrica es una función acotada."

### Etapa 8.2 — System prompt + orquestador gerencial
- [ ] **T08.2.1** — System prompt del agente gerencial + orquestador del loop tool-use.
  - **Criterio:** dada una pregunta en lenguaje natural, llama a las tools correctas y compone una respuesta con los números reales; si falta el dato, lo dice; responde en el idioma de la pregunta y con tono ejecutivo.
  - **Prompt sugerido:** "Crea backend/app/agent/insights_agent.py con responder_gerencia(pregunta, rango=None) que use Claude (tool use) con insights_tools. System prompt de gerencia: claro, ejecutivo, basado SOLO en datos de las tools, sin inventar; si no hay datos, dilo. Maneja el ciclo mensaje→tool_use→tool_result→respuesta. Devuelve el texto y (opcional) los datos crudos usados."
- [ ] **T08.2.2** — Interpretación de rango temporal (hoy / esta semana / este mes) — esqueleto.
  - **Criterio:** preguntas con "esta semana" o "este mes" acotan las métricas al rango; si no se especifica, usa un default razonable (ej. últimos 30 días).

### Etapa 8.3 — Endpoint
- [ ] **T08.3.1** — `POST /insights/ask` que recibe la pregunta y devuelve la respuesta del agente.
  - **Criterio:** `POST /insights/ask {"pregunta": "¿cuántos leads calientes hay esta semana?"}` responde con el número real y una frase de contexto.
  - **Prompt sugerido:** "Crea backend/app/api/insights.py con POST /insights/ask {pregunta, rango?} que llame a responder_gerencia y devuelva {respuesta, datos?}. Regístralo en app/main.py."

### Etapa 8.4 — Surface en el dashboard
- [ ] **T08.4.1** — Panel "Pregúntale a Aquamarine" en el dashboard (E05).
  - **Criterio:** Claudia escribe una pregunta en una caja del dashboard y ve la respuesta; incluye 2–3 preguntas sugeridas de ejemplo.
  - **Prompt sugerido:** "En el dashboard React (E05), agrega un panel con una caja de texto que llame a POST /insights/ask y muestre la respuesta del agente gerencial. Ofrece chips con preguntas sugeridas ('¿cómo van los leads esta semana?', '¿qué asesor va mejor?')."

## Definición de hecho (épica)
Claudia abre el dashboard, escribe "¿cómo van los leads esta semana y cuáles están calientes?" y recibe una **respuesta correcta basada en datos reales** de Postgres; las cifras coinciden con las del panel de métricas (E05). El agente nunca inventa: ante falta de datos, lo dice.

## Documentación del feature
Al construirlo, crea `Aquamarine Project/insights-agent.md` y enlázalo en `CLAUDE.md` (convención de docs por feature).
