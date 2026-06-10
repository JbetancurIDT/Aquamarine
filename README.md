# Aquamarine

Agente de IA + CRM propio para **Aquamarine Group SAS**, inmobiliaria de finca raíz de lujo.

Atiende leads al instante con tono humano, los califica (caliente/tibio/frío), recomienda
inmuebles reales mediante RAG y hace handoff al asesor cuando el lead está listo — todo
visible en un dashboard propio con el pipeline y las métricas del negocio.

Entregable: **PMV (producto mínimo viable)** bajo un Joint Venture con ID Technology.

## Estado

🚧 **En construcción.** Épica **E00 (Setup y Fundaciones)** completada: monorepo, esqueleto de
backend (FastAPI), esqueleto de frontend (React + TS), Alembic y Chroma listos, y un
"hola mundo" end-to-end (`/chat` consulta `/health` del backend).

## Stack

- **Frontend:** React + TypeScript (Vite)
- **Backend:** FastAPI (Python) — SQLAlchemy + Alembic, Pydantic, Uvicorn
- **Motor IA:** Claude API (Anthropic)
- **Base de datos:** PostgreSQL (relacional) + Chroma (vectorial)
- **Scraping / RAG:** Firecrawl → Chroma

## Estructura del monorepo

```
.
├── backend/            # FastAPI: API, agente IA, RAG, modelos
│   ├── app/
│   │   ├── api/        # routers REST
│   │   ├── agent/      # lógica del agente + prompts
│   │   ├── rag/        # Firecrawl + Chroma (chroma_client.py)
│   │   ├── models/     # modelos SQLAlchemy
│   │   ├── schemas/    # esquemas Pydantic
│   │   └── core/       # config, db
│   ├── scripts/        # ingesta, seed
│   ├── alembic/        # migraciones
│   ├── requirements.txt
│   └── .env.example
├── frontend/           # React + TS (chat del lead + dashboard/CRM)
├── docs/               # documentación local (la fuente de verdad vive en la vault Obsidian)
└── docker-compose.yml  # Postgres para desarrollo (las DBs van en Docker; back y front NO)
```

## Requisitos

- **Python** 3.11+
- **Node** 18+
- **Docker** (para las bases de datos; el backend y el frontend corren nativos)

## Bases de datos (Docker)

Solo las bases de datos corren en contenedores; **el backend y el frontend se ejecutan
nativos** en tu máquina. Levanta Postgres antes de las migraciones o la app:

```bash
docker compose up -d     # Postgres en localhost:5432 (datos en un volumen persistente)
docker compose down      # detener (agrega -v para borrar también los datos)
```

> **Chroma** (BD vectorial) es **embebido**: no usa contenedor; persiste en disco en
> `CHROMA_PERSIST_DIR` (`./chroma_store`).

## Backend — levantar en desarrollo (nativo, sin Docker)

```bash
cd backend
cp .env.example .env          # editar con credenciales reales
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head           # aplica migraciones (requiere Postgres: docker compose up -d)
uvicorn app.main:app --reload  # http://localhost:8000
```

Verificar: `GET http://localhost:8000/health` → `{"status":"ok","environment":"development"}`.

## Frontend — levantar en desarrollo

```bash
cd frontend
cp .env.example .env
npm install
npm run dev                    # http://localhost:5173
```

## Verificación end-to-end

Con el backend y el frontend corriendo, abrir **http://localhost:5173/chat**: debe mostrar
**"backend ok"** (la página consulta `/health` al cargar). Si el backend está apagado,
mostrará "backend sin conexión".

## Documentación

La documentación completa del proyecto (negocio, arquitectura, épicas, modelo de datos) se
mantiene en una vault de Obsidian aparte (repositorio independiente).

---

_Proyecto desarrollado por ID Technology para Aquamarine Group SAS._
