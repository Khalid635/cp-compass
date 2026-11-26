/* Settings — account (handle connect/disconnect), weekly practice goal,
   appearance (language + theme), data export, account deletion. In demo
   mode everything is read-only and says so. */
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Download, LogOut, RefreshCw, Trash2, Unlink } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { Theme } from '../hooks/useTheme';
import { LanguageToggle, useLanguage } from '../i18n';
import { HandleConnect } from './Auth';
import { Button, Card, EmptyState, Input, Skeleton } from '../components/ui';

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

export default function Settings({
  demo = false,
  theme,
  toggleTheme,
}: {
  demo?: boolean;
  theme: Theme;
  toggleTheme: () => void;
}) {
  const { t } = useLanguage();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { logout, refresh } = useAuth();
  const [goal, setGoalInput] = useState('5');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const query = useQuery({
    queryKey: demo ? ['demo-settings'] : ['settings'],
    queryFn: demo ? api.demoSettings : api.settings,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (query.data) setGoalInput(String(query.data.weekly_goal));
  }, [query.data?.weekly_goal]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveGoal = useMutation({
    mutationFn: () => api.setGoal(Number(goal)),
    onSuccess: (data) => {
      toast(t.settingsGoalSaved);
      setGoalInput(String(data.weekly_goal));
      void qc.invalidateQueries({ queryKey: ['settings'] });
      void qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const disconnect = useMutation({
    mutationFn: api.disconnectHandle,
    onSuccess: () => {
      toast(t.settingsDisconnected);
      setConfirmDisconnect(false);
      void refresh();
      void qc.invalidateQueries({ queryKey: ['settings'] });
      void qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const exportData = useMutation({
    mutationFn: demo ? api.demoExport : api.exportData,
    onSuccess: (data) => {
      downloadJson(`cp-compass-export-${new Date().toISOString().slice(0, 10)}.json`, data);
      toast(t.settingsExported);
    },
  });

  const deleteAccount = useMutation({
    mutationFn: api.deleteAccount,
    onSuccess: () => {
      logout();
      navigate('/');
    },
  });

  if (query.isPending) {
    return (
      <div className="page-enter flex flex-col gap-4">
        <Skeleton className="h-[200px] w-full" />
        <Skeleton className="h-[160px] w-full" />
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

  const s = query.data;
  const goalNum = Number(goal);
  const goalValid = Number.isInteger(goalNum) && goalNum >= 1 && goalNum <= 50;
  const goalPct = Math.min(100, Math.round((s.solved_this_week / Math.max(1, s.weekly_goal)) * 100));

  return (
    <div className="page-enter flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">{t.settingsTitle}</h1>
      {demo && (
        <p className="rounded-md border border-primary/40 bg-primary/5 px-3 py-2 text-sm text-muted">
          {t.settingsDemoNote}
        </p>
      )}

      {/* Account */}
      <Card title={t.settingsAccount} className="min-w-0">
        <dl className="flex flex-col gap-2 text-sm">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted">{t.email}</dt>
            <dd className="font-medium">{s.email ?? t.settingsDemoAccount}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted">{t.settingsHandle}</dt>
            <dd className="font-mono font-medium">{s.cf_handle ?? '—'}</dd>
          </div>
          {s.rank && (
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">{t.settingsRank}</dt>
              <dd className="font-medium">{s.rank}</dd>
            </div>
          )}
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted">{t.statRating}</dt>
            <dd className="font-mono font-medium">{s.current_rating ?? '—'}</dd>
          </div>
        </dl>
        {s.cf_handle === null ? (
          <div className="mt-4">
            {demo ? (
              <p className="text-sm text-muted">{t.disabledInDemo}</p>
            ) : (
              <HandleConnect onDone={() => void query.refetch()} />
            )}
          </div>
        ) : (
          <div className="mt-4">
            {confirmDisconnect ? (
              <div className="flex flex-col gap-2 rounded-md border border-danger/40 bg-danger/5 p-3">
                <p className="text-sm">{t.settingsDisconnectConfirm}</p>
                <div className="flex gap-2">
                  <Button
                    variant="danger"
                    className="h-8 text-xs"
                    loading={disconnect.isPending}
                    disabled={demo}
                    onClick={() => disconnect.mutate()}
                  >
                    <Unlink size={13} aria-hidden /> {t.settingsDisconnect}
                  </Button>
                  <Button
                    variant="ghost"
                    className="h-8 text-xs"
                    onClick={() => setConfirmDisconnect(false)}
                  >
                    {t.undo}
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="secondary"
                className="h-8 text-xs"
                disabled={demo}
                onClick={() => setConfirmDisconnect(true)}
              >
                <Unlink size={13} aria-hidden /> {t.settingsDisconnect}
              </Button>
            )}
          </div>
        )}
      </Card>

      {/* Weekly goal */}
      <Card title={t.settingsGoal} className="min-w-0">
        <p className="mb-3 text-sm text-muted">{t.settingsGoalHint}</p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex flex-col gap-1 text-xs text-muted">
            {t.settingsGoal}
            <Input
              type="number"
              min={1}
              max={50}
              value={goal}
              disabled={demo}
              onChange={(e) => setGoalInput(e.target.value)}
              className="w-32"
              aria-label={t.settingsGoal}
            />
          </label>
          <Button
            disabled={demo || !goalValid || saveGoal.isPending || goalNum === s.weekly_goal}
            onClick={() => saveGoal.mutate()}
          >
            {t.settingsGoalSave}
          </Button>
        </div>
        {!goalValid && <p className="mt-2 text-xs text-danger">1–50</p>}
        <div className="mt-4">
          <p className="mb-1.5 text-sm">
            {t.settingsGoalProgress(s.solved_this_week, s.weekly_goal)}
          </p>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${goalPct}%` }}
            />
          </div>
        </div>
      </Card>

      {/* Appearance */}
      <Card title={t.settingsAppearance} className="min-w-0">
        <div className="flex flex-wrap items-center gap-4">
          <LanguageToggle />
          <Button variant="secondary" onClick={toggleTheme}>
            {theme === 'dark' ? t.switchToLight : t.switchToDark}
          </Button>
        </div>
      </Card>

      {/* Export */}
      <Card title={t.settingsExport} className="min-w-0">
        <p className="mb-3 text-sm text-muted">{t.settingsExportHint}</p>
        <Button
          variant="secondary"
          loading={exportData.isPending}
          onClick={() => exportData.mutate()}
        >
          <Download size={15} aria-hidden /> {t.settingsExport}
        </Button>
        {exportData.isError && (
          <p role="alert" className="mt-2 text-xs text-danger">
            {exportData.error instanceof ApiError
              ? exportData.error.message
              : t.somethingWrong}
          </p>
        )}
      </Card>

      {/* Delete account */}
      {!demo && (
        <Card title={t.settingsDelete} className="min-w-0">
          <p className="mb-3 text-sm text-muted">{t.settingsDeleteHint}</p>
          {confirmDelete ? (
            <div className="flex flex-col gap-2 rounded-md border border-danger/40 bg-danger/5 p-3">
              <p className="text-sm font-medium">{t.settingsDeleteConfirm}</p>
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  className="h-8 text-xs"
                  loading={deleteAccount.isPending}
                  onClick={() => deleteAccount.mutate()}
                >
                  <Trash2 size={13} aria-hidden /> {t.settingsDelete}
                </Button>
                <Button
                  variant="ghost"
                  className="h-8 text-xs"
                  onClick={() => setConfirmDelete(false)}
                >
                  {t.undo}
                </Button>
              </div>
            </div>
          ) : (
            <Button
              variant="danger"
              className="h-8 text-xs"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 size={13} aria-hidden /> {t.settingsDelete}
            </Button>
          )}
        </Card>
      )}

      {!demo && (
        <Button
          variant="ghost"
          className="self-start"
          onClick={() => {
            logout();
            navigate('/');
          }}
        >
          <LogOut size={15} aria-hidden /> {t.logOut}
        </Button>
      )}
    </div>
  );
}
