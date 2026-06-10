---
tipo: epica
audiencia: dev
estado: pendiente
epica: E06
actualizado: 2026-06-09
tags: [area/desarrollo, comp/handoff, estado/pendiente]
---

# E06 — Handoff Asesor

> **En términos de negocio:** el momento clave. Cuando el asistente detecta que un cliente está "caliente" (listo para comprar), le avisa al asesor humano y le entrega el cliente con todo el perfil ya armado. Aquí se respeta lo que Claudia insiste: en el lujo, el cierre lo hace una persona, no una máquina.
> **Objetivo técnico:** al cruzar el umbral de "caliente", asignar asesor, cambiar estado a `calificado`, emitir evento `handoff` y mostrar notificación en el dashboard. Funcional, no simulado.

## Contexto para el agente
El scoring de E03 marca `caliente`. La asignación de asesor puede ser por disponibilidad (MVP) y dejar el gancho para reglas por geolocalización/distribución (roadmap, mencionado en el transcript). El asesor ve la notificación en el dashboard de E05.

## Dependencias
- **Requiere:** E03 (scoring), E02 (leads/asesores/eventos), E05 (UI de notificación).
- **Bloquea:** demo (es el clímax del flujo).

## Etapas y tareas

### Etapa 6.1 — Disparo del handoff
- [ ] **T06.1.1** — Detectar transición a `caliente` y ejecutar el handoff.
  - **Criterio:** cuando un lead pasa a caliente, se asigna asesor, estado → `calificado`, y se emite evento `handoff` con el perfil completo.
  - **Prompt sugerido:** "Crea app/services/handoff_service.py con ejecutar_handoff(lead_id) que: asigne un asesor disponible (lead.asesor_id), cambie el estado a 'calificado', emita un evento 'handoff' con snapshot del perfil y la conversación, y registre el timestamp. Integra el disparo en el orquestador cuando la temperatura pase a 'caliente' (idempotente: no re-disparar)."

### Etapa 6.2 — Notificación al asesor
- [ ] **T06.2.1** — Endpoint de notificaciones pendientes del asesor.
  - **Criterio:** `GET /asesores/{id}/notificaciones` lista handoffs recientes con resumen del lead.
  - **Prompt sugerido:** "Crea GET /asesores/{id}/notificaciones que devuelva los eventos 'handoff' recientes de leads asignados a ese asesor, con nombre, temperatura, perfil resumido y enlace al detalle."
- [ ] **T06.2.2** — UI de notificación en el dashboard (toast/bandeja).
  - **Criterio:** cuando hay un handoff nuevo, el dashboard muestra una alerta visible con el lead listo para tomar.
  - **Prompt sugerido:** "En el dashboard React, agrega una bandeja/toast de notificaciones que consulte periódicamente GET /asesores/{id}/notificaciones y muestre los leads calientes recién entregados, con un botón para abrir el detalle del lead."

### Etapa 6.3 — Toma del lead por el asesor
- [ ] **T06.3.1** — Acción "tomar lead" que pasa el estado a `negociando`.
  - **Criterio:** el asesor toma el lead desde la notificación → estado `negociando` + evento.

## Definición de hecho (épica)
Cuando un lead se vuelve caliente en el chat, el dashboard del asesor muestra la notificación con el perfil completo; el asesor lo toma y el lead avanza en el pipeline. Todo con eventos registrados (base para medir el tiempo de respuesta).
