/* Dashboard — 4 StatCards, RatingChart + Today's Plan, TopicRadar + Heatmap,
   Recent submissions. TanStack Query caches data so the Render cold start
   hurts only the first load (skeleton + ColdStartBanner meanwhile). */
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  CalendarCheck2,
  Flame,
  Link2,
  RefreshCw,
  Target,
  Trophy,
} from 'lucide-react';
import { api } from '../api/client';
import { rankOf } from '../api/types';
import { Heatmap, RatingChart, TopicRadar } from '../components/charts';
import { RecentSubmissions, StatCard } from '../components/cards';
import { ColdStartBanner } from '../components/layout';
import { Button, Card, EmptyState, RatingBadge, Skeleton } from '../components/ui';
import { HandleConnect } from './Auth';

function DashboardSkeleton() {
  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[118px] w-full" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-12">
        <Skeleton className="h-[320px] w-full lg:col-span-8" />
        <Skeleton className="h-[320px] w-full lg:col-span-4" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-[300px] w-full" />
        <Skeleton className="h-[300px] w-full" />
      </div>
    </div>
  );
}

export default function Dashboard({ demo = false }: { demo?: boolean }) {
  const query = useQuery({
    queryKey: demo ? ['demo-dashboard'] : ['dashboard'],
    queryFn: demo ? api.demoDashboard : api.dashboard,
    staleTime: 60_000,
  });
  const [showColdStart, setShowColdStart] = useState(false);

  // ColdStartBanner only if the first load is actually slow (>1.5s).
  useEffect(() => {
    if (!query.isPending) return;
    const t = setTimeout(() => setShowColdStart(true), 1500);
    return () => clearTimeout(t);
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
          title="Codeforces didn't respond"
          text="We'll retry automatically. If this keeps happening, check your connection and try again."
          action={
            <Button onClick={() => void query.refetch()}>
              <RefreshCw size={14} aria-hidden /> Retry
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
        <h1 className="mb-4 text-2xl font-semibold tracking-tight">Dashboard</h1>
        <HandleConnect onDone={() => void query.refetch()} />
        <p className="mt-4 text-sm text-muted">
          After connecting your handle, press “Sync now” in the top bar to pull
          your submissions.
        </p>
      </div>
    );
  }

  const rank = rankOf(d.stats?.rating ?? null);
  const hist = d.rating_history;
  const delta =
    hist.length >= 2 ? hist[hist.length - 1].rating - hist[hist.length - 2].rating : 0;

  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Dashboard
          {d.user.handle && (
            <span className="ml-3 font-mono text-sm font-medium text-muted">
              {d.user.handle}
            </span>
          )}
        </h1>
        {!d.synced && !demo && (
          <p className="text-sm text-muted">
            No submissions synced yet — press <strong>Sync now</strong> above.
          </p>
        )}
      </div>

      {/* Row 1 — stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Current rating"
          value={d.stats?.rating ?? '—'}
          icon={<Trophy size={16} aria-hidden />}
          delta={
            delta !== 0
              ? { text: `${delta > 0 ? '+' : ''}${delta} last contest`, good: delta > 0 }
              : undefined
          }
          sub={rank.name}
        />
        <StatCard
          label="Total solved"
          value={d.stats?.solved ?? 0}
          icon={<Target size={16} aria-hidden />}
          sub="accepted submissions"
        />
        <StatCard
          label="Streak"
          value={d.stats?.streak ?? 0}
          sub={d.stats?.streak === 1 ? 'day in a row' : 'days in a row'}
          icon={<Flame size={16} aria-hidden />}
        />
        <StatCard
          label="Revision due"
          value={d.stats?.revisions_due ?? 0}
          sub="problems waiting"
          icon={<CalendarCheck2 size={16} aria-hidden />}
        />
      </div>

      {/* Row 2 — rating chart + today's plan */}
      <div className="grid gap-4 lg:grid-cols-12">
        <Card
          title="Rating history"
          className="lg:col-span-8"
          action={
            d.stats?.rating !== null && d.stats?.rating !== undefined ? (
              <RatingBadge rating={d.stats.rating} rankName={rank.name} rankColor={rank.token} />
            ) : undefined
          }
        >
          <RatingChart data={d.rating_history} />
        </Card>
        <Card title="Today's plan" className="lg:col-span-4">
          {d.today_plan.problems.length === 0 && d.today_plan.revisions.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">
              Nothing planned yet — sync your submissions first.
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {d.today_plan.problems.map((p) => (
                <div key={`${p.contest_id}${p.index}`} className="rounded-md border border-border bg-bg p-3">
                  <div className="flex items-start justify-between gap-2">
                    <a
                      href={`https://codeforces.com/problemset/problem/${p.contest_id}/${p.index}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-text hover:text-primary hover:no-underline"
                    >
                      {p.contest_id}
                      {p.index} — {p.name}
                    </a>
                    <RatingBadge
                      rating={p.rating}
                      rankName={rankOf(p.rating).name}
                      rankColor={rankOf(p.rating).token}
                    />
                  </div>
                  <p className="mt-1 text-xs text-muted">{p.why}</p>
                </div>
              ))}
              {d.today_plan.revisions.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-2 rounded-md border border-border bg-bg p-3 text-sm"
                >
                  <Link2 size={14} className="shrink-0 text-muted" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">
                    Revise: {r.problem.contest_id}
                    {r.problem.index} — {r.problem.name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Row 3 — radar + heatmap */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Topic strength — acceptance % by tag">
          <TopicRadar tags={d.tag_strengths} />
          {d.tag_strengths.filter((t) => t.weak).length > 0 && (
            <p className="mt-2 text-sm text-muted">
              Weak right now:{' '}
              {d.tag_strengths
                .filter((t) => t.weak)
                .map((t) => t.tag)
                .join(', ')}
              . Practice picks target these first.
            </p>
          )}
        </Card>
        <Card title="Daily activity — accepted submissions">
          <Heatmap days={d.heatmap} />
        </Card>
      </div>

      {/* Row 4 — recent submissions */}
      <Card title="Recent submissions">
        <RecentSubmissions rows={d.recent} />
      </Card>

      {demo && (
        <p className="text-center text-xs text-muted">
          Demo data — seeded example account. Your own dashboard fills up as you sync.
        </p>
      )}
    </div>
  );
}
