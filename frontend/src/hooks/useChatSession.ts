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
  atendidoPorHumano: boolean
}

type ChatResponse = {
  respuesta: string
  inmuebles: Inmueble[]
  handoff: boolean
  temperatura: string
  lead_id: string
  atendido_por_humano: boolean
}

export function useChatSession(origen: string | undefined): {
  mensajes: Mensaje[]
  leadId: string | null
  temperatura: string
  cargando: boolean
  error: string | null
  handoff: boolean
  atendidoPorHumano: boolean
  enviar: (texto: string) => Promise<void>
} {
  const [state, setState] = useState<SessionState>({
    mensajes: [],
    leadId: null,
    temperatura: 'desconocido',
    cargando: false,
    error: null,
    atendidoPorHumano: false,
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
          if (origen !== undefined) {
            const { data } = await apiClient.post<ChatResponse>(`/chat/${origen}`, { mensaje: texto })
            response = data
          } else {
            const { data } = await apiClient.post<ChatResponse>('/chat', { mensaje: texto })
            response = data
          }
        } else {
          const { data } = await apiClient.post<ChatResponse>('/chat', {
            lead_id: state.leadId,
            mensaje: texto,
          })
          response = data
        }

        if (response.atendido_por_humano) {
          // IA silenciada: persiste el mensaje del lead pero no agrega burbuja de agente vacía
          setState((prev) => ({
            ...prev,
            leadId: response.lead_id,
            temperatura: response.temperatura,
            atendidoPorHumano: true,
            cargando: false,
            error: null,
          }))
          return
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
    leadId: state.leadId,
    temperatura: state.temperatura,
    cargando: state.cargando,
    error: state.error,
    handoff: ultimoHandoff,
    atendidoPorHumano: state.atendidoPorHumano,
    enviar,
  }
}
