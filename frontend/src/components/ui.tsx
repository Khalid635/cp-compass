/* UI primitives per the design spec: Button / Card / Badge / Skeleton /
   EmptyState / Input / Tabs. Solid colours, 12/8/6px radii, 2px focus ring. */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

/* ---------- Button ---------- */
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

export function Button({
  variant = 'primary',
  loading = false,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
}) {
  const base =
    'inline-flex h-9 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium ' +
    'transition-colors duration-120 ease-out select-none cursor-pointer ' +
    'disabled:cursor-not-allowed disabled:opacity-50 ' +
    'active:scale-[0.98]';
  const styles: Record<ButtonVariant, string> = {
    primary: 'bg-primary text-on-primary hover:opacity-90',
    secondary: 'bg-surface-2 text-text border border-border hover:bg-hover',
    ghost: 'bg-transparent text-text hover:bg-hover',
    danger:
      'bg-transparent text-danger border border-danger/40 hover:bg-danger/10',
  };
  return (
    <button
      className={`${base} ${styles[variant]} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader2 size={16} className="animate-spin" aria-hidden />}
      {props.children}
    </button>
  );
}

/* ---------- Card ---------- */
export function Card({
  title,
  action,
  children,
  className = '',
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-border bg-surface p-5 ${className}`}
      style={{ boxShadow: 'var(--shadow-card)' }}
    >
      {title !== undefined && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">{title}</h2>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/* ---------- RatingBadge ---------- */
export function RatingBadge({
  rating,
  rankName,
  rankColor,
}: {
  rating: number | null;
  rankName: string;
  rankColor: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-xs font-medium"
      style={{
        color: rankColor,
        background: 'transparent',
        border: `1px solid ${rankColor}`,
      }}
      title={rankName}
    >
      {rating ?? '—'}
    </span>
  );
}

/* ---------- TagChip ---------- */
export function TagChip({ tag, weak = false }: { tag: string; weak?: boolean }) {
  return (
    <span
      className="inline-flex items-center rounded-sm px-1.5 py-0.5 text-xs"
      style={{
        background: weak
          ? 'color-mix(in srgb, var(--danger) 12%, transparent)'
          : 'var(--surface-2)',
        color: weak ? 'var(--danger)' : 'var(--muted)',
      }}
    >
      {tag}
    </span>
  );
}

/* ---------- Skeleton ---------- */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/* ---------- EmptyState ---------- */
export function EmptyState({
  icon,
  title,
  text,
  action,
}: {
  icon: ReactNode;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-surface-2 text-muted">
        {icon}
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="max-w-sm text-sm text-muted">{text}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/* ---------- Input ---------- */
export function Input({
  error,
  className = '',
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { error?: string }) {
  return (
    <div className={className}>
      <input
        className={`h-10 w-full rounded-md border bg-surface-2 px-3 text-sm text-text placeholder:text-muted focus:border-ring focus:outline-none ${
          error ? 'border-danger' : 'border-border'
        }`}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}

/* ---------- Tabs ---------- */
export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: string; count?: number }[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div
      className="flex gap-1 border-b border-border"
      role="tablist"
      aria-label="Sections"
    >
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={`relative cursor-pointer px-3 pb-2 pt-1 text-sm font-medium transition-colors ${
            active === t.id ? 'text-text' : 'text-muted hover:text-text'
          }`}
        >
          {t.label}
          {t.count !== undefined && (
            <span className="ml-1.5 rounded-full bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted">
              {t.count}
            </span>
          )}
          {active === t.id && (
            <span className="absolute inset-x-0 -bottom-px h-0.5 bg-primary" />
          )}
        </button>
      ))}
    </div>
  );
}
