/* Friend compare — /app/compare (Batch 5, auth required). Side A is the
   signed-in user's own dashboard stats; side B is any handle resolved
   through the public profile endpoint (the friend must have opted in).
   No new backend endpoint. */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Users } from 'lucide-react';
import { api } from '../api/client';
import { useLanguage } from '../i18n';
import { Button, Card, EmptyState, Input, Skeleton } from '../components/ui';

function barWidth(value: number | null, max: number) {
  const v = value ?? 0;
  return Math.max(0, Math.min(100, (v / Math.max(1, max)) * 100));
}

export default function Compare() {
  const { t } = useLanguage();
  const [input, setInput] = useState('');
  const [handle, setHandle] = useState('');
  const mine = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard });
  const theirs = useQuery({
    queryKey: ['public-profile', handle.toLowerCase()],
    queryFn: () => api.publicProfile(handle),
    enabled: handle !== '',
    retry: false,
  });
  const a = mine.data;
  const b = theirs.data ?? null;
  const rows = [
    { label: t.profileRating, av: a?.stats?.rating ?? null, bv: b?.current_rating ?? null },
    { label: t.profileSolved, av: a?.stats?.solved ?? null, bv: b?.solved ?? null },
    { label: t.profileAttempted, av: a?.recent_total ?? null, bv: b?.attempted ?? null },
    { label: t.profileStreak, av: a?.stats?.streak ?? null, bv: b?.current_streak ?? null },
  ];
  const aTags = [...(a?.tag_strengths ?? [])]
    .sort((x, y) => y.solved - x.solved)
    .slice(0, 5);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6">
      <h1 className="text-2xl font-bold">{t.compareTitle}</h1>
      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setHandle(input.trim());
        }}
      >
        <Input
          className="flex-1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t.comparePlaceholder}
          aria-label={t.comparePlaceholder}
        />
        <Button type="submit">{t.compareButton}</Button>
      </form>

      {handle === '' ? (
        <p className="mt-6 text-sm text-muted">{t.compareEnterHandle}</p>
      ) : theirs.isPending || mine.isPending ? (
        <Skeleton className="mt-6 h-64 w-full" />
      ) : theirs.isError || !b ? (
        <EmptyState
          icon={<Users size={28} aria-hidden />}
          title={t.compareNotPublic(handle)}
          text={t.profilePrivateHint}
        />
      ) : (
        <>
          <Card
            title={`${t.compareYou} ${t.compareVs} ${b.handle}`}
            className="mt-6"
          >
            {rows.map((row) => {
              const max = Math.max(1, row.av ?? 0, row.bv ?? 0);
              return (
                <div key={row.label} className="mb-5 last:mb-0">
                  <p className="mb-2 text-sm font-medium">{row.label}</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-muted">{t.compareYou}</p>
                      <p className="text-lg font-bold">{row.av ?? '—'}</p>
                      <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-2">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${barWidth(row.av, max)}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-muted">{b.handle}</p>
                      <p className="text-lg font-bold">{row.bv ?? '—'}</p>
                      <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-2">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${barWidth(row.bv, max)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </Card>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Card title={`${t.compareYou} — ${t.profileTopTags}`}>
              {aTags.length === 0 ? (
                <p className="text-sm text-muted">—</p>
              ) : (
                aTags.map((tg) => (
                  <p key={tg.tag} className="mb-2 flex justify-between text-sm last:mb-0">
                    <span>{tg.tag}</span>
                    <span className="text-muted">{tg.solved}</span>
                  </p>
                ))
              )}
            </Card>
            <Card title={`${b.handle} — ${t.profileTopTags}`}>
              {b.top_tags.length === 0 ? (
                <p className="text-sm text-muted">—</p>
              ) : (
                b.top_tags.map((tg) => (
                  <p key={tg.tag} className="mb-2 flex justify-between text-sm last:mb-0">
                    <span>{tg.tag}</span>
                    <span className="text-muted">{tg.solved}</span>
                  </p>
                ))
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
