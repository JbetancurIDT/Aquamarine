# Aquamarine Project — El producto (código)

Este es el repositorio del **producto real** de Aquamarine: el agente de IA + CRM + dashboard
para Aquamarine Group SAS (finca raíz de lujo). Repo git independiente del de documentación.

> [!note] Estado actual (actualizado 2026-06-10)
> **E00–E03 completadas:** Setup + Ingesta RAG (Firecrawl→Chroma) + Backend Core (FastAPI +
> Postgres: leads, mensajes, métricas, eventos) + Agente Aqua (Claude, tool `buscar_inmuebles`,
> perfilamiento, scoring, handoff mínimo). **E04 (Chatbot Frontend) funcional end-to-end**
> (chat React cableado a `POST /chat`, tarjetas de inmueble, badge de temperatura); falta
> validar paleta/diseño, tests de front y doc de feature. **Pendientes:** E05 (CRM/Dashboard,
> hoy stub), E06 (notificación/UI/impersonación de handoff), E07 (demo/seed), E08 (agente de
> métricas). Detalle vivo en `AQUAMARINE-BRAIN/04_PROGRESO/`.

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
│   ├── requirements.txt · .env.example   # (sin Dockerfile: la app corre nativa, ver D10)
├── frontend/       # React + TS con Vite (chat + dashboard)
│   └── src/{pages,api}, App.tsx, main.tsx
└── docs/           # documentación local (la vault Obsidian es la fuente de verdad)
```

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
