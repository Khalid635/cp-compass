/* Settings — account (handle connect/disconnect), weekly practice goal,
   appearance (language + theme), data export, account deletion. In demo
   mode everything is read-only and says so. Batch 1 adds a Security
   card: email verification status + TOTP 2FA setup. */
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { QRCodeSVG } from 'qrcode.react';
import { CheckCircle2, Download, LogOut, RefreshCw, ShieldCheck, Trash2, Unlink } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { trainedOnLabel } from '../api/types';
import { useAuth } from '../hooks/useAuth';
import type { Theme } from '../hooks/useTheme';
import { formatDateTime, LanguageToggle, useLanguage } from '../i18n';
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
  const { t, lang } = useLanguage();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { logout, refresh } = useAuth();
  const [goal, setGoalInput] = useState('5');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  /* Batch 1 — 2FA setup state. */
  const [totpSetup, setTotpSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [totpCode, setTotpCode] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [totpPassword, setTotpPassword] = useState('');
  const [confirmDisable2fa, setConfirmDisable2fa] = useState(false);
  const [confirmRegenCodes, setConfirmRegenCodes] = useState(false);

  const query = useQuery({
    queryKey: demo ? ['demo-settings'] : ['settings'],
    queryFn: demo ? api.demoSettings : api.settings,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (query.data) setGoalInput(String(query.data.weekly_goal));
  }, [query.data?.weekly_goal]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Phase 3 — prediction model status + retrain. */
  const mlQuery = useQuery({
    queryKey: demo ? ['demo-ml-status'] : ['ml-status'],
    queryFn: demo ? api.demoMlStatus : api.mlStatus,
    staleTime: 30_000,
  });
  const retrain = useMutation({
    mutationFn: api.retrainModel,
    onSuccess: (data) => {
      toast(data.trained ? t.predRetrained : t.predRetrainFailed);
      void qc.invalidateQueries({ queryKey: ['ml-status'] });
      void qc.invalidateQueries({ queryKey: ['demo-ml-status'] });
    },
    onError: (e) => {
      toast(e instanceof ApiError ? e.message : t.predRetrainFailed);
    },
  });

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
    mutationFn: (password: string) => api.deleteAccount(password),
    onSuccess: () => {
      logout();
      navigate('/');
    },
  });

  /* Batch 1 — TOTP 2FA: status, setup, enable, disable, regenerate. */
  const totpStatusQuery = useQuery({
    queryKey: ['totp-status'],
    queryFn: api.totpStatus,
    enabled: !demo,
    staleTime: 30_000,
  });

  const totpSetupMutation = useMutation({
    mutationFn: api.totpSetup,
    onSuccess: (data) => {
      setTotpSetup(data);
      setBackupCodes(null);
      setTotpCode('');
    },
    onError: (e) => {
      toast(e instanceof ApiError ? e.message : t.somethingWrong);
    },
  });

  const totpEnableMutation = useMutation({
    mutationFn: () => api.totpEnable(totpCode.trim()),
    onSuccess: (data) => {
      setBackupCodes(data.backup_codes);
      setTotpSetup(null);
      setTotpCode('');
      toast(t.totpEnabled);
      void qc.invalidateQueries({ queryKey: ['settings'] });
      void qc.invalidateQueries({ queryKey: ['totp-status'] });
    },
    onError: (e) => {
      toast(e instanceof ApiError ? e.message : t.somethingWrong);
    },
  });

  const totpDisableMutation = useMutation({
    mutationFn: () => api.totpDisable(totpPassword),
    onSuccess: () => {
      setConfirmDisable2fa(false);
      setTotpPassword('');
      toast(t.totpDisabled);
      void qc.invalidateQueries({ queryKey: ['settings'] });
      void qc.invalidateQueries({ queryKey: ['totp-status'] });
    },
    onError: (e) => {
      toast(e instanceof ApiError ? e.message : t.somethingWrong);
    },
  });

  const totpRegenMutation = useMutation({
    mutationFn: () => api.totpRegenerateCodes(totpPassword),
    onSuccess: (data) => {
      setBackupCodes(data.backup_codes);
      setConfirmRegenCodes(false);
      setTotpPassword('');
      void qc.invalidateQueries({ queryKey: ['totp-status'] });
    },
    onError: (e) => {
      toast(e instanceof ApiError ? e.message : t.somethingWrong);
    },
  });

  const resendCodeMutation = useMutation({
    mutationFn: () => api.resendCode(query.data?.email ?? ''),
    onSuccess: () => toast(t.codeResent),
    onError: (e) => {
      toast(e instanceof ApiError ? e.message : t.somethingWrong);
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

      {/* Security (Batch 1): email verification + TOTP 2FA */}
      {!demo && (
        <Card title={t.securityTitle} className="min-w-0">
          <dl className="flex flex-col gap-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">{t.email}</dt>
              <dd className="flex items-center gap-2 font-medium">
                {s.email_verified ? (
                  <>
                    <CheckCircle2 size={15} className="text-success" aria-hidden />
                    {t.emailVerified}
                  </>
                ) : (
                  <>
                    {t.emailNotVerified}
                    <Button
                      variant="secondary"
                      className="h-8 text-xs"
                      loading={resendCodeMutation.isPending}
                      onClick={() => resendCodeMutation.mutate()}
                    >
                      {t.resendCode}
                    </Button>
                  </>
                )}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="flex items-center gap-1.5 text-muted">
                <ShieldCheck size={15} aria-hidden />
                {t.totpTitle}
              </dt>
              <dd className="font-medium">
                {s.totp_enabled ? t.totpStatusOn : t.totpStatusOff}
                {totpStatusQuery.data && s.totp_enabled && (
                  <span className="ml-2 text-xs text-muted">
                    · {t.totpRemaining(totpStatusQuery.data.backup_codes_remaining)}
                  </span>
                )}
              </dd>
            </div>
          </dl>

          {backupCodes && (
            <div className="mt-4 rounded-md border border-primary/40 bg-primary/5 p-3">
              <p className="text-sm font-medium">{t.totpBackupTitle}</p>
              <p className="mt-1 text-xs text-muted">{t.totpBackupText}</p>
              <div className="mt-2 grid grid-cols-2 gap-1 font-mono text-sm">
                {backupCodes.map((code) => (
                  <code key={code} className="rounded bg-surface-2 px-2 py-1 text-center">
                    {code.slice(0, 4)}-{code.slice(4)}
                  </code>
                ))}
              </div>
              <Button
                variant="secondary"
                className="mt-3 h-8 text-xs"
                onClick={() => setBackupCodes(null)}
              >
                {t.totpBackupSaved}
              </Button>
            </div>
          )}

          {!s.totp_enabled && !backupCodes && (
            <div className="mt-4">
              {totpSetup ? (
                <div className="flex flex-col gap-3">
                  <p className="text-sm text-muted">{t.totpSetupText}</p>
                  <div className="flex justify-center rounded-md bg-white p-3">
                    <QRCodeSVG value={totpSetup.otpauth_uri} size={160} />
                  </div>
                  <p className="text-center text-sm text-muted">{t.totpScanQr}</p>
                  <p className="text-xs text-muted">{t.totpManualSecret}</p>
                  <code className="rounded-md bg-surface-2 px-3 py-2 text-center font-mono text-sm tracking-wider break-all">
                    {totpSetup.secret}
                  </code>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input
                      value={totpCode}
                      onChange={(e) => setTotpCode(e.target.value)}
                      placeholder={t.totpCodeLabel}
                      inputMode="numeric"
                      className="flex-1"
                    />
                    <Button
                      loading={totpEnableMutation.isPending}
                      disabled={totpCode.trim().length !== 6}
                      onClick={() => totpEnableMutation.mutate()}
                    >
                      {t.totpEnableBtn}
                    </Button>
                  </div>
                  <Button variant="ghost" onClick={() => setTotpSetup(null)}>
                    {t.undo}
                  </Button>
                </div>
              ) : (
                <Button
                  variant="secondary"
                  loading={totpSetupMutation.isPending}
                  onClick={() => totpSetupMutation.mutate()}
                >
                  <ShieldCheck size={14} aria-hidden /> {t.totpSetupTitle}
                </Button>
              )}
            </div>
          )}

          {s.totp_enabled && (
            <div className="mt-4 flex flex-col gap-3">
              {confirmRegenCodes ? (
                <div className="flex flex-col gap-2 rounded-md border border-primary/40 bg-primary/5 p-3">
                  <label className="flex flex-col gap-1 text-xs text-muted">
                    {t.passwordConfirmLabel}
                    <Input
                      type="password"
                      value={totpPassword}
                      onChange={(e) => setTotpPassword(e.target.value)}
                      autoComplete="current-password"
                    />
                  </label>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      className="h-8 text-xs"
                      loading={totpRegenMutation.isPending}
                      disabled={!totpPassword}
                      onClick={() => totpRegenMutation.mutate()}
                    >
                      {t.totpRegenerate}
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 text-xs"
                      onClick={() => setConfirmRegenCodes(false)}
                    >
                      {t.undo}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="secondary"
                  className="h-8 self-start text-xs"
                  onClick={() => setConfirmRegenCodes(true)}
                >
                  {t.totpRegenerate}
                </Button>
              )}
              {confirmDisable2fa ? (
                <div className="flex flex-col gap-2 rounded-md border border-danger/40 bg-danger/5 p-3">
                  <label className="flex flex-col gap-1 text-xs text-muted">
                    {t.passwordConfirmLabel}
                    <Input
                      type="password"
                      value={totpPassword}
                      onChange={(e) => setTotpPassword(e.target.value)}
                      autoComplete="current-password"
                    />
                  </label>
                  <div className="flex gap-2">
                    <Button
                      variant="danger"
                      className="h-8 text-xs"
                      loading={totpDisableMutation.isPending}
                      disabled={!totpPassword}
                      onClick={() => totpDisableMutation.mutate()}
                    >
                      {t.totpDisableBtn}
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 text-xs"
                      onClick={() => setConfirmDisable2fa(false)}
                    >
                      {t.undo}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="danger"
                  className="h-8 self-start text-xs"
                  onClick={() => setConfirmDisable2fa(true)}
                >
                  {t.totpDisableBtn}
                </Button>
              )}
            </div>
          )}
        </Card>
      )}

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


      {/* Prediction model (Phase 3) */}
      <Card title={t.predSettingsTitle} className="min-w-0">
        {mlQuery.isPending ? (
          <Skeleton className="h-[120px] w-full" />
        ) : mlQuery.isError ? (
          <p className="text-sm text-muted">{t.cfRetryAutoShort}</p>
        ) : !mlQuery.data?.trained ? (
          <p className="text-sm text-muted">{t.predNotTrained}</p>
        ) : (
          <>
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
              {mlQuery.data.shipped && (
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted">{t.predTestAuc}</dt>
                  <dd className="font-mono font-medium">
                    {mlQuery.data.evaluation?.random_forest.test_auc ?? '—'} · {t.predBaselineAuc}{' '}
                    {mlQuery.data.evaluation?.baseline.auc ?? '—'}
                  </dd>
                </div>
              )}
            </dl>
            {!mlQuery.data.shipped && (
              <p className="mt-3 text-sm text-muted">{t.predNotShipped}</p>
            )}
            <p className="mt-3 text-sm text-muted">{t.predBias}</p>
            <div className="mt-4">
              <Button
                variant="secondary"
                disabled={demo || retrain.isPending}
                loading={retrain.isPending}
                onClick={() => retrain.mutate()}
                title={demo ? t.disabledInDemo : undefined}
              >
                <RefreshCw size={14} aria-hidden />{' '}
                {retrain.isPending ? t.predRetraining : t.predRetrain}
              </Button>
            </div>
          </>
        )}
      </Card>

      {/* Other platforms (Phase 3 scaffolding — Codeforces only for now) */}
      <Card title={t.predPlatformTitle} className="min-w-0">
        <p className="text-sm text-muted">{t.predPlatformNote}</p>
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
              <p className="text-xs text-muted">{t.deletePasswordHint}</p>
              <Input
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                placeholder={t.password}
                autoComplete="current-password"
              />
              {deleteAccount.isError && (
                <p role="alert" className="text-xs text-danger">
                  {deleteAccount.error instanceof ApiError
                    ? deleteAccount.error.message
                    : t.somethingWrong}
                </p>
              )}
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  className="h-8 text-xs"
                  loading={deleteAccount.isPending}
                  disabled={!deletePassword}
                  onClick={() => deleteAccount.mutate(deletePassword)}
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
