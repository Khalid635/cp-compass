/* Login / Register — small centered card. Register is followed by a
   handle-connect step (verified against the Codeforces API). */
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CheckCircle2, Compass } from 'lucide-react';
import { ApiError } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { Button, Card, Input } from '../components/ui';

export function LoginPage() {
  return <AuthPage mode="login" />;
}

export function RegisterPage() {
  return <AuthPage mode="register" />;
}

function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === 'login') await login(email, password);
      else await register(email, password);
      navigate('/app', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <Compass size={32} className="text-primary" aria-hidden />
          <h1 className="text-2xl font-semibold tracking-tight">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="text-sm text-muted">
            {mode === 'login'
              ? 'Log in to see your practice plan.'
              : 'One account, one Codeforces handle. Free forever.'}
          </p>
        </div>
        <Card>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1 text-sm font-medium">
              Email
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
              Password
              <Input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </label>
            {error && (
              <p role="alert" className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}
            <Button type="submit" loading={busy} className="w-full">
              {mode === 'login' ? 'Log in' : 'Create account'}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-sm text-muted">
          {mode === 'login' ? (
            <>
              No account yet? <Link to="/register">Create one</Link>
            </>
          ) : (
            <>
              Already have an account? <Link to="/login">Log in</Link>
            </>
          )}
        </p>
        {mode === 'register' && user && (
          <p className="mt-2 flex items-center justify-center gap-1 text-center text-xs text-muted">
            <CheckCircle2 size={14} className="text-success" aria-hidden />
            Account created — next, connect your handle.
          </p>
        )}
      </div>
    </div>
  );
}

/* Handle-connect step — shown after register, and from the dashboard when
   no handle is connected yet. */
export function HandleConnect({ onDone }: { onDone?: () => void }) {
  const { setHandle: connectHandle } = useAuth();
  const [handle, setHandle] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await connectHandle(handle.trim());
      onDone?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not verify the handle.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Connect your Codeforces handle">
      <p className="mb-4 text-sm text-muted">
        We check the handle against the Codeforces API — a wrong handle gives a
        clear error, never partial data.
      </p>
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <Input
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
          placeholder="e.g. tourist"
          className="flex-1"
          aria-label="Codeforces handle"
        />
        <Button type="submit" loading={busy}>
          Verify & connect
        </Button>
      </form>
      {error && (
        <p role="alert" className="mt-3 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  );
}
