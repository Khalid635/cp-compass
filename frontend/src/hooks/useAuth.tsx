/* Auth state. Batch 6, N4: tokens live in HttpOnly cookies — the
   frontend never sees them. Boot is api.me() only; legacy localStorage
   token keys are deleted unconditionally on boot, never read. Login may
   stop at the TOTP second step — both return their response so the page
   can branch on it. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  api,
  apiOrigin,
  clearCsrfToken,
  clearLegacyTokens,
  setCsrfToken,
} from '../api/client';
import type {
  AuthResponse,
  GoogleCallbackResponse,
  HandleStartResponse,
  LoginResponse,
  RegisterResponse,
} from '../api/client';
import { ApiError } from '../api/client';

export interface AuthUser {
  email: string;
  cf_handle: string | null;
  current_rating: number | null;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  /** True when a login succeeded server-side but the session cookie did
      not stick — the browser is blocking third-party cookies (a005, Q6).
      The login page shows a banner naming the API origin. */
  cookiesBlocked: boolean;
  cookiesBlockedOrigin: string;
  login: (email: string, password: string) => Promise<LoginResponse>;
  register: (email: string, password: string) => Promise<RegisterResponse>;
  verifyEmail: (email: string, code: string) => Promise<AuthResponse>;
  verifyTotp: (pre_token: string, code: string) => Promise<AuthResponse>;
  startGoogleSignIn: () => Promise<void>;
  completeGoogleSignIn: (code: string, state: string) => Promise<GoogleCallbackResponse>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  startHandleVerification: (handle: string) => Promise<HandleStartResponse>;
  confirmHandleVerification: (handle: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [cookiesBlocked, setCookiesBlocked] = useState(false);

  const refresh = useCallback(async () => {
    clearLegacyTokens();
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /* After a login that succeeded server-side, an immediate me() 401
     means the session cookie did not stick. Set the flag at once (the
     banner is the honest message) and confirm with the probe: if the
     cookies actually are coming back, clear it again. */
  const checkCookiesStuck = useCallback(async () => {
    try {
      const first = await api.cookieProbe();
      if (first.cookies_ok) {
        setCookiesBlocked(false);
        return;
      }
      const second = await api.cookieProbe();
      if (second.cookies_ok) setCookiesBlocked(false);
    } catch {
      /* probe failure is not proof of blocking; the flag stays */
    }
  }, []);

  /* After any auth transition: take the CSRF echo into the in-memory
     copy, then prove the session with me(). A 401 here means the
     cookie did not stick — flag it and throw so the page stays put. */
  const afterAuth = useCallback(
    async (res: AuthResponse): Promise<AuthResponse> => {
      if (res.csrf_token) setCsrfToken(res.csrf_token);
      try {
        const me = await api.me();
        setUser(me);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          setCookiesBlocked(true);
          void checkCookiesStuck();
        }
        throw err;
      }
      return res;
    },
    [checkCookiesStuck],
  );

  const login = useCallback(
    async (email: string, password: string): Promise<LoginResponse> => {
      setCookiesBlocked(false);
      const res = await api.login(email, password);
      if (res.totp_required) return res;
      await afterAuth({
        email: res.email,
        cf_handle: res.cf_handle ?? null,
        csrf_token: res.csrf_token,
      });
      return res;
    },
    [afterAuth],
  );

  const register = useCallback(async (email: string, password: string) => {
    const res = await api.register(email, password);
    return res;
  }, []);

  const verifyEmail = useCallback(
    async (email: string, code: string): Promise<AuthResponse> => {
      setCookiesBlocked(false);
      const res = await api.verifyEmail(email, code);
      return afterAuth(res);
    },
    [afterAuth],
  );

  const verifyTotp = useCallback(
    async (pre_token: string, code: string): Promise<AuthResponse> => {
      setCookiesBlocked(false);
      const res = await api.totpVerify(pre_token, code);
      return afterAuth(res);
    },
    [afterAuth],
  );

  const startGoogleSignIn = useCallback(async () => {
    const res = await api.googleAuthUrl();
    window.location.href = res.auth_url;
  }, []);

  const completeGoogleSignIn = useCallback(
    async (code: string, state: string): Promise<GoogleCallbackResponse> => {
      setCookiesBlocked(false);
      const res = await api.googleCallback(code, state);
      if ('totp_required' in res) return res;
      return afterAuth(res);
    },
    [afterAuth],
  );

  const startHandleVerification = useCallback(async (handle: string) => {
    const res = await api.startHandleVerification(handle);
    return res;
  }, []);

  const confirmHandleVerification = useCallback(async (handle: string) => {
    await api.confirmHandleVerification(handle);
    const me = await api.me();
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* logout is best-effort: the server may already have dropped the
         session (expired refresh cookie) — still clear local state */
    } finally {
      clearCsrfToken();
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      cookiesBlocked,
      cookiesBlockedOrigin: apiOrigin(),
      login,
      register,
      verifyEmail,
      verifyTotp,
      startGoogleSignIn,
      completeGoogleSignIn,
      logout,
      refresh,
      startHandleVerification,
      confirmHandleVerification,
    }),
    [
      user,
      loading,
      cookiesBlocked,
      login,
      register,
      verifyEmail,
      verifyTotp,
      startGoogleSignIn,
      completeGoogleSignIn,
      logout,
      refresh,
      startHandleVerification,
      confirmHandleVerification,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
