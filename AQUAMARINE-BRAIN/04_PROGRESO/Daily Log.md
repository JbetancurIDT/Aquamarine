---
tipo: log
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-10
tags: [area/proyecto, log, progreso]
---

# Daily Log

> Bitácora del proyecto. Cada avance, una línea. Sirve para que la comercial sepa en qué va el dev y viceversa. Formato: fecha + qué se hizo + referencia a tarea (ej. T03.2.1).

## 2026-06-09 — Planeación
- Cerrado el alcance del MVP y el stack (ver [[Decisiones (Decision Log)]] D01–D09).
- Creado este vault como cerebro del proyecto.
- Definidas las épicas E00–E07 con tareas granulares.
- **Pendiente de definir:** URLs fuente concretas para el scraping (ver [[Riesgos y Bloqueos]]).

## Día 1 (hackathon) — 2026-06-09
- [E00] **Setup y Fundaciones completado.** Monorepo `Aquamarine Project/` (backend FastAPI + frontend React+TS con Vite + `docs/`). Backend: `GET /health` ok, SQLAlchemy 2.0 + Alembic (migraciones contra Postgres), Chroma embebido (`get_chroma_client()` + colección `inmuebles`). Frontend: rutas `/chat` y `/dashboard`; `/chat` consulta `/health` → "backend ok". Verificado en runtime (build + servidores). T00.1.1, T00.2.1, T00.2.2, T00.3.1, T00.3.2, T00.4.1, T00.5.1 ✅

## Día 2 (hackathon) — 2026-06-10
- [E00] **Ajuste de entorno.** Backend y frontend corren **nativos**; Docker **solo para las BDs**: se quitó el `Dockerfile` del backend y se agregó `docker-compose.yml` (Postgres). Chroma sigue embebido. Ver [[Decisiones (Decision Log)]] D10.
- [E00] **VS Code:** `.vscode/tasks.json` con **`Ctrl+Shift+B`** que levanta back + front en paralelo (lado a lado), sin Docker. Detalle en [[Setup del Entorno]].
- [E01] **Paso 0 — Chroma a modo servidor + env.** `chroma_client` ahora usa `HttpClient` contra el contenedor `aquamarine-chroma` (`localhost:8002`); en `config.py` se agregan `CHROMA_HOST`/`CHROMA_PORT` y se elimina `CHROMA_PERSIST_DIR`; `.env.example`/`.env` actualizados (keys API vacías para el usuario). Verificado: `heartbeat` + `col inmuebles 0`.
- [E01] **T01.1.1 — Cliente Firecrawl.** Nuevo `app/rag/firecrawl_client.py` con `scrape_url(url) -> {"url", "markdown"}` (SDK `firecrawl-py` v4, formato markdown, error claro sin key, reintentos con backoff). Guardrail `scripts/test_scrape.py` (Caso A offline con mock + ValueError; Caso B smoke real opcional). Verificado el Caso A. Archivos: `app/core/config.py`, `app/rag/chroma_client.py`, `app/rag/firecrawl_client.py`, `requirements.txt` (+`firecrawl-py`), `scripts/test_scrape.py`, `.env(.example)`. T01.1.1 ✅
- [E01] **T01.1.1 — smoke real validado.** Con la key del usuario, scrape real de una ficha de `idealrealestate.com.co` (web de Claudia) devolvió ~30k chars de markdown ✅. Se agregó `_normalize_url()` al cliente: tolera URLs pegadas con envoltorios (`<'...'>`, comillas) y agrega `https://` si falta el esquema (Firecrawl exige URL con esquema). El cromo/menú del sitio lo limpiará la extracción con Claude en T01.2.1.
- [E01] **Extracción estructurada (sin Claude) + indexado.** `extract_property` (Firecrawl JSON + schema, `max_age` 48h), schema `InmuebleIn`, mapper `to_inmueble`, `map_properties` (endpoint map, filtro de fichas), y `scripts/ingest.py` (extract → validar → upsert idempotente en Chroma). Verificado 1 ficha real (count=1, idempotente). Archivos: `app/schemas/inmueble.py`, `app/rag/firecrawl_client.py`, `scripts/ingest.py`, `scripts/test_inmueble.py`. T01.1.1/T01.1.2/T01.2.1/T01.2.2/T01.3.1.
- [E01] **Endurecido tras revisión adversarial** — schema tolerante, normalización de listas, parseo de miles, reintentos de errores permanentes, upsert protegido. Tests offline ampliados.
- [E01] **Cierre: búsqueda + endpoint + convención de docs.** `app/rag/search.py` (`buscar_inmuebles` semántica + filtros, siempre por `tenant_id`); `ingest()` movido a `app/rag/ingest.py` (CLI delgado); endpoints `POST /rag/reindex` y `GET /rag/inmuebles/buscar` (`app/api/rag.py`, registrados en `main.py`). Nueva convención: un `<feature>.md` por feature en la raíz enlazado desde `CLAUDE.md` → creado `scraper.md`. Verificado: where offline + búsqueda con 5 fichas + endpoints (TestClient). **E01 cerrada ✅**
- [E02] **Endurecido tras revisión adversarial.** `response_model` tipado en `/metrics/overview` (contrato para el front), tenant por defecto a prueba de carreras (`tenants.nombre` UNIQUE + migración + `IntegrityError`→re-SELECT), N+1 quitado en métricas (`selectinload`), bucket `"otros"` + invariante de conteos, y `contenido` de mensaje no vacío. Nuevos tests: tiempo de primera respuesta determinista, **aislamiento multitenant**, invariante y validaciones. **28 tests en verde.**
- [E02] **Backend Core completo (CRM + métricas).** Modelos SQLAlchemy (tenants/leads/mensajes/asesores/eventos, UUID+JSONB+timestamptz), migración Alembic aplicada (`pgcrypto`), `lead_service` (centraliza eventos), schemas Pydantic, routers `/leads` (+filtros, detalle con mensajes, PATCH estado), `/leads/{id}/mensajes`, `/metrics/overview`. **24 tests pytest en verde** (BD aislada, happy/422/404/efectos). Doc: `crm.md` enlazado en `CLAUDE.md`. **E02 cerrada ✅**
- [docs/planeación] **Vault al día con lo construido.** Decisiones **D11** (Chroma como servidor en Docker), **D12** (extracción con Firecrawl, no Claude) y **D13** (segundo agente gerencial). `Modelo de Datos` con el **schema extendido** de `InmuebleIn`. `Stack Tecnológico` y `Setup del Entorno` corregidos (Chroma servidor; env `CHROMA_HOST`/`CHROMA_PORT`). Nueva épica **[[E08 - Agente de Métricas (Gerencia)]]** + checklist y MOC actualizados.

---
> **Cómo usar:** al cerrar una tarea, agrega una línea aquí y marca el checkbox en su épica. Sube `actualizado` en el frontmatter.
