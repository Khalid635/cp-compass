/* Minimal Markdown preview for problem notes — no new dependency.
   Supports: # / ## headings, - bullet lists, **bold**, *italic*,
   `code`, and plain paragraphs. Anything else renders as text. */
import type { ReactNode } from 'react';

function inline(text: string, keyPrefix: string): ReactNode[] {
  // Split on **bold**, *italic* and `code`, keeping the delimiters.
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={key} className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

export function Markdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flushList = () => {
    if (list.length > 0) {
      const items = list;
      list = [];
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="my-2 list-disc pl-5">
          {items.map((item, i) => (
            <li key={i} className="my-0.5">
              {inline(item, `li-${blocks.length}-${i}`)}
            </li>
          ))}
        </ul>,
      );
    }
  };
  lines.forEach((line, i) => {
    const trimmed = line.trim();
    if (trimmed.startsWith('- ')) {
      list.push(trimmed.slice(2));
      return;
    }
    flushList();
    if (trimmed.startsWith('## ')) {
      blocks.push(
        <h3 key={i} className="mb-1 mt-3 text-sm font-semibold">
          {inline(trimmed.slice(3), `h3-${i}`)}
        </h3>,
      );
    } else if (trimmed.startsWith('# ')) {
      blocks.push(
        <h2 key={i} className="mb-1 mt-3 text-base font-semibold">
          {inline(trimmed.slice(2), `h2-${i}`)}
        </h2>,
      );
    } else if (trimmed === '') {
      // Blank line — paragraph break, nothing to render.
    } else {
      blocks.push(
        <p key={i} className="my-1.5 text-sm leading-relaxed">
          {inline(line, `p-${i}`)}
        </p>,
      );
    }
  });
  flushList();
  return <div className="min-w-0">{blocks}</div>;
}
