# Chat del lead — feature doc

## Qué hace
Chat web público donde el lead conversa con el agente Aqua (IA sobre Claude). El agente
perfila, califica y, si el lead lo pide o es caliente, hace handoff al asesor.

## Rutas frontend
- `/chat` — chat sin origen (lead llega directo).
- `/chat/:origen` — lead llega por un canal (`web`, `meta`, `portal`, `referido`, `otro`);
  el origin se guarda en el lead y se muestra como chip "vía {origen}" en el header.

## Backend: endpoint
`POST /chat` (o `POST /chat/:origen`) — ver `backend/app/api/chat.py`.

Request:
```json
{ "lead_id": "<uuid|null>", "mensaje": "texto del lead", "origen": "<string|null>" }
```

Response (`ChatResponse`):
```json
{ "respuesta": "...", "inmuebles": [...], "handoff": false, "temperatura": "tibio", "lead_id": "..." }
```

- Si `lead_id` es null, se crea el lead automáticamente y se devuelve su id para los
  turnos siguientes.
- `inmuebles` son las tarjetas de `PropertyCard` que el front renderiza bajo la burbuja.
- `handoff: true` dispara el bloque de "Conectando con un asesor" en el chat.
- `temperatura` es dato interno del CRM; **no se expone al lead** en el header del chat.

## Componentes frontend
| Archivo | Rol |
|---|---|
| `src/pages/ChatPage.tsx` | Página principal: header, mensajes, input |
| `src/hooks/useChatSession.ts` | Hook de estado de la sesión (mensajes, leadId, temperatura, enviar) |
| `src/components/PropertyCard.tsx` | Tarjeta de inmueble con imagen real (`imagen_principal`/`imagenes`) |
| `src/components/TemperaturaBadge.tsx` | Badge de temperatura (usado en dashboard, NO en el chat público) |

## Notas de diseño
- El badge de temperatura (`Frío/Tibio/Caliente`) es **dato interno del CRM**. El lead
  público no lo ve. `useChatSession` sí expone `temperatura` para consumo interno.
- Las imágenes de inmuebles se muestran via `imagen_principal` o `imagenes[0]`. Si la URL
  falla (`onError`), cae al placeholder de texto.

## Cómo correr
```bash
# Backend (desde backend/)
uvicorn app.main:app --reload

# Frontend (desde frontend/)
npm run dev
```
