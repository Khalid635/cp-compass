/* Tiny fetch wrapper: JWT from localStorage, JSON errors surfaced as messages. */
import type { DashboardData, Recommendation, RevisionItem, SyncStatus } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function token(): string | null {
  return localStorage.getItem('cp_token');
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const msg =
      (body as { detail?: string } | null)?.detail ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  register: (email: string, password: string) =>
    request<{ token: string; email: string; cf_handle: string | null }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ token: string; email: string; cf_handle: string | null }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () =>
    request<{ email: string; cf_handle: string | null; current_rating: number | null }>(
      '/api/auth/me',
    ),
  setHandle: (handle: string) =>
    request<{ cf_handle: string; current_rating: number | null; rank?: string }>(
      '/api/auth/handle',
      { method: 'POST', body: JSON.stringify({ handle }) },
    ),
  startSync: () => request<{ job_id: number; status: string }>('/api/sync', { method: 'POST' }),
  syncStatus: () => request<SyncStatus>('/api/sync/status'),
  dashboard: () => request<DashboardData>('/api/dashboard'),
  recommendations: (params: { tag?: string; min_rating?: number; max_rating?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.tag) q.set('tag', params.tag);
    if (params.min_rating !== undefined) q.set('min_rating', String(params.min_rating));
    if (params.max_rating !== undefined) q.set('max_rating', String(params.max_rating));
    const s = q.toString();
    return request<Recommendation[]>(`/api/recommendations${s ? `?${s}` : ''}`);
  },
  recommendationAction: (contest_id: number, index: string, action: 'later' | 'not_interested') =>
    request<{ ok: boolean }>('/api/recommendations/action', {
      method: 'POST',
      body: JSON.stringify({ contest_id, index, action }),
    }),
  revisions: (tab: 'due' | 'upcoming' | 'done') =>
    request<RevisionItem[]>(`/api/revisions?tab=${tab}`),
  revisionCounts: () =>
    request<{ due: number; upcoming: number; done: number }>('/api/revisions/counts'),
  reviewRevision: (revision_id: number, result: 'again' | 'hard' | 'good' | 'easy') =>
    request<{ ok: boolean; next_due: string; interval_days: number }>('/api/revisions/review', {
      method: 'POST',
      body: JSON.stringify({ revision_id, result }),
    }),

  /* Demo — no auth, read-only, honestly labelled seed data. */
  demoDashboard: () => request<DashboardData>('/api/demo/dashboard'),
  demoRecommendations: () => request<Recommendation[]>('/api/demo/recommendations'),
  demoRevisions: () =>
    request<{ due: RevisionItem[]; upcoming: RevisionItem[]; done: RevisionItem[] }>(
      '/api/demo/revisions',
    ),
};
