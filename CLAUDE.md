# Aquamarine Project — El producto (código)

Este es el repositorio del **producto real** de Aquamarine: el agente de IA + CRM + dashboard
para Aquamarine Group SAS (finca raíz de lujo). Repo git independiente del de documentación.

> [!note] Estado actual
> **Épicas E00–E07 completadas.** Backend completo: modelos Postgres, agente conversacional con tool
> use, RAG semántico + búsqueda exacta, endpoints leads / asesores / métricas con filtros, handoff
> automático con **balanceo por carga**, **takeover humano** (IA silenciada), **barrido** de
> notificaciones + reasignación, `GET /metrics/asesores` + `/metrics/propiedades` (mock). Frontend:
> `/chat` (+ banner de asesor humano), `/dashboard` (KPIs + funnel + donut + inventario + equipo),
> `/pipeline` (Kanban), `/asesor/:id` (en-vivo + disponibilidad + campana), `/performance` (SLA).
> **145 tests backend en verde.** Pendiente: Analyst (§4.5).

## Documentación por feature (convención)

El contexto detallado de cada feature vive en su propio `<feature>.md` en la raíz de este repo,
referenciado desde aquí. Este CLAUDE.md es el índice; los `.md` de feature tienen el detalle (cómo
funciona, integraciones, capacidades, cómo correrlo). **Al construir o cambiar un feature, crea o
actualiza su `<feature>.md` y enlázalo en esta tabla.**

| Feature | Doc | Resumen |
|---|---|---|
| Scraping + RAG (ingesta e índice de inmuebles) | [scraper.md](scraper.md) | Firecrawl → `InmuebleIn` → Chroma; búsqueda semántica + filtros; `POST /rag/reindex` |
| CRM / Backend Core (leads, conversación, pipeline, métricas) | [crm.md](crm.md) | Modelos Postgres + eventos; API `/leads`, `/leads/{id}/mensajes`, `/metrics/overview` |
| Agente Aqua (IA conversacional sobre Claude) | [agent.md](agent.md) | System prompt + tool `buscar_inmuebles` + loop de tool use; endpoint `POST /chat` |
| Chat del lead (E04) | [chat.md](chat.md) | Chat web público `/chat[/:origen]`; `useChatSession`; tarjetas con imágenes reales; handoff UI |
| Dashboard métricas + Pipeline Kanban (E05/E06) | [dashboard.md](dashboard.md) | `/dashboard` (KPIs/funnel/donut) + `/pipeline` (Kanban drag-drop + asignar asesor) + `/asesor/:id`; `GET /metrics/overview` con filtros; `PATCH /leads/{id}/asesor`; seed_demo.py |
| Handoff completo: takeover + barrido + performance (E07) | [handoff.md](handoff.md) | Auto-asignación por carga; `POST /leads/{id}/tomar` (IA silenciada); barrido (notificaciones + reasignación); `/leads/en-vivo`, `PATCH /asesores/{id}/disponibilidad`, `GET /metrics/asesores` + `/metrics/propiedades`; `/performance` con SLA |
| Búsqueda por proximidad geográfica (E09) | [geo.md](geo.md) | Cercanía haversine: categorías fijas (`dist_*_m` precalculadas en Chroma) + tool `cerca_de`/`radio_km` como filtro DURO y honesto (metro solo Valle de Aburrá). CORE v1; fuentes en vivo (OSM/GTFS/Nominatim) y fallback por nombre propio en roadmap |

## Dónde está el contexto del proyecto

La **fuente de verdad** (negocio, alcance, arquitectura, épicas, modelo de datos) vive en la
vault de Obsidian, en el repo hermano: `../Obsidian/AQUAMARINE-BRAIN/`. Antes de construir,
consulta especialmente:

- `02_DESARROLLO/Arquitectura.md` — diseño del sistema y flujo del lead
- `02_DESARROLLO/Stack Tecnológico.md` — librerías y decisiones por capa
- `02_DESARROLLO/Modelo de Datos.md` — tablas
- `02_DESARROLLO/Epicas/` — E00→E07, tareas con prompts listos para Claude Code
- `01_PROYECTO/Alcance del MVP.md` — qué entra y qué no

## Stack previsto

| Capa | Tecnología |
|---|---|
| Frontend | React + TypeScript (Vite) — chat del lead + dashboard/CRM |
| Backend | FastAPI (Python) — SQLAlchemy + Alembic, Pydantic, Uvicorn |
| Motor IA | Claude API (SDK Anthropic), patrón tool use (`buscar_inmuebles`) |
| BD relacional | PostgreSQL (fuente de verdad: leads, conversaciones, scoring, pipeline, métricas) |
| BD vectorial | Chroma (índice semántico de inventario, solo lectura) |
| Scraping | Firecrawl (ingesta on-demand de inmuebles → Chroma) |

## Estructura del monorepo (creada en E00)

```
Aquamarine Project/
├── backend/        # FastAPI, agente, RAG, modelos
│   ├── app/
│   │   ├── api/         # routers REST (vacío hasta E02)
│   │   ├── agent/       # lógica del agente + prompts (vacío hasta E03)
│   │   ├── rag/         # firecrawl + chroma (chroma_client.py)
│   │   ├── models/      # SQLAlchemy (sin tablas reales hasta E02)
│   │   ├── schemas/     # Pydantic
│   │   └── core/        # config.py, db.py
│   ├── scripts/         # ingesta, seed
│   ├── alembic/         # migraciones (env.py lee DATABASE_URL de settings)
│   ├── requirements.txt · .env.example
├── frontend/       # React + TS con Vite (chat + dashboard)
│   └── src/{pages,api}, App.tsx, main.tsx
├── docs/           # documentación local (la vault Obsidian es la fuente de verdad)
└── docker-compose.yml  # Postgres para desarrollo (las DBs van en Docker; la app no)
```

> [!note] App nativa, DBs en Docker
> El backend (venv + uvicorn) y el frontend (npm) corren **nativos** en la máquina, no en
> contenedores. Docker se usa **solo para las bases de datos** (`docker compose up -d` levanta
> Postgres). En VS Code, `Ctrl+Shift+B` arranca back + front directamente; la BD se levanta
> aparte con `docker compose up -d`.

Arranque y verificación: ver `README.md`. Diseño objetivo: `Arquitectura.md` en la vault.

## Variables de entorno (referencia, cuando exista código)

```
ANTHROPIC_API_KEY=
FIRECRAWL_API_KEY=
DATABASE_URL=postgresql://...
CHROMA_HOST=localhost
CHROMA_PORT=8002
```

## Principios a respetar al construir

1. **Canales desacoplados (adapters).** El agente no sabe si el lead vino por web/WhatsApp/Meta.
2. **Dos almacenes con roles claros.** Postgres = transaccional (escribe); Chroma = semántico (lee).
3. **Agente como orquestador.** Conversa, perfila, califica, consulta RAG y persiste en Postgres.
4. **Multitenant-ready.** Todo registro lleva `tenant_id` desde el día 1.
