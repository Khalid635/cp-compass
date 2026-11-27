/* 10-block segmented score (Finance Assistant pattern): mastery at a
   glance — clearer than a ring at small size. pct 0–100; each block is
   10 points. Filled blocks teal, empty blocks hairline outline.
   `wide` stretches the blocks across the full width (weekly-goal bar). */
export function SegmentedScore({
  pct,
  label,
  variant = 'compact',
}: {
  pct: number;
  label?: string;
  variant?: 'compact' | 'wide';
}) {
  const filled = Math.round(Math.max(0, Math.min(100, pct)) / 10);
  return (
    <div
      className={`flex items-center gap-1 ${variant === 'wide' ? 'w-full' : ''}`}
      role="img"
      aria-label={label ?? `${Math.round(pct)}%`}
    >
      {Array.from({ length: 10 }, (_, i) => (
        <span
          key={i}
          className={variant === 'wide' ? 'h-2.5 flex-1 rounded-[2px]' : 'h-2 w-3 rounded-[2px]'}
          style={{
            background: i < filled ? 'var(--primary)' : 'transparent',
            border: '1px solid var(--border)',
          }}
        />
      ))}
    </div>
  );
}
