---
tipo: log
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-09
tags: [area/proyecto, riesgos]
---

# Riesgos y Bloqueos

> Lo que puede salir mal y qué hacer al respecto. Mantener vivo durante la hackathon.

## Riesgos abiertos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| R01 | **URLs fuente del scraping no definidas.** Falta confirmar la web de Claudia y los portales exactos a scrapear. | Alto (bloquea E01) | Conseguir las URLs cuanto antes; plan B: cargar un dataset manual de ~15–20 inmuebles reales si Firecrawl falla con algún portal |
| R02 | **Portales con anti-scraping.** Algunos portales bloquean bots. | Medio | Firecrawl maneja parte; si un portal bloquea, priorizar la web propia de Claudia + carga manual |
| R03 | **Tono del agente "robótico".** Riesgo de no lograr la calidez que Claudia exige. | Alto (es el diferenciador) | Iterar el system prompt (T03.1.1) con ejemplos reales; validar en E07 |
| R04 | **Alcance vs. 2 días.** Demasiadas tareas para el tiempo. | Medio | Camino crítico definido; E05 y E06 son must-have, nurturing (T03.5) puede quedar como esqueleto |
| R05 | **Demo en vivo falla.** Dependencia de red/API en la presentación. | Alto | Plan B con datos seed + video de respaldo (ver [[Demo - Guion]]) |
| R06 | **Coherencia con "no chatbot básico / omnicanal" del reto.** El MVP simula canales. | Medio | Sostener narrativa de arquitectura desacoplada + mock de origen (ver [[Alcance del MVP]]) |

## Bloqueos activos
- ⛔ **R01 — URLs fuente:** pendiente de que el equipo/cliente las entregue. *Owner: dev + comercial.*

## Resueltos
- _(ninguno aún)_

> **Cómo usar:** cuando aparezca un bloqueo, agrégalo aquí con owner. Cuando se resuelva, muévelo a "Resueltos" con la fecha.
