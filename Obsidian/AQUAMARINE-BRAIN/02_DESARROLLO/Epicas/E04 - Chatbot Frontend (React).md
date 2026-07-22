---
tipo: epica
audiencia: dev
estado: completado
epica: E04
actualizado: 2026-06-10
tags: [area/desarrollo, comp/frontend, stack/react, estado/completado]
---

# E04 — Chatbot Frontend (React)

> **En términos de negocio:** la ventana de chat donde el cliente conversa con el asistente. Se ve y se siente como un WhatsApp, para que sea natural y para mostrar cómo vivirá en el canal real.
> **Objetivo técnico:** UI de chat en React+TS conectada al orquestador del agente, con manejo de sesión de lead, historial y estado de "origen" simulado.

> [!success] Cerrada (2026-06-10)
> Chat construido, cableado y pulido. Archivos: `frontend/src/pages/ChatPage.tsx`, `useChatSession.ts`, `components/PropertyCard.tsx`, `components/TemperaturaBadge.tsx`, routing en `App.tsx` (`/chat` y `/chat/:origen`). Doc de feature: `chat.md`.
> **Cierre del pulido:**
> - ✅ Temperatura **oculta** al lead en el chat público (es dato interno del CRM; se movió a `TemperaturaBadge`, que solo usa el dashboard).
> - ✅ Tarjetas de inmueble con **imagen real** (`imagen_principal`/`imagenes[0]`, fallback `onError` al placeholder).
> - ✅ Búsqueda por código exacto disponible end-to-end ([[Riesgos y Bloqueos]] R07 implementado).
> **Queda como deuda menor (no bloquea):** validar **paleta/diseño** fino contra [[Diseño UI (referencia)]] y agregar **tests de frontend** (hoy no hay).

## Contexto para el agente
Estética tipo WhatsApp (burbujas, estados). **El lead lo crea el AGENTE** (E03) en el primer `POST /chat` — el front NO lo crea. El **origen** del lead se simula por la **ruta**: `/chat/<origen>/` (ej. `/chat/metrocuadrado/`); `/chat/` a secas = sin origen (el agente lo pregunta si surge natural, o lo deja null). Slugs: `web | meta | metrocuadrado | fincaraiz`. Ver [[Alcance del MVP]] y [[Decisiones (Decision Log)]] D15.

## Dependencias
- **Requiere:** E03 (agente), E02 (leads).
- **Bloquea:** demo.

## Etapas y tareas

### Etapa 4.1 — Sesión y origen
- [x] **T04.1.1** — Leer el `origen` de la **ruta** `/chat/<origen>/` y pasarlo al agente (el agente crea el lead). *(Hecho: `useChatSession.ts` — primer turno a `POST /chat` o `POST /chat/<origen>`; guarda y reutiliza `lead_id`.)*
  - **Criterio:** `/chat/metrocuadrado/` manda el primer mensaje a `POST /chat` con `origen: "metrocuadrado"`; `/chat/` (sin slug) no manda origen (queda null y el agente puede preguntarlo). El front **guarda el `lead_id` que devuelve `/chat`** y lo reusa en los siguientes mensajes (NO crea el lead él mismo).
  - **Prompt sugerido:** "En el chat React, lee el segmento de origen de la URL (`/chat/:origen?`); en el primer envío llama a `POST /chat {mensaje, origen}` (omite `origen` si la ruta no lo trae), guarda el `lead_id` de la respuesta y úsalo en los siguientes `POST /chat {lead_id, mensaje}`."

### Etapa 4.2 — UI de conversación
- [x] **T04.2.1** — Componente de chat estilo WhatsApp (burbujas, input, scroll). *(Hecho: `ChatPage.tsx` — burbujas lead/agente, timestamps, auto-scroll, input con Enter.)*
  - **Criterio:** mensajes del lead a la derecha, del agente a la izquierda; auto-scroll; input con envío por Enter.
  - **Prompt sugerido:** "Crea un componente Chat en React+TS con estética tipo WhatsApp: lista de burbujas (usuario derecha, agente izquierda), timestamps, auto-scroll al último mensaje, input fijo abajo con envío por Enter y botón. Usa Tailwind o CSS modules. Estado de mensajes en useState."
- [x] **T04.2.2** — Conectar envío de mensaje al orquestador y mostrar respuesta. *(Hecho: `useChatSession.ts` llama `POST /chat`; `ChatPage` muestra indicador "escribiendo" y maneja errores con mensaje amable.)*
  - **Criterio:** al enviar, llama al endpoint del agente, muestra indicador de "escribiendo", luego la respuesta.
  - **Prompt sugerido:** "Conecta el componente Chat al backend: al enviar un mensaje, POST a /leads/{id}/mensajes (o el endpoint del agente) y renderiza la respuesta del agente. Muestra un indicador de 'escribiendo...' mientras espera. Maneja errores con un mensaje amable."

### Etapa 4.3 — Presentación de inmuebles
- [x] **T04.3.1** — Render de tarjetas de inmueble cuando el agente sugiere propiedades. *(Hecho: `PropertyCard.tsx` — tipo/título/zona/precio COP + enlace a fuente, incrustadas en el chat.)*
  - **Criterio:** si la respuesta incluye inmuebles, se muestran como tarjetas (foto/título/zona/precio) dentro del chat.
  - **Prompt sugerido:** "Cuando la respuesta del agente incluya inmuebles sugeridos (en metadata), renderiza tarjetas dentro del chat con tipo, zona, precio formateado en COP y un enlace a la fuente. Diseño limpio, acorde a mercado de lujo."

## Definición de hecho (épica)
Un usuario abre `/chat/metrocuadrado/` (o `/chat/`), conversa con el agente —que **crea el lead** con ese origen—, recibe respuestas humanas y ve tarjetas de inmuebles reales sugeridos.

## Diseño (UI) — ver [[Diseño UI (referencia)]] §4.1 y §1
Pantalla **pública** `/chat`, estética WhatsApp con paleta de lujo. Header con badge de **temperatura en vivo** (Frío→Tibio→Caliente) y chip de canal ("vía Meta"); **PropertyCard** incrustada cuando Aqua recomienda inventario (RAG); bloque de **handoff** con CTA verde WhatsApp ("Continuar por WhatsApp"). El backend debe poder anexar `cards:[propId]` y `handoff:true` a un mensaje. La **paleta es requisito duro**.
