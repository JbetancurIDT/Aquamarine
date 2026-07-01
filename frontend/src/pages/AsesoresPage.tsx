import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../api/client'
import type { Asesor } from '../api/types'
import { ConsolaNav } from '../components/ConsolaNav'

function iniciales(nombre: string): string {
  return nombre.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2)
}

function TarjetaAsesor({ asesor, onClick }: { asesor: Asesor; onClick: () => void }) {
  const cargaTxt = `${asesor.carga} ${asesor.carga === 1 ? 'lead activo' : 'leads activos'}`
  return (
    <button
      onClick={onClick}
      className="text-left p-4 rounded-2xl border border-[color:var(--line)] hover:border-[color:var(--champ-soft)] hover:shadow-sm transition-all cursor-pointer flex flex-col gap-3"
      style={{ background: 'var(--card)' }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span
          className="w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-semibold"
          style={{ background: 'var(--champ-bg)', color: 'var(--champ)' }}
        >
          {iniciales(asesor.nombre)}
        </span>
        <div className="min-w-0">
          <p
            className="text-base font-semibold truncate"
            style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}
          >
            {asesor.nombre}
          </p>
          <span className="flex items-center gap-1.5 mt-0.5">
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ background: asesor.disponible ? '#2D7A4F' : 'var(--gray-soft)' }}
            />
            <span
              className="text-xs"
              style={{ color: asesor.disponible ? '#2D7A4F' : 'var(--gray-soft)' }}
            >
              {asesor.disponible ? 'disponible' : 'no disponible'}
            </span>
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--gray)' }}>{cargaTxt}</span>
        <span className="text-xs font-medium" style={{ color: 'var(--champ)' }}>Ver tablero →</span>
      </div>
    </button>
  )
}

export default function AsesoresPage() {
  const navigate = useNavigate()
  const [asesores, setAsesores] = useState<Asesor[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiClient.get<Asesor[]>('/asesores')
      .then(({ data }) => setAsesores(data))
      .catch(() => setError('No se pudo cargar la lista de asesores.'))
      .finally(() => setCargando(false))
  }, [])

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <header
        className="flex-shrink-0 border-b px-6 py-3 flex items-center justify-between gap-4"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        <h1 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
          <span className="font-normal" style={{ color: 'var(--gray-soft)' }}> · Asesores</span>
        </h1>
        <ConsolaNav active="/asesores" />
      </header>

      <main className="flex-1 overflow-y-auto scrollbar-brand px-6 py-6 max-w-6xl mx-auto w-full">
        <div className="mb-5">
          <h2
            className="text-xl font-semibold"
            style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}
          >
            Asesores
          </h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--gray-soft)' }}>
            Entra al tablero de cada asesor · clic en una tarjeta
          </p>
        </div>

        {cargando ? (
          <p className="text-sm text-center mt-12" style={{ color: 'var(--gray-soft)' }}>Cargando…</p>
        ) : error ? (
          <p className="text-sm text-center mt-12" style={{ color: '#B4543A' }}>{error}</p>
        ) : asesores.length === 0 ? (
          <p className="text-sm text-center mt-12" style={{ color: 'var(--gray-soft)' }}>
            No hay asesores. Corre <code>scripts/seed_asesores.py</code> o <code>scripts/seed_demo.py</code>.
          </p>
        ) : (
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}
          >
            {asesores.map(a => (
              <TarjetaAsesor key={a.id} asesor={a} onClick={() => navigate(`/asesor/${a.id}`)} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
