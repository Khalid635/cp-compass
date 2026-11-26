/* Feature cards: StatCard, ProblemCard, RevisionCard, RecentSubmissions,
   FilterBar — per the design spec. All user-facing text via i18n. */
import { useState } from 'react';
import type { ReactNode } from 'react';
import { ArrowUpRight, Check, Clock, ExternalLink, RotateCcw, X } from 'lucide-react';
import type { ProblemRef, RevisionItem, SubmissionRow, WhyInfo } from '../api/types';
import { cfUrl, rankOf } from '../api/types';
import { formatDateTime, formatWhy, useLanguage } from '../i18n';
import type { Dict } from '../i18n/dict';
import { Button, Card, RatingBadge, TagChip } from './ui';

/* ---------- StatCard ---------- */
export function StatCard({
  label,
  value,
  sub,
  delta,
  icon,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  delta?: { text: string; good: boolean };
  icon?: ReactNode;
}) {
  return (
    <div
      className="rounded-lg border border-border bg-surface p-5"
      style={{ boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-[0.04em] text-muted">{label}</p>
        {icon && <span className="text-muted">{icon}</span>}
      </div>
      <p className="tabular mt-2 font-mono text-[32px] font-semibold leading-none">{value}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        {delta && (
          <span
            className="whitespace-nowrap rounded-full px-2 py-0.5 font-medium"
            style={{
              color: delta.good ? 'var(--success)' : 'var(--danger)',
              background: delta.good
                ? 'color-mix(in srgb, var(--success) 12%, transparent)'
                : 'color-mix(in srgb, var(--danger) 12%, transparent)',
            }}
          >
            {delta.good ? '▲' : '▼'} {delta.text}
          </span>
        )}
        {sub && <span className="text-muted">{sub}</span>}
      </div>
    </div>
  );
}

/* ---------- ProblemCard ---------- */
export function ProblemCard({
  problem,
  why,
  score,
  demo = false,
  onAction,
  actionState,
}: {
  problem: ProblemRef;
  why: WhyInfo;
  score?: number;
  demo?: boolean;
  onAction?: (action: 'later' | 'not_interested') => void;
  actionState?: 'later' | 'not_interested' | 'hidden' | null;
}) {
  const { t } = useLanguage();
  const rank = rankOf(problem.rating);
  const hidden = actionState === 'hidden';
  if (hidden) return null;
  return (
    <article className="flex min-w-0 flex-col rounded-lg border border-border bg-surface p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-semibold leading-snug">{problem.name}</h3>
        <RatingBadge rating={problem.rating} rankName={rank.name} rankColor={rank.token} />
      </div>
      <p className="mt-1 font-mono text-[13px] font-medium text-muted">
        {problem.contest_id}
        {problem.index}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {problem.tags.map((tg) => (
          <TagChip key={tg} tag={tg} />
        ))}
      </div>
      <p className="mt-3 text-sm text-muted">{formatWhy(why, t)}</p>
      {score !== undefined && (
        <p className="mt-1 font-mono text-xs text-muted">{t.recScore(score)}</p>
      )}
      <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
        <a
          href={cfUrl(problem)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-on-primary transition-colors hover:opacity-90"
        >
          {t.openOnCf} <ExternalLink size={14} aria-hidden />
        </a>
        <Button
          variant="secondary"
          disabled={demo || actionState === 'later'}
          onClick={() => onAction?.('later')}
          title={demo ? t.disabledInDemo : undefined}
        >
          <Clock size={14} aria-hidden /> {actionState === 'later' ? t.savedForLater : t.later}
        </Button>
        <Button
          variant="ghost"
          disabled={demo}
          onClick={() => onAction?.('not_interested')}
          title={demo ? t.disabledInDemo : undefined}
        >
          <X size={14} aria-hidden /> {t.notInterested}
        </Button>
      </div>
    </article>
  );
}

function resultLabel(result: string, t: Dict): string {
  switch (result) {
    case 'again':
      return t.reviewAgain;
    case 'hard':
      return t.reviewHard;
    case 'good':
      return t.reviewGood;
    case 'easy':
      return t.reviewEasy;
    default:
      return result;
  }
}

/* ---------- RevisionCard ---------- */
export function RevisionCard({
  revision,
  demo = false,
  onReview,
  reviewed,
}: {
  revision: RevisionItem;
  demo?: boolean;
  onReview?: (result: 'again' | 'hard' | 'good' | 'easy') => void;
  reviewed?: string | null;
}) {
  const { t } = useLanguage();
  const rank = rankOf(revision.problem.rating);
  const options = [
    { id: 'again' as const, label: t.reviewAgain, key: '1', hint: t.hintAgain },
    { id: 'hard' as const, label: t.reviewHard, key: '2', hint: t.hintHard },
    { id: 'good' as const, label: t.reviewGood, key: '3', hint: t.hintGood },
    { id: 'easy' as const, label: t.reviewEasy, key: '4', hint: t.hintEasy },
  ];
  return (
    <article className="rounded-lg border border-border bg-surface p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">{revision.problem.name}</h3>
          <p className="mt-1 font-mono text-[13px] font-medium text-muted">
            {revision.problem.contest_id}
            {revision.problem.index}
          </p>
        </div>
        <RatingBadge
          rating={revision.problem.rating}
          rankName={rank.name}
          rankColor={rank.token}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {revision.problem.tags.map((tg) => (
          <TagChip key={tg} tag={tg} />
        ))}
      </div>
      <p className="mt-4 text-sm text-muted">
        {t.lastAttempt(revision.wrong_attempts, revision.interval_days)}
        {revision.last_result ? t.lastReview(resultLabel(revision.last_result, t)) : ''}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <a
          href={cfUrl(revision.problem)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-on-primary transition-colors hover:opacity-90"
        >
          {t.openOnCf} <ExternalLink size={14} aria-hidden />
        </a>
      </div>
      {reviewed ? (
        <p className="mt-5 flex items-center gap-2 text-sm text-success">
          <Check size={16} aria-hidden />{' '}
          {t.reviewedAs(
            resultLabel(reviewed, t),
            reviewed === 'again' ? t.reviewedNext1Day : t.reviewedNextLonger,
          )}
        </p>
      ) : (
        <>
          <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {options.map((o) => (
              <button
                key={o.id}
                disabled={demo}
                onClick={() => onReview?.(o.id)}
                title={demo ? t.disabledInDemo : o.hint}
                className="flex cursor-pointer flex-col items-center gap-0.5 rounded-md border border-border bg-surface-2 px-3 py-2.5 text-sm font-medium transition-colors hover:bg-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {o.label}
                <span className="text-xs font-normal text-muted">{o.hint}</span>
              </button>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">{t.rateKeysHint}</p>
        </>
      )}
    </article>
  );
}

/* ---------- Recent submissions table ---------- */
const VERDICT_STYLE: Record<string, { color: string; icon: ReactNode }> = {
  OK: { color: 'var(--success)', icon: <Check size={14} aria-hidden /> },
};

export function RecentSubmissions({ rows }: { rows: SubmissionRow[] }) {
  const { t, lang } = useLanguage();
  if (rows.length === 0) {
    return <p className="py-6 text-center text-sm text-muted">{t.noSubmissionsYet}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
            <th className="pb-2 pr-3 font-medium">{t.thProblem}</th>
            <th className="pb-2 pr-3 font-medium">{t.thVerdict}</th>
            <th className="hidden pb-2 pr-3 font-medium sm:table-cell">{t.thLanguage}</th>
            <th className="pb-2 text-right font-medium">{t.thTime}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const v = VERDICT_STYLE[r.verdict] ?? {
              color: 'var(--danger)',
              icon: <X size={14} aria-hidden />,
            };
            const label =
              r.verdict === 'OK' ? t.verdictAccepted : r.verdict.replace(/_/g, ' ');
            return (
              <tr key={i} className="border-b border-border/60 last:border-0 hover:bg-hover">
                <td className="py-3 pr-3">
                  <a
                    href={cfUrl(r.problem)}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-text hover:text-primary hover:no-underline"
                  >
                    {r.problem.contest_id}
                    {r.problem.index} — {r.problem.name}
                  </a>
                </td>
                <td className="py-3 pr-3">
                  <span
                    className="inline-flex items-center gap-1 font-medium"
                    style={{ color: v.color }}
                  >
                    {v.icon} {label}
                  </span>
                </td>
                <td className="hidden py-3 pr-3 font-mono text-xs text-muted sm:table-cell">
                  {r.language ?? '—'}
                </td>
                <td className="py-3 text-right text-muted">
                  {formatDateTime(r.submitted_at, lang)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- FilterBar ---------- */
export function FilterBar({
  tags,
  tag,
  setTag,
  minRating,
  setMinRating,
  maxRating,
  setMaxRating,
  hideSolved,
  setHideSolved,
}: {
  tags: string[];
  tag: string;
  setTag: (v: string) => void;
  minRating: string;
  setMinRating: (v: string) => void;
  maxRating: string;
  setMaxRating: (v: string) => void;
  hideSolved: boolean;
  setHideSolved: (v: boolean) => void;
}) {
  const { t } = useLanguage();
  const [showAllTags, setShowAllTags] = useState(false);
  const visibleTags = showAllTags ? tags : tags.slice(0, 10);
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">
          {t.filterTag}
          <select
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            className="h-10 rounded-md border border-border bg-surface-2 px-2 text-sm text-text focus:border-ring focus:outline-none"
          >
            <option value="">{t.filterAllTags}</option>
            {tags.map((tg) => (
              <option key={tg} value={tg}>
                {tg}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">
          {t.filterMinRating}
          <input
            type="number"
            value={minRating}
            onChange={(e) => setMinRating(e.target.value)}
            placeholder="800"
            className="h-10 w-24 rounded-md border border-border bg-surface-2 px-2 text-sm text-text placeholder:text-muted focus:border-ring focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">
          {t.filterMaxRating}
          <input
            type="number"
            value={maxRating}
            onChange={(e) => setMaxRating(e.target.value)}
            placeholder="1600"
            className="h-10 w-24 rounded-md border border-border bg-surface-2 px-2 text-sm text-text placeholder:text-muted focus:border-ring focus:outline-none"
          />
        </label>
        <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm">
          <input
            type="checkbox"
            checked={hideSolved}
            onChange={(e) => setHideSolved(e.target.checked)}
            className="h-4 w-4 accent-[var(--primary)]"
          />
          {t.filterHideSolved}
        </label>
      </div>
      {tags.length > 10 && (
        <button
          onClick={() => setShowAllTags((s) => !s)}
          className="mt-3 cursor-pointer text-xs text-primary hover:underline"
        >
          {showAllTags ? t.filterShowFewer : t.filterShowAll(tags.length)}
        </button>
      )}
      {visibleTags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {visibleTags.map((tg) => (
            <button key={tg} onClick={() => setTag(tag === tg ? '' : tg)} className="cursor-pointer">
              <TagChip tag={tg} weak={tag === tg} />
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

export function RotateCcwIcon() {
  return <RotateCcw size={14} aria-hidden />;
}

export function ArrowUpRightIcon() {
  return <ArrowUpRight size={14} aria-hidden />;
}
