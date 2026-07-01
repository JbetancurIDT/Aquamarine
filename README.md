# Aquamarine — Agente IA + CRM inmobiliario

Agente de IA + CRM propio para **Aquamarine Group SAS**, inmobiliaria de finca raíz de lujo.

**Aqua**, el agente conversacional (construido sobre la Claude API), atiende a los leads al
instante con tono humano, los perfila sin formularios, los califica (caliente / tibio / frío),
recomienda **inmuebles reales** del inventario indexado vía RAG (Firecrawl → Chroma) y hace
handoff automático al asesor con balanceo de carga, notificaciones escaladas y **takeover
humano** (la IA se silencia cuando el asesor toma la conversación). Todo es visible en una
consola interna: dashboard de métricas, pipeline Kanban con drag-and-drop, tablero por asesor
y vista de performance con SLA.

Entregable: **PMV** bajo un Joint Venture entre ID Technology y Aquamarine Group SAS.

## Estado

✅ Épicas **E00–E07 completadas**, más asistente de insights para gerencia (burbuja de chat en
`/dashboard`, `POST /insights/ask`) y búsqueda RAG endurecida. **145 tests de backend en verde.**

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | React 18 + TypeScript (Vite), Tailwind CSS, react-router, axios |
| Backend | FastAPI (Python) — SQLAlchemy + Alembic, Pydantic, Uvicorn |
| Motor IA | Claude API (SDK de Anthropic), patrón tool use |
| BD relacional | PostgreSQL 16 (fuente de verdad: leads, conversaciones, pipeline, métricas) |
| BD vectorial | Chroma (índice semántico del inventario, solo lectura) |
| Scraping | Firecrawl (ingesta on-demand de inmuebles → Chroma) |

## Estructura del repositorio

```
.
├── backend/            # FastAPI: API REST, agente Aqua, RAG, modelos
│   ├── app/{api,agent,rag,models,schemas,services,core}
│   ├── scripts/        # ingesta RAG, seeds de demo
│   ├── alembic/        # migraciones
│   └── requirements.txt · .env.example
├── frontend/           # React + TS: chat del lead + consola interna
├── docker-compose.yml  # SOLO bases de datos (Postgres + Chroma)
├── chroma-config.yaml  # config del servidor Chroma (montada en el contenedor)
└── *.md                # documentación por feature (ver tabla)
```

Documentación detallada por feature (en la raíz del repo):

| Doc | Contenido |
|---|---|
| [scraper.md](scraper.md) | Ingesta Firecrawl → Chroma, búsqueda semántica + filtros, `POST /rag/reindex` |
| [crm.md](crm.md) | Modelos Postgres, eventos, API de leads/mensajes/métricas |
| [agent.md](agent.md) | Aqua: system prompt, tool use, scoring, handoff |
| [chat.md](chat.md) | Chat web público del lead (`/chat[/:origen]`) |
| [dashboard.md](dashboard.md) | Dashboard de métricas + pipeline Kanban + asistente de insights |
| [handoff.md](handoff.md) | Handoff completo: takeover humano, barrido, performance/SLA |

La fuente de verdad del proyecto (negocio, arquitectura, épicas) vive en la vault de Obsidian,
en el repo hermano **Aquamarine-Brain**.

## Requisitos

- **Docker** (solo para las bases de datos; backend y frontend corren nativos)
- **Python 3.11+** (probado con 3.12)
- **Node 18+** (Vite 5 exige `^18.0.0 || >=20`)
- **Clave de Claude API** (`ANTHROPIC_API_KEY`) — **obligatoria**: es el motor del agente
- **Clave de Firecrawl** (`FIRECRAWL_API_KEY`) — **necesaria para la ingesta del inventario**

Cada requisito de infraestructura, con sus pasos para correrlo en local:

---

### Requerimiento: PostgreSQL 16

Base relacional (leads, conversaciones, pipeline, métricas). Corre en Docker con la
configuración ya incluida en `docker-compose.yml`.

**Pasos para ejecutarlo en local:**

```bash
# desde la raíz del repo
docker compose up -d        # levanta Postgres (y Chroma, ver abajo)
docker compose ps           # verificar: aquamarine-postgres "healthy"
```

- Queda en `localhost:5432`, usuario `postgres`, contraseña `postgres`, BD `aquamarine`.
- Los datos persisten en el volumen `aquamarine_pgdata` (`docker compose down -v` los borra).
- Las tablas se crean con las migraciones de Alembic (paso 2 de la puesta en marcha).

---

### Requerimiento: ChromaDB

Base vectorial con el índice semántico del inventario (colección `inmuebles`). Corre como
**servidor** en Docker — el mismo `docker-compose.yml` la levanta junto a Postgres.

**Pasos para ejecutarlo en local:**

```bash
# desde la raíz del repo (el mismo comando de arriba levanta ambas)
docker compose up -d
docker ps                   # verificar: contenedor aquamarine-chroma corriendo
```

- Imagen `chromadb/chroma:1.5.9` (fijada). `requirements.txt` no fija versiones a propósito:
  si el cliente `chromadb` que instala pip no fuera compatible con el servidor, alinéalo con
  `pip install "chromadb==1.5.9"`.
- Expuesta en `localhost:8002` (mapeo `8002:8000`; el puerto 8000 del host lo usa el backend).
- Usa `chroma-config.yaml` de la raíz del repo (persistencia en el volumen
  `aquamarine_chroma_data` + CORS abierto para UIs de desarrollo).
- El índice arranca vacío: se puebla con la ingesta (ver "Indexar el inventario" abajo).

---

### Requerimiento: Firecrawl (servicio externo — **se necesita una API key**)

Aquí no hay nada que instalar: Firecrawl es un servicio en la nube que hace el scraping del
inventario real ([idealrealestate.com.co](https://idealrealestate.com.co)).

1. Crear cuenta en [firecrawl.dev](https://firecrawl.dev) y generar una API key.
2. Ponerla en `backend/.env` como `FIRECRAWL_API_KEY=fc-...`.

Sin esta clave el chat y el CRM funcionan, pero **no** se puede indexar/actualizar el
inventario (`scripts/ingest.py` y `POST /rag/reindex` fallarán). Costo aproximado: **1 crédito
por ficha scrapeada** (el sitio completo son ~130 fichas) — empieza con `--limit 5`.

---

### Requerimiento: Claude API (Anthropic — **se necesita una API key**)

El motor de Aqua. Generar una clave en [console.anthropic.com](https://console.anthropic.com)
y ponerla en `backend/.env` como `ANTHROPIC_API_KEY=sk-ant-...`. Sin ella el servidor arranca,
pero el agente no puede responder en `/chat` ni en el asistente de insights.

---

## Puesta en marcha local (paso a paso)

Los comandos son para Linux/macOS (bash/zsh); las diferencias de Windows están en la
[tabla por sistema operativo](#notas-por-sistema-operativo).

**0. Clonar y levantar las bases de datos**

```bash
git clone https://github.com/JbetancurIDT/Aquamarine.git
cd Aquamarine
docker compose up -d
```

**1. Backend — entorno e instalación**

```bash
cd backend
cp .env.example .env        # editar: ANTHROPIC_API_KEY y FIRECRAWL_API_KEY reales
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Backend — migraciones y datos de demo**

```bash
alembic upgrade head              # crea las tablas (requiere Postgres arriba)
python scripts/seed_demo.py       # demo completa: 3 asesores + 22 leads realistas (idempotente)
# alternativa mínima: python scripts/seed_asesores.py  (solo 2 asesores, sin leads)
```

**3. Backend — arrancar el servidor**

```bash
uvicorn app.main:app --reload     # http://localhost:8000
```

Verificar: `curl http://localhost:8000/health` → `{"status":"ok","environment":"development"}`.
Swagger interactivo en <http://localhost:8000/docs>.

**4. Indexar el inventario (RAG)** — requiere `FIRECRAWL_API_KEY`

> Uvicorn quedó ocupando la terminal del paso 3: abre una **segunda terminal** para este paso
> y el siguiente (`cd backend` y reactivar el venv con `source .venv/bin/activate`).

```bash
# con el venv activo, desde backend/
python scripts/ingest.py --limit 5          # indexa 5 fichas (~5 créditos Firecrawl)
# o una ficha puntual:  python scripts/ingest.py --url "<URL_DE_UNA_FICHA>"
# o sin args para mapear e indexar el sitio completo (~130 fichas)
```

También existe el equivalente HTTP (con el backend corriendo):

```bash
curl -X POST http://localhost:8000/rag/reindex \
  -H "Content-Type: application/json" -d '{"limit": 5}'
```

Verificar el índice:

```bash
curl "http://localhost:8000/rag/inmuebles/buscar?q=apartamento%20de%20lujo&k=5"
```

> Nota: `seed_demo.py` usa inmuebles reales de Chroma si el índice ya está poblado, y un
> fallback curado si no — así que puedes probar el dashboard sin gastar créditos de Firecrawl.

**5. Frontend**

```bash
cd ../frontend
cp .env.example .env        # opcional: VITE_API_URL (default http://localhost:8000)
npm install
npm run dev                 # http://localhost:5173
```

**6. Probar la aplicación**

| URL | Qué es |
|---|---|
| <http://localhost:5173/chat> | Chat público del lead con Aqua (`/chat/:origen` etiqueta el canal) |
| <http://localhost:5173/dashboard> | Dashboard de métricas (KPIs, funnel, donut) + burbuja de insights |
| <http://localhost:5173/pipeline> | Kanban de leads con drag-and-drop y asignación de asesor |
| <http://localhost:5173/asesores> | Índice de asesores |
| <http://localhost:5173/asesor/:id> | Consola del asesor: leads en vivo, disponibilidad, campana |
| <http://localhost:5173/performance> | Tabla de performance con SLA por asesor |

### Notas por sistema operativo

| Paso | Linux | macOS | Windows |
|---|---|---|---|
| Docker | Docker Engine + plugin compose | Docker Desktop | Docker Desktop (backend WSL2) |
| Crear venv | `python3 -m venv .venv` | `python3 -m venv .venv` | `py -m venv .venv` |
| Activar venv | `source .venv/bin/activate` | `source .venv/bin/activate` | PowerShell: `.venv\Scripts\Activate.ps1` · CMD: `.venv\Scripts\activate.bat` |
| Copiar .env | `cp .env.example .env` | `cp .env.example .env` | `copy .env.example .env` |

El resto (`docker compose`, `pip`, `alembic`, `uvicorn`, `npm`) es idéntico en los tres.
Única salvedad: en Windows PowerShell 5.x `curl` es un alias de `Invoke-WebRequest` y los
comandos `curl` de esta guía fallan — usa `curl.exe` o abre las URLs en el navegador
(p. ej. <http://localhost:8000/docs>).

### Atajo en VS Code

`Ctrl+Shift+B` corre la tarea **"dev: start all"** (`.vscode/tasks.json`, incluido en el
repo): backend (uvicorn en `:8000`) + frontend (Vite en `:5173`) en paralelo. Las bases de
datos van aparte con `docker compose up -d`. La tarea de backend usa la ruta de venv de
Linux/macOS (`.venv/bin/uvicorn`); en Windows ajústala a `.venv\Scripts\uvicorn`.

## Tests

```bash
# requiere Postgres arriba (docker compose up -d); usa una BD aislada aquamarine_test
cd backend && .venv/bin/python -m pytest -q      # 145 tests
```

> Usa `python -m pytest` (no el binario `pytest` directo): el proyecto no define `pytest.ini`,
> así que solo `python -m` agrega `backend/` al path y permite importar `app`.

## Variables de entorno (`backend/.env`)

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/aquamarine` | Conexión a Postgres (compose de dev) |
| `CHROMA_HOST` / `CHROMA_PORT` | `localhost` / `8002` | Servidor Chroma (contenedor `aquamarine-chroma`) |
| `ANTHROPIC_API_KEY` | — | **Obligatoria.** Motor del agente Aqua |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Modelo conversacional del agente |
| `ANTHROPIC_EXTRACTION_MODEL` | `claude-haiku-4-5` | Modelo barato para extracción de perfil |
| `FIRECRAWL_API_KEY` | — | **Necesaria para la ingesta** (scraping del inventario) |
| `ENVIRONMENT` | `development` | `development` \| `staging` \| `production` |

Existen además variables de afinación del handoff/barrido (E07) con defaults sensatos en
`backend/app/core/config.py`: `MAX_LEADS_ACTIVOS_POR_ASESOR`, `SWEEP_INTERVALO_SEG`,
`NOTIF_SEG_*` por temperatura, `NOTIF_MAX_ANTES_REASIGNAR` y `NOTIF_SCALE` (acelera los
intervalos para demos, p. ej. `NOTIF_SCALE=60`).

El frontend solo lee `VITE_API_URL` (`frontend/.env`, default `http://localhost:8000`).

## API principal

- `POST /chat` · `POST /chat/{origen}` — chat del lead con Aqua (crea el lead si no existe)
- `POST /rag/reindex` · `GET /rag/inmuebles/buscar` — ingesta y búsqueda del inventario
- `POST/GET /leads` (+ filtros) · `GET /leads/en-vivo` · `PATCH /leads/{id}/estado` ·
  `PATCH /leads/{id}/asesor` · `POST /leads/{id}/tomar` (takeover humano, silencia la IA)
- `GET/POST /leads/{id}/mensajes` — conversación del lead
- `GET /asesores` · `GET /asesores/{id}/leads` · `GET /asesores/{id}/notificaciones` ·
  `PATCH /asesores/{id}/disponibilidad`
- `GET /metrics/overview` (+ filtros) · `GET /metrics/asesores` · `GET /metrics/propiedades`
- `POST /insights/ask` — asistente de métricas para gerencia (tool use de solo lectura)

Detalle completo en Swagger (`/docs`) y en los `.md` por feature.

---

_Proyecto desarrollado por ID Technology para Aquamarine Group SAS (Joint Venture)._
