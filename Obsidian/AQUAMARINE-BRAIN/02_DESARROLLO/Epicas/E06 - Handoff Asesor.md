---
tipo: epica
audiencia: dev
estado: completado
epica: E06
actualizado: 2026-07-24
tags: [area/desarrollo, comp/handoff, estado/completado]
---

# E06 — Handoff Asesor

> **En términos de negocio:** el momento clave. Cuando el asistente detecta que un cliente está "caliente" (listo para comprar), le avisa al asesor humano y le entrega el cliente con todo el perfil ya armado. Aquí se respeta lo que Claudia insiste: en el lujo, el cierre lo hace una persona, no una máquina.
> **Objetivo técnico:** al cruzar el umbral de "caliente", asignar asesor, cambiar estado a `calificado`, emitir evento `handoff` y mostrar notificación en el dashboard. Funcional, no simulado.

## Contexto para el agente
El handoff se dispara por **dos vías**: (a) el lead se vuelve **caliente** (scoring de E03), o (b) el lead **pide explícitamente un humano** (T06.1.2). La asignación de asesor puede ser por disponibilidad (MVP) y dejar el gancho para reglas por geolocalización/distribución (roadmap, mencionado en el transcript). El asesor ve la notificación en el dashboard de E05.

## Dependencias
- **Requiere:** E03 (scoring), E02 (leads/asesores/eventos), E05 (UI de notificación).
- **Bloquea:** demo (es el clímax del flujo).

## Etapas y tareas

### Etapa 6.1 — Disparo del handoff
- [ ] **T06.1.1** — Detectar transición a `caliente` y ejecutar el handoff.
  - **Criterio:** cuando un lead pasa a caliente, se asigna asesor, estado → `calificado`, y se emite evento `handoff` con el perfil completo.
  - **Prompt sugerido:** "Crea app/services/handoff_service.py con ejecutar_handoff(lead_id) que: asigne un asesor disponible (lead.asesor_id), cambie el estado a 'calificado', emita un evento 'handoff' con snapshot del perfil y la conversación, y registre el timestamp. Integra el disparo en el orquestador cuando la temperatura pase a 'caliente' (idempotente: no re-disparar)."

- [ ] **T06.1.2** — Handoff por **solicitud del cliente** ("quiero hablar con un humano").
  - **Criterio:** si el lead pide un asesor humano (o "no quiero hablar con una máquina"), se dispara el handoff **de inmediato**, sin esperar a "caliente". Antes, Aqua intenta capturar nombre + contacto; si el cliente se niega, se pasa igual con **temperatura `desconocido` y score null** (sin calificar). Idempotente.
  - **Nota:** la **detección** de la intención y el **handoff mínimo** (asignar asesor disponible + evento `handoff` + estado) ya se hacen en **E03** (`app/agent/`, ver D15); E06 añade la **notificación, la UI del asesor y la impersonación**.

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

### Etapa 6.4 — Impersonación de asesor (demo del handover)
- [ ] **T06.4.1** — Ruta `/asesor/<nombre>/<id>` que carga el dashboard del asesor SIN auth (mecanismo de DEMO).
  - **Criterio:** abrir `/asesor/daniela/a1` muestra los leads asignados a ese asesor + las notificaciones de handoff entrantes y permite "tomar" un lead, para **simular el handover** frente al cliente. NO es auth real (ver [[Decisiones (Decision Log)]] D14). Requiere 2–3 asesores sembrados. Diseño: [[Diseño UI (referencia)]] §4.4.

## Definición de hecho (épica)
Cuando un lead se vuelve caliente en el chat, el dashboard del asesor muestra la notificación con el perfil completo; el asesor lo toma y el lead avanza en el pipeline. Todo con eventos registrados (base para medir el tiempo de respuesta).

## Diseño (UI) — ver [[Diseño UI (referencia)]] §4.1 y §4.3
Handoff visible en el **chat del lead** (bloque "Conectando con &lt;asesor&gt;" + CTA verde WhatsApp) y en la consola interna dentro del `LeadDetail` (timeline + "Asignar / reasignar"). La **impersonación de asesor** (T06.4.1) permite ver la vista del asesor que recibe el lead.
