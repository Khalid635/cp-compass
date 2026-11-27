/* Auth state. Batch 1 security: register no longer logs the user in
   (an email code must be verified first), and login may stop at the
   TOTP second step — both return their response so the page can branch
   on it. Handle linking goes through the profile-token flow. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  api,
  clearTokens,
  storeTokens,
} from '../api/client';
import type {
  HandleStartResponse,
  LoginResponse,
  RegisterResponse,
} from '../api/client';

export interface AuthUser {
  email: string;
  cf_handle: string | null;
  current_rating: number | null;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<LoginResponse>;
  register: (email: string, password: string) => Promise<RegisterResponse>;
  verifyEmail: (email: string, code: string) => Promise<void>;
  verifyTotp: (preToken: string, code: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  startHandleVerification: (handle: string) => Promise<HandleStartResponse>;
  confirmHandleVerification: (handle: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!localStorage.getItem('cp_access_token')) {
      // Legacy single-token sessions (pre-refresh era) are invalid now.
      clearTokens();
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    if (res.totp_required) return res; // second step: TOTP code
    if (!res.access_token || !res.refresh_token) return res;
    storeTokens(res.access_token, res.refresh_token);
    const me = await api.me();
    setUser(me);
    return res;
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    // No auto-login: the account is unverified until the email code.
    return api.register(email, password);
  }, []);

  const verifyEmail = useCallback(async (email: string, code: string) => {
    const res = await api.verifyEmail(email, code);
    storeTokens(res.access_token, res.refresh_token);
    const me = await api.me();
    setUser(me);
  }, []);

  const verifyTotp = useCallback(async (preToken: string, code: string) => {
    const res = await api.totpVerify(preToken, code);
    storeTokens(res.access_token, res.refresh_token);
    const me = await api.me();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    void api.logout().catch(() => undefined); // revoke server-side, best effort
    clearTokens();
    setUser(null);
  }, []);

  const startHandleVerification = useCallback(async (handle: string) => {
    return api.startHandleVerification(handle);
  }, []);

  const confirmHandleVerification = useCallback(async (handle: string) => {
    await api.confirmHandleVerification(handle);
    const me = await api.me();
    setUser(me);
  }, []);

  const value = useMemo(
    () => ({
      user, loading, login, register, verifyEmail, verifyTotp, logout,
      refresh, startHandleVerification, confirmHandleVerification,
    }),
    [user, loading, login, register, verifyEmail, verifyTotp, logout,
     refresh, startHandleVerification, confirmHandleVerification],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
