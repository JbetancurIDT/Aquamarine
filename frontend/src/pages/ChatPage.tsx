import { useEffect, useState } from 'react'
import apiClient from '../api/client'

type BackendStatus = 'checking' | 'ok' | 'error'

export default function ChatPage() {
  const [status, setStatus] = useState<BackendStatus>('checking')

  useEffect(() => {
    apiClient
      .get('/health')
      .then((res) => setStatus(res.data?.status === 'ok' ? 'ok' : 'error'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem' }}>
      <h1>Chat</h1>
      <p>
        Estado del backend:{' '}
        {status === 'checking' && <span>verificando conexión…</span>}
        {status === 'ok' && <strong style={{ color: 'green' }}>backend ok</strong>}
        {status === 'error' && (
          <strong style={{ color: 'crimson' }}>backend sin conexión</strong>
        )}
      </p>
    </main>
  )
}
