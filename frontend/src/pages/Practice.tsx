/* Practice — FilterBar + ProblemCard grid. "Why suggested" on every card.
   Later / Not interested persist to the backend (disabled in demo). */
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { useLanguage } from '../i18n';
import { FilterBar, ProblemCard } from '../components/cards';
import { Button, Card, EmptyState, Skeleton } from '../components/ui';

type ActionState = 'later' | 'not_interested' | 'hidden' | null;

export default function Practice({ demo = false }: { demo?: boolean }) {
  const { t } = useLanguage();
  const qc = useQueryClient();
  const [tag, setTag] = useState('');
  const [minRating, setMinRating] = useState('');
  const [maxRating, setMaxRating] = useState('');
  const [hideSolved, setHideSolved] = useState(true);
  const [states, setStates] = useState<Record<string, ActionState>>({});

  const query = useQuery({
    queryKey: demo
      ? ['demo-recommendations']
      : ['recommendations', tag, minRating, maxRating, hideSolved],
    queryFn: demo
      ? api.demoRecommendations
      : () =>
          api.recommendations({
            tag: tag || undefined,
            min_rating: minRating ? Number(minRating) : undefined,
            max_rating: maxRating ? Number(maxRating) : undefined,
          }),
    staleTime: 60_000,
  });

  const action = useMutation({
    mutationFn: ({
      contest_id,
      index,
      act,
    }: {
      contest_id: number;
      index: string;
      act: 'later' | 'not_interested';
    }) => api.recommendationAction(contest_id, index, act),
    onSuccess: (_data, vars) => {
      setStates((s) => ({
        ...s,
        [`${vars.contest_id}${vars.index}`]:
          vars.act === 'not_interested' ? 'hidden' : 'later',
      }));
      void qc.invalidateQueries({ queryKey: ['recommendations'] });
    },
  });

  const tags = useMemo(() => {
    const all = new Set<string>();
    (query.data ?? []).forEach((p) => p.tags.forEach((tg) => all.add(tg)));
    return [...all].sort();
  }, [query.data]);

  return (
    <div className="page-enter flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">{t.practice}</h1>
      <FilterBar
        tags={tags}
        tag={tag}
        setTag={setTag}
        minRating={minRating}
        setMinRating={setMinRating}
        maxRating={maxRating}
        setMaxRating={setMaxRating}
        hideSolved={hideSolved}
        setHideSolved={setHideSolved}
      />

      {query.isPending && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-[220px] w-full" />
          ))}
        </div>
      )}

      {query.isError && (
        <Card>
          <EmptyState
            icon={<RefreshCw size={40} aria-hidden />}
            title={t.cfNoResponse}
            text={t.cfRetryAutoShort}
            action={
              <Button onClick={() => void query.refetch()}>
                <RefreshCw size={14} aria-hidden /> {t.retry}
              </Button>
            }
          />
        </Card>
      )}

      {query.data && query.data.length === 0 && (
        <Card>
          <EmptyState
            icon={<RefreshCw size={40} aria-hidden />}
            title={t.noProblemsMatch}
            text={t.noProblemsMatchHint}
          />
        </Card>
      )}

      {query.data && query.data.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {query.data.map((p) => (
            <ProblemCard
              key={`${p.contest_id}${p.index}`}
              problem={p}
              why={p.why}
              score={p.score}
              demo={demo}
              actionState={states[`${p.contest_id}${p.index}`] ?? null}
              onAction={(act) =>
                action.mutate({ contest_id: p.contest_id, index: p.index, act })
              }
            />
          ))}
        </div>
      )}

      {demo && <p className="text-center text-xs text-muted">{t.demoPracticeNote}</p>}
    </div>
  );
}
