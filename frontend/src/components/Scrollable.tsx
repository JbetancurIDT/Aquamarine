import type { CSSProperties, ReactNode } from 'react'

/**
 * Wrapper de scroll con la scrollbar de marca.
 * Aplica overflow-auto + .scrollbar-brand (o -thin si thin=true).
 */
export function Scrollable({
  children,
  className = '',
  thin = false,
  style,
}: {
  children: ReactNode
  className?: string
  thin?: boolean
  style?: CSSProperties
}) {
  return (
    <div
      className={`overflow-auto ${thin ? 'scrollbar-brand-thin' : 'scrollbar-brand'} ${className}`}
      style={style}
    >
      {children}
    </div>
  )
}
