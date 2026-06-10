# Aquamarine Project — El producto (código)

Este es el repositorio del **producto real** de Aquamarine: el agente de IA + CRM + dashboard
para Aquamarine Group SAS (finca raíz de lujo). Repo git independiente del de documentación.

> [!note] Estado actual
> El repo está **vacío a propósito**. Aún no se han creado los ambientes de backend ni
> frontend. Por ahora solo viven aquí este `CLAUDE.md` y el `README.md` para inicializar git.
> El back y el front se construirán más adelante. Este documento se irá actualizando conforme
> avance el proyecto.

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

## Estructura prevista (monorepo)

Aún no creada. El diseño objetivo (ver `Arquitectura.md` en la vault):

```
Aquamarine Project/
├── backend/        # FastAPI, agente, RAG, modelos
│   ├── app/
│   │   ├── api/         # routers REST
│   │   ├── agent/       # lógica del agente + prompts
│   │   ├── rag/         # firecrawl + chroma
│   │   ├── models/      # SQLAlchemy
│   │   ├── schemas/     # Pydantic
│   │   └── core/        # config, db, seguridad
│   └── scripts/         # ingesta, seed
└── frontend/       # React + TS (chat + dashboard)
```

## Variables de entorno (referencia, cuando exista código)

```
ANTHROPIC_API_KEY=
FIRECRAWL_API_KEY=
DATABASE_URL=postgresql://...
CHROMA_PERSIST_DIR=./chroma_store
```

## Principios a respetar al construir

1. **Canales desacoplados (adapters).** El agente no sabe si el lead vino por web/WhatsApp/Meta.
2. **Dos almacenes con roles claros.** Postgres = transaccional (escribe); Chroma = semántico (lee).
3. **Agente como orquestador.** Conversa, perfila, califica, consulta RAG y persiste en Postgres.
4. **Multitenant-ready.** Todo registro lleva `tenant_id` desde el día 1.
