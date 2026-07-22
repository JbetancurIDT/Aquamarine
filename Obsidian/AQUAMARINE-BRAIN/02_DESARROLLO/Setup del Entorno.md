---
tipo: nota-tecnica
audiencia: dev
estado: completado
actualizado: 2026-06-10
tags: [area/desarrollo, setup]
---

# Setup del Entorno

## En términos de negocio
Los pasos para "encender" el proyecto en la máquina del desarrollador antes de empezar a construir.

> [!success] Estado: implementado en [[E00 - Setup y Fundaciones]] (2026-06-10)
> El monorepo vive en `Aquamarine Project/`. El backend y el frontend corren **nativos**;
> Docker se usa para las **dos BDs** (Postgres + Chroma servidor) con `docker compose up -d`. En VS Code,
> **`Ctrl+Shift+B`** levanta back + front en paralelo (nativos).

## Requisitos
- Python 3.11+ (implementado y verificado en 3.12)
- Node 18+ (verificado en 18.19; Vite 5)
- Docker — **solo para las bases de datos**; el back y el front corren nativos
- Cuentas/keys: Anthropic (Claude), Firecrawl

## Pasos
1. Clonar el monorepo (estructura en [[Arquitectura]]).
2. **Backend:**
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # llenar keys
   alembic upgrade head    # migraciones (requiere Postgres arriba: paso 4)
   uvicorn app.main:app --reload
   ```
3. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. **Bases de datos (Docker):** desde la raíz del repo `Aquamarine Project/`:
   ```bash
   docker compose up -d    # Postgres (localhost:5432) + Chroma servidor (localhost:8002)
   docker compose down     # detener (agrega -v para borrar también los datos)
   ```
5. **Chroma (servidor en Docker):** ya queda arriba con `docker compose up -d` (`localhost:8002`); el backend conecta por `HttpClient` usando `CHROMA_HOST`/`CHROMA_PORT`. El paquete cliente `chromadb` viene con el backend.

## Variables de entorno (`.env`)
```
ANTHROPIC_API_KEY=
FIRECRAWL_API_KEY=
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aquamarine
CHROMA_HOST=localhost
CHROMA_PORT=8002
```

## Atajo en VS Code
`.vscode/tasks.json` define la tarea de build por defecto **`Dev: backend + frontend`**: pulsa
**`Ctrl+Shift+B`** y se levantan los dos servidores en paralelo, lado a lado (backend `:8000`,
frontend `:5173`), sin Docker y sin preguntar. La base de datos se levanta aparte con
`docker compose up -d`.

## Orden de arranque para la demo
1. Levantar Postgres → migraciones → seed ([[E07 - Demo, Seed y Pulido]]).
2. Correr ingesta RAG ([[E01 - Ingesta RAG (Firecrawl + Chroma)]]).
3. Levantar backend.
4. Levantar frontend.
5. Verificar flujo end-to-end (chat → score → handoff → dashboard).

> Definición de "hecho" del setup: el dev puede abrir el chat web, mandar un mensaje y recibir respuesta del agente con datos reales de un inmueble.
