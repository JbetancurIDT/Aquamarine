# Feature: Scraping + RAG (ingesta e índice de inmuebles)

> Doc de feature (convención del repo). El índice está en [CLAUDE.md](CLAUDE.md); aquí va el detalle.
> Épica de origen: `../Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E01 - Ingesta RAG (Firecrawl + Chroma).md`.

## Qué es / para qué
Índice **semántico** del inventario real de Claudia (web `idealrealestate.com.co`, plantilla wasi.co)
para que el agente recomiende **inmuebles reales** (RAG) y no invente. Leemos cada ficha, la
estandarizamos a un esquema común y la guardamos en Chroma, buscable por significado + filtros.

## Flujo
```
map_properties(base_url)      → descubre las URLs de todas las fichas (endpoint `map` de Firecrawl, barato)
   → extract_property(url)    → Firecrawl extracción estructurada JSON (SIN Claude) → dict de contenido
   → to_inmueble(raw, url)    → mapper: combina contenido + campos fijos/derivados, limpia y VALIDA (Pydantic)
   → upsert en Chroma         → idempotente por `inmueble_id` (re-correr no duplica)
```
Re-ejecutable on-demand (CLI o endpoint). La extracción la hace **Firecrawl**, no Claude.

## Integración con Chroma
- **Servidor en Docker**: contenedor `aquamarine-chroma` (imagen `chromadb/chroma:1.5.9`), `localhost:8002`
  (→ `:8000` interno), cliente `HttpClient` en `app/rag/chroma_client.py`.
- **Colección** `inmuebles`; **embeddings** = función por defecto de Chroma (all-MiniLM-L6-v2, se calcula
  en el cliente). Server en Rust → solo API **v2** y CORS por `chroma-config.yaml` (`cors_allow_origins`).
- Por inmueble se guarda: **id** (`inmueble_id`), **document** (texto que se embebe) y **metadata** (campos
  planos filtrables). `descripcion` va en el document, no en la metadata.

## Schema `InmuebleIn` (`app/schemas/inmueble.py`)
- **Obligatorios mínimos:** `inmueble_id`, `url_fuente`, `titulo`, `ciudad`. El resto es opcional para no
  descartar fichas válidas cuando Firecrawl omite un campo (p.ej. "Precio a consultar" → `precio` None).
- **Reglas de limpieza:** listas normalizadas sin explotar strings en caracteres (`caracteristicas`,
  `imagenes`); parseo del separador de miles colombiano (`"1.234 m2"` → 1234); geo `0,0` → `None`;
  precios a `int` sin puntos; `tipo`/`tipo_negocio`/`condicion` a minúsculas; `es_lujo` desde las
  características ("Inmueble de Lujo").
- **metadata para Chroma:** solo `str|int|float|bool`; sin `None` (se omiten); `caracteristicas` → string;
  `imagenes` → JSON string.

## Capacidades
- **`buscar_inmuebles(query, filtros, k=5)`** (`app/rag/search.py`): búsqueda **tolerante** (E09).
  - **Filtros duros en el `where` de Chroma** (numéricos/confiables): `tenant_id`, `tipo_negocio`,
    `precio_min`/`precio_max`, `habitaciones`/`banos` (≥), `es_lujo`.
  - **`tipo`/`zona`/`ciudad` NO van como `$eq` duro** (era la causa de los 0 resultados): se inyectan
    en el texto de la consulta (señal semántica) y se aplican como **post-filtro tolerante** —
    normalización sin acentos + `contains` + **aliases de tipo** (familias: casa↔finca↔campestre,
    apartamento↔apto↔penthouse, lote↔terreno). "Las Palmas" hace match en "Alto de las Palmas".
  - **Relax-and-retry:** over-fetch (20) y, si quedan < k, relaja en orden **zona → tipo → precio ±15%**
    y reintenta. **Nunca devuelve vacío si hay inmuebles dentro de precio/habitaciones.**
  - Cada resultado se marca **`coincidencia: "exacta" | "cercana"`** (+ `motivo`) para que el agente
    distinga matches exactos de alternativas cercanas y lo comunique con honestidad. Devuelve metadata
    + `relevancia` + `coincidencia` + `motivo`.
  - `obtener_inmueble_por_codigo(codigo)` (R07) sin cambios: lookup exacto por id, sin embedding.
- **Endpoints** (`app/api/rag.py`, registrados en `app/main.py`):
  - `POST /rag/reindex` — dispara la ingesta (cuerpo `{base_url?, urls?, limit?}`); el botón del dashboard
    la usará en E05. Síncrono en el MVP (TODO: background/cola si hace falta).
  - `GET /rag/inmuebles/buscar?q=...&ciudad=&zona=&tipo=&precio_max=&habitaciones=&es_lujo=&k=` — prueba la búsqueda.

## Cómo correrlo
```bash
docker compose up -d                                   # BDs (Postgres + Chroma)
cd backend
.venv/bin/python scripts/ingest.py --no-index --url "<URL>"   # prueba 1 ficha, sin indexar
.venv/bin/python scripts/ingest.py --url "<URL>"             # indexa 1 ficha
.venv/bin/python scripts/ingest.py --limit 5                 # mapea el sitio e indexa 5
.venv/bin/python scripts/ingest.py                           # TODO el inventario
```
Variables en `backend/.env`: `FIRECRAWL_API_KEY`, `CHROMA_HOST` (localhost), `CHROMA_PORT` (8002),
`DATABASE_URL`, `DEFAULT_TENANT_ID` (aquamarine).

## Guardrails y límites
- **Costo Firecrawl:** ~1 crédito por ficha; `max_age` de 48h cachea y evita re-scrapear (re-correr es ~gratis).
  El barrido completo (~130 fichas) lo dispara el usuario, no automático. Circuit-breaker: aborta tras 5 errores seguidos.
- **R01:** por ahora una sola fuente (`idealrealestate.com.co`); el base URL entra por parámetro, no se hardcodea.
- **Matching de `zona`/`ciudad`/`tipo` ya NO es `$eq` duro** (resuelto en E09): es post-filtro tolerante
  (sin acentos + substring + aliases) con relax-and-retry. Mejora opcional pendiente: enriquecer el
  `document` embebido con sinónimos en `ingest.py` (no obligatorio; el post-filtro ya resuelve el recall).

## Archivos
`app/rag/firecrawl_client.py` (extract/map/mapper), `app/rag/ingest.py` (orquestación), `app/rag/search.py`
(búsqueda), `app/rag/chroma_client.py` (cliente Chroma), `app/schemas/inmueble.py` (schema), `app/api/rag.py`
(endpoints), `scripts/ingest.py` (CLI), `chroma-config.yaml` (config del server Chroma + CORS).
