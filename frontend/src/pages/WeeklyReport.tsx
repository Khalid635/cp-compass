/* Weekly report — this week's solved/attempted/acceptance, weak-topic
   movement vs last week, most-practiced tags, next week's focus, and the
   archive of past weeks. Export downloads the report as JSON. */
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ArrowDownRight, ArrowUpRight, Download, Minus, RefreshCw, Target } from 'lucide-react';
import { api } from '../api/client';
import { useLanguage } from '../i18n';
import { StatCard } from '../components/cards';
import { Button, Card, EmptyState, Skeleton, TagChip } from '../components/ui';

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function WeeklyReport({ demo = false }: { demo?: boolean }) {
  const { t } = useLanguage();
  const query = useQuery({
    queryKey: demo ? ['demo-weekly-report'] : ['weekly-report'],
    queryFn: demo ? api.demoWeeklyReport : api.weeklyReport,
    staleTime: 60_000,
  });

  if (query.isPending) {
    return (
      <div className="page-enter flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
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
  const solvedDelta = d.current.solved - d.previous.solved;
  const accDelta = Math.round((d.current.acceptance - d.previous.acceptance) * 100);

  const exportReport = () => {
    downloadJson(`rung-weekly-${d.current.week_start}.json`, d);
    toast(t.weeklyExported);
  };

  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          {t.weeklyTitle}
          <span className="ml-3 font-mono text-sm font-medium text-muted">
            {d.current.week_start}
          </span>
        </h1>
        <Button variant="secondary" onClick={exportReport} disabled={demo}>
          <Download size={15} aria-hidden /> {t.weeklyExport}
        </Button>
      </div>
      {demo && (
        <p className="text-sm text-muted">{t.demoFootnote}</p>
      )}

      {/* Week stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label={t.weekSolved}
          value={d.current.solved}
          animate
          delta={{ text: t.weekVsLast(solvedDelta), good: solvedDelta >= 0 }}
        />
        <StatCard label={t.weekAttempted} value={d.current.attempted} animate />
        <StatCard
          label={t.weekAcceptance}
          value={`${Math.round(d.current.acceptance * 100)}%`}
          animate
          delta={{ text: t.weekVsLast(accDelta), good: accDelta >= 0 }}
        />
        <StatCard
          label={t.weekFocus}
          value={d.focus.length > 0 ? d.focus[0] : '—'}
          sub={d.focus.length > 1 ? d.focus.slice(1).join(', ') : undefined}
        />
      </div>

      {/* Weak-topic movement */}
      <Card title={t.weakMovement} className="min-w-0">
        {d.weak_movement.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">{t.weekFocusEmpty}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="pb-2 pr-3 font-medium">{t.filterTag}</th>
                  <th className="pb-2 pr-3 font-medium">{t.weekAcceptance}</th>
                  <th className="pb-2 font-medium">Δ</th>
                </tr>
              </thead>
              <tbody>
                {d.weak_movement.map((m) => (
                  <tr key={m.tag} className="border-b border-border/50 last:border-0">
                    <td className="py-2.5 pr-3">
                      <TagChip tag={m.tag} weak />
                    </td>
                    <td className="py-2.5 pr-3 font-mono">
                      {m.this_week !== null ? `${Math.round(m.this_week * 100)}%` : '—'}
                      {m.last_week !== null && (
                        <span className="text-muted"> ← {Math.round(m.last_week * 100)}%</span>
                      )}
                    </td>
                    <td className="py-2.5">
                      {m.delta === null ? (
                        <span className="inline-flex items-center gap-1 text-xs text-muted">
                          <Minus size={13} aria-hidden /> {t.movementNoData}
                        </span>
                      ) : (
                        <span
                          className={`inline-flex items-center gap-1 font-mono text-sm font-semibold ${
                            m.delta >= 0 ? 'text-success' : 'text-danger'
                          }`}
                        >
                          {m.delta >= 0 ? (
                            <ArrowUpRight size={15} aria-hidden />
                          ) : (
                            <ArrowDownRight size={15} aria-hidden />
                          )}
                          {m.delta > 0 ? '+' : ''}
                          {Math.round(m.delta * 100)}%
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Most practiced tags + focus */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card title={t.weekTopTags} className="min-w-0">
          {d.top_tags.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">{t.noActivityYet}</p>
          ) : (
            <div className="flex flex-col gap-2">
              {d.top_tags.map((tg) => (
                <div key={tg.tag} className="flex items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-medium">{tg.tag}</span>
                  <span className="shrink-0 font-mono text-xs text-muted">
                    {tg.solved}/{tg.attempted} · {Math.round(tg.acceptance * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title={t.weekFocus} className="min-w-0">
          {d.focus.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">{t.weekFocusEmpty}</p>
          ) : (
            <div className="flex flex-col gap-2">
              {d.focus.map((tag) => (
                <div
                  key={tag}
                  className="flex items-center gap-2 rounded-md border border-border bg-bg p-3 text-sm"
                >
                  <Target size={15} aria-hidden className="shrink-0 text-primary" />
                  <span className="font-medium">{tag}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Archive */}
      <Card title={t.weeklyArchive} className="min-w-0">
        {d.archive.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">{t.noActivityYet}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="pb-2 pr-3 font-medium">{t.weeklyTitle}</th>
                  <th className="pb-2 pr-3 font-medium">{t.weekSolved}</th>
                  <th className="pb-2 pr-3 font-medium">{t.weekAttempted}</th>
                  <th className="pb-2 font-medium">{t.weekAcceptance}</th>
                </tr>
              </thead>
              <tbody>
                {d.archive.map((w) => (
                  <tr key={w.week_start} className="border-b border-border/50 last:border-0">
                    <td className="py-2.5 pr-3 font-mono">{w.week_start}</td>
                    <td className="py-2.5 pr-3 font-mono">{w.solved}</td>
                    <td className="py-2.5 pr-3 font-mono">{w.attempted}</td>
                    <td className="py-2.5 font-mono">{Math.round(w.acceptance * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
