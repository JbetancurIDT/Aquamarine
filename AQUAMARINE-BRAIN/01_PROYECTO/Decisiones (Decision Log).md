---
tipo: nota-proyecto
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-11
tags: [area/proyecto, decisiones]
---

# Decisiones (Decision Log)

Registro de decisiones clave. Cada una: contexto, decisión y consecuencia. Para que nadie tenga que reconstruir "por qué hicimos esto".

| # | Fecha | Decisión | Por qué | Consecuencia |
|---|---|---|---|---|
| D01 | 2026-06-09 | No integrar WhatsApp/APIs reales en el MVP | Fricción de aprobación; el diferenciador es la lógica del agente | Se construye chat web propio + mock de origen |
| D02 | 2026-06-09 | Frontend en **React + TypeScript** | Versatilidad y experiencia previa del equipo | UI de chat y dashboard en React |
| D03 | 2026-06-09 | Backend en **FastAPI (Python)** | Rápido para IA, ecosistema Python para Claude/RAG | API y lógica del agente en Python |
| D04 | 2026-06-09 | Motor IA: **Claude API** | Calidad conversacional; alineado con la propuesta y NAIA | Agente y prompts sobre Claude |
| D05 | 2026-06-09 | CRM y pipeline **propios** (no HubSpot) | Control total de la visualización y la demo | Se construye dashboard in-house |
| D06 | 2026-06-09 | Persistencia central en **PostgreSQL** | Robusto, relacional, multitenant-ready | Leads, pipeline, métricas en Postgres |
| D07 | 2026-06-09 | **RAG** de inmuebles con **Firecrawl → Chroma** | Grounding real + recomendación de similares; capa gratuita | Pipeline de ingesta re-ejecutable |
| D08 | 2026-06-09 | Handoff a asesor **funcional** (no simulado) | Demuestra el ciclo completo y el rol humano (clave en lujo) | Notificación + cambio de estado real |
| D09 | 2026-06-09 | Cerebro del proyecto en **Obsidian** | Convergencia dev/comercial + lectura por agentes IA | Este vault |
| D10 | 2026-06-10 | **App nativa; Docker solo para las BDs** (backend sin `Dockerfile`) | Iteración local más simple y rápida: el equipo corre back/front directo y aísla en contenedor solo la persistencia | `docker-compose.yml` levanta Postgres (y Chroma, ver D11); backend (venv+uvicorn) y frontend (npm) nativos; `Ctrl+Shift+B` en VS Code arranca back+front |
| D11 | 2026-06-10 | **Chroma en modo servidor (Docker), no embebido** (supersede la parte "embebido" de D10) | Tener UI/observabilidad y separar la persistencia del proceso del backend; cliente y servidor a la misma versión | Imagen `chromadb/chroma:1.5.9` en `localhost:8002`; el backend conecta por `HttpClient` (`CHROMA_HOST`/`CHROMA_PORT`); config en `chroma-config.yaml` (persist + CORS); se elimina `CHROMA_PERSIST_DIR`. Detalle en `scraper.md` |
| D12 | 2026-06-10 | **Extracción de inmuebles con Firecrawl estructurado, NO con Claude** | La extracción JSON-con-schema de Firecrawl estandariza las fichas sola; evita una llamada extra a Claude (costo/latencia) en la ingesta | `extract_property` usa `formats=[{"type":"json","schema":…}]`; se descarta el `normalizer` con Claude de E01/T01.2.1. Claude queda para el agente de ventas (E03) y el gerencial (E08) |
| D13 | 2026-06-10 | **Segundo agente "Insights/Gerencia" para Claudia** (métricas en lenguaje natural) | Cierra el valor para la gerente, no solo para el lead: preguntar cómo van leads, asesores y conversión sin leer tablas | Nueva épica **[[E08 - Agente de Métricas (Gerencia)]]**; agente Claude read-only con tools sobre las métricas de E02; surface en el dashboard (E05) |
| D14 | 2026-06-10 | **Diseño de referencia del frontend** (mock de Claude Design) | Tener un norte visual del producto; alinear front con UI de lujo coherente | Se adopta el mock como **referencia visual oficial** ([[Diseño UI (referencia)]]). **Se conserva la paleta exacta** como requisito duro; tipografía/radios/sombras/posiciones son ajustables. El **chat del lead va separado y público** (`/chat`); el resto es consola interna. Para la demo del handover se usa **impersonación de asesor por URL** (`/asesor/<nombre>/<id>`) sin auth |
| D15 | 2026-06-10 | **El agente es la 1ª capa: crea el lead, origen simulado por URL, y handoff por solicitud** | El agente recibe al cliente desde el primer mensaje (no se crea el lead afuera); el origen se simula por la ruta; el cliente puede pedir un humano en cualquier momento | El front pasa `origen` de `/chat/<origen>/` al `POST /chat`; el **agente crea el lead** (no el front) y devuelve el `lead_id`. Si el lead **pide un humano** → **handoff inmediato** (E03 hace el mínimo: asignar asesor + evento `handoff`; E06 pule notificación/UI/impersonación). Si se pasa sin calificar: `temperatura="desconocido"`, `score=null`. `origen` puede ser null |
| D16 | 2026-06-11 | **Tiempo real por polling (no WebSockets) en el MVP** | El chat en vivo asesor↔cliente y las notificaciones se resuelven con polling, consistente con el resto del MVP y sin infra nueva | El chat del cliente y el modal del asesor consultan cada ~3–4 s; lag de segundos aceptable. WebSockets queda como mejora futura |
| D17 | 2026-06-11 | **Takeover humano apaga la IA** (flag `atendido_por_humano` en `lead`) | Cuando un asesor toma la conversación, la IA debe dejar de responder y el cliente habla solo con el humano | Nuevo campo `atendido_por_humano`; `orchestrator.responder` corta-circuito (no llama a Claude) si está activo; al tomar, la IA persiste un mensaje de **despedida**. `POST /leads/{id}/tomar` y `ChatResponse.atendido_por_humano` |
| D18 | 2026-06-11 | **Auto-asignación por menor cola + cap (balanceo)** en el handoff | Evitar sobrecargar a un asesor en hora pico; repartir según carga real | `asesor_con_menor_cola` elige entre `disponible=True` el de menos leads activos (calificado+negociando), respetando `MAX_LEADS_ACTIVOS_POR_ASESOR`; toggle `PATCH /asesores/{id}/disponibilidad` |
| D19 | 2026-06-11 | **Motor de notificaciones escalonadas + reasignación automática** (barrido backend) | Asegurar que el asesor responda; si no, reasignar para no perder el lead | Job `sweep_loop` (lifespan FastAPI) cada `SWEEP_INTERVALO_SEG`: notifica según temperatura (caliente<tibio<frío), y tras `NOTIF_MAX_ANTES_REASIGNAR` la IA se disculpa y reasigna. Intervalos configurables (`NOTIF_SCALE` para demo) |
| D20 | 2026-06-11 | **Métricas de propiedades = mock** (no se conecta la DB vectorial todavía) | Conectar Chroma para activas/en negociación/cerradas es costoso para el MVP; las de asesores sí son reales | `GET /metrics/propiedades` devuelve mock swappable; `GET /metrics/asesores` calcula real desde Postgres |

> Para agregar una decisión nueva: añade fila, sube `actualizado`, y si afecta el build, refleja el cambio en la épica correspondiente.
