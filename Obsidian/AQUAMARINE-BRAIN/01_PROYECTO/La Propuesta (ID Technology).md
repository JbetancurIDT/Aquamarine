---
tipo: nota-proyecto
audiencia: ambos
estado: completado
actualizado: 2026-06-09
tags: [area/proyecto, propuesta]
---

# La Propuesta (ID Technology)

> Fuente original: [[Propuesta IDT (original)]]

## En términos de negocio
ID Technology propone una plataforma omnicanal con IA que centraliza los leads, los califica en menos de un minuto y entrega solo los buenos al asesor correcto, con el perfil ya armado. Lo respalda **NAIA**, un producto similar ya en producción con clientes pagando — o sea, no es promesa, ya lo sabemos hacer.

## Los 4 componentes propuestos
1. **Centralización omnicanal** — Meta Ads, portales (Metrocuadrado, Fincaraíz), WhatsApp y web propia → una sola bandeja vía webhooks/APIs.
2. **Motor de calificación con IA conversacional** — agente sobre **Claude API** con prompts especializados en el contexto inmobiliario colombiano. Hace 4 preguntas (tipo de inmueble, zona, presupuesto, plazo) y calcula score: caliente / tibio / frío.
3. **Routing diferenciado** — caliente: notificación inmediata + deal; tibio: nurturing 7 días; frío: reactivación mensual.
4. **Dashboard analítico** — volumen por canal, distribución por score, tiempos, conversión lead→cita y cita→negociación. Optimiza pauta por costo por lead calificado.

## Indicadores de éxito comprometidos
- Respuesta inicial < 1 min para el 100% de leads.
- Conversión +15% a +40%.
- Productividad del asesor +50%.

## Stack de la propuesta (versión original)
Claude API · WhatsApp Business API (Twilio) · Azure · HubSpot · Meta Lead Ads API.
Frameworks: LangChain, Crew.AI, Azure AI Foundry.

> [!important] Diferencias entre la propuesta y el MVP de hackathon
> El MVP **ajusta** este stack para priorizar la lógica del agente en 2 días. Cambios principales:
> - **HubSpot → CRM/pipeline propios** (Postgres + dashboard in-house).
> - **WhatsApp/Twilio/Meta → simulados** (chat web propio + mock de origen).
> - **Se agrega RAG** de inmuebles reales (Firecrawl → Chroma).
> Ver el detalle y la justificación en [[Alcance del MVP]] y [[Decisiones (Decision Log)]].

## Equipo (propuesta)
- **Santiago** — CTO, arquitectura e integraciones (arquitecto de NAIA).
- **Jerónimo** — full-stack, backend + flujos de chat + widget embebible.
- **Lau** — estrategia de producto: scoring, preguntas de calificación, nurturing.
- **Mariana** — coordinación con el comercial de Aquamarine y ciclos de feedback.

## Trayectoria / respaldo
ID Technology SAS, 15 años, +50 proyectos. Hito central: **NAIA** (asistente conversacional por WhatsApp, mismo stack, 5 clientes en producción, 90% de cierre sobre demos calificadas).

## Modelo de relación
Joint venture: IDT aporta tecnología y capacidad de escalado; Aquamarine aporta el conocimiento del mercado y la validación con datos reales. PI compartida.
