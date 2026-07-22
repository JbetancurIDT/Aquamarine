---
tipo: nota-proyecto
audiencia: ambos
estado: completado
actualizado: 2026-06-09
tags: [area/proyecto, alcance, mvp]
---

# Alcance del MVP

## En términos de negocio
En la hackathon construimos el **corazón** de la plataforma: el agente de IA que conversa, entiende y califica al cliente, más el panel donde Claudia ve sus leads y métricas. No conectamos todavía WhatsApp ni los portales reales (eso es "enchufar" después); en cambio simulamos de dónde vino el lead para contar la historia completa. Esto nos deja demostrar lo que de verdad importa y diferencia: **la inteligencia de la conversación**.

## ✅ Dentro de alcance (lo que SÍ construimos)
1. **Chatbot web propio** (React + TS): UI de chat fabricada donde el lead conversa con el agente.
2. **Agente de IA** (Claude API): recibe, perfila, califica (caliente/tibio/frío) y nutre, con **tono humano**.
3. **Origen del lead simulado**: mock visible en el dashboard ("vino de Meta", "de Metrocuadrado", "web").
4. **CRM_IA + pipeline propios** (FastAPI + **PostgreSQL**): el lead se guarda en nuestro sistema. Estados: contactado → calificado → negociando → cerrado / descartado.
5. **Dashboard propio**: métricas (volumen, score, tiempos, conversión) + pipeline visual + pantallas de validación.
6. **Handoff a asesor FUNCIONAL**: al calificar como caliente, dispara notificación + cambio de estado real.
7. **RAG de inmuebles reales**: Firecrawl scrapea la web/portales de Claudia → Chroma. El agente usa esto para (a) **grounding** sobre inventario real y (b) **recomendar similares**. Re-ejecutable on-demand.

## ❌ Fuera de alcance (roadmap post-hackathon)
- WhatsApp Business API / Twilio.
- Meta, Google, portales reales (solo mock de origen).
- HubSpot u otro CRM externo.
- Multitenant productivo (la arquitectura lo prevé, pero no se implementa completo).

## Por qué este recorte tiene sentido
- **El diferenciador real** no es conectar APIs (eso es commodity), es la **calidad de la conversación y la calificación**. Ahí ponemos el tiempo.
- Las integraciones reales (WhatsApp/Meta) tienen fricción de aprobación que quemaría el tiempo de hackathon.
- Un CRM/dashboard propio nos da **control total de la demo** y de la visualización — justo lo que Claudia pidió ("repúblicas independientes" → un solo lugar claro).

## Cómo seguimos cubriendo el "qué no se desea" del reto
| Restricción del reto | Cómo la respetamos en el MVP |
|---|---|
| No "un solo canal" | Mock de múltiples orígenes + arquitectura de canales desacoplada |
| No chatbot básico | Agente con contexto real (RAG), perfilamiento y scoring |
| Debe integrar externos | Adapters desacoplados; demostramos el patrón, conectamos después |
| Debe ser escalable | Diseño multitenant-ready (ver [[Arquitectura]]) |
| Analítica en tiempo real | Dashboard propio con métricas en vivo |
| Ciclo completo del lead | Captación (sim) → calificación → nurturing → handoff → pipeline |

## Restricciones de la hackathon
- **Tiempo:** 2 días.
- **Equipo de build:** 1 dev full-stack mid + Claude Code (Opus 4.8).
- **Implicación:** tareas muy granulares, cada una con prompt listo para Claude Code. Ver [[🗺️ MOC - Desarrollo]].
