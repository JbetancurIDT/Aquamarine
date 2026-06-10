---
tipo: nota-tecnica
audiencia: dev
estado: completado
actualizado: 2026-06-09
tags: [area/desarrollo, setup]
---

# Setup del Entorno

## En términos de negocio
Los pasos para "encender" el proyecto en la máquina del desarrollador antes de empezar a construir.

## Requisitos
- Python 3.11+
- Node 20+
- PostgreSQL 15+ (local o Docker)
- Cuentas/keys: Anthropic (Claude), Firecrawl

## Pasos
1. Clonar el monorepo (estructura en [[Arquitectura]]).
2. **Backend:**
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # llenar keys
   alembic upgrade head    # migraciones
   uvicorn app.main:app --reload
   ```
3. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. **Postgres (Docker rápido):**
   ```bash
   docker run --name aqua-pg -e POSTGRES_PASSWORD=dev -p 5432:5432 -d postgres:15
   ```
5. **Chroma:** se instala con el backend (`pip install chromadb`); persiste en `CHROMA_PERSIST_DIR`.

## Variables de entorno (`.env`)
```
ANTHROPIC_API_KEY=
FIRECRAWL_API_KEY=
DATABASE_URL=postgresql://postgres:dev@localhost:5432/aquamarine
CHROMA_PERSIST_DIR=./chroma_store
```

## Orden de arranque para la demo
1. Levantar Postgres → migraciones → seed ([[E07 - Demo, Seed y Pulido]]).
2. Correr ingesta RAG ([[E01 - Ingesta RAG (Firecrawl + Chroma)]]).
3. Levantar backend.
4. Levantar frontend.
5. Verificar flujo end-to-end (chat → score → handoff → dashboard).

> Definición de "hecho" del setup: el dev puede abrir el chat web, mandar un mensaje y recibir respuesta del agente con datos reales de un inmueble.
