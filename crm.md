# Feature: CRM / Backend Core (leads, conversación, pipeline, métricas)

> Doc de feature (convención del repo). Índice en [CLAUDE.md](CLAUDE.md); aquí el detalle.
> Épica de origen: `../Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E02 - Backend Core (FastAPI + Postgres).md`.

## Qué es / para qué
La "bodega" y las reglas del negocio: guarda los **leads**, su **conversación**, en qué paso del
**embudo** van y su **temperatura**, y emite **eventos** que alimentan las **métricas** del dashboard.
Es la API REST que el frontend (E04/E05) y el agente (E03) consumen; toda la lógica vive aquí, no en el front.

## Modelos (Postgres, SQLAlchemy síncrono)
Todo lleva `tenant_id` (multitenant-ready; en el MVP un solo tenant "Aquamarine Group"). PK UUID
(`gen_random_uuid()`, requiere `pgcrypto`), timestamps `timestamptz`, JSONB para `perfil`/`payload`/`metadata`.
- **`tenants`** — `id`, `nombre`, `creado_en`.
- **`leads`** — `id`, `tenant_id`, `nombre?`, `contacto?`, `origen`, `idioma?`, `score`(0), `temperatura`(frio),
  `estado`(nuevo), `perfil`(JSONB {}), `asesor_id?`, `creado_en`/`actualizado_en`.
- **`mensajes`** — `id`, `lead_id`, `rol`, `contenido`, `metadata`(JSONB?), `creado_en`. La conversación de un
  lead = sus mensajes ordenados por `creado_en` (sin tabla aparte). *Nota: el atributo ORM es `meta` porque
  `metadata` es reservado en SQLAlchemy; la columna sí se llama "metadata".*
- **`asesores`** — `id`, `tenant_id`, `nombre`, `disponible`.
- **`eventos`** — `id`, `lead_id`, `tipo`, `payload`(JSONB?), `creado_en`.

## Pipeline y valores válidos (`app/core/enums.py`)
- **estado (pipeline):** `nuevo → contactado → calificado → negociando → cerrado_ganado / cerrado_perdido → descartado`.
- **temperatura:** `caliente, tibio, frio` · **origen:** `web, meta, metrocuadrado, fincaraiz` · **rol:** `lead, agente, asesor`.
Se usan como Enums en los schemas → un valor inválido devuelve **422** automáticamente.

## Eventos (base de las métricas)
Centralizados en `app/services/lead_service.py` (no en los routers), para que API y agente reutilicen:
- `create_lead` → emite **`lead_creado`**.
- `set_estado` → valida y emite **`estado_cambiado`** (`{anterior, nuevo}`).
- `set_score` → emite **`score_actualizado`** (`{score, temperatura}`).
- `agregar_mensaje`, `update_lead`, `get_or_create_default_tenant`.

## Endpoints (`app/api/`, registrados en `app/main.py`)
- `POST /leads` — crea (defaults nuevo/frio/score 0); origen inválido → 422.
- `GET /leads?estado=&temperatura=&origen=` — lista con filtros.
- `GET /leads/{id}` — detalle **con sus mensajes**; 404 si no existe.
- `PATCH /leads/{id}/estado` — cambia estado (emite evento); inválido → 422; lead inexistente → 404.
- `GET /leads/{id}/mensajes` · `POST /leads/{id}/mensajes` — conversación (orden por fecha; rol inválido o
  `contenido` vacío → 422).
- `GET /metrics/overview` — contrato tipado (`response_model=MetricsOverview`) para el dashboard: `total_leads`,
  `por_origen`, `por_temperatura`, `por_estado`, `tiempo_primera_respuesta_seg`, `conversion`. Cada bucket
  incluye una clave `"otros"` (valores fuera de catálogo) → invariante: `sum(bucket) == total_leads`.

## Cómo correrlo
```bash
docker compose up -d                                   # Postgres (y Chroma)
cd backend
.venv/bin/alembic upgrade head                         # crea las tablas (migración e02)
.venv/bin/uvicorn app.main:app --reload --port 8000    # API → http://localhost:8000/docs
```

## Tests (exhaustivos, BD aislada)
`backend/tests/` usa una BD separada `aquamarine_test` (no la de dev); cada test parte de BD limpia.
Cubre cada endpoint con happy path + errores (422/404) + efectos (eventos emitidos).
```bash
cd backend && .venv/bin/python -m pytest -q     # 28 tests en verde
```
Incluye tests de **aislamiento multitenant** (un tenant no ve/cuenta/lee datos de otro), tiempo de primera
respuesta con timestamps deterministas, invariante de las métricas y validaciones (rol/contenido).

## Archivos
`app/models/{tenant,lead,mensaje,asesor,evento}.py`, `app/core/enums.py`, `app/schemas/{lead,mensaje,evento}.py`,
`app/services/lead_service.py`, `app/api/{deps,leads,mensajes,metrics}.py`, `alembic/versions/*_e02_modelos.py`,
`backend/tests/{conftest,test_leads,test_mensajes,test_metrics,test_service}.py`.

## Pendientes / TODO
- `conversion` (lead→cita, cita→negociación) queda en 0.0 hasta modelar la "cita" en el handoff (E06).
- La API aún no recibe el tenant por request (sin auth); `tenant_actual` devuelve el tenant por defecto.
