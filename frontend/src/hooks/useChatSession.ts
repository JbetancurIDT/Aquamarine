import { useState, useCallback } from 'react'
import apiClient from '../api/client'
import type { Inmueble } from '../components/PropertyCard'

export type Mensaje = {
  id: string
  rol: 'lead' | 'agente'
  contenido: string
  timestamp: Date
  inmuebles?: Inmueble[]
  handoff?: boolean
}

type SessionState = {
  mensajes: Mensaje[]
  leadId: string | null
  temperatura: string
  cargando: boolean
  error: string | null
}

type ChatResponse = {
  respuesta: string
  inmuebles: Inmueble[]
  handoff: boolean
  temperatura: string
  lead_id: string
}

export function useChatSession(origen: string | undefined): {
  mensajes: Mensaje[]
  temperatura: string
  cargando: boolean
  error: string | null
  handoff: boolean
  enviar: (texto: string) => Promise<void>
} {
  const [state, setState] = useState<SessionState>({
    mensajes: [],
    leadId: null,
    temperatura: 'desconocido',
    cargando: false,
    error: null,
  })

  const enviar = useCallback(
    async (texto: string) => {
      const mensajeUsuario: Mensaje = {
        id: crypto.randomUUID(),
        rol: 'lead',
        contenido: texto,
        timestamp: new Date(),
      }

      setState((prev) => ({
        ...prev,
        mensajes: [...prev.mensajes, mensajeUsuario],
        cargando: true,
        error: null,
      }))

      try {
        let response: ChatResponse

        if (state.leadId === null) {
          // Primer turno: crea el lead
          if (origen !== undefined) {
            const { data } = await apiClient.post<ChatResponse>(`/chat/${origen}`, {
              mensaje: texto,
            })
            response = data
          } else {
            const { data } = await apiClient.post<ChatResponse>('/chat', {
              mensaje: texto,
            })
            response = data
          }
        } else {
          // Turnos siguientes: reutiliza el lead existente
          const { data } = await apiClient.post<ChatResponse>('/chat', {
            lead_id: state.leadId,
            mensaje: texto,
          })
          response = data
        }

        const mensajeAgente: Mensaje = {
          id: crypto.randomUUID(),
          rol: 'agente',
          contenido: response.respuesta,
          timestamp: new Date(),
          inmuebles: response.inmuebles,
          handoff: response.handoff,
        }

        setState((prev) => ({
          ...prev,
          mensajes: [...prev.mensajes, mensajeAgente],
          leadId: response.lead_id,
          temperatura: response.temperatura,
          cargando: false,
          error: null,
        }))
      } catch {
        setState((prev) => ({
          ...prev,
          cargando: false,
          error: 'No pude conectarme. ¿Intentamos de nuevo?',
        }))
      }
    },
    [state.leadId, origen],
  )

  const ultimoHandoff =
    state.mensajes
      .filter((m) => m.rol === 'agente')
      .at(-1)?.handoff ?? false

  return {
    mensajes: state.mensajes,
    temperatura: state.temperatura,
    cargando: state.cargando,
    error: state.error,
    handoff: ultimoHandoff,
    enviar,
  }
}
