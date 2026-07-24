import type { MapaPreview } from '../hooks/useChatSession'

/**
 * Tarjeta "Ver mapa interactivo" para el chat: consistente con PropertyCard (tokens de marca, w-52,
 * Newsreader en el título) pero con velo + 🗺️ para distinguirla de un inmueble. Abre la página
 * pública `/mapa/propiedad/:codigo` (rutas animadas + servicios) en una pestaña nueva.
 */
export function MapaCard({ mapa }: { mapa: MapaPreview }) {
  return (
    <a href={`/mapa/propiedad/${mapa.codigo}`} target="_blank" rel="noopener noreferrer"
       className="group flex flex-col flex-shrink-0 w-52 rounded-xl overflow-hidden mt-1"
       style={{ background: 'var(--card)', border: '1px solid var(--line)',
                boxShadow: '0 1px 4px rgba(26,26,26,.07)' }}>
      <div className="relative h-24 w-full">
        {mapa.imagen ? (
          <img src={mapa.imagen} alt={mapa.titulo} loading="lazy" className="w-full h-24 object-cover" />
        ) : (
          <div className="w-full h-24"
               style={{ background: 'linear-gradient(135deg, var(--charcoal), var(--champ))' }} />
        )}
        <div className="absolute inset-0 flex items-center justify-center"
             style={{ background: 'rgba(26,26,26,.35)' }}>
          <span className="text-2xl">🗺️</span>
        </div>
      </div>
      <div className="p-3 flex flex-col gap-1">
        <p className="text-sm font-semibold leading-snug"
           style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}>
          Ver mapa interactivo
        </p>
        <p className="text-xs line-clamp-1" style={{ color: 'var(--gray-soft)' }}>{mapa.titulo}</p>
        <span className="text-xs mt-1 font-medium" style={{ color: 'var(--champ)' }}>
          Rutas y servicios cercanos →
        </span>
      </div>
    </a>
  )
}
