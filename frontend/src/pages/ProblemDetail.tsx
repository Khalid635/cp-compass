/* Problem Detail — one problem: your attempts, submissions, revision
   status with grade buttons, Save for Later / Not Interested, and a
   personal Markdown note. */
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowUpRight, Bookmark, Check, Eye, Pencil, RefreshCw, X } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { cfUrl, rankOf } from '../api/types';
import { formatDate, formatTimeAgo, useLanguage } from '../i18n';
import { Markdown } from '../components/Markdown';
import { Button, Card, EmptyState, RatingBadge, Skeleton, TagChip } from '../components/ui';

const GRADES = ['again', 'hard', 'good', 'easy'] as const;

export default function ProblemDetail({ demo = false }: { demo?: boolean }) {
  const { t, lang } = useLanguage();
  const qc = useQueryClient();
  const { contestId, index } = useParams<{ contestId: string; index: string }>();
  const cid = Number(contestId ?? 0);
  const idx = index ?? '';

  const query = useQuery({
    queryKey: demo ? ['demo-problem', cid, idx] : ['problem', cid, idx],
    queryFn: demo ? () => api.demoProblemDetail(cid, idx) : () => api.problemDetail(cid, idx),
    enabled: cid > 0 && idx !== '',
    staleTime: 30_000,
  });

  const [noteBody, setNoteBody] = useState('');
  const [preview, setPreview] = useState(false);
  const [noteDirty, setNoteDirty] = useState(false);

  // Seed the editor from the loaded note (once per problem).
  useEffect(() => {
    if (query.data) {
      setNoteBody(query.data.note.body);
      setNoteDirty(false);
    }
  }, [query.data?.note.body]); // eslint-disable-line react-hooks/exhaustive-deps

  const review = useMutation({
    mutationFn: (result: 'again' | 'hard' | 'good' | 'easy') =>
      api.reviewRevision(query.data!.revision!.id, result),
    onSuccess: (_res, result) => {
      toast(t.toastReviewed(result));
      void qc.invalidateQueries({ queryKey: ['problem', cid, idx] });
      void qc.invalidateQueries({ queryKey: ['revisions'] });
    },
  });

  const preference = useMutation({
    mutationFn: (action: 'later' | 'not_interested' | 'interested') =>
      api.recommendationAction(cid, idx, action),
    onSuccess: (_res, action) => {
      toast(action === 'later' ? t.toastSavedLater : t.toastNotInterested);
      void qc.invalidateQueries({ queryKey: ['problem', cid, idx] });
    },
  });

  const saveNote = useMutation({
    mutationFn: () => api.saveNote(cid, idx, noteBody),
    onSuccess: () => {
      toast(t.noteSaved);
      setNoteDirty(false);
      void qc.invalidateQueries({ queryKey: ['problem', cid, idx] });
    },
  });

  if (query.isPending) {
    return (
      <div className="page-enter flex flex-col gap-4">
        <Skeleton className="h-[180px] w-full" />
        <Skeleton className="h-[260px] w-full" />
      </div>
    );
  }

  if (query.isError) {
    const msg = query.error instanceof ApiError ? query.error.message : t.somethingWrong;
    return (
      <Card>
        <EmptyState
          icon={<RefreshCw size={40} aria-hidden />}
          title={msg}
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
  const p = d.problem;
  const rank = rankOf(p.rating);
  const pref = d.preference;

  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">
            {p.contest_id}
            {p.index} — {p.name}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <RatingBadge rating={p.rating} rankName={rank.name} rankColor={rank.token} />
            {p.tags.map((tag) => (
              <TagChip key={tag} tag={tag} />
            ))}
          </div>
        </div>
        <a
          href={cfUrl(p)}
          target="_blank"
          rel="noreferrer"
          className="group inline-flex items-center gap-1 text-sm font-medium text-primary hover:no-underline"
        >
          {t.openOnCf}
          <ArrowUpRight size={14} aria-hidden className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
        </a>
      </div>

      {/* Stats + revision */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card title={t.problemAttempts} className="min-w-0">
          <div className="flex flex-col gap-2 text-sm">
            <p>
              <span className="font-mono text-lg font-semibold">{d.attempts}</span>{' '}
              <span className="text-muted">{t.problemAttempts.toLowerCase()}</span>
            </p>
            <p className={d.solved ? 'text-success' : 'text-muted'}>
              {d.solved ? `✓ ${t.problemSolved}` : t.problemNotSolved}
            </p>
            {d.first_attempt && (
              <p className="text-muted">
                {t.problemFirstAttempt}: {formatTimeAgo(d.first_attempt, t)}
              </p>
            )}
            {d.last_attempt && (
              <p className="text-muted">
                {t.problemLastAttempt}: {formatTimeAgo(d.last_attempt, t)}
              </p>
            )}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant={pref === 'later' ? 'primary' : 'secondary'}
              className="h-8 text-xs"
              disabled={demo}
              onClick={() => preference.mutate('later')}
            >
              <Bookmark size={13} aria-hidden /> {pref === 'later' ? t.savedForLater : t.later}
            </Button>
            <Button
              variant={pref === 'dismissed' ? 'primary' : 'secondary'}
              className="h-8 text-xs"
              disabled={demo}
              onClick={() => preference.mutate('not_interested')}
            >
              <X size={13} aria-hidden /> {t.notInterested}
            </Button>
            {pref !== null && (
              <Button
                variant="ghost"
                className="h-8 text-xs"
                disabled={demo}
                onClick={() => preference.mutate('interested')}
              >
                {t.undo}
              </Button>
            )}
          </div>
          {demo && <p className="mt-3 text-xs text-muted">{t.demoPracticeNote}</p>}
        </Card>

        <Card title={t.revisionStatus} className="min-w-0">
          {d.revision === null ? (
            <p className="py-4 text-center text-sm text-muted">{t.revisionNoRevision}</p>
          ) : (
            <div className="flex flex-col gap-3 text-sm">
              <p>
                {t.lastAttempt(d.wrong_attempts, d.revision.interval_days)}
                {d.revision.last_result ? t.lastReview(d.revision.last_result) : ''}
              </p>
              <p className="text-muted">
                {t.comingUp}: {formatDate(d.revision.due_date, lang)}
              </p>
              <div className="flex flex-wrap gap-2">
                {GRADES.map((g) => (
                  <Button
                    key={g}
                    variant="secondary"
                    className="h-8 text-xs capitalize"
                    disabled={demo || review.isPending}
                    onClick={() => review.mutate(g)}
                  >
                    {t[`review${g[0].toUpperCase()}${g.slice(1)}` as 'reviewAgain' | 'reviewHard' | 'reviewGood' | 'reviewEasy']}
                  </Button>
                ))}
              </div>
              {demo && <p className="text-xs text-muted">{t.demoRevisionNote}</p>}
            </div>
          )}
        </Card>
      </div>

      {/* Submissions */}
      <Card title={t.problemSubmissions} className="min-w-0">
        {d.submissions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">{t.noSubmissionsYet}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="pb-2 pr-3 font-medium">{t.thVerdict}</th>
                  <th className="hidden pb-2 pr-3 font-medium sm:table-cell">{t.thLanguage}</th>
                  <th className="pb-2 font-medium">{t.thTime}</th>
                </tr>
              </thead>
              <tbody>
                {d.submissions.map((s, i) => (
                  <tr key={i} className="border-b border-border/50 last:border-0">
                    <td className={`py-2.5 pr-3 font-medium ${s.verdict === 'OK' ? 'text-success' : 'text-danger'}`}>
                      {s.verdict === 'OK' ? `✓ ${t.verdictAccepted}` : s.verdict}
                    </td>
                    <td className="hidden py-2.5 pr-3 font-mono text-xs text-muted sm:table-cell">
                      {s.language ?? '—'}
                    </td>
                    <td className="py-2.5 text-muted">{formatTimeAgo(s.submitted_at, t)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Notes */}
      <Card
        title={t.problemNotes}
        className="min-w-0"
        action={
          <div className="flex gap-1">
            <Button
              variant={preview ? 'ghost' : 'secondary'}
              className="h-8 px-2.5 text-xs"
              onClick={() => setPreview(false)}
            >
              <Pencil size={13} aria-hidden /> {t.noteEdit}
            </Button>
            <Button
              variant={preview ? 'secondary' : 'ghost'}
              className="h-8 px-2.5 text-xs"
              onClick={() => setPreview(true)}
            >
              <Eye size={13} aria-hidden /> {t.notePreview}
            </Button>
          </div>
        }
      >
        {preview ? (
          noteBody.trim() === '' ? (
            <p className="py-4 text-center text-sm text-muted">{t.noteEmpty}</p>
          ) : (
            <Markdown text={noteBody} />
          )
        ) : (
          <textarea
            value={noteBody}
            onChange={(e) => {
              setNoteBody(e.target.value);
              setNoteDirty(true);
            }}
            placeholder={t.notePlaceholder}
            disabled={demo}
            rows={6}
            className="w-full resize-y rounded-md border border-border bg-surface-2 p-3 text-sm text-text placeholder:text-muted focus:border-ring focus:outline-none disabled:opacity-60"
          />
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            disabled={demo || saveNote.isPending || !noteDirty}
            onClick={() => saveNote.mutate()}
          >
            {saveNote.isPending ? <RefreshCw size={14} className="animate-spin" aria-hidden /> : <Check size={14} aria-hidden />}{' '}
            {t.noteSave}
          </Button>
          {demo && <p className="text-xs text-muted">{t.disabledInDemo}</p>}
        </div>
      </Card>

      <Link to={demo ? '/demo/practice' : '/app/practice'} className="text-sm text-muted">
        ← {t.practice}
      </Link>
    </div>
  );
}
