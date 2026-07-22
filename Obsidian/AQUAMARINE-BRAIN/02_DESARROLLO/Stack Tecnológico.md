---
tipo: nota-tecnica
audiencia: dev
estado: completado
actualizado: 2026-06-10
tags: [area/desarrollo, stack]
---

# Stack Tecnológico

## En términos de negocio
Elegimos herramientas que permiten construir mucho en poco tiempo, con capa gratuita para el piloto, y que escalan si el proyecto crece.

## Resumen
| Capa | Tecnología | Estado | Por qué |
|---|---|---|---|
| Frontend | **React + TypeScript** | ✅ confirmado | Versatilidad, experiencia previa, tipado seguro |
| Backend | **FastAPI (Python)** | ✅ confirmado | Rápido de levantar, ecosistema IA/RAG en Python |
| Motor IA | **Claude API (Anthropic)** | ✅ confirmado | Calidad conversacional; alineado con NAIA y la propuesta |
| BD relacional | **PostgreSQL** | ✅ confirmado | Robusto, relacional, multitenant-ready |
| BD vectorial | **Chroma** | ✅ confirmado | Open-source; en el MVP corre como **servidor en Docker**, gratis |
| Scraping | **Firecrawl** | ✅ confirmado | Convierte web a formato LLM-ready; capa gratuita |

## Detalle por capa

### Frontend — React + TypeScript
- Build: Vite (rápido para hackathon).
- Estado: React Query o estado simple para llamadas al backend.
- Dos vistas: **Chat** (lead) y **Dashboard** (Claudia/asesor).
- UI del chat: imitar estética tipo WhatsApp para que se "sienta" el canal final.

### Backend — FastAPI
- ORM: SQLAlchemy + Alembic (migraciones).
- Validación: Pydantic.
- Cliente IA: SDK oficial de Anthropic para Python.
- Servidor: Uvicorn.

### Motor IA — Claude API
- El agente usa Claude para conversar, perfilar y decidir.
- Patrón de **tool use**: el agente puede llamar una herramienta `buscar_inmuebles` que consulta Chroma.
- El system prompt encapsula el tono humano y las reglas del negocio de lujo (ver [[E03 - Agente IA (Claude)]]).

### BD vectorial — Chroma
- En el MVP corre como **servidor en Docker** (`chromadb/chroma:1.5.9`, `localhost:8002`); el backend conecta por `HttpClient`. Persiste en un volumen. (Decisión [[Decisiones (Decision Log)]] D11.)
- Embeddings con la **función por defecto** de Chroma (all-MiniLM); guarda **metadata filtrable** (zona, precio, tipo, habitaciones, área, lujo…).
- Permite búsqueda por similitud **y** filtros → matching inteligente y "similares".

### Scraping — Firecrawl
- Patrón establecido: Firecrawl scrapea → markdown/JSON estructurado → embeddings → Chroma.
- Fuentes: **web propia de Claudia + portales** donde publica.
- Ingesta **re-ejecutable on-demand** (script/botón) para refrescar el inventario.

## Notas de costos (capa gratuita para el MVP)
- **Chroma:** gratis, local.
- **Firecrawl:** capa gratuita para el volumen del MVP (~100 inmuebles).
- **Claude API:** consumo por uso (controlado, dataset pequeño).
- **Postgres:** local o contenedor.
> Si ganamos, se escala a capas de pago donde haga falta. Por ahora, todo apunta a costo mínimo.

## Variables de entorno (referencia)
```
ANTHROPIC_API_KEY=
FIRECRAWL_API_KEY=
DATABASE_URL=postgresql://...
CHROMA_HOST=localhost
CHROMA_PORT=8002
```
