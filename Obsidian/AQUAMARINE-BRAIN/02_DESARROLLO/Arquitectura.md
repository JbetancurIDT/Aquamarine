---
tipo: nota-tecnica
audiencia: dev
estado: completado
actualizado: 2026-06-09
tags: [area/desarrollo, arquitectura]
---

# Arquitectura

## En términos de negocio
La plataforma tiene tres partes: lo que el cliente ve (el chat y el panel), el "cerebro" que conversa y decide, y la bodega donde se guarda todo. Está diseñada para que mañana se le puedan "enchufar" WhatsApp o los portales sin rehacer nada, y para que varias inmobiliarias la usen sin mezclarse.

## Vista general

```
┌─────────────────────────────────────────────────────────┐
│                     FRONTEND (React + TS)                 │
│   ┌──────────────┐         ┌─────────────────────────┐    │
│   │  Chatbot Web │         │  Dashboard / CRM (panel) │    │
│   └──────┬───────┘         └───────────┬─────────────┘    │
└──────────┼─────────────────────────────┼─────────────────┘
           │ HTTP/REST (JSON)            │ HTTP/REST
┌──────────┼─────────────────────────────┼─────────────────┐
│          ▼          BACKEND (FastAPI)   ▼                 │
│   ┌─────────────────┐   ┌────────────────────────────┐    │
│   │  Capa Canales   │   │   API CRM / Pipeline / KPIs │    │
│   │  (adapters)     │   └──────────────┬─────────────┘    │
│   │  web | mock Meta│                  │                  │
│   └────────┬────────┘                  │                  │
│            ▼                            │                  │
│   ┌─────────────────────────┐          │                  │
│   │   AGENTE IA (orquestador)│─────────┤                  │
│   │   - perfilamiento        │         │                  │
│   │   - scoring caliente/...  │        │                  │
│   │   - nurturing            │          │                  │
│   │   - tool: buscar inmueble│          │                  │
│   └───────┬──────────────┬───┘          │                  │
└───────────┼──────────────┼──────────────┼─────────────────┘
            │              │              │
            ▼              ▼              ▼
     ┌────────────┐  ┌───────────┐  ┌──────────────┐
     │ Claude API │  │  Chroma   │  │ PostgreSQL   │
     │  (cerebro) │  │ (inmuebles│  │ (leads, CRM, │
     │            │  │  vectorial)│  │  pipeline,   │
     └────────────┘  └───────────┘  │  métricas)   │
                                     └──────────────┘
            ▲
     ┌──────┴───────┐
     │  Firecrawl   │  (ingesta on-demand: web + portales de Claudia)
     └──────────────┘
```

## Principios de diseño
1. **Canales desacoplados (adapters).** El agente no sabe si el lead vino por web, WhatsApp o Meta. Hoy solo existe el adapter `web` + un mock de origen; mañana se añaden otros sin tocar el core. *Esto es lo que sostiene la promesa omnicanal.*
2. **Dos almacenes con roles claros:**
   - **PostgreSQL** = fuente de verdad transaccional (leads, conversaciones, estados, scoring, métricas). El agente **escribe** aquí.
   - **Chroma** = índice semántico de solo-lectura del inventario. El agente **consulta** aquí.
3. **Agente como orquestador.** Recibe el mensaje, decide si necesita buscar inmuebles (tool de RAG), actualiza el perfil y el score, y persiste en Postgres.
4. **Multitenant-ready.** Todo registro lleva un `tenant_id` desde el día 1 (aunque en el MVP haya un solo tenant: Aquamarine). Así el salto a multitenant no obliga a migrar datos.

## Flujo de un lead (end-to-end)
1. El lead abre el chat web (con `origen` simulado: meta/portal/web).
2. El agente saluda con tono humano y conversa para perfilar: tipo, zona, presupuesto, plazo.
3. Si menciona/insinúa un inmueble, el agente consulta **Chroma** y ofrece coincidencias o **similares**.
4. Con cada respuesta, recalcula el **score** (caliente/tibio/frío) y lo guarda en **Postgres**.
5. Al volverse **caliente**, dispara el **handoff**: notificación al asesor + cambio de estado en el pipeline.
6. Todo se refleja en el **dashboard** en vivo.

## Estructura de repos sugerida (monorepo)
```
aquamarine-mvp/
├── backend/        # FastAPI, agente, RAG, modelos
│   ├── app/
│   │   ├── api/         # routers REST
│   │   ├── agent/       # lógica del agente + prompts
│   │   ├── rag/         # firecrawl + chroma
│   │   ├── models/      # SQLAlchemy
│   │   ├── schemas/     # Pydantic
│   │   └── core/        # config, db, seguridad
│   └── scripts/         # ingesta, seed
├── frontend/       # React + TS (chat + dashboard)
└── docs/           # opcional: export de este vault
```

Ver detalle de tablas en [[Modelo de Datos]] y librerías en [[Stack Tecnológico]].
