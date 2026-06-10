---
tipo: nota-proyecto
audiencia: ambos
estado: completado
actualizado: 2026-06-09
tags: [area/proyecto, glosario, traduccion]
---

# Glosario (Tech ↔ Negocio)

> Para que la comercial (y su agente de IA) entiendan lo técnico sin código. Si un agente responde a la comercial, debe usar la columna **"En negocio"**.

| Término técnico | En negocio (cómo explicarlo) |
|---|---|
| **Agente de IA / LLM** | Un asistente que conversa como una persona y entiende lo que el cliente quiere |
| **Claude API** | El "cerebro" que usa el asistente para conversar |
| **RAG** | Que el asistente conozca el inventario real de Claudia para no inventar y poder recomendar inmuebles parecidos |
| **Firecrawl** | La herramienta que lee las páginas de Claudia y copia la info de sus inmuebles |
| **Chroma / base vectorial** | Una "memoria de inmuebles" que permite encontrar propiedades parecidas por significado, no solo por palabra exacta |
| **Embeddings** | Convertir cada inmueble en algo que la máquina puede comparar por similitud |
| **Scoring / lead caliente-tibio-frío** | Qué tan listo está el cliente para comprar (caliente = listo ya) |
| **Pipeline** | El embudo de ventas: en qué paso va cada cliente |
| **CRM** | El sistema donde se guardan y gestionan los clientes |
| **Handoff** | El momento en que el asistente le pasa el cliente bueno al asesor humano |
| **Nurturing** | Hacerle seguimiento al cliente que aún no está listo, para no perderlo |
| **Backend / FastAPI** | La "cocina": donde pasa la lógica que el cliente no ve |
| **Frontend / React** | Lo que el usuario ve y toca (el chat, el panel) |
| **PostgreSQL** | La bodega de datos del negocio (clientes, ventas, métricas) |
| **Mock de origen** | Simular de qué canal vino el cliente (Meta, portal, web) para la demo |
| **Multitenant** | Que la misma plataforma sirva a varias inmobiliarias, cada una con su espacio privado |
| **Endpoint / webhook** | Un "enchufe" para conectar la plataforma con otras herramientas |
| **Dashboard** | El panel con gráficas y números para tomar decisiones |
