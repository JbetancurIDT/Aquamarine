# Aquamarine

Agente de IA + CRM propio para **Aquamarine Group SAS**, inmobiliaria de finca raíz de lujo.

Atiende leads al instante con tono humano, los califica (caliente/tibio/frío), recomienda
inmuebles reales mediante RAG y hace handoff al asesor cuando el lead está listo — todo
visible en un dashboard propio con el pipeline y las métricas del negocio.

Entregable: **PMV (producto mínimo viable)** bajo un Joint Venture con ID Technology.

## Estado

🚧 **En construcción.** El repositorio se está inicializando. Aún no existen los ambientes de
backend ni frontend; se añadirán en las próximas iteraciones.

## Stack

- **Frontend:** React + TypeScript (Vite)
- **Backend:** FastAPI (Python)
- **Motor IA:** Claude API (Anthropic)
- **Base de datos:** PostgreSQL (relacional) + Chroma (vectorial)
- **Scraping / RAG:** Firecrawl → Chroma

## Estructura prevista

```
backend/    # FastAPI: API, agente IA, RAG, modelos
frontend/   # React + TS: chat del lead + dashboard/CRM
```

## Documentación

La documentación completa del proyecto (negocio, arquitectura, épicas, modelo de datos) se
mantiene en una vault de Obsidian aparte (repositorio independiente).

---

_Proyecto desarrollado por ID Technology para Aquamarine Group SAS._
