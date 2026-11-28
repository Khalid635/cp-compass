/* Batch 4 — contest post-mortem detail: summary stats, verdict chips,
per-problem table, unsolved + practice-next-week card, weak topics, and
the Gemini-written AI analysis (signed-in only; the demo shows a note). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { FileSearch, RefreshCw, Sparkles } from 'lucide-react';
import { ApiError, api } from '../api/client';
import { cfUrl } from '../api/types';
import { formatDate, useLanguage } from '../i18n';
import { StatCard } from '../components/cards';
import { Button, Card, EmptyState, Skeleton, TagChip } from '../components/ui';

export default function Postmortem({ demo = false }: { demo?: boolean }) {
  const { t, lang } = useLanguage();
  const { contestId } = useParams();
  const cid = Number(contestId);
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: demo ? ['demo-postmortem', cid] : ['postmortem', cid],
    queryFn: demo ? () => api.demoPostmortem(cid) : () => api.postmortem(cid),
    staleTime: 60_000,
  });

  const analysisQuery = useQuery({
    queryKey: ['postmortem-analysis', cid],
    queryFn: () => api.getPostmortemAnalysis(cid),
    enabled: !demo && query.isSuccess,
    staleTime: 60_000,
  });

  const genMut = useMutation({
    mutationFn: () => api.requestPostmortemAnalysis(cid, lang),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['postmortem-analysis', cid] });
    },
  });

  if (query.isPending) {
    return (
      <div className="page-enter flex flex-col gap-4">
        <Skeleton className="h-8 w-72" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[118px] w-full" />
          ))}
        </div>
        <Skeleton className="h-[300px] w-full" />
      </div>
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
  const title = d.contest_name ?? `Contest ${d.contest_id}`;

  if (!d.has_data) {
    return (
      <div className="page-enter flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <Card>
          <EmptyState
            icon={<FileSearch size={40} aria-hidden />}
            title={t.postmortemNoData}
            text={t.postmortemNoDataHint}
          />
        </Card>
      </div>
    );
  }

  const analysis = analysisQuery.data;

  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          {title}
          <span className="ml-3 font-mono text-sm font-medium text-muted">
            {d.first_submission ? formatDate(d.first_submission, lang) : ''}
          </span>
        </h1>
      </div>
      {demo && <p className="text-sm text-muted">{t.demoFootnote}</p>}

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard
          label={t.postmortemSolvedOf(d.solved, d.attempted)}
          value={`${d.solved}/${d.attempted}`}
          animate
        />
        <StatCard
          label={t.postmortemSubmissions(d.total_submissions)}
          value={d.total_submissions}
          animate
        />
        <StatCard
          label={t.postmortemTimeSpent(d.time_spent_minutes ?? 0)}
          value={d.time_spent_minutes != null ? `${d.time_spent_minutes}` : '—'}
          animate
        />
      </div>

      {/* Verdicts */}
      <Card title={t.postmortemVerdicts} className="min-w-0">
        <div className="flex flex-wrap gap-2">
          {d.verdict_breakdown.map((v) => (
            <TagChip key={v.verdict} tag={`${v.verdict} × ${v.count}`} />
          ))}
        </div>
      </Card>

      {/* Per problem */}
      <Card title={t.postmortemPerProblem} className="min-w-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="pb-2 pr-3 font-medium">{t.thProblem}</th>
                <th className="pb-2 pr-3 font-medium">{t.postmortemAttempts}</th>
                <th className="pb-2 pr-3 font-medium">{t.postmortemSolved}</th>
                <th className="pb-2 pr-3 font-medium">{t.postmortemMinutesToSolve}</th>
                <th className="pb-2 font-medium">{t.postmortemVerdicts}</th>
              </tr>
            </thead>
            <tbody>
              {d.per_problem.map((row) => (
                <tr key={`${row.problem.contest_id}${row.problem.index}`} className="border-b border-border/50 last:border-0">
                  <td className="py-2 pr-3">
                    <a
                      href={cfUrl(row.problem)}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-primary hover:underline"
                    >
                      {row.problem.index} — {row.problem.name}
                    </a>
                    <span className="ml-2 text-xs text-muted">
                      {row.problem.rating ?? ''}
                    </span>
                  </td>
                  <td className="py-2 pr-3">{row.attempts}</td>
                  <td className="py-2 pr-3">
                    {row.solved ? t.postmortemSolved : t.postmortemNotSolved}
                  </td>
                  <td className="py-2 pr-3">
                    {row.minutes_to_solve != null ? `${row.minutes_to_solve}` : '—'}
                  </td>
                  <td className="py-2 text-muted">{row.verdicts.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Weak topics + practice next week */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t.postmortemWeakTopics} className="min-w-0">
          {d.weak_topics.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted">{t.weekFocusEmpty}</p>
          ) : (
            <div className="flex flex-col gap-2">
              {d.weak_topics.map((wt) => (
                <div key={wt.tag} className="flex items-center justify-between gap-2 text-sm">
                  <TagChip tag={wt.tag} />
                  <span className="text-muted">
                    {wt.solved}/{wt.attempted} · {Math.round(wt.acceptance * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title={t.postmortemPracticeNext} className="min-w-0">
          {d.practice_next_week.topics.length === 0 &&
          d.practice_next_week.problems.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted">{t.weekFocusEmpty}</p>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-2">
                {d.practice_next_week.topics.map((tag) => (
                  <TagChip key={tag} tag={tag} />
                ))}
              </div>
              {d.practice_next_week.problems.length > 0 && (
                <div className="flex flex-col gap-1 text-sm">
                  <p className="text-xs font-medium text-muted">{t.postmortemUnsolved}</p>
                  {d.practice_next_week.problems.map((p) => (
                    <a
                      key={`${p.contest_id}${p.index}`}
                      href={cfUrl(p)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary hover:underline"
                    >
                      {p.index} — {p.name}
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* AI analysis */}
      <Card title={t.postmortemAnalysisTitle} className="min-w-0">
        {demo ? (
          <p className="py-4 text-center text-sm text-muted">{t.postmortemDemoNote}</p>
        ) : analysisQuery.isPending ? (
          <Skeleton className="h-[120px] w-full" />
        ) : analysisQuery.isError ? (
          <p className="py-4 text-center text-sm text-muted">{t.postmortemUnavailable}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-xs text-muted">{t.postmortemNeverSolution}</p>
            {!analysis?.configured && (
              <p className="text-sm text-muted">{t.postmortemNotConfigured}</p>
            )}
            {analysis?.analysis && (
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {analysis.analysis}
              </p>
            )}
            <p className="text-xs text-muted">
              {analysis
                ? t.postmortemUsedToday(analysis.used_today, analysis.limit)
                : ''}
            </p>
            <div>
              <Button
                onClick={() => genMut.mutate()}
                disabled={
                  !analysis?.configured ||
                  genMut.isPending ||
                  (analysis != null && analysis.used_today >= analysis.limit)
                }
              >
                <Sparkles size={15} aria-hidden />{' '}
                {genMut.isPending ? t.postmortemGenerating : t.postmortemGenerate}
              </Button>
            </div>
            {genMut.isError && (
              <p className="text-sm text-red-500">
                {genMut.error instanceof ApiError
                  ? genMut.error.status === 503
                    ? t.postmortemNotConfigured
                    : genMut.error.status === 502
                      ? t.postmortemUnavailable
                      : genMut.error.status === 429
                        ? t.postmortemLimitReached
                        : genMut.error.message
                  : String(genMut.error)}
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
