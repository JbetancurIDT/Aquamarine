---
tipo: epica
audiencia: dev
estado: completado
epica: E07
actualizado: 2026-07-24
tags: [area/desarrollo, comp/demo, estado/completado]
---

# E07 — Demo, Seed y Pulido

> **En términos de negocio:** dejar todo listo para la presentación: datos de ejemplo creíbles, un guion que se vea fluido, y los detalles finales para que nada falle en vivo.
> **Objetivo técnico:** datos seed, escenario de demo reproducible, pulido de UI y manejo de errores, y verificación del flujo end-to-end.

## Contexto para el agente
La demo prometida muestra el flujo completo: lead entra (mock origen) → agente conversa y califica → se vuelve caliente → handoff al asesor → todo visible en el dashboard. Coordinar con el guion comercial en [[Demo - Guion]].

## Dependencias
- **Requiere:** E01–E06.

## Etapas y tareas

### Etapa 7.1 — Datos seed
- [ ] **T07.1.1** — Script de seed: tenant Aquamarine, 1–2 asesores, algunos leads en distintos estados.
  - **Criterio:** `scripts/seed.py` deja el dashboard con datos creíbles (pipeline poblado, métricas con sentido).
  - **Prompt sugerido:** "Crea backend/scripts/seed.py que inserte: el tenant Aquamarine, 2 asesores, y ~8 leads de ejemplo distribuidos en los estados del pipeline con temperaturas variadas, orígenes mixtos (web/meta/portales) y conversaciones cortas, para que el dashboard y las métricas se vean realistas en la demo."
- [ ] **T07.1.2** — Asegurar inventario real cargado en Chroma (correr ingesta).
  - **Criterio:** hay inmuebles reales buscables para la demo (ver [[E01 - Ingesta RAG (Firecrawl + Chroma)]]).

### Etapa 7.2 — Escenario de demo
- [ ] **T07.2.1** — Guion técnico reproducible (lead "extranjero busca apto en El Poblado").
  - **Criterio:** existe un script de conversación de ejemplo que recorre frío → tibio → caliente → handoff de forma confiable.

### Etapa 7.3 — Pulido y robustez
- [ ] **T07.3.1** — Manejo de errores y estados de carga en frontend.
  - **Criterio:** sin pantallas en blanco; errores muestran mensajes amables.
- [ ] **T07.3.2** — Revisión de tono del agente con casos del mercado de lujo.
  - **Criterio:** el agente no abruma, no usa formularios, suena humano (validar contra reglas de [[E03 - Agente IA (Claude)]]).

### Etapa 7.4 — Verificación final
- [ ] **T07.4.1** — Checklist end-to-end antes de presentar.
  - **Criterio:** se completa el flujo entero sin intervención manual; tiempos de respuesta aceptables.

## Definición de hecho (épica)
La demo corre de principio a fin de forma confiable y se ve profesional; los datos y el inventario son creíbles; el tono del agente es humano.
