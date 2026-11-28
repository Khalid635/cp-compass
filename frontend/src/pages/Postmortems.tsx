/* Batch 4 — contest post-mortems: one card per contest with submissions,
most recently active first. Links to the per-contest detail page. */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { History, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { formatDate, useLanguage } from '../i18n';
import { Button, Card, EmptyState, Skeleton } from '../components/ui';

export default function Postmortems({ demo = false }: { demo?: boolean }) {
  const { t, lang } = useLanguage();
  const query = useQuery({
    queryKey: demo ? ['demo-postmortems'] : ['postmortems'],
    queryFn: demo ? api.demoPostmortems : api.postmortems,
    staleTime: 60_000,
  });

  if (query.isPending) {
    return (
      <div className="page-enter flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-[76px] w-full" />
        ))}
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

  const items = query.data;

  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{t.postmortemsTitle}</h1>
      </div>
      {demo && <p className="text-sm text-muted">{t.demoFootnote}</p>}
      {items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<History size={40} aria-hidden />}
            title={t.postmortemNoContests}
            text={t.postmortemNoContestsHint}
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <Link
              key={item.contest_id}
              to={`${demo ? '/demo' : '/app'}/postmortems/${item.contest_id}`}
              className="block"
            >
              <Card className="transition-colors hover:border-primary/50">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">
                      {item.contest_name ?? `Contest ${item.contest_id}`}
                    </p>
                    <p className="text-sm text-muted">
                      {formatDate(item.last_activity, lang)}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span>{t.postmortemSolvedOf(item.solved, item.attempted)}</span>
                    <span className="text-muted">
                      {t.postmortemSubmissions(item.submissions)}
                    </span>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
