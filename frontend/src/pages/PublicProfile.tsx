/* Public profile — /u/:handle (Batch 5). No auth: the backend 404s for
   private or unknown handles, and the two cases are deliberately
   indistinguishable here too. */
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Compass } from 'lucide-react';
import { api } from '../api/client';
import { formatTimeAgo, useLanguage } from '../i18n';
import { Button, Card, EmptyState, Skeleton } from '../components/ui';

export default function PublicProfile() {
  const { handle } = useParams<{ handle: string }>();
  const { t } = useLanguage();
  const query = useQuery({
    queryKey: ['public-profile', handle?.toLowerCase()],
    queryFn: () => api.publicProfile(handle ?? ''),
    enabled: !!handle,
    retry: false,
  });
  const data = query.data;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6">
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-2 text-sm text-muted hover:text-text"
      >
        <Compass size={16} aria-hidden /> CP Compass
      </Link>
      {query.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : query.isError || !data ? (
        <EmptyState
          icon={<Compass size={28} aria-hidden />}
          title={t.profilePrivate}
          text={t.profilePrivateHint}
          action={
            <Link to="/register">
              <Button>{t.createAccount}</Button>
            </Link>
          }
        />
      ) : (
        <>
          <h1 className="text-2xl font-bold">{t.profileTitle(data.handle)}</h1>
          {data.rank && <p className="mt-1 text-sm text-muted">{data.rank}</p>}
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card title={t.profileRating}>
              <p className="text-2xl font-bold">{data.current_rating ?? '—'}</p>
            </Card>
            <Card title={t.profileSolved}>
              <p className="text-2xl font-bold">{data.solved}</p>
            </Card>
            <Card title={t.profileAttempted}>
              <p className="text-2xl font-bold">{data.attempted}</p>
            </Card>
            <Card title={t.profileStreak}>
              <p className="text-2xl font-bold">{data.current_streak}</p>
            </Card>
          </div>
          {data.top_tags.length > 0 && (
            <Card title={t.profileTopTags} className="mt-4">
              {data.top_tags.map((tag) => (
                <div key={tag.tag} className="mb-3 last:mb-0">
                  <div className="flex justify-between text-sm">
                    <span>{tag.tag}</span>
                    <span className="text-muted">
                      {tag.solved}/{tag.attempted}
                    </span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.round(tag.acceptance * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </Card>
          )}
          <p className="mt-4 text-xs text-muted">
            {data.last_synced_at
              ? t.profileLastSynced(formatTimeAgo(data.last_synced_at, t))
              : t.profileNeverSynced}
          </p>
        </>
      )}
    </div>
  );
}
