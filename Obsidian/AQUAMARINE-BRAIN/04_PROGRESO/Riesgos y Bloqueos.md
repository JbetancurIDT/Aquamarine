---
tipo: log
audiencia: ambos
estado: en-progreso
actualizado: 2026-07-24
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
| R11 | **Dependencia de fuentes geo en vivo (Overpass/Nominatim/GTFS).** Disponibilidad y rate limits de servicios públicos gratuitos (E09/E10). | Medio | Los datos se **materializan offline** en artefactos versionados (`geocache`/`metro`/`poi`) que se consumen en runtime; `geocode_vivo` respeta 1 req/s con caché; la ingesta es **falla-suave** (`[geo-skip]`) y nunca aborta por un fallo geo (ver [[Decisiones (Decision Log)]] D24) |
| R12 | **Drift / versionado de los artefactos geo.** `geocache.json`/POIs/estaciones se desactualizan frente al mundo real; además `geocode_vivo` escribe entradas `lugar:*` en el `geocache.json` versionado → el archivo deriva con el uso. | Bajo | Fechar y regenerar periódicamente vía `build_metro`/`build_poi`/`build_geocache`; si se busca reproducibilidad, mover la caché runtime a un archivo aparte/gitignored (follow-up) |
| R13 | **Dependencia de routing externo (ORS/OSRM).** El mapa por propiedad depende de servicios de ruteo de terceros. | Bajo | Cadena de fallback **ORS→OSRM→línea recta** (D23): OSRM público da rutas por calles sin API key y la recta garantiza respuesta; **la búsqueda no depende de rutas**, solo la visualización |
| R14 | **Cobertura de coordenadas en Chroma.** Muchos inmuebles sin lat/lng precisa; se geocodifica por **centroide de barrio/municipio** (~1.5 km de error); todos los de una misma (zona,ciudad) comparten `dist_*_m`. | Bajo (honestidad por diseño) | **Piso de radio 1500 m** y filtro DURO que **omite** los inmuebles sin dato (D21); copy aproximado obligatorio ("a pocos minutos", nunca cifra exacta) |

## Bloqueos activos
- _(ninguno)_

## Resueltos
- ✅ **R08 — `LeadOut.score` null → 500 (2026-06-11):** corregido a `score: int | None` en `schemas/lead.py`; los endpoints serializan leads sin calificar sin romper. Verificado en código.
- ✅ **R09 — refresco en vivo de listas (2026-06-11):** `/pipeline` y `/asesor/:id` pollean la lista (~5 s) además del detalle; los handoffs nuevos aparecen solos.
- ✅ **R07 — Búsqueda por código exacto (2026-06-10):** implementado `obtener_inmueble_por_codigo` (`col.get(ids=[...])`, respeta tenant) + param `codigo` en la tool `buscar_inmuebles` + ruteo en el handler. **Pendiente de verificación funcional** con el caso real `9718612` (back + Chroma arriba).
- ✅ **R01 — URLs fuente (2026-06-10):** se confirmó la web propia de Claudia (`idealrealestate.com.co`) como fuente; el scrape real funcionó (~30k chars) y hay inmuebles reales indexados en Chroma. El plan B (carga manual) ya no es necesario para el MVP.

> **Cómo usar:** cuando aparezca un bloqueo, agrégalo aquí con owner. Cuando se resuelva, muévelo a "Resueltos" con la fecha.
