/* Donut goal rings — the "Fama" Pots pattern, applied to real topic data:
   one ring per top tag, acceptance % in the centre, a fixed 80% goal, and
   one action that jumps to Practice pre-filtered by that tag. No invented
   numbers — every % is the tag's real acceptance rate. */
import { useNavigate } from 'react-router-dom';
import type { TagStrength } from '../api/types';
import { useLanguage } from '../i18n';
import { Button } from './ui';

const GOAL_PCT = 80;

function Ring({ pct, weak }: { pct: number; weak: boolean }) {
  const { t } = useLanguage();
  const r = 40;
  const c = 2 * Math.PI * r;
  const filled = Math.max(0, Math.min(100, pct)) / 100;
  return (
    <svg width="96" height="96" viewBox="0 0 96 96" role="img" aria-label={`${pct}%`}>
      <circle cx="48" cy="48" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="9" />
      <circle
        cx="48"
        cy="48"
        r={r}
        fill="none"
        stroke={weak ? 'var(--danger)' : 'var(--primary)'}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={`${filled * c} ${c}`}
        transform="rotate(-90 48 48)"
      />
      <text
        x="48"
        y="45"
        textAnchor="middle"
        fill="var(--text)"
        fontSize="19"
        fontWeight="600"
        fontFamily="var(--font-mono)"
      >
        {pct}%
      </text>
      <text x="48" y="62" textAnchor="middle" fill="var(--muted)" fontSize="10">
        {weak ? t.goalWeak : t.goalOnTrack}
      </text>
    </svg>
  );
}

export function GoalRings({ tags, base }: { tags: TagStrength[]; base: string }) {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const top = [...tags].sort((a, b) => b.attempted - a.attempted).slice(0, 4);
  if (top.length === 0) return null;
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {top.map((tg) => {
        const pct = Math.round(tg.acceptance * 100);
        return (
          <div
            key={tg.tag}
            className="flex flex-col items-center gap-1 rounded-lg border border-border bg-bg p-4 text-center"
          >
            <Ring pct={pct} weak={tg.weak} />
            <p className="mt-1 text-sm font-semibold">{tg.tag}</p>
            <p className="text-xs text-muted">
              {t.goalAttempted(tg.attempted)} · {t.goalTarget(GOAL_PCT)}
            </p>
            <Button
              variant="secondary"
              className="mt-2 h-8 text-xs"
              onClick={() => navigate(`${base}/practice?tag=${encodeURIComponent(tg.tag)}`)}
            >
              {t.goalPractice(tg.tag)}
            </Button>
          </div>
        );
      })}
    </div>
  );
}
