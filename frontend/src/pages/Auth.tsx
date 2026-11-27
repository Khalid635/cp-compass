/* Login / Register — small centered card.
   Batch 1 security: register ends with an email-code step (the account
   is unverified until the code), and login may stop at the TOTP second
   step when 2FA is on. Handle connect is a 2-step profile-token flow. */
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CheckCircle2, Compass, Copy, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { api, ApiError } from '../api/client';
import { useLanguage } from '../i18n';
import { useAuth } from '../hooks/useAuth';
import { Button, Card, Input } from '../components/ui';

export function LoginPage() {
  return <AuthPage mode="login" />;
}

export function RegisterPage() {
  return <AuthPage mode="register" />;
}

type Step = 'form' | 'verify' | 'totp';

function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { t } = useLanguage();
  const { login, register, verifyEmail, verifyTotp } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [preToken, setPreToken] = useState('');
  const [step, setStep] = useState<Step>('form');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      if (mode === 'login') {
        const res = await login(email, password);
        if (res.totp_required && res.pre_token) {
          setPreToken(res.pre_token);
          setStep('totp');
        } else {
          navigate('/app', { replace: true });
        }
      } else {
        await register(email, password);
        setStep('verify');
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        // Login before the signup code was verified -> show that step.
        setStep('verify');
        setError(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : t.somethingWrong);
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (step === 'verify') {
        await verifyEmail(email, code.trim());
      } else {
        await verifyTotp(preToken, code.trim());
      }
      navigate('/app', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.somethingWrong);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    setInfo(null);
    try {
      await api.resendCode(email);
      setInfo(t.codeResent);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.somethingWrong);
    }
  }

  const heading =
    step === 'verify'
      ? t.verifyEmailTitle
      : step === 'totp'
        ? t.totpTitle
        : mode === 'login'
          ? t.welcomeBack
          : t.createAccountTitle;
  const sub =
    step === 'verify'
      ? t.verifyEmailText(email)
      : step === 'totp'
        ? t.totpText
        : mode === 'login'
          ? t.loginSub
          : t.registerSub;

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          {step === 'totp' ? (
            <ShieldCheck size={32} className="text-primary" aria-hidden />
          ) : (
            <Compass size={32} className="text-primary" aria-hidden />
          )}
          <h1 className="text-2xl font-semibold tracking-tight">{heading}</h1>
          <p className="text-sm text-muted">{sub}</p>
        </div>
        <Card>
          {step === 'form' ? (
            <form onSubmit={submit} className="flex flex-col gap-4">
              <label className="flex flex-col gap-1 text-sm font-medium">
                {t.email}
                <Input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm font-medium">
                {t.password}
                <Input
                  type="password"
                  required
                  minLength={mode === 'register' ? 8 : 1}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t.passwordPlaceholder}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
              </label>
              {error && (
                <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              )}
              <Button type="submit" loading={busy} className="w-full">
                {mode === 'login' ? t.logIn : t.createAccountBtn}
              </Button>
            </form>
          ) : (
            <form onSubmit={submitCode} className="flex flex-col gap-4">
              <label className="flex flex-col gap-1 text-sm font-medium">
                {step === 'verify' ? t.verifyCodeLabel : t.totpCodeLabel}
                <Input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder={
                    step === 'verify' ? t.verifyCodePlaceholder : '123456'
                  }
                  autoComplete="one-time-code"
                  inputMode="numeric"
                />
              </label>
              {step === 'totp' && (
                <p className="text-xs text-muted">{t.totpUseBackup}</p>
              )}
              {error && (
                <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              )}
              {info && (
                <p className="rounded-md bg-success/10 px-3 py-2 text-sm text-success">
                  {info}
                </p>
              )}
              <Button type="submit" loading={busy} className="w-full">
                {step === 'verify' ? t.verifyEmailBtn : t.totpVerifyBtn}
              </Button>
              {step === 'verify' && (
                <Button type="button" variant="ghost" onClick={() => void resend()}>
                  {t.resendCode}
                </Button>
              )}
            </form>
          )}
        </Card>
        <p className="mt-4 text-center text-sm text-muted">
          {mode === 'login' ? (
            <>
              {t.noAccountYet} <Link to="/register">{t.createAccount}</Link>
            </>
          ) : (
            <>
              {t.haveAccount} <Link to="/login">{t.logIn}</Link>
            </>
          )}
        </p>
        {mode === 'register' && step === 'verify' && (
          <p className="mt-2 flex items-center justify-center gap-1 text-center text-xs text-muted">
            <CheckCircle2 size={14} className="text-success" aria-hidden />
            {t.accountCreated}
          </p>
        )}
      </div>
    </div>
  );
}

/* Handle-connect step — 2-step profile-token verification (Batch 1 / F1).
   Shown after register, and from Settings when no handle is connected. */
export function HandleConnect({ onDone }: { onDone?: () => void }) {
  const { t } = useLanguage();
  const { startHandleVerification, confirmHandleVerification } = useAuth();
  const [handle, setHandle] = useState('');
  const [token, setToken] = useState<string | null>(null);
  const [pendingHandle, setPendingHandle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api
      .pendingHandleVerification()
      .then((res) => {
        if (res.pending) setPendingHandle(res.pending.handle);
      })
      .catch(() => undefined);
  }, []);

  async function start(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await startHandleVerification(handle.trim());
      setToken(res.token);
      setPendingHandle(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.handleVerifyError);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setError(null);
    setBusy(true);
    try {
      await confirmHandleVerification(handle.trim());
      toast(t.handleVerified);
      onDone?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.handleVerifyError);
    } finally {
      setBusy(false);
    }
  }

  function copyToken() {
    if (!token) return;
    void navigator.clipboard?.writeText(token).then(
      () => toast(t.tokenCopied),
      () => undefined,
    );
  }

  return (
    <Card title={t.connectHandleTitle}>
      <p className="mb-4 text-sm text-muted">{t.connectHandleText}</p>
      {pendingHandle && !token && (
        <p className="mb-4 rounded-md border border-primary/40 bg-primary/5 px-3 py-2 text-sm">
          {t.handlePendingText(pendingHandle)}
        </p>
      )}
      {token === null ? (
        <form onSubmit={start} className="flex flex-col gap-3 sm:flex-row">
          <Input
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder={t.handlePlaceholder}
            className="flex-1"
            aria-label="Codeforces handle"
          />
          <Button type="submit" loading={busy}>
            {pendingHandle ? t.handleStartAgain : t.verifyConnect}
          </Button>
        </form>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t.handleStep1Text}</p>
          <div>
            <p className="mb-1 text-xs font-medium text-muted">{t.handleTokenLabel}</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-md bg-surface-2 px-3 py-2 text-center font-mono text-lg font-bold tracking-widest">
                {token}
              </code>
              <Button variant="secondary" className="h-9 text-xs" onClick={copyToken}>
                <Copy size={13} aria-hidden /> {t.copyToken}
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted">{t.handleTokenHint}</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button loading={busy} onClick={() => void confirm()}>
              {t.handleConfirmBtn}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setToken(null);
                setHandle('');
              }}
            >
              {t.handleStartAgain}
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
