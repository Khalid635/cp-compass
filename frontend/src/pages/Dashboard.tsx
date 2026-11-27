/* Dashboard — 4 StatCards, RatingChart + Today's Plan, TopicRadar + Heatmap,
   Recent submissions. TanStack Query caches data so the Render cold start
   hurts only the first load (skeleton + ColdStartBanner meanwhile). */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { toast } from 'sonner';
import {
  ArrowUpRight,
  CalendarCheck2,
  Check,
  Copy,
  Flame,
  Link2,
  RefreshCw,
  Target,
  Trophy,
} from 'lucide-react';
import { api } from '../api/client';
import { rankOf } from '../api/types';
import { formatWhy, useLanguage } from '../i18n';
import { CumulativeSolved, Heatmap, RatingChart, TopicRadar } from '../components/charts';
import type { ChartRange } from '../components/charts';
import { RecentSubmissions, StatCard } from '../components/cards';
import { GoalRings } from '../components/GoalRings';
import { HudPanel } from '../components/HudPanel';
import { SegmentedScore } from '../components/SegmentedScore';
import { ColdStartBanner } from '../components/layout';
import { Button, Card, EmptyState, RatingBadge, SegmentedControl, Skeleton } from '../components/ui';
import { HandleConnect } from './Auth';

function DashboardSkeleton() {
  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[118px] w-full" />
        ))}
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-12">
        <Skeleton className="h-[320px] w-full lg:col-span-8" />
        <Skeleton className="h-[320px] w-full lg:col-span-4" />
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Skeleton className="h-[300px] w-full" />
        <Skeleton className="h-[300px] w-full" />
      </div>
    </div>
  );
}

export default function Dashboard({ demo = false }: { demo?: boolean }) {
  const { t } = useLanguage();
  const query = useQuery({
    queryKey: demo ? ['demo-dashboard'] : ['dashboard'],
    queryFn: demo ? api.demoDashboard : api.dashboard,
    staleTime: 60_000,
  });
  const [showColdStart, setShowColdStart] = useState(false);
  const [range, setRange] = useState<ChartRange>('day');
  const [heatMode, setHeatMode] = useState<'day' | 'week'>('day');
  const [copied, setCopied] = useState(false);
  const [planRef] = useAutoAnimate<HTMLDivElement>();
  /* Weekly goal progress (Phase 2) — its own small query so the dashboard
     does not wait on it; it renders once the settings call lands. */
  const settingsQuery = useQuery({
    queryKey: demo ? ['demo-settings'] : ['settings'],
    queryFn: demo ? api.demoSettings : api.settings,
    staleTime: 60_000,
  });
  /* Phase 3 — solvability predictions for today's plan. Runs once the
     dashboard says a handle is connected (auth mode); always in demo. */
  const predictionsQuery = useQuery({
    queryKey: demo ? ['demo-ml-predictions'] : ['ml-predictions'],
    queryFn: () => (demo ? api.demoMlPredictions(24) : api.mlPredictions(24)),
    staleTime: 60_000,
    enabled: demo || query.data?.has_handle === true,
  });
  const solvByKey = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of predictionsQuery.data?.recommendations ?? []) {
      if (r.solvability !== undefined && r.solvability !== null) {
        m.set(`${r.contest_id}${r.index}`, r.solvability);
      }
    }
    return m;
  }, [predictionsQuery.data]);

  // ColdStartBanner only if the first load is actually slow (>1.5s).
  useEffect(() => {
    if (!query.isPending) return;
    const tt = setTimeout(() => setShowColdStart(true), 1500);
    return () => clearTimeout(tt);
  }, [query.isPending]);

  if (query.isPending) {
    return (
      <>
        {showColdStart && <ColdStartBanner />}
        <DashboardSkeleton />
      </>
    );
  }

  if (query.isError) {
    return (
      <Card>
        <EmptyState
          icon={<RefreshCw size={40} aria-hidden />}
          title={t.cfNoResponse}
          text={t.cfRetryAuto}
          action={
            <Button onClick={() => void query.refetch()}>
              <RefreshCw size={14} aria-hidden /> {t.retry}
            </Button>
          }
        />
      </Card>
    );
  }

  const d = query.data;

  if (!d.has_handle) {
    return (
      <div className="page-enter">
        <h1 className="mb-4 text-2xl font-semibold tracking-tight">{t.dashboard}</h1>
        <HandleConnect onDone={() => void query.refetch()} />
        <p className="mt-4 text-sm text-muted">{t.connectHandleHint}</p>
      </div>
    );
  }

  const rank = rankOf(d.stats?.rating ?? null);
  const hist = d.rating_history;
  const delta =
    hist.length >= 2 ? hist[hist.length - 1].rating - hist[hist.length - 2].rating : 0;

  /* Copy training plan — weak topics + today's problems + revisions, in the
     active locale. Button flips to "Copied" for 2s + a toast confirms. */
  const copyPlan = async () => {
    const weak = d.tag_strengths.filter((tg) => tg.weak).map((tg) => tg.tag);
    const lines: string[] = [
      `${t.dashboard} — ${d.user.handle ?? ''}`,
      weak.length > 0 ? t.weakRightNow(weak.join(', ')) : '',
      `${t.todaysPlan}:`,
      ...d.today_plan.problems.map(
        (p) => `- ${p.contest_id}${p.index} — ${p.name} (${p.rating ?? '?'}) — ${formatWhy(p.why, t)}`,
      ),
      ...d.today_plan.revisions.map(
        (r) => `- ${t.reviseLabel}: ${r.problem.contest_id}${r.problem.index} — ${r.problem.name}`,
      ),
      `${t.statRating}: ${d.stats?.rating ?? '—'} · ${t.statSolved}: ${d.stats?.solved ?? 0} · ${t.statStreak}: ${d.stats?.streak ?? 0}`,
    ].filter(Boolean);
    const text = lines.join('\n');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    setCopied(true);
    toast(t.toastCopied);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          {t.dashboard}
          {d.user.handle && (
            <span className="ml-3 font-mono text-sm font-medium text-muted">
              {d.user.handle}
            </span>
          )}
        </h1>
        {!d.synced && !demo && (
          <p className="text-sm text-muted">
            {t.noSyncYet}
          </p>
        )}
      </div>

      {/* HUD telemetry strip — ops-style status line, real data only. */}
      <HudPanel
        rating={d.stats?.rating ?? null}
        delta={delta}
        solved={d.stats?.solved ?? 0}
        streak={d.stats?.streak ?? 0}
        revisionsDue={d.stats?.revisions_due ?? 0}
        rankName={rank.name}
        synced={d.synced}
        demo={demo}
        lastContest={t.lastContest}
      />

      {/* Row 1 — stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label={t.statRating}
          value={d.stats?.rating ?? '—'}
          animate
          icon={<Trophy size={16} aria-hidden />}
          delta={
            delta !== 0
              ? { text: `${delta > 0 ? '+' : ''}${delta}`, good: delta > 0 }
              : undefined
          }
          sub={delta !== 0 ? `${rank.name} · ${t.lastContest}` : rank.name}
        />
        <StatCard
          label={t.statSolved}
          value={d.stats?.solved ?? 0}
          animate
          icon={<Target size={16} aria-hidden />}
          sub={t.subSolved}
        />
        <StatCard
          label={t.statStreak}
          value={d.stats?.streak ?? 0}
          animate
          sub={t.subStreak(d.stats?.streak ?? 0)}
          icon={<Flame size={16} aria-hidden />}
        />
        <StatCard
          label={t.statRevisionDue}
          value={d.stats?.revisions_due ?? 0}
          animate
          sub={t.subRevisions}
          icon={<CalendarCheck2 size={16} aria-hidden />}
        />
      </div>

      {/* Weekly goal + insights links (Phase 2) */}
      <div className="grid items-start gap-4 lg:grid-cols-12">
        <Card className="min-w-0 lg:col-span-8">
          {settingsQuery.data ? (
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">
                  {t.weeklyGoal}:{' '}
                  {t.settingsGoalProgress(
                    settingsQuery.data.solved_this_week,
                    settingsQuery.data.weekly_goal,
                  )}
                </p>
                <Link
                  to={demo ? '/demo/settings' : '/app/settings'}
                  className="text-xs font-medium text-primary hover:no-underline"
                >
                  {t.navSettings} →
                </Link>
              </div>
              <SegmentedScore
                pct={Math.round(
                  (settingsQuery.data.solved_this_week /
                    Math.max(1, settingsQuery.data.weekly_goal)) *
                    100,
                )}
                variant="wide"
                label={t.settingsGoalProgress(
                  settingsQuery.data.solved_this_week,
                  settingsQuery.data.weekly_goal,
                )}
              />
              {settingsQuery.data.solved_this_week >= settingsQuery.data.weekly_goal && (
                <p className="text-xs text-success">{t.weeklyGoalDone}</p>
              )}
            </div>
          ) : (
            <Skeleton className="h-[52px] w-full" />
          )}
        </Card>
        <Card title={t.insightsTitle} className="min-w-0 lg:col-span-4">
          <div className="flex flex-col gap-2">
            <Link
              to={demo ? '/demo/analytics' : '/app/analytics'}
              className="text-sm font-medium text-primary hover:no-underline"
            >
              {t.viewAnalytics} →
            </Link>
            <Link
              to={demo ? '/demo/reports/weekly' : '/app/reports/weekly'}
              className="text-sm font-medium text-primary hover:no-underline"
            >
              {t.viewWeeklyReport} →
            </Link>
          </div>
        </Card>
      </div>

      {/* Row 2 — rating chart + today's plan */}
      <div className="grid items-start gap-4 lg:grid-cols-12">
        <Card
          title={t.ratingHistory}
          className="min-w-0 lg:col-span-8"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <SegmentedControl<ChartRange>
                ariaLabel={t.ratingHistory}
                options={[
                  { id: 'day', label: t.rangeDays },
                  { id: 'week', label: t.rangeWeeks },
                  { id: 'month', label: t.rangeMonths },
                ]}
                value={range}
                onChange={setRange}
              />
              {d.stats?.rating !== null && d.stats?.rating !== undefined ? (
                <RatingBadge rating={d.stats.rating} rankName={rank.name} rankColor={rank.token} neutral />
              ) : undefined}
            </div>
          }
        >
          <RatingChart data={d.rating_history} range={range} />
        </Card>
        <Card
          title={t.todaysPlan}
          className="min-w-0 lg:col-span-4"
          action={
            <Button
              variant="ghost"
              className="h-8 shrink-0 whitespace-nowrap px-2 text-xs"
              onClick={() => void copyPlan()}
            >
              {copied ? <Check size={13} aria-hidden /> : <Copy size={13} aria-hidden />}{' '}
              {copied ? t.copied : t.copyPlan}
            </Button>
          }
        >
          {d.today_plan.problems.length === 0 && d.today_plan.revisions.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">{t.nothingPlanned}</p>
          ) : (
            <div ref={planRef} className="flex flex-col gap-3">
              {d.today_plan.problems.map((p) => {
                const solv = solvByKey.get(`${p.contest_id}${p.index}`);
                return (
                <div key={`${p.contest_id}${p.index}`} className="rounded-md border border-border bg-bg p-3">
                  <div className="flex items-start justify-between gap-2">
                    <a
                      href={`https://codeforces.com/problemset/problem/${p.contest_id}/${p.index}`}
                      target="_blank"
                      rel="noreferrer"
                      className="group inline-flex items-center gap-1 text-sm font-medium text-text hover:text-primary hover:no-underline"
                    >
                      {p.contest_id}
                      {p.index} — {p.name}
                      <ArrowUpRight
                        size={13}
                        aria-hidden
                        className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      />
                    </a>
                    <RatingBadge
                      rating={p.rating}
                      rankName={rankOf(p.rating).name}
                      rankColor={rankOf(p.rating).token}
                    />
                  </div>
                  <p className="mt-1 text-xs text-muted">{formatWhy(p.why, t)}</p>
                  {p.score !== undefined && (
                    <p className="mt-1 font-mono text-xs text-muted">{t.recScore(p.score)}</p>
                  )}
                  {solv !== undefined && (
                    <p className="mt-1 font-mono text-xs text-muted">
                      {t.predSolvable(Math.round(solv * 100))}
                    </p>
                  )}
                </div>
                );
              })}
              {d.today_plan.revisions.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-2 rounded-md border border-border bg-bg p-3 text-sm"
                >
                  <Link2 size={14} className="shrink-0 text-muted" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">
                    {t.reviseLabel}: {r.problem.contest_id}
                    {r.problem.index} — {r.problem.name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Row 3 — radar + heatmap */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card title={t.topicStrength} className="min-w-0">
          <TopicRadar tags={d.tag_strengths} />
          {d.tag_strengths.filter((tg) => tg.weak).length > 0 && (
            <p className="mt-2 text-sm text-muted">
              {t.weakRightNow(
                d.tag_strengths
                  .filter((tg) => tg.weak)
                  .map((tg) => tg.tag)
                  .join(', '),
              )}
            </p>
          )}
        </Card>
        <Card
          title={t.dailyActivity}
          className="min-w-0"
          action={
            <SegmentedControl<'day' | 'week'>
              ariaLabel={t.dailyActivity}
              options={[
                { id: 'day', label: t.activityDaily },
                { id: 'week', label: t.activityWeekly },
              ]}
              value={heatMode}
              onChange={setHeatMode}
            />
          }
        >
          <Heatmap
            days={d.heatmap}
            mode={heatMode}
            caption={t.heatAllTime(d.heatmap.reduce((a, day) => a + day.count, 0))}
          />
        </Card>
      </div>

      {/* Cumulative solved curve — full history, step function */}
      <Card title={t.cumulativeTitle} className="min-w-0">
        <CumulativeSolved points={d.cumulative ?? []} />
      </Card>

      {/* Topic goal rings — real acceptance % per top tag, goal 80% */}
      {d.tag_strengths.length > 0 && (
        <Card title={t.topicGoals} className="min-w-0">
          <GoalRings tags={d.tag_strengths} base={demo ? '/demo' : '/app'} />
        </Card>
      )}

      {/* Row 4 — recent submissions */}
      <Card title={t.recentSubmissions} className="min-w-0">
        <RecentSubmissions rows={d.recent} total={d.recent_total ?? d.recent.length} />
      </Card>

      {demo && (
        <p className="text-center text-xs text-muted">{t.demoFootnote}</p>
      )}
    </div>
  );
}
