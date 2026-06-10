---
tipo: epica
audiencia: dev
estado: pendiente
epica: E00
actualizado: 2026-06-09
tags: [area/desarrollo, comp/backend, comp/frontend, estado/pendiente]
---

# E00 — Setup y Fundaciones

> **En términos de negocio:** preparar el terreno para que todo lo demás se pueda construir. No produce algo visible para el cliente, pero sin esto nada funciona.
> **Objetivo técnico:** monorepo, esqueletos de backend y frontend, Postgres con migraciones, Chroma instalado, variables de entorno y un "hola mundo" end-to-end.

## Contexto para el agente
Stack: React+TS (Vite) en `frontend/`, FastAPI en `backend/`. Postgres como BD relacional, Chroma como vectorial. Ver [[Arquitectura]], [[Stack Tecnológico]] y [[Modelo de Datos]]. Todo registro debe contemplar `tenant_id`.

## Dependencias
- **Requiere:** nada (es el inicio).
- **Bloquea:** E01, E02, E03, E04, E05.

## Etapas y tareas

### Etapa 0.1 — Estructura del repo
- [ ] **T00.1.1** — Crear monorepo con carpetas `backend/`, `frontend/`, `docs/`.
  - **Criterio:** estructura coincide con la de [[Arquitectura]]; `README.md` raíz con instrucciones básicas.
  - **Prompt sugerido:** "Crea un monorepo para un MVP con backend FastAPI (Python) y frontend React+TypeScript (Vite). Estructura: backend/app/{api,agent,rag,models,schemas,core}, backend/scripts, frontend/, docs/. Incluye README raíz, .gitignore para Python y Node, y requirements.txt + package.json base."

### Etapa 0.2 — Backend base
- [ ] **T00.2.1** — Inicializar FastAPI con Uvicorn y endpoint `/health`.
  - **Criterio:** `GET /health` responde `{"status":"ok"}`.
  - **Prompt sugerido:** "En backend/, crea una app FastAPI mínima (app/main.py) con config por entorno (app/core/config.py usando pydantic-settings) y un endpoint GET /health que devuelva status ok. Agrega CORS abierto para desarrollo."
- [ ] **T00.2.2** — Configurar SQLAlchemy + Alembic apuntando a Postgres.
  - **Criterio:** `alembic upgrade head` corre sin error contra la `DATABASE_URL`.
  - **Prompt sugerido:** "Configura SQLAlchemy 2.0 (async o sync, elige lo más simple) y Alembic en backend/. Lee DATABASE_URL del entorno. Crea la sesión de BD en app/core/db.py y deja Alembic listo para autogenerar migraciones desde app/models."

### Etapa 0.3 — Vectorial y entorno
- [ ] **T00.3.1** — Instalar y configurar Chroma persistente.
  - **Criterio:** función `get_chroma_client()` devuelve un cliente que persiste en `CHROMA_PERSIST_DIR`.
  - **Prompt sugerido:** "Agrega chromadb al backend. Crea app/rag/chroma_client.py con una función get_chroma_client() que use PersistentClient apuntando a CHROMA_PERSIST_DIR del entorno, y una colección 'inmuebles'."
- [ ] **T00.3.2** — Crear `.env.example` con todas las variables.
  - **Criterio:** incluye ANTHROPIC_API_KEY, FIRECRAWL_API_KEY, DATABASE_URL, CHROMA_PERSIST_DIR.

### Etapa 0.4 — Frontend base
- [ ] **T00.4.1** — Inicializar React+TS con Vite y routing a dos vistas (`/chat`, `/dashboard`).
  - **Criterio:** ambas rutas cargan páginas placeholder; cliente HTTP configurado hacia el backend.
  - **Prompt sugerido:** "En frontend/, crea una app React+TypeScript con Vite. Configura react-router con dos rutas: /chat y /dashboard, cada una con un componente placeholder. Crea un cliente API (axios o fetch wrapper) que apunte a la URL del backend vía variable de entorno VITE_API_URL."

### Etapa 0.5 — Verificación end-to-end
- [ ] **T00.5.1** — Conectar frontend `/health` con backend y mostrar estado.
  - **Criterio:** la página `/chat` muestra "backend ok" al cargar (prueba de conexión).

## Definición de hecho (épica)
Backend levanta, migraciones corren, Chroma inicializa, frontend carga las dos vistas y se conecta al backend.
