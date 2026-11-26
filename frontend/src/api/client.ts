/* Tiny fetch wrapper: JWT access token from localStorage, JSON errors
   surfaced as messages. On a 401 the refresh token is tried once and the
   original request retried — the access token lives only 15 minutes. */
import type { DashboardData, Recommendation, RevisionItem, SyncStatus } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';
const V1 = '/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function accessToken(): string | null {
  return localStorage.getItem('cp_access_token');
}

function refreshToken(): string | null {
  return localStorage.getItem('cp_refresh_token');
}

export function storeTokens(access: string, refresh: string) {
  localStorage.setItem('cp_access_token', access);
  localStorage.setItem('cp_refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('cp_access_token');
  localStorage.removeItem('cp_refresh_token');
  localStorage.removeItem('cp_token'); // legacy single-token key
}

/* Single-flight refresh: concurrent 401s share one refresh call. */
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const rt = refreshToken();
      if (!rt) return false;
      try {
        const res = await fetch(`${BASE}${V1}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!res.ok) return false;
        const body = (await res.json()) as { access_token: string; refresh_token: string };
        storeTokens(body.access_token, body.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

async function request<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const t = accessToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (res.status === 401 && !retried && refreshToken()) {
    if (await tryRefresh()) return request<T>(path, init, true);
    clearTokens();
  }
  if (!res.ok) {
    const msg =
      (body as { detail?: string } | null)?.detail ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return body as T;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  email: string;
  cf_handle: string | null;
}

export const api = {
  health: () => request<{ status: string }>(`${V1}/health`),
  register: (email: string, password: string) =>
    request<AuthResponse>(`${V1}/auth/register`, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<AuthResponse>(`${V1}/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => {
    const rt = refreshToken();
    if (!rt) return Promise.resolve({ ok: true });
    return request<{ ok: boolean }>(`${V1}/auth/logout`, {
      method: 'POST',
      body: JSON.stringify({ refresh_token: rt }),
    });
  },
  me: () =>
    request<{ email: string; cf_handle: string | null; current_rating: number | null }>(
      `${V1}/auth/me`,
    ),
  setHandle: (handle: string) =>
    request<{ cf_handle: string; current_rating: number | null; rank?: string }>(
      `${V1}/auth/handle`,
      { method: 'POST', body: JSON.stringify({ handle }) },
    ),
  startSync: () => request<{ job_id: number; status: string }>(`${V1}/sync`, { method: 'POST' }),
  syncStatus: () => request<SyncStatus>(`${V1}/sync/status`),
  dashboard: () => request<DashboardData>(`${V1}/dashboard`),
  recommendations: (params: { tag?: string; min_rating?: number; max_rating?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.tag) q.set('tag', params.tag);
    if (params.min_rating !== undefined) q.set('min_rating', String(params.min_rating));
    if (params.max_rating !== undefined) q.set('max_rating', String(params.max_rating));
    const s = q.toString();
    return request<Recommendation[]>(`${V1}/recommendations${s ? `?${s}` : ''}`);
  },
  recommendationAction: (
    contest_id: number,
    index: string,
    action: 'later' | 'not_interested' | 'interested',
  ) =>
    request<{ ok: boolean }>(`${V1}/recommendations/action`, {
      method: 'POST',
      body: JSON.stringify({ contest_id, index, action }),
    }),
  preferences: () =>
    request<
      { contest_id: number; index: string; name: string; rating: number | null; tags: string[]; state: string }[]
    >(`${V1}/practice/preferences`),
  revisions: (tab: 'due' | 'upcoming' | 'done') =>
    request<RevisionItem[]>(`${V1}/revisions?tab=${tab}`),
  revisionCounts: () =>
    request<{ due: number; upcoming: number; done: number }>(`${V1}/revisions/counts`),
  reviewRevision: (revision_id: number, result: 'again' | 'hard' | 'good' | 'easy') =>
    request<{ ok: boolean; next_due: string; interval_days: number }>(`${V1}/revisions/review`, {
      method: 'POST',
      body: JSON.stringify({ revision_id, result }),
    }),

  /* Demo — no auth, read-only, honestly labelled seed data. */
  demoDashboard: () => request<DashboardData>(`${V1}/demo/dashboard`),
  demoRecommendations: () => request<Recommendation[]>(`${V1}/demo/recommendations`),
  demoRevisions: () =>
    request<{ due: RevisionItem[]; upcoming: RevisionItem[]; done: RevisionItem[] }>(
      `${V1}/demo/revisions`,
    ),
};
