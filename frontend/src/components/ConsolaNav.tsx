import { Link } from 'react-router-dom'

// Nav interno compartido por las pantallas de la consola (dashboard / pipeline /
// performance / asesores). `active` = ruta de la página actual → se resalta en champagne.
const LINKS: { to: string; label: string }[] = [
  { to: '/chat',        label: 'Chat' },
  { to: '/dashboard',   label: 'Dashboard' },
  { to: '/pipeline',    label: 'Pipeline' },
  { to: '/performance', label: 'Performance' },
  { to: '/asesores',    label: 'Asesores' },
]

export function ConsolaNav({ active }: { active: string }) {
  return (
    <nav className="flex items-center gap-2 flex-wrap">
      {LINKS.map(({ to, label }) => {
        const esActiva = to === active
        return (
          <Link
            key={to}
            to={to}
            className="text-xs px-3 py-1.5 rounded-lg transition-colors"
            style={esActiva
              ? { color: 'var(--champ)', background: 'var(--champ-bg)', border: '1px solid var(--champ-soft)' }
              : { color: 'var(--gray)', background: 'var(--line-soft)' }}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
