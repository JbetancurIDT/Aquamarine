import { useCallback, useEffect, useRef, useState, KeyboardEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useChatSession, type Mensaje } from '../hooks/useChatSession'
import type { LeadConMensajes, Mensaje as MensajeServidor } from '../api/types'
import apiClient from '../api/client'
import { PropertyCardList } from '../components/PropertyCard'
import { MarkdownMessage } from '../components/MarkdownMessage'

function formatHHMM(date: Date): string {
  return date.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function formatHHMMStr(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function BurbujaMensaje({ mensaje }: { mensaje: Mensaje }) {
  const esLead = mensaje.rol === 'lead'
  return (
    <div className={`flex ${esLead ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-[85%] min-w-0 ${esLead ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div
          className={`px-4 py-2 rounded-2xl text-sm break-words min-w-0 max-w-full${esLead ? ' whitespace-pre-wrap' : ''}`}
          style={
            esLead
              ? { background: 'var(--charcoal)', color: 'var(--card)', borderBottomRightRadius: '5px' }
              : { background: 'var(--card)', color: 'var(--ink)', borderBottomLeftRadius: '5px',
                  boxShadow: '0 1px 3px rgba(26,26,26,.08)' }
          }
        >
          {esLead ? mensaje.contenido : <MarkdownMessage text={mensaje.contenido} />}
        </div>
        {!esLead && mensaje.inmuebles && mensaje.inmuebles.length > 0 && (
          <PropertyCardList inmuebles={mensaje.inmuebles} />
        )}
        <span className="text-xs px-1" style={{ color: 'var(--gray-soft)' }}>
          {formatHHMM(mensaje.timestamp)}
        </span>
      </div>
    </div>
  )
}

function BurbujaServidor({ m }: { m: MensajeServidor }) {
  const esLead   = m.rol === 'lead'
  const esAsesor = m.rol === 'asesor'
  // Markdown solo para la IA ('agente'): el texto tecleado por lead/asesor humano va plano.
  const esTextoPlano = esLead || esAsesor
  return (
    <div className={`flex ${esLead ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-[85%] min-w-0 flex flex-col gap-1 ${esLead ? 'items-end' : 'items-start'}`}>
        {esAsesor && (
          <span className="text-xs px-1 font-medium" style={{ color: 'var(--champ)' }}>Asesor</span>
        )}
        <div
          className={`px-4 py-2 rounded-2xl text-sm break-words min-w-0 max-w-full${esTextoPlano ? ' whitespace-pre-wrap' : ''}`}
          style={
            esLead
              ? { background: 'var(--charcoal)', color: 'var(--card)', borderBottomRightRadius: '5px' }
              : esAsesor
              ? { background: 'var(--champ-bg)', color: 'var(--ink)', borderBottomLeftRadius: '5px',
                  border: '1px solid var(--champ-soft)', boxShadow: '0 1px 3px rgba(26,26,26,.06)' }
              : { background: 'var(--card)', color: 'var(--ink)', borderBottomLeftRadius: '5px',
                  boxShadow: '0 1px 3px rgba(26,26,26,.08)' }
          }
        >
          {esTextoPlano ? m.contenido : <MarkdownMessage text={m.contenido} />}
        </div>
        <span className="text-xs px-1" style={{ color: 'var(--gray-soft)' }}>
          {formatHHMMStr(m.creado_en)}
        </span>
      </div>
    </div>
  )
}

function IndicadorEscribiendo() {
  return (
    <div className="flex justify-start mb-3">
      <div
        className="rounded-2xl px-4 py-3 flex gap-1 items-center"
        style={{ background: 'var(--card)', boxShadow: '0 1px 3px rgba(26,26,26,.08)' }}
      >
        <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:0ms]"
              style={{ background: 'var(--gray-soft)' }} />
        <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:150ms]"
              style={{ background: 'var(--gray-soft)' }} />
        <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:300ms]"
              style={{ background: 'var(--gray-soft)' }} />
      </div>
    </div>
  )
}

export default function ChatPage() {
  const { origen } = useParams<{ origen?: string }>()
  const { mensajes, cargando, error, handoff, enviar, leadId, atendidoPorHumano } = useChatSession(origen)
  const [texto, setTexto] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Estado del lead según el servidor (fuente de verdad del takeover + transcripción).
  const [serverLead, setServerLead] = useState<LeadConMensajes | null>(null)

  const pollNow = useCallback(async () => {
    if (!leadId) return
    try {
      const { data } = await apiClient.get<LeadConMensajes>(`/leads/${leadId}`)
      setServerLead(data)
    } catch {}
  }, [leadId])

  // Poll base mientras exista leadId: así el lead detecta que un asesor tomó el chat
  // AUNQUE esté inactivo (sin tener que enviar otro mensaje).
  useEffect(() => {
    if (!leadId) return
    void pollNow()
    const id = setInterval(() => void pollNow(), 3000)
    return () => clearInterval(id)
  }, [leadId, pollNow])

  // El takeover lo confirma el servidor (o la respuesta inmediata del hook).
  const takeover = atendidoPorHumano || !!serverLead?.atendido_por_humano
  const serverMensajes: MensajeServidor[] = serverLead?.mensajes ?? []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, cargando, serverMensajes.length])

  function handleEnviar() {
    const contenido = texto.trim()
    if (!contenido || cargando) return
    setTexto('')
    // Tras enviar, refresca de inmediato para que el mensaje propio aparezca sin esperar el poll.
    void enviar(contenido).then(() => { void pollNow() })
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleEnviar()
    }
  }

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>

      {/* Header */}
      <header
        className="flex-shrink-0 border-b px-4 py-3 flex items-center gap-3"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
          style={{ background: 'var(--charcoal)' }}
        >
          <span
            className="italic text-base leading-none"
            style={{ color: 'var(--card)', fontFamily: 'Newsreader, Georgia, serif', fontWeight: 600 }}
          >
            A
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <h1 className="text-sm font-semibold leading-tight" style={{ color: 'var(--ink)' }}>
            Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
            <span style={{ color: 'var(--gray-soft)' }}> · Asistente Inmobiliario</span>
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--gray-soft)' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
              en línea
            </span>
            {origen && (
              <span
                className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border"
                style={{
                  borderColor: 'var(--champ-soft)',
                  color: 'var(--gray)',
                  background: 'var(--bg)',
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: 'var(--champ-soft)' }} />
                vía {origen}
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Banner: asesor humano tomó el chat */}
      {takeover && (
        <div
          className="flex-shrink-0 px-4 py-2.5 flex items-center gap-2"
          style={{ background: 'var(--champ-bg)', borderBottom: '1px solid var(--champ-soft)' }}
        >
          <span
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ background: 'var(--champ)' }}
          />
          <p className="text-xs font-medium" style={{ color: 'var(--champ)' }}>
            Ahora te atiende un asesor humano del equipo Aquamarine.
          </p>
        </div>
      )}

      {/* Lista de mensajes */}
      <main className="flex-1 overflow-y-auto scrollbar-brand-thin px-4 py-4">
        {!takeover && (
          <>
            {mensajes.length === 0 && !cargando && (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-center" style={{ color: 'var(--gray-soft)' }}>
                  Hola, soy Aqua. Cuéntame qué tipo de inmueble estás buscando.
                </p>
              </div>
            )}
            {mensajes.map((m) => <BurbujaMensaje key={m.id} mensaje={m} />)}
            {cargando && <IndicadorEscribiendo />}
            {handoff && (
              <div className="flex justify-start mb-3">
                <div
                  className="rounded-2xl p-4 flex flex-col gap-2 max-w-[80%]"
                  style={{
                    background: 'var(--card)',
                    border: '1px solid var(--line)',
                    boxShadow: '0 1px 3px rgba(26,26,26,.08)',
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ background: 'var(--champ)' }} />
                    <span className="text-sm font-medium" style={{ color: 'var(--ink)' }}>
                      Conectando con un asesor
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--gray)' }}>
                    Un asesor de Aquamarine Group se comunicará contigo pronto. Mientras tanto, puedo
                    seguir ayudándote: cuéntame más sobre el inmueble o lo que estás buscando.
                  </p>
                </div>
              </div>
            )}
          </>
        )}

        {takeover && serverMensajes.map((m) => (
          <BurbujaServidor key={m.id} m={m} />
        ))}

        <div ref={bottomRef} />
      </main>

      {/* Zona inferior: error + input */}
      <div
        className="flex-shrink-0 border-t"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        {error && (
          <div className="px-4 pt-2">
            <p
              className="text-xs rounded-lg px-3 py-2"
              style={{ color: '#B4543A', background: '#F6E9E4', border: '1px solid #E8C4B8' }}
            >
              {error}
            </p>
          </div>
        )}
        <div className="flex items-end gap-2 px-4 py-3">
          <textarea
            ref={textareaRef}
            rows={1}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={cargando}
            placeholder={takeover ? 'Responde al asesor…' : 'Escribe un mensaje…'}
            className="flex-1 resize-none text-sm focus:outline-none disabled:opacity-50 max-h-20 leading-snug bg-transparent"
            style={{
              minHeight: '2.5rem',
              border: '1px solid var(--line)',
              borderRadius: '999px',
              padding: '0.5rem 1rem',
              color: 'var(--ink)',
            }}
          />
          <button
            onClick={handleEnviar}
            disabled={cargando || !texto.trim()}
            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: 'var(--charcoal)', color: 'var(--card)' }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
