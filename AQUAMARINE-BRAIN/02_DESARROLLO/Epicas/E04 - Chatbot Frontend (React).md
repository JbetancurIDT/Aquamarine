---
tipo: epica
audiencia: dev
estado: pendiente
epica: E04
actualizado: 2026-06-09
tags: [area/desarrollo, comp/frontend, stack/react, estado/pendiente]
---

# E04 — Chatbot Frontend (React)

> **En términos de negocio:** la ventana de chat donde el cliente conversa con el asistente. Se ve y se siente como un WhatsApp, para que sea natural y para mostrar cómo vivirá en el canal real.
> **Objetivo técnico:** UI de chat en React+TS conectada al orquestador del agente, con manejo de sesión de lead, historial y estado de "origen" simulado.

## Contexto para el agente
Estética tipo WhatsApp (burbujas, estados). El chat crea/usa un `lead` y conversa contra el backend del agente (E03). El **origen** del lead se simula vía un parámetro (ej. `?origen=meta`) para la narrativa omnicanal. Ver [[Alcance del MVP]].

## Dependencias
- **Requiere:** E03 (agente), E02 (leads).
- **Bloquea:** demo.

## Etapas y tareas

### Etapa 4.1 — Sesión y origen
- [ ] **T04.1.1** — Al abrir el chat, crear un lead con `origen` desde query param.
  - **Criterio:** `/chat?origen=meta` crea un lead con ese origen vía `POST /leads`; sin param usa `web`.
  - **Prompt sugerido:** "En el componente de Chat (React+TS), al montar, crea un lead llamando a POST /leads con el origen tomado del query param 'origen' (default 'web'). Guarda el lead_id en estado/sesión para los siguientes mensajes."

### Etapa 4.2 — UI de conversación
- [ ] **T04.2.1** — Componente de chat estilo WhatsApp (burbujas, input, scroll).
  - **Criterio:** mensajes del lead a la derecha, del agente a la izquierda; auto-scroll; input con envío por Enter.
  - **Prompt sugerido:** "Crea un componente Chat en React+TS con estética tipo WhatsApp: lista de burbujas (usuario derecha, agente izquierda), timestamps, auto-scroll al último mensaje, input fijo abajo con envío por Enter y botón. Usa Tailwind o CSS modules. Estado de mensajes en useState."
- [ ] **T04.2.2** — Conectar envío de mensaje al orquestador y mostrar respuesta.
  - **Criterio:** al enviar, llama al endpoint del agente, muestra indicador de "escribiendo", luego la respuesta.
  - **Prompt sugerido:** "Conecta el componente Chat al backend: al enviar un mensaje, POST a /leads/{id}/mensajes (o el endpoint del agente) y renderiza la respuesta del agente. Muestra un indicador de 'escribiendo...' mientras espera. Maneja errores con un mensaje amable."

### Etapa 4.3 — Presentación de inmuebles
- [ ] **T04.3.1** — Render de tarjetas de inmueble cuando el agente sugiere propiedades.
  - **Criterio:** si la respuesta incluye inmuebles, se muestran como tarjetas (foto/título/zona/precio) dentro del chat.
  - **Prompt sugerido:** "Cuando la respuesta del agente incluya inmuebles sugeridos (en metadata), renderiza tarjetas dentro del chat con tipo, zona, precio formateado en COP y un enlace a la fuente. Diseño limpio, acorde a mercado de lujo."

## Definición de hecho (épica)
Un usuario abre `/chat?origen=meta`, conversa con el agente, recibe respuestas humanas y ve tarjetas de inmuebles reales sugeridos.
