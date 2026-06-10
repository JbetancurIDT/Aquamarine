---
tipo: epica
audiencia: dev
estado: completado
epica: E02
actualizado: 2026-06-10
tags: [area/desarrollo, comp/backend, comp/crm, stack/fastapi, stack/postgres, estado/completado]
---

# E02 — Backend Core (FastAPI + Postgres)

> **En términos de negocio:** la "bodega" y las reglas del negocio. Aquí se guardan los clientes, sus conversaciones, en qué paso del embudo van y su temperatura. Es lo que alimenta el panel.
> **Objetivo técnico:** modelos SQLAlchemy, migraciones, y API REST para el ciclo de vida del lead, conversaciones, pipeline y eventos.

## Contexto para el agente
Esquema completo en [[Modelo de Datos]]. Todo lleva `tenant_id`. Estados del pipeline: nuevo → contactado → calificado → negociando → cerrado_ganado/perdido → descartado. Los **eventos** son la base de las métricas, así que hay que emitirlos en cada cambio relevante.

## Dependencias
- **Requiere:** E00.
- **Bloquea:** E03 (el agente escribe aquí), E05 (el dashboard lee de aquí), E06.

## Etapas y tareas

### Etapa 2.1 — Modelos y migraciones
- [x] **T02.1.1** — Modelos SQLAlchemy: tenant, lead, conversacion, mensaje, asesor, evento.
  - **Criterio:** modelos reflejan [[Modelo de Datos]]; relaciones y `jsonb` para `perfil`/`payload`.
  - **Prompt sugerido:** "Crea los modelos SQLAlchemy en backend/app/models/ según el esquema de [Modelo de Datos]: Tenant, Lead, Mensaje, Asesor, Evento. Usa UUID PK, timestamptz, y JSONB para perfil (Lead) y payload (Evento). Incluye tenant_id en todas las tablas de negocio."
- [x] **T02.1.2** — Generar migración inicial con Alembic.
  - **Criterio:** `alembic upgrade head` crea todas las tablas.

### Etapa 2.2 — Schemas y repositorios
- [x] **T02.2.1** — Schemas Pydantic (in/out) para lead, mensaje, evento.
  - **Prompt sugerido:** "Crea schemas Pydantic en backend/app/schemas/ para Lead (create/update/out), Mensaje (create/out) y Evento (out). El LeadOut debe incluir score, temperatura, estado y perfil."
- [x] **T02.2.2** — Capa de repositorio/servicio para CRUD de leads y emisión de eventos.
  - **Criterio:** crear/actualizar lead emite automáticamente un `evento` correspondiente.
  - **Prompt sugerido:** "Crea app/services/lead_service.py con funciones create_lead, update_lead, set_estado, set_score que persistan en Postgres y emitan un Evento por cada cambio relevante (lead_creado, score_actualizado, estado_cambiado). Centraliza aquí la lógica para que la API y el agente la reutilicen."

### Etapa 2.3 — API REST
- [x] **T02.3.1** — Router de leads: crear, listar (con filtros), detalle, actualizar estado.
  - **Criterio:** `GET /leads?estado=&temperatura=&origen=` filtra; `PATCH /leads/{id}/estado` cambia estado y emite evento.
  - **Prompt sugerido:** "Crea backend/app/api/leads.py con endpoints: POST /leads, GET /leads (filtros por estado, temperatura, origen), GET /leads/{id} (incluye mensajes), PATCH /leads/{id}/estado. Usa lead_service. Documenta con tags FastAPI."
- [x] **T02.3.2** — Router de mensajes/conversación de un lead.
  - **Criterio:** `GET /leads/{id}/mensajes` y `POST /leads/{id}/mensajes`.
- [x] **T02.3.3** — Router de métricas (lee de `eventos`/`leads`).
  - **Criterio:** `GET /metrics/overview` devuelve volúmenes por origen y temperatura, tiempos y conversión.
  - **Prompt sugerido:** "Crea app/api/metrics.py con GET /metrics/overview que calcule desde Postgres: leads por origen, leads por temperatura, tiempo promedio de primera respuesta, conteo por estado del pipeline, conversión lead→cita y cita→negociación. Devuelve JSON listo para graficar."

## Definición de hecho (épica)
Se puede crear un lead vía API, agregarle mensajes, cambiar su estado, y consultar métricas — todo persistido en Postgres con eventos emitidos.

> ✅ **E02 cerrada (2026-06-10).** Modelos SQLAlchemy (tenants/leads/mensajes/asesores/eventos, UUID + JSONB +
> timestamptz), migración Alembic aplicada (`alembic upgrade head` + `pgcrypto`), servicio `lead_service`
> (centraliza la emisión de eventos), schemas Pydantic, y routers `/leads`, `/leads/{id}/mensajes`,
> `/metrics/overview`. **24 tests en verde** (BD aislada `aquamarine_test`): happy path + 422 + 404 + efectos
> (eventos). Detalle del feature: `Aquamarine Project/crm.md`.
