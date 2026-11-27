/* HUD telemetry strip (Freight Command ops style): mono uppercase
   labels, hairline dividers, status dots (teal — never green), gold
   rank highlight, ONE coral alert only when the rating dropped in the
   last contest. Every value comes from the dashboard query — nothing
   invented. In demo mode the sync cell reads DEMO / SEEDED instead. */
import type { ReactNode } from 'react';
import { Fragment } from 'react';

export function HudPanel({
  rating,
  delta,
  solved,
  streak,
  revisionsDue,
  rankName,
  synced,
  demo = false,
  lastContest,
}: {
  rating: number | null;
  delta: number;
  solved: number;
  streak: number;
  revisionsDue: number;
  rankName: string;
  synced: boolean;
  demo?: boolean;
  lastContest: string;
}) {
  const dropped = delta < 0;
  const item = (label: string, value: ReactNode) => (
    <span className="flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-wide text-muted">{label}</span>
      {value}
    </span>
  );
  const items: ReactNode[] = [
    demo
      ? item(
          'Mode',
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: 'var(--primary)' }}
            />
            <span className="text-sm font-semibold text-text">DEMO · SEEDED</span>
          </span>,
        )
      : item(
          'Sync',
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: synced ? 'var(--primary)' : 'var(--muted)' }}
            />
            <span className="text-sm font-semibold text-text">
              {synced ? 'OK' : 'NEVER'}
            </span>
          </span>,
        ),
    item(
      'Rating',
      <span className="inline-flex items-center gap-2">
        <span className="text-sm font-semibold text-text">{rating ?? '—'}</span>
        {delta !== 0 &&
          (dropped ? (
            <span className="inline-flex items-center gap-1.5 font-semibold text-danger">
              <span className="pulse-dot inline-block h-2 w-2 rounded-full bg-danger" />
              ▼ {delta}
              <span className="text-[11px] font-medium uppercase tracking-wide text-muted">
                {lastContest}
              </span>
            </span>
          ) : (
            <span className="font-semibold text-success">▲ +{delta}</span>
          ))}
      </span>,
    ),
    item('Solved', <span className="text-sm font-semibold text-text">{solved}</span>),
    item('Streak', <span className="text-sm font-semibold text-text">{streak}D</span>),
    item(
      'Revisions',
      <span className="text-sm font-semibold text-text">{revisionsDue} DUE</span>,
    ),
    item(
      'Rank',
      <span className="text-sm font-semibold uppercase" style={{ color: 'var(--gold)' }}>
        {rankName}
      </span>,
    ),
  ];
  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-surface px-4 py-3 font-mono text-xs"
      role="status"
    >
      {items.map((it, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="hidden h-4 w-px bg-border sm:block" aria-hidden />}
          {it}
        </Fragment>
      ))}
    </div>
  );
}
