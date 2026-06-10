---
tipo: epica
audiencia: dev
estado: completado
epica: E01
actualizado: 2026-06-10
tags: [area/desarrollo, comp/rag, stack/firecrawl, stack/chroma, estado/completado]
---

# E01 — Ingesta RAG (Firecrawl + Chroma)

> **En términos de negocio:** enseñarle al asistente cuáles son los inmuebles reales de Claudia, para que no invente y pueda recomendar propiedades parecidas. Leemos sus páginas, copiamos la info de cada inmueble y la guardamos en una "memoria" que se busca por significado.
> **Objetivo técnico:** pipeline re-ejecutable que scrapea web + portales con Firecrawl, normaliza cada inmueble a un esquema común, genera embeddings y los carga en Chroma con metadata filtrable.

## Contexto para el agente
Fuentes: web propia de Claudia + portales donde publica (Metrocuadrado, Fincaraíz). Esquema de inmueble y metadata: ver [[Modelo de Datos]]. El patrón es Firecrawl (scrape → markdown/JSON limpio) → normalizar → embeddings → Chroma colección `inmuebles`. Debe ser **re-ejecutable on-demand**.

## Dependencias
- **Requiere:** E00 (Chroma configurado).
- **Bloquea:** E03 (el agente consulta este índice).
- **Paraleliza con:** E02.

## Etapas y tareas

### Etapa 1.1 — Scraping con Firecrawl
- [x] **T01.1.1** — Crear cliente Firecrawl y función de scrape de una URL.
  - **Criterio:** dada una URL de un inmueble, devuelve markdown/HTML limpio.
  - **Prompt sugerido:** "En backend/app/rag/firecrawl_client.py crea un cliente de Firecrawl que lea FIRECRAWL_API_KEY del entorno y exponga scrape_url(url) -> dict con el contenido en markdown. Maneja errores y rate limits con reintentos simples."
  - **Hecho (2026-06-10):** `firecrawl_client.scrape_url(url)` con SDK `firecrawl-py` v4 (`Firecrawl.scrape(formats=["markdown"], only_main_content=True)`), error claro si falta la key y reintentos con backoff (1s/2s/4s). Verificado offline con `scripts/test_scrape.py` (mock del SDK + ValueError sin key). Incluye **Paso 0**: Chroma pasa a **servidor** (`HttpClient`, contenedor `aquamarine-chroma`) y env Chroma/Postgres (`CHROMA_HOST`/`CHROMA_PORT`, se quita `CHROMA_PERSIST_DIR`). Smoke real (URL real) queda para el usuario (R01).
- [x] **T01.1.2** — Crawl de listados: obtener URLs de inmuebles desde las páginas índice.
  - **Criterio:** dada la URL de un listado, devuelve la lista de URLs de inmuebles individuales.
  - **Prompt sugerido:** "Agrega a firecrawl_client.py una función crawl_listing(listing_url) que use el modo crawl/map de Firecrawl para extraer todas las URLs de fichas de inmueble dentro de un portal o de la web de Claudia. Devuelve lista de URLs deduplicada."
  - **Nota:** las URLs fuente concretas se definen al implementar (ver [[Riesgos y Bloqueos]]).

### Etapa 1.2 — Normalización
- [x] **T01.2.1** — Extraer campos estructurados de cada inmueble con Claude.
  - **Criterio:** de un markdown de ficha sale un dict con {tipo, zona, ciudad, precio, moneda, habitaciones, banos, area_m2, estado, descripcion, url_fuente}.
  - **Prompt sugerido:** "Crea app/rag/normalizer.py con una función extract_property(markdown, url) que use Claude API para extraer un JSON estructurado del inmueble con el esquema de [Modelo de Datos]. Usa un prompt que fuerce salida JSON estricta y valida con un schema Pydantic InmuebleIn."
- [x] **T01.2.2** — Esquema Pydantic del inmueble + validación.
  - **Criterio:** registros inválidos se descartan o marcan, no rompen la ingesta.

### Etapa 1.3 — Carga en Chroma
- [x] **T01.3.1** — Generar el texto a embedear y upsert en Chroma con metadata.
  - **Criterio:** cada inmueble queda en la colección `inmuebles` con su texto y metadata filtrable; re-correr no duplica (upsert por `inmueble_id`).
  - **Prompt sugerido:** "Crea app/rag/indexer.py con upsert_inmueble(inmueble: InmuebleIn) que construya un texto descriptivo rico (zona+tipo+características+entorno) y haga upsert en la colección Chroma 'inmuebles' usando inmueble_id como id y el resto como metadata. Idempotente."

### Etapa 1.4 — Búsqueda semántica
- [x] **T01.4.1** — Función de búsqueda por similitud + filtros de metadata.
  - **Criterio:** `buscar_inmuebles(query, filtros)` devuelve top-k con filtros opcionales (zona, precio_max, habitaciones).
  - **Prompt sugerido:** "Crea app/rag/search.py con buscar_inmuebles(query: str, filtros: dict | None, k: int = 5) que consulte Chroma combinando similitud semántica con filtros de metadata (where). Devuelve lista de inmuebles con score de relevancia."

### Etapa 1.5 — Orquestación re-ejecutable
- [x] **T01.5.1** — Script de ingesta completo `scripts/ingest.py`.
  - **Criterio:** un comando corre todo (crawl → scrape → normalizar → indexar) y loguea cuántos inmuebles cargó.
  - **Prompt sugerido:** "Crea backend/scripts/ingest.py que orqueste el pipeline completo: recibe lista de URLs de listados, crawlea, scrapea cada ficha, normaliza con Claude, valida e indexa en Chroma. Imprime resumen (procesados, cargados, descartados). Debe ser re-ejecutable sin duplicar."
- [x] **T01.5.2** — Endpoint `POST /rag/reindex` para refrescar desde el dashboard.
  - **Criterio:** un botón en el dashboard dispara la reindexación (se conecta en E05).

## Definición de hecho (épica)
Corriendo `ingest.py`, el inventario real de Claudia queda buscable en Chroma; `buscar_inmuebles("apartamento en El Poblado 3 habitaciones")` devuelve resultados coherentes.

> ✅ **E01 cerrada (2026-06-10).** Pipeline Firecrawl→Chroma con extracción estructurada (sin Claude),
> schema `InmuebleIn` endurecido, búsqueda semántica + filtros (`buscar_inmuebles`) y endpoints
> `POST /rag/reindex` / `GET /rag/inmuebles/buscar`. Verificado contra la web real (`idealrealestate.com.co`).
> Detalle del feature: `Aquamarine Project/scraper.md`. *Nota: T01.2.1 se resolvió con extracción
> estructurada de Firecrawl, no con Claude (decisión del planner).*
