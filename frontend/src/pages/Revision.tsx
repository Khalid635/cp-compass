/* Revision — Due today / Upcoming / Done tabs, one big RevisionCard at a
   time, Again/Hard/Good/Easy + keys 1–4. Intervals: 1/3/7/14/30 days. */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import { api } from '../api/client';
import type { RevisionItem } from '../api/types';
import { formatDate, useLanguage } from '../i18n';
import { RevisionCard } from '../components/cards';
import { Button, Card, EmptyState, Skeleton, Tabs } from '../components/ui';

type Tab = 'due' | 'upcoming' | 'done';
type Result = 'again' | 'hard' | 'good' | 'easy';

export default function Revision({ demo = false }: { demo?: boolean }) {
  const { t, lang } = useLanguage();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('due');
  const [index, setIndex] = useState(0);
  const [reviewed, setReviewed] = useState<Record<number, Result>>({});

  const countsQuery = useQuery({
    queryKey: demo ? ['demo-revision-counts'] : ['revision-counts'],
    queryFn: demo
      ? async () => {
          const r = await api.demoRevisions();
          return { due: r.due.length, upcoming: r.upcoming.length, done: r.done.length };
        }
      : api.revisionCounts,
  });

  const listQuery = useQuery({
    queryKey: demo ? ['demo-revisions', tab] : ['revisions', tab],
    queryFn: demo
      ? async () => (await api.demoRevisions())[tab]
      : () => api.revisions(tab),
  });

  const items = useMemo(() => listQuery.data ?? [], [listQuery.data]);
  const current: RevisionItem | undefined = items[index];

  const review = useMutation({
    mutationFn: ({ id, result }: { id: number; result: Result }) =>
      api.reviewRevision(id, result),
    onSuccess: (_data, vars) => {
      setReviewed((r) => ({ ...r, [vars.id]: vars.result }));
      void qc.invalidateQueries({ queryKey: ['revision-counts'] });
      void qc.invalidateQueries({ queryKey: ['revisions'] });
    },
  });

  const doReview = useCallback(
    (result: Result) => {
      if (!current || demo) return;
      review.mutate({ id: current.id, result });
    },
    [current, demo, review],
  );

  // Keys 1–4 rate the current card.
  useEffect(() => {
    if (tab !== 'due') return;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const map: Record<string, Result> = { '1': 'again', '2': 'hard', '3': 'good', '4': 'easy' };
      const r = map[e.key];
      if (r && current && !reviewed[current.id]) doReview(r);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tab, current, reviewed, doReview]);

  // Reset the card index when the tab or list changes.
  useEffect(() => setIndex(0), [tab, listQuery.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps

  const counts = countsQuery.data ?? { due: 0, upcoming: 0, done: 0 };

  return (
    <div className="page-enter flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">{t.revision}</h1>
      <Tabs<Tab>
        tabs={[
          { id: 'due', label: t.tabDue, count: counts.due },
          { id: 'upcoming', label: t.tabUpcoming, count: counts.upcoming },
          { id: 'done', label: t.tabDone, count: counts.done },
        ]}
        active={tab}
        onChange={setTab}
      />

      {listQuery.isPending && <Skeleton className="h-[320px] w-full" />}

      {listQuery.data && items.length === 0 && (
        <Card>
          <EmptyState
            icon={<CheckCircle2 size={40} aria-hidden />}
            title={tab === 'due' ? t.noRevisionsDue : t.nothingHere}
            text={
              tab === 'due'
                ? t.allCaughtUp
                : tab === 'upcoming'
                  ? t.upcomingHint
                  : t.doneHint
            }
          />
        </Card>
      )}

      {current && (
        <div className="mx-auto w-full max-w-2xl">
          <RevisionCard
            revision={current}
            demo={demo}
            reviewed={reviewed[current.id] ?? null}
            onReview={doReview}
          />
          {items.length > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button
                variant="secondary"
                disabled={index === 0}
                onClick={() => setIndex((i) => Math.max(0, i - 1))}
              >
                <ChevronLeft size={14} aria-hidden /> {t.previous}
              </Button>
              <span className="font-mono text-sm text-muted">
                {index + 1} / {items.length}
              </span>
              <Button
                variant="secondary"
                disabled={index >= items.length - 1}
                onClick={() => setIndex((i) => Math.min(items.length - 1, i + 1))}
              >
                {t.next} <ChevronRight size={14} aria-hidden />
              </Button>
            </div>
          )}
        </div>
      )}

      {tab === 'upcoming' && items.length > 0 && (
        <div className="mx-auto w-full max-w-2xl">
          <Card title={t.comingUp}>
            <ul className="flex flex-col gap-2">
              {items.slice(0, 10).map((r) => (
                <li key={r.id} className="flex items-center gap-2 text-sm">
                  <RotateCcw size={14} className="shrink-0 text-muted" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">
                    {r.problem.contest_id}
                    {r.problem.index} — {r.problem.name}
                  </span>
                  <span className="font-mono text-xs text-muted">
                    {formatDate(r.due_date, lang)}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}

      {demo && <p className="text-center text-xs text-muted">{t.demoRevisionNote}</p>}
    </div>
  );
}
