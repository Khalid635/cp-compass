/* Analytics — peak rating, streaks, difficulty distribution (solved vs
   attempted per rating bucket), topic strength, milestones and contest
   auto-analysis. All numbers come from the user's own synced data. */
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ArrowDownRight, ArrowUpRight, Award, CheckCircle2, Flame, RefreshCw, TrendingUp, Trophy } from 'lucide-react';
import { api } from '../api/client';
import { rankOf, trainedOnLabel } from '../api/types';
import { formatDateTime, useLanguage } from '../i18n';
import { TopicRadar } from '../components/charts';
import { StatCard } from '../components/cards';
import { Button, Card, EmptyState, RatingBadge, Skeleton, TagChip } from '../components/ui';

function AnalyticsSkeleton() {
  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[118px] w-full" />
        ))}
      </div>
      <Skeleton className="h-[300px] w-full" />
      <Skeleton className="h-[300px] w-full" />
    </div>
  );
}

export default function Analytics({ demo = false }: { demo?: boolean }) {
  const { t, lang } = useLanguage();
  const query = useQuery({
    queryKey: demo ? ['demo-analytics'] : ['analytics'],
    queryFn: demo ? api.demoAnalytics : api.analytics,
    staleTime: 60_000,
  });
  /* Phase 3 — prediction model status + evaluation (read-only here;
     retraining lives in Settings). */
  const mlQuery = useQuery({
    queryKey: demo ? ['demo-ml-status'] : ['ml-status'],
    queryFn: demo ? api.demoMlStatus : api.mlStatus,
    staleTime: 60_000,
  });
  /* Batch 2 — failure patterns: where the user's solutions fail. */
  const failQuery = useQuery({
    queryKey: demo ? ['demo-failures'] : ['failures'],
    queryFn: demo ? api.demoFailurePatterns : api.failurePatterns,
    staleTime: 60_000,
  });

  const bucketChart = useMemo(() => {
    const data = query.data?.buckets ?? [];
    return data.map((b) => ({
      bucket: b.bucket,
      solved: b.solved,
      attempted: b.attempted,
      acceptance: Math.round(b.acceptance * 100),
    }));
  }, [query.data]);

  if (query.isPending) return <AnalyticsSkeleton />;

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
  const rank = rankOf(d.current_rating);
  const peakRank = rankOf(d.peak_rating);

  return (
    <div className="page-enter flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">{t.analyticsTitle}</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label={t.statRating}
          value={d.current_rating ?? '—'}
          animate
          icon={<Trophy size={16} aria-hidden />}
          sub={d.current_rating !== null ? rank.name : undefined}
        />
        <StatCard
          label={t.statPeakRating}
          value={d.peak_rating ?? '—'}
          animate
          icon={<TrendingUp size={16} aria-hidden />}
          sub={d.peak_rating !== null ? peakRank.name : undefined}
        />
        <StatCard
          label={t.statStreak}
          value={d.streak}
          animate
          icon={<Flame size={16} aria-hidden />}
          sub={t.subStreak(d.streak)}
        />
        <StatCard
          label={t.statLongestStreak}
          value={d.longest_streak}
          animate
          icon={<Award size={16} aria-hidden />}
          sub={t.subStreak(d.longest_streak)}
        />
      </div>

      {/* Difficulty distribution */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card title={t.difficultyDist} className="min-w-0">
          {bucketChart.every((b) => b.attempted === 0) ? (
            <p className="py-8 text-center text-sm text-muted">{t.noTagData}</p>
          ) : (
            <div className="h-64 w-full min-w-0" role="img" aria-label={t.difficultyDist}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bucketChart} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="bucket"
                    tick={{ fill: 'var(--muted)', fontSize: 12 }}
                    tickLine={false}
                    axisLine={{ stroke: 'var(--border)' }}
                  />
                  <YAxis
                    tick={{ fill: 'var(--muted)', fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload || payload.length === 0) return null;
                      const row = bucketChart.find((b) => b.bucket === label);
                      return (
                        <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-lg">
                          <div className="font-medium text-text">{label}</div>
                          <div className="font-mono text-muted">
                            {row?.solved}/{row?.attempted} · {row?.acceptance}%
                          </div>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="solved" fill="var(--primary)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="attempted" fill="var(--gold-bar)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-primary" /> {t.statSolved}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-gold-bar" /> {t.problemAttempts}
            </span>
          </div>
        </Card>

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
      </div>

      {/* Difficulty success table */}
      <Card title={t.difficultySuccess} className="min-w-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="pb-2 pr-3 font-medium">{t.filterRatingBand}</th>
                <th className="pb-2 pr-3 font-medium">{t.statSolved}</th>
                <th className="pb-2 pr-3 font-medium">{t.problemAttempts}</th>
                <th className="pb-2 font-medium">{t.weekAcceptance}</th>
              </tr>
            </thead>
            <tbody>
              {d.buckets.map((b) => (
                <tr key={b.bucket} className="border-b border-border/50 last:border-0">
                  <td className="py-2.5 pr-3 font-mono">{b.bucket}</td>
                  <td className="py-2.5 pr-3 font-mono">{b.solved}</td>
                  <td className="py-2.5 pr-3 font-mono">{b.attempted}</td>
                  <td className="py-2.5">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className="inline-block h-2 rounded-full"
                        style={{
                          width: `${Math.round(b.acceptance * 100)}px`,
                          maxWidth: '100px',
                          background: b.acceptance < 0.5 ? 'var(--danger)' : 'var(--primary)',
                        }}
                      />
                      <span className="font-mono">{Math.round(b.acceptance * 100)}%</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Batch 2 — failure patterns */}
      <Card title={t.failTitle} className="min-w-0">
        {failQuery.isPending ? (
          <Skeleton className="h-[180px] w-full" />
        ) : failQuery.isError ? (
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">{t.cfRetryAutoShort}</p>
            <Button variant="secondary" onClick={() => void failQuery.refetch()}>
              <RefreshCw size={14} aria-hidden /> {t.retry}
            </Button>
          </div>
        ) : failQuery.data.total_submissions === 0 ? (
          <EmptyState
            icon={<RefreshCw size={40} aria-hidden />}
            title={t.failNoSubs}
            text={t.failNoSubsHint}
          />
        ) : failQuery.data.total_wrong === 0 ? (
          <EmptyState
            icon={<CheckCircle2 size={40} aria-hidden />}
            title={t.failNoWrong}
            text={t.failNoWrongHint}
          />
        ) : (
          <div className="flex flex-col gap-5">
            <p className="text-xs text-muted">
              {t.failBasedOn(failQuery.data.total_wrong, failQuery.data.total_submissions)}
            </p>
            {!failQuery.data.enough_data && (
              <p className="text-sm text-muted">{t.failLowData}</p>
            )}
            {failQuery.data.without_test_data > 0 && (
              <p className="text-sm text-muted">{t.failNoTestData}</p>
            )}

            {/* Verdict breakdown */}
            <div>
              <h3 className="text-sm font-medium">{t.failVerdicts}</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {failQuery.data.verdict_breakdown.map((b) => (
                  <span
                    key={b.verdict}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg px-2.5 py-1 font-mono text-xs"
                  >
                    {b.verdict}
                    <span className="font-semibold text-text">{b.count}</span>
                  </span>
                ))}
              </div>
            </div>

            {/* Last 30 days */}
            <div>
              <h3 className="text-sm font-medium">{t.failRecentTitle}</h3>
              {failQuery.data.recent.total_wrong === 0 ? (
                <p className="mt-1.5 text-sm text-muted">{t.failRecentNone}</p>
              ) : (
                <div className="mt-2 flex flex-col gap-2">
                  <p className="text-sm text-muted">
                    {t.failRecentLine(failQuery.data.recent.total_wrong)}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {failQuery.data.recent.verdict_breakdown.map((b) => (
                      <span
                        key={b.verdict}
                        className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg px-2.5 py-1 font-mono text-xs"
                      >
                        {b.verdict}
                        <span className="font-semibold text-text">{b.count}</span>
                      </span>
                    ))}
                  </div>
                  {failQuery.data.recent.top_topics.length > 0 && (
                    <p className="text-sm text-muted">
                      {failQuery.data.recent.top_topics
                        .map((tp) => t.failRecentTopic(tp.tag, tp.wrong))
                        .join(' \u00b7 ')}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Where solutions fail */}
            <div>
              <h3 className="text-sm font-medium">{t.failStages}</h3>
              <div className="mt-2 flex flex-col gap-2">
                {(
                  [
                    [t.failStageEarly, failQuery.data.test_stages.early],
                    [t.failStageMiddle, failQuery.data.test_stages.middle],
                    [t.failStageLate, failQuery.data.test_stages.late],
                    [t.failStageUnknown, failQuery.data.test_stages.unknown],
                  ] as [string, number][]
                ).map(([label, count]) => (
                  <div key={label} className="flex items-center gap-3 text-sm">
                    <span className="w-44 shrink-0 truncate text-muted">{label}</span>
                    <span
                      className="inline-block h-2 rounded-full bg-primary"
                      style={{
                        width: `${Math.round(
                          (count / Math.max(failQuery.data!.total_wrong, 1)) * 120,
                        )}px`,
                        maxWidth: '120px',
                        minWidth: count > 0 ? '6px' : '0',
                      }}
                    />
                    <span className="font-mono">{count}</span>
                  </div>
                ))}
              </div>
              {(() => {
                const s = failQuery.data.test_stages;
                const known = s.early + s.middle + s.late;
                if (known > 0 && s.early / known >= 0.6) return <p className="mt-2 text-sm text-muted">{t.failEarlyHint}</p>;
                if (known > 0 && s.late / known >= 0.6) return <p className="mt-2 text-sm text-muted">{t.failLateHint}</p>;
                return null;
              })()}
            </div>

            {/* Per-topic patterns */}
            {failQuery.data.per_topic.length > 0 && (
              <div>
                <h3 className="text-sm font-medium">{t.failTopics}</h3>
                <div className="mt-2 flex flex-col gap-3">
                  {failQuery.data.per_topic.slice(0, 5).map((tp) => (
                    <div key={tp.tag} className="rounded-lg border border-border bg-bg p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <TagChip tag={tp.tag} />
                        <span className="font-mono text-xs text-muted">
                          {t.failWrongAttempts(tp.wrong)}
                        </span>
                        {tp.median_passed !== null && (
                          <span className="font-mono text-xs text-muted">
                            · {t.failTopicMedian(tp.median_passed)}
                          </span>
                        )}
                      </div>
                      <p className="mt-1.5 text-sm text-muted">
                        {tp.signal === 'early' && tp.early_share !== null
                          ? t.failTopicEarly(Math.round(tp.early_share * 100))
                          : tp.signal === 'late' && tp.late_share !== null
                            ? t.failTopicLate(Math.round(tp.late_share * 100))
                            : tp.signal === 'mixed'
                              ? t.failTopicMixed
                              : t.failTopicThin(tp.wrong)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Problems with the most wrong attempts */}
            {failQuery.data.per_problem.length > 0 && (
              <div>
                <h3 className="text-sm font-medium">{t.failProblems}</h3>
                <div className="mt-2 flex flex-col gap-2">
                  {failQuery.data.per_problem.map((pp) => (
                    <Link
                      key={`${pp.problem.contest_id}${pp.problem.index}`}
                      to={`${demo ? '/demo' : '/app'}/problems/${pp.problem.contest_id}/${pp.problem.index}`}
                      className="flex flex-col gap-0.5 rounded-lg border border-border bg-bg p-3 text-text hover:border-primary/50 hover:no-underline sm:flex-row sm:items-center sm:justify-between"
                    >
                      <span className="min-w-0 truncate text-sm font-medium">
                        {pp.problem.contest_id}
                        {pp.problem.index} — {pp.problem.name}
                      </span>
                      <span className="shrink-0 font-mono text-xs text-muted">
                        {t.failWrongAttempts(pp.wrong_attempts)} ·{' '}
                        {pp.median_passed !== null ? t.failTopicMedian(pp.median_passed) : '—'}{' '}
                        · {pp.solved ? t.problemSolved : t.failUnsolved}
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Wrong attempts before first AC */}
            <div>
              <h3 className="text-sm font-medium">{t.failAcTitle}</h3>
              <p className="mt-1.5 text-sm text-muted">
                {t.failAcBuckets(
                  failQuery.data.wrong_before_first_ac.zero,
                  failQuery.data.wrong_before_first_ac.one_two,
                  failQuery.data.wrong_before_first_ac.three_plus,
                )}
              </p>
              {failQuery.data.wrong_before_first_ac.median !== null && (
                <p className="mt-1 text-sm text-muted">
                  {t.failAcMedian(failQuery.data.wrong_before_first_ac.median)}
                </p>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* Milestones */}
      <Card title={t.milestonesTitle} className="min-w-0">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {d.milestones.map((m) => (
            <div
              key={m.threshold}
              className={`rounded-lg border p-4 text-center ${
                m.unlocked ? 'border-primary/50 bg-primary/5' : 'border-border bg-bg'
              }`}
            >
              <Trophy
                size={22}
                aria-hidden
                className={`mx-auto ${m.unlocked ? 'text-primary' : 'text-muted'}`}
              />
              <p className="mt-2 font-mono text-lg font-semibold">{m.threshold}</p>
              <p className="text-xs text-muted">{t.statSolved}</p>
              <p className={`mt-1 text-xs font-medium ${m.unlocked ? 'text-primary' : 'text-muted'}`}>
                {m.unlocked ? t.milestoneUnlocked : t.milestoneLocked(m.threshold - m.solved)}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {/* Contest auto-analysis */}
      <Card title={t.contestsTitle} className="min-w-0">
        {d.contests.length === 0 ? (
          <EmptyState
            icon={<Trophy size={40} aria-hidden />}
            title={t.noContests}
            text={t.noContestsHint}
          />
        ) : (
          <div className="flex flex-col gap-3">
            {d.contests.slice(0, 8).map((c) => (
              <div
                key={c.contest_id}
                className="flex flex-col gap-2 rounded-lg border border-border bg-bg p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{c.contest_name}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {c.date} · {t.contestSolvedDay(c.solved_that_day, c.attempted_that_day)}
                  </p>
                  {c.weak_tags_that_day.length > 0 && (
                    <p className="mt-1.5 flex flex-wrap items-center gap-1 text-xs text-muted">
                      {t.contestWeakTags}:
                      {c.weak_tags_that_day.map((tag) => (
                        <TagChip key={tag} tag={tag} weak />
                      ))}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <RatingBadge
                    rating={c.new_rating}
                    rankName={rankOf(c.new_rating).name}
                    rankColor={rankOf(c.new_rating).token}
                  />
                  {c.delta === null ? (
                    <span className="font-mono text-xs text-muted">{t.contestFirst}</span>
                  ) : (
                    <span
                      className={`inline-flex items-center gap-0.5 font-mono text-sm font-semibold ${
                        c.delta >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      {c.delta >= 0 ? (
                        <ArrowUpRight size={15} aria-hidden />
                      ) : (
                        <ArrowDownRight size={15} aria-hidden />
                      )}
                      {c.delta > 0 ? '+' : ''}
                      {c.delta}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>


      {/* Phase 3 — how predictions work */}
      <Card title={t.predTitle} className="min-w-0">
        {mlQuery.isPending ? (
          <Skeleton className="h-[120px] w-full" />
        ) : mlQuery.isError ? (
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">{t.cfRetryAutoShort}</p>
            <Button variant="secondary" onClick={() => void mlQuery.refetch()}>
              <RefreshCw size={14} aria-hidden /> {t.retry}
            </Button>
          </div>
        ) : !mlQuery.data?.trained ? (
          <p className="text-sm text-muted">{t.predNotTrained}</p>
        ) : !mlQuery.data.shipped ? (
          <p className="text-sm text-muted">{t.predNotShipped}</p>
        ) : (
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">{t.predModel}</dt>
              <dd className="font-medium">{mlQuery.data.model_type}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">{t.predTrainedOn}</dt>
              <dd className="font-medium">
                {mlQuery.data.trained_at
                  ? formatDateTime(mlQuery.data.trained_at, lang)
                  : '—'}{' '}
                · {trainedOnLabel(mlQuery.data, t)}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">{t.predData}</dt>
              <dd className="font-mono font-medium">
                {t.predRows(mlQuery.data.n_rows ?? 0, mlQuery.data.n_solved ?? 0)}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">{t.predTestAuc}</dt>
              <dd className="font-mono font-medium">
                {mlQuery.data.evaluation?.random_forest.test_auc ?? '—'} · {t.predBaselineAuc}{' '}
                {mlQuery.data.evaluation?.baseline.auc ?? '—'}
              </dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted">{t.predFeatures}</dt>
              <dd className="font-mono text-xs text-muted">
                {(mlQuery.data.features ?? []).join(', ')}
              </dd>
            </div>
            <p className="mt-1 text-sm text-muted">{t.predBias}</p>
          </dl>
        )}
      </Card>
      {demo && <p className="text-center text-xs text-muted">{t.demoFootnote}</p>}
    </div>
  );
}
