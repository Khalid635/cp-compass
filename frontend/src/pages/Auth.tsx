/* Login / Register — small centered card.
   Batch 1 security: register ends with an email-code step (the account
   is unverified until the code), and login may stop at the TOTP second
   step when 2FA is on. Handle connect is a 2-step profile-token flow. */
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
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
  const { login, register, verifyEmail, verifyTotp, startGoogleSignIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [preToken, setPreToken] = useState('');
  const [step, setStep] = useState<Step>('form');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Google sign-in with 2FA on: the callback page leaves the pre-token
  // here so this page opens straight at the TOTP step.
  useEffect(() => {
    if (sessionStorage.getItem('cp_google_totp') !== '1') return;
    sessionStorage.removeItem('cp_google_totp');
    const tok = sessionStorage.getItem('cp_google_pre_token');
    if (!tok) return;
    sessionStorage.removeItem('cp_google_pre_token');
    setPreToken(tok);
    setStep('totp');
  }, []);

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

  async function google() {
    setError(null);
    setBusy(true);
    try {
      await startGoogleSignIn(); // navigates away to Google on success
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.somethingWrong);
      setBusy(false);
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
              <div className="flex items-center gap-3 text-xs text-muted" aria-hidden>
                <span className="h-px flex-1 bg-border" />
                {t.orContinueWith}
                <span className="h-px flex-1 bg-border" />
              </div>
              <Button
                type="button"
                variant="secondary"
                className="w-full"
                onClick={() => void google()}
                disabled={busy}
              >
                <GoogleMark /> {t.continueWithGoogle}
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

/* Google "G" mark (lucide has no brand icons): the standard
   four-colour G, inline SVG. */
function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

/* Google OAuth callback — Google redirects here with ?code&state after
   the user approves. Exchanges the code once (the ref guard also stops
   React StrictMode's double effect in dev from burning the single-use
   code) and lands on /app; a TOTP-enabled account is handed to the
   login page's TOTP step via sessionStorage. */
export function GoogleCallbackPage() {
  const { t } = useLanguage();
  const { completeGoogleSignIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const err = params.get('error');
    const code = params.get('code');
    const state = params.get('state');
    if (err || !code || !state) {
      setError(t.googleSignInError);
      return;
    }
    let cancelled = false;
    void completeGoogleSignIn(code, state)
      .then((res) => {
        if (cancelled) return;
        if ('totp_required' in res && res.pre_token) {
          sessionStorage.setItem('cp_google_pre_token', res.pre_token);
          sessionStorage.setItem('cp_google_totp', '1');
          navigate('/login', { replace: true });
          return;
        }
        navigate('/app', { replace: true });
      })
      .catch(() => {
        if (!cancelled) setError(t.googleSignInError);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        <Compass size={32} className="mx-auto text-primary" aria-hidden />
        {error ? (
          <>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight">
              {t.googleSignInError}
            </h1>
            <p className="mt-4 text-sm text-muted">
              <Link to="/login">{t.logIn}</Link>
            </p>
          </>
        ) : (
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">
            {t.googleSigningIn}
          </h1>
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
