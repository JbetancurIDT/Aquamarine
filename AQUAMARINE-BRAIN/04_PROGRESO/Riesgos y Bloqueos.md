---
tipo: log
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-11
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
| R10 | **El barrido vive en el proceso del backend.** Las notificaciones escalonadas/reasignación dependen de que el proceso (lifespan FastAPI) esté vivo; si se reinicia, el reloj continúa desde los timestamps en BD pero no hay "catch-up" de ciclos perdidos. | Bajo (operativo) | El estado vive en BD (`asignado_en`/`notificaciones_count`), así que se retoma solo. Para demo, usar `NOTIF_SCALE` con intervalos cortos. A futuro: scheduler dedicado si se despliega multi-proceso. |

## Bloqueos activos
- _(ninguno)_

## Resueltos
- ✅ **R08 — `LeadOut.score` null → 500 (2026-06-11):** corregido a `score: int | None` en `schemas/lead.py`; los endpoints serializan leads sin calificar sin romper. Verificado en código.
- ✅ **R09 — refresco en vivo de listas (2026-06-11):** `/pipeline` y `/asesor/:id` pollean la lista (~5 s) además del detalle; los handoffs nuevos aparecen solos.
- ✅ **R07 — Búsqueda por código exacto (2026-06-10):** implementado `obtener_inmueble_por_codigo` (`col.get(ids=[...])`, respeta tenant) + param `codigo` en la tool `buscar_inmuebles` + ruteo en el handler. **Pendiente de verificación funcional** con el caso real `9718612` (back + Chroma arriba).
- ✅ **R01 — URLs fuente (2026-06-10):** se confirmó la web propia de Claudia (`idealrealestate.com.co`) como fuente; el scrape real funcionó (~30k chars) y hay inmuebles reales indexados en Chroma. El plan B (carga manual) ya no es necesario para el MVP.

> **Cómo usar:** cuando aparezca un bloqueo, agrégalo aquí con owner. Cuando se resuelva, muévelo a "Resueltos" con la fecha.
