import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, clearTokens, storeTokens } from '../api/client';

export interface AuthUser {
  email: string;
  cf_handle: string | null;
  current_rating: number | null;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  setHandle: (handle: string) => Promise<void>;
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
    storeTokens(res.access_token, res.refresh_token);
    const me = await api.me();
    setUser(me);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const res = await api.register(email, password);
    storeTokens(res.access_token, res.refresh_token);
    const me = await api.me();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    void api.logout().catch(() => undefined); // revoke server-side, best effort
    clearTokens();
    setUser(null);
  }, []);

  const setHandle = useCallback(async (handle: string) => {
    await api.setHandle(handle);
    const me = await api.me();
    setUser(me);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refresh, setHandle }),
    [user, loading, login, register, logout, refresh, setHandle],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
