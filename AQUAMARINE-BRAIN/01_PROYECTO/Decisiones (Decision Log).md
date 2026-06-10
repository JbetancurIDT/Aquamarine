---
tipo: nota-proyecto
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-10
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
| D10 | 2026-06-10 | **App nativa; Docker solo para las BDs** (backend sin `Dockerfile`, Chroma embebido) | Iteración local más simple y rápida: el equipo corre back/front directo y aísla en contenedor solo la persistencia | `docker-compose.yml` levanta Postgres; backend (venv+uvicorn) y frontend (npm) nativos; Chroma `PersistentClient`; `Ctrl+Shift+B` en VS Code arranca back+front |

> Para agregar una decisión nueva: añade fila, sube `actualizado`, y si afecta el build, refleja el cambio en la épica correspondiente.
