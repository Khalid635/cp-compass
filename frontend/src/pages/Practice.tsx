/* Practice — FilterBar + filter pills (with counts) + saved views +
   ProblemCard grid with AutoAnimate. "Why suggested" on every card.
   Later / Not interested persist to the backend (disabled in demo) and
   toast with an Undo action. ?tag= in the URL pre-filters by tag
   (used by the dashboard goal rings). */
import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { toast } from 'sonner';
import { Bookmark, RefreshCw, X } from 'lucide-react';
import { api } from '../api/client';
import { useLanguage } from '../i18n';
import { FilterBar, ProblemCard } from '../components/cards';
import { FilterPills, RATING_BANDS, bandIdFor } from '../components/FilterPills';
import type { PillCount } from '../components/FilterPills';
import { useSavedViews } from '../hooks/useSavedViews';
import { Button, Card, EmptyState, Input, Skeleton } from '../components/ui';

type ActionState = 'later' | 'not_interested' | 'hidden' | null;

export default function Practice({ demo = false }: { demo?: boolean }) {
  const { t } = useLanguage();
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const [tag, setTag] = useState('');
  const [minRating, setMinRating] = useState('');
  const [maxRating, setMaxRating] = useState('');
  const [hideSolved, setHideSolved] = useState(true);
  const [states, setStates] = useState<Record<string, ActionState>>({});
  const [gridRef] = useAutoAnimate<HTMLDivElement>();
  const { views, save, remove } = useSavedViews();
  const [viewName, setViewName] = useState('');

  // ?tag= pre-filters (goal-ring deep link); reacts to navigation too.
  useEffect(() => {
    const tg = searchParams.get('tag');
    if (tg) setTag(tg);
  }, [searchParams]);

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

  /* Unfiltered list — only used to count pills honestly (counts come from
     the full set, not the already-filtered one). */
  const allQuery = useQuery({
    queryKey: demo ? ['demo-recommendations-all'] : ['recommendations-all'],
    queryFn: demo ? api.demoRecommendations : () => api.recommendations({}),
    staleTime: 60_000,
  });

  /* Phase 3 — solvability predictions, merged onto the cards by key. */
  const predQuery = useQuery({
    queryKey: demo ? ['demo-ml-predictions'] : ['ml-predictions'],
    queryFn: () => (demo ? api.demoMlPredictions(24) : api.mlPredictions(24)),
    staleTime: 60_000,
    enabled: demo || query.isSuccess,
  });
  const solvByKey = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of predQuery.data?.recommendations ?? []) {
      if (r.solvability !== undefined && r.solvability !== null) {
        m.set(`${r.contest_id}${r.index}`, r.solvability);
      }
    }
    return m;
  }, [predQuery.data]);

  const { tagPills, bandPills } = useMemo(() => {
    const list = allQuery.data ?? [];
    const tagCounts = new Map<string, number>();
    const bandCounts = new Map<string, number>();
    for (const p of list) {
      for (const tg of p.tags) tagCounts.set(tg, (tagCounts.get(tg) ?? 0) + 1);
      if (p.rating !== null) {
        const band = RATING_BANDS.find(
          (b) => p.rating! >= Number(b.min) && (b.max === '' || p.rating! <= Number(b.max)),
        );
        if (band) bandCounts.set(band.id, (bandCounts.get(band.id) ?? 0) + 1);
      }
    }
    const tagPills: PillCount[] = [...tagCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([id, count]) => ({ id, label: id, count }));
    const bandPills: PillCount[] = RATING_BANDS.map((b) => ({
      id: b.id,
      label: b.label,
      count: bandCounts.get(b.id) ?? 0,
    }));
    return { tagPills, bandPills };
  }, [allQuery.data]);

  const activeBand = bandIdFor(minRating, maxRating);
  const activeCount =
    (tag ? 1 : 0) + (minRating || maxRating ? 1 : 0) + (hideSolved ? 0 : 1);

  const applyBand = (bandId: string | null) => {
    if (!bandId) {
      setMinRating('');
      setMaxRating('');
      return;
    }
    const band = RATING_BANDS.find((b) => b.id === bandId);
    if (band) {
      setMinRating(band.min);
      setMaxRating(band.max);
    }
  };

  const clearFilters = () => {
    setTag('');
    setMinRating('');
    setMaxRating('');
    setHideSolved(true);
  };

  const applyView = (v: { tag: string; minRating: string; maxRating: string; hideSolved: boolean }) => {
    setTag(v.tag);
    setMinRating(v.minRating);
    setMaxRating(v.maxRating);
    setHideSolved(v.hideSolved);
  };

  const undoAction = (contest_id: number, index: string) => {
    // 'interested' keeps the problem in the list — it clears later/dismissed.
    void api.recommendationAction(contest_id, index, 'interested');
    setStates((s) => ({ ...s, [`${contest_id}${index}`]: null }));
    void qc.invalidateQueries({ queryKey: ['recommendations'] });
    toast(t.toastUndone);
  };

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
      toast(vars.act === 'later' ? t.toastSavedLater : t.toastNotInterested, {
        action: {
          label: t.undo,
          onClick: () => undoAction(vars.contest_id, vars.index),
        },
      });
    },
  });

  const tags = useMemo(() => {
    const all = new Set<string>();
    (query.data ?? []).forEach((p) => p.tags.forEach((tg) => all.add(tg)));
    return [...all].sort();
  }, [query.data]);

  const canSaveView = tag !== '' || minRating !== '' || maxRating !== '';

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

      <Card>
        <FilterPills
          tags={tagPills}
          activeTag={tag}
          onTag={setTag}
          bands={bandPills}
          activeBand={activeBand}
          onBand={applyBand}
          activeCount={activeCount}
          onClear={clearFilters}
        />
        <div className="mt-4 border-t border-border pt-4">
          <p className="text-xs font-medium text-muted">{t.savedViews}</p>
          {views.length === 0 ? (
            <p className="mt-1 text-sm text-muted">{t.noSavedViews}</p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {views.map((v) => (
                <span
                  key={v.id}
                  className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 py-1 pl-3 pr-1 text-xs"
                >
                  <button
                    type="button"
                    onClick={() => applyView(v)}
                    className="cursor-pointer font-medium text-text hover:text-primary"
                  >
                    {v.name}
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(v.id)}
                    aria-label={t.deleteView}
                    className="flex h-5 w-5 cursor-pointer items-center justify-center rounded-full text-muted hover:bg-hover hover:text-danger"
                  >
                    <X size={12} aria-hidden />
                  </button>
                </span>
              ))}
            </div>
          )}
          {canSaveView && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Input
                value={viewName}
                onChange={(e) => setViewName(e.target.value)}
                placeholder={t.saveViewName}
                aria-label={t.saveViewName}
                className="w-48"
              />
              <Button
                variant="secondary"
                disabled={!viewName.trim()}
                onClick={() => {
                  save({ name: viewName.trim(), tag, minRating, maxRating, hideSolved });
                  setViewName('');
                  toast(t.viewSaved);
                }}
              >
                <Bookmark size={14} aria-hidden /> {t.saveView}
              </Button>
            </div>
          )}
        </div>
      </Card>

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
        <div ref={gridRef} className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {query.data.map((p) => (
            <ProblemCard
              key={`${p.contest_id}${p.index}`}
              problem={p}
              why={p.why}
              score={p.score}
              solvability={solvByKey.get(`${p.contest_id}${p.index}`)}
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
