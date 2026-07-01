import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Render compartido de Markdown para las burbujas de chat (cliente + gerencia).
 *
 * - GFM habilitado (remark-gfm): tablas, listas de tareas, tachado.
 * - SIN HTML crudo (react-markdown lo ignora por defecto; no se añade rehype-raw) → seguro.
 * - Estilos acordes a la paleta de lujo y al tamaño de las burbujas (texto pequeño, márgenes chicos).
 * - Las tablas se envuelven en un contenedor `overflow-x-auto scrollbar-brand` para que no rompan
 *   el ancho de la burbuja en paneles/pantallas angostos.
 */

const components: Components = {
  // Párrafo: margen pequeño + respeta saltos de línea simples (softbreaks de Aqua).
  p: ({ children }) => (
    <p className="my-1 first:mt-0 last:mb-0 whitespace-pre-wrap break-words leading-snug">
      {children}
    </p>
  ),
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,

  ul: ({ children }) => (
    <ul className="list-disc pl-5 my-1 space-y-0.5 marker:text-[var(--gray-soft)]">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-5 my-1 space-y-0.5 marker:text-[var(--gray-soft)]">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-snug break-words">{children}</li>,

  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline break-words"
      style={{ color: 'var(--champ)' }}
    >
      {children}
    </a>
  ),

  // Encabezados: discretos, acordes al tamaño de burbuja (no "gigantes").
  h1: ({ children }) => <h1 className="text-sm font-semibold my-1 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-semibold my-1 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold my-1 first:mt-0">{children}</h3>,

  blockquote: ({ children }) => (
    <blockquote
      className="border-l-2 pl-2 my-1 italic"
      style={{ borderColor: 'var(--champ-soft)', color: 'var(--gray)' }}
    >
      {children}
    </blockquote>
  ),

  hr: () => <hr className="my-2" style={{ borderColor: 'var(--line)' }} />,

  code: ({ children }) => (
    <code
      className="font-mono rounded px-1 py-0.5 text-[0.85em] break-words"
      style={{ background: 'var(--line-soft)' }}
    >
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre
      className="overflow-x-auto scrollbar-brand my-1.5 p-2 rounded-lg text-xs"
      style={{ background: 'var(--line-soft)' }}
    >
      {children}
    </pre>
  ),

  // Tabla: envuelta para scroll horizontal dentro de la burbuja sin romper el layout.
  table: ({ children }) => (
    <div
      className="overflow-x-auto scrollbar-brand my-1.5 max-w-full min-w-0 rounded-lg border"
      style={{ borderColor: 'var(--line)' }}
    >
      <table className="border-collapse text-xs w-full">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead style={{ background: 'var(--line-soft)' }}>{children}</thead>
  ),
  th: ({ children }) => (
    <th
      className="px-2 py-1 text-left font-semibold whitespace-nowrap border"
      style={{ borderColor: 'var(--line)', color: 'var(--ink)' }}
    >
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td
      className="px-2 py-1 align-top border"
      style={{ borderColor: 'var(--line)', color: 'var(--ink)' }}
    >
      {children}
    </td>
  ),
}

export function MarkdownMessage({ text }: { text: string }) {
  return (
    <div className="min-w-0 break-words" style={{ color: 'var(--ink)' }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  )
}
