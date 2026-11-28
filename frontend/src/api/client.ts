/* Tiny fetch wrapper. Batch 6, N4 (arena winner a005): auth tokens live
   in HttpOnly cookies — never in localStorage or any JS-readable store.
   Every request sends credentials: 'include'; mutations carry the CSRF
   token (X-CSRF-Token) from the /auth/csrf JSON body. On a 401 the
   refresh cookie is tried once (single-flight) and the original request
   retried — the access token lives only 15 minutes. */
import type {
  AnalyticsData,
  CalendarMonth,
  DashboardData,
  FailurePatternsData,
  HintUnlockResponse,
  HintsResponse,
  MlPredictionsResponse,
  MlStatus,
  PostmortemAnalysisGenerate,
  PostmortemAnalysisResponse,
  PostmortemData,
  PostmortemListItem,
  ProblemDetailData,
  PublicProfile,
  ProblemNote,
  Recommendation,
  RevisionItem,
  SettingsData,
  SubmissionRow,
  SyncStatus,
  WeeklyReportData,
} from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';
const V1 = '/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/* The API origin, for messages that must name it (e.g. the
   third-party-cookies-blocked banner). In dev BASE is '' (Vite proxy)
   so the origin is the page itself; in prod it is the Render URL. */
export function apiOrigin(): string {
  return BASE || window.location.origin;
}

/* Legacy localStorage token keys (pre-Batch 6). Deleted unconditionally
   on boot, never read — a005's live-session migration. */
export function clearLegacyTokens() {
  localStorage.removeItem('cp_access_token');
  localStorage.removeItem('cp_refresh_token');
  localStorage.removeItem('cp_token'); // legacy single-token key
}

/* CSRF token: module-level only, never persisted. The value comes from
   the GET /auth/csrf JSON body (a005) — cross-site JS cannot read the
   cp_csrf cookie via document.cookie, so the body is load-bearing. */
let csrfToken: string | null = null;
let csrfPromise: Promise<string> | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function clearCsrfToken() {
  csrfToken = null;
  csrfPromise = null;
}

/** Fetches the CSRF token (single-flight). Idempotent server-side:
    /auth/csrf returns the current cookie value if one exists. */
export async function ensureCsrf(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  if (!force && csrfPromise) return csrfPromise;
  csrfPromise = (async () => {
    const res = await fetch(`${BASE}${V1}/auth/csrf`, { credentials: 'include' });
    if (!res.ok) throw new ApiError(res.status, `Request failed (${res.status})`);
    const body = (await res.json()) as { csrf_token: string };
    csrfToken = body.csrf_token;
    return csrfToken;
  })();
  try {
    return await csrfPromise;
  } finally {
    csrfPromise = null;
  }
}

/* Single-flight refresh: concurrent 401s share one refresh call.
   Cookie-based (Batch 6, N4): the refresh token travels in the
   cp_refresh cookie, never in a body. Refresh is a mutation, so it
   carries the CSRF header too. */
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const token = await ensureCsrf();
        const res = await fetch(`${BASE}${V1}/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
        });
        return res.ok;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

function isMutation(init?: RequestInit): boolean {
  const m = (init?.method ?? 'GET').toUpperCase();
  return m === 'POST' || m === 'PUT' || m === 'PATCH' || m === 'DELETE';
}

async function request<T>(
  path: string,
  init?: RequestInit,
  retried = false,
  csrfRetried = false,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (isMutation(init)) {
    headers['X-CSRF-Token'] = await ensureCsrf();
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers, credentials: 'include' });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  // CSRF 403: the token rotated (e.g. on login) and our in-memory copy
  // is stale — refetch once and retry once (a005/a001).
  if (
    res.status === 403 &&
    !csrfRetried &&
    (body as { detail?: string } | null)?.detail === 'csrf_check_failed'
  ) {
    await ensureCsrf(true);
    return request<T>(path, init, retried, true);
  }
  if (res.status === 401 && !retried) {
    if (await tryRefresh()) return request<T>(path, init, true, csrfRetried);
  }
  if (!res.ok) {
    const msg =
      (body as { detail?: string } | null)?.detail ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return body as T;
}

/* Same as request(), but for endpoints that return a file (the .ics
   export): the body is a Blob, not JSON. GET only, so no CSRF header. */
async function requestBlob(path: string, retried = false): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, { credentials: 'include' });
  if (res.status === 401 && !retried) {
    if (await tryRefresh()) return requestBlob(path, true);
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      msg = ((await res.json()) as { detail?: string }).detail ?? msg;
    } catch {
      /* keep the default message */
    }
    throw new ApiError(res.status, msg);
  }
  return res.blob();
}

/* Batch 6, N4: no token fields — tokens live in HttpOnly cookies.
   csrf_token is echoed by the backend after an auth transition so the
   frontend can update its in-memory copy. */
export interface AuthResponse {
  email: string;
  cf_handle: string | null;
  csrf_token?: string | null;
}

/* Batch 1 security: register no longer returns tokens — it returns a
   verification prompt, and login may stop at the 2FA second step. */
export interface RegisterResponse {
  email: string;
  verification_required: boolean;
  message: string;
}

/* Google sign-in callback: either the normal AuthResponse, or the
   TOTP second step (same shape as password login's totp branch). */
export type GoogleCallbackResponse =
  | AuthResponse
  | { totp_required: true; pre_token: string; email: string };

export interface LoginResponse {
  email: string;
  cf_handle?: string | null;
  csrf_token?: string | null;
  totp_required?: boolean;
  pre_token?: string;
}

export interface HandleStartResponse {
  handle: string;
  token: string;
  expires_in_minutes: number;
  fields: string[];
  message: string;
}

export interface HandlePendingResponse {
  pending: { handle: string; expires_at: string; attempts_left: number } | null;
}

export const api = {
  health: () => request<{ status: string }>(`${V1}/health`),
  register: (email: string, password: string) =>
    request<RegisterResponse>(`${V1}/auth/register`, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  verifyEmail: (email: string, code: string) =>
    request<AuthResponse>(`${V1}/auth/verify-email`, {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    }),
  resendCode: (email: string) =>
    request<{ ok: boolean; message: string }>(`${V1}/auth/resend-code`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  /* Batch 6, N2 — password recovery. */
  forgotPassword: (email: string) =>
    request<{ ok: boolean; message: string }>(`${V1}/auth/forgot-password`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, newPassword: string) =>
    request<{ ok: boolean; message: string }>(`${V1}/auth/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),
  login: (email: string, password: string) =>
    request<LoginResponse>(`${V1}/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  /* Google sign-in: the backend builds the authorization URL (the
     OAuth client lives server-side); the callback page exchanges the
     code for tokens. */
  googleAuthUrl: () =>
    request<{ auth_url: string }>(`${V1}/auth/google`),
  googleCallback: (code: string, state: string) =>
    request<GoogleCallbackResponse>(`${V1}/auth/google/callback`, {
      method: 'POST',
      body: JSON.stringify({ code, state }),
    }),
  totpVerify: (pre_token: string, code: string) =>
    request<AuthResponse>(`${V1}/auth/2fa/verify`, {
      method: 'POST',
      body: JSON.stringify({ pre_token, code }),
    }),
  totpStatus: () =>
    request<{ enabled: boolean; backup_codes_remaining: number }>(
      `${V1}/auth/2fa/status`,
    ),
  totpSetup: () =>
    request<{ secret: string; otpauth_uri: string }>(`${V1}/auth/2fa/setup`, {
      method: 'POST',
    }),
  totpEnable: (code: string) =>
    request<{ ok: boolean; backup_codes: string[] }>(`${V1}/auth/2fa/enable`, {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  totpDisable: (password: string) =>
    request<{ ok: boolean }>(`${V1}/auth/2fa/disable`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
  totpRegenerateCodes: (password: string) =>
    request<{ ok: boolean; backup_codes: string[] }>(
      `${V1}/auth/2fa/backup-codes`,
      { method: 'POST', body: JSON.stringify({ password }) },
    ),
  logout: async () => {
    try {
      return await request<{ ok: boolean }>(`${V1}/auth/logout`, {
        method: 'POST',
      });
    } finally {
      clearCsrfToken();
    }
  },
  /* Batch 6, N4 (a002's supplement): confirms whether the browser is
     blocking third-party cookies. First call sets a throwaway cookie;
     a second call checks whether it came back. */
  cookieProbe: () =>
    request<{ cookies_ok: boolean }>(`${V1}/auth/cookie-probe`),
  me: () =>
    request<{ email: string; cf_handle: string | null; current_rating: number | null }>(
      `${V1}/auth/me`,
    ),
  /* Handle verification (Batch 1 / F1): ownership proof via a profile
     token — the old direct-link endpoint is closed server-side. */
  startHandleVerification: (handle: string) =>
    request<HandleStartResponse>(`${V1}/auth/handle/start`, {
      method: 'POST',
      body: JSON.stringify({ handle }),
    }),
  pendingHandleVerification: () =>
    request<HandlePendingResponse>(`${V1}/auth/handle/pending`),
  confirmHandleVerification: (handle: string) =>
    request<{ cf_handle: string; current_rating: number | null; rank?: string }>(
      `${V1}/auth/handle/confirm`,
      { method: 'POST', body: JSON.stringify({ handle }) },
    ),
  startSync: () => request<{ job_id: number; status: string }>(`${V1}/sync`, { method: 'POST' }),
  syncStatus: () => request<SyncStatus>(`${V1}/sync/status`),
  /* Batch 5 — SSE sync stream; Batch 6, N4: the access token no longer
     travels as a ?token= query param (deleted server-side — a URL token
     lands in logs, history, and Referer). The cookie goes with
     withCredentials instead; layout.tsx opens the stream. */
  syncStreamUrl: () => `${BASE}${V1}/sync/stream`,
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

  /* Phase 3 — ML solvability prediction */
  mlStatus: () => request<MlStatus>(`${V1}/ml/status`),
  retrainModel: () =>
    request<MlStatus>(`${V1}/ml/retrain`, { method: 'POST' }),
  mlPredictions: (limit = 24) =>
    request<MlPredictionsResponse>(`${V1}/ml/predictions?limit=${limit}`),
  revisions: (tab: 'due' | 'upcoming' | 'done') =>
    request<RevisionItem[]>(`${V1}/revisions?tab=${tab}`),
  revisionCounts: () =>
    request<{ due: number; upcoming: number; done: number }>(`${V1}/revisions/counts`),
  reviewRevision: (revision_id: number, result: 'again' | 'hard' | 'good' | 'easy') =>
    request<{ ok: boolean; next_due: string; interval_days: number }>(`${V1}/revisions/review`, {
      method: 'POST',
      body: JSON.stringify({ revision_id, result }),
    }),

  /* Phase 2 — Analytics / Calendar / Weekly report / Problem detail / Settings */
  analytics: () => request<AnalyticsData>(`${V1}/analytics`),
  /* Batch 2 — failure-pattern analysis */
  failurePatterns: () => request<FailurePatternsData>(`${V1}/analytics/failures`),
  calendar: (year: number, month: number) =>
    request<CalendarMonth>(`${V1}/calendar?year=${year}&month=${month}`),
  calendarDay: (day: string) =>
    request<{ date: string; submissions: SubmissionRow[] }>(
      `${V1}/calendar/day?day=${encodeURIComponent(day)}`,
    ),
  weeklyReport: () => request<WeeklyReportData>(`${V1}/reports/weekly`),
  problemDetail: (contest_id: number, index: string) =>
    request<ProblemDetailData>(`${V1}/problems/${contest_id}/${index}`),
  getNote: (contest_id: number, index: string) =>
    request<ProblemNote>(`${V1}/problems/${contest_id}/${index}/notes`),
  saveNote: (contest_id: number, index: string, body: string) =>
    request<ProblemNote>(`${V1}/problems/${contest_id}/${index}/notes`, {
      method: 'PUT',
      body: JSON.stringify({ body }),
    }),
  getHints: (contest_id: number, index: string) =>
    request<HintsResponse>(`${V1}/problems/${contest_id}/${index}/hints`),
  requestHint: (contest_id: number, index: string, step: number, lang: string) =>
    request<HintUnlockResponse>(`${V1}/problems/${contest_id}/${index}/hints`, {
      method: 'POST',
      body: JSON.stringify({ step, lang }),
    }),
  /* Batch 4 — contest post-mortem */
  postmortems: () => request<PostmortemListItem[]>(`${V1}/postmortems`),
  latestPostmortem: () => request<PostmortemData>(`${V1}/postmortems/latest`),
  postmortem: (contest_id: number) =>
    request<PostmortemData>(`${V1}/postmortems/${contest_id}`),
  getPostmortemAnalysis: (contest_id: number) =>
    request<PostmortemAnalysisResponse>(
      `${V1}/postmortems/${contest_id}/analysis`,
    ),
  requestPostmortemAnalysis: (contest_id: number, lang: string) =>
    request<PostmortemAnalysisGenerate>(
      `${V1}/postmortems/${contest_id}/analysis`,
      {
        method: 'POST',
        body: JSON.stringify({ lang }),
      },
    ),
  settings: () => request<SettingsData>(`${V1}/settings`),
  /* Batch 5 — public profile opt-in + public profile + .ics export */
  setPublicProfile: (isPublic: boolean) =>
    request<{ public_profile: boolean }>(`${V1}/settings/public-profile`, {
      method: 'POST',
      body: JSON.stringify({ public: isPublic }),
    }),
  publicProfile: (handle: string) =>
    request<PublicProfile>(`${V1}/u/${encodeURIComponent(handle)}`),
  exportCalendarIcs: () => requestBlob(`${V1}/calendar/export.ics`),
  setGoal: (target: number) =>
    request<SettingsData>(`${V1}/settings/goal`, {
      method: 'POST',
      body: JSON.stringify({ target }),
    }),
  disconnectHandle: () =>
    request<{ ok: boolean }>(`${V1}/settings/handle`, { method: 'DELETE' }),
  deleteAccount: (password: string) =>
    request<{ ok: boolean }>(`${V1}/auth/account`, {
      method: 'DELETE',
      body: JSON.stringify({ password }),
    }),
  exportData: () => request<Record<string, unknown>>(`${V1}/export`),

  /* Demo — no auth, read-only, honestly labelled seed data. */
  demoDashboard: () => request<DashboardData>(`${V1}/demo/dashboard`),
  demoRecommendations: () => request<Recommendation[]>(`${V1}/demo/recommendations`),
  demoRevisions: () =>
    request<{ due: RevisionItem[]; upcoming: RevisionItem[]; done: RevisionItem[] }>(
      `${V1}/demo/revisions`,
    ),
  demoAnalytics: () => request<AnalyticsData>(`${V1}/demo/analytics`),
  demoFailurePatterns: () =>
    request<FailurePatternsData>(`${V1}/demo/analytics/failures`),
  demoPostmortems: () =>
    request<PostmortemListItem[]>(`${V1}/demo/postmortems`),
  demoLatestPostmortem: () =>
    request<PostmortemData>(`${V1}/demo/postmortems/latest`),
  demoPostmortem: (contest_id: number) =>
    request<PostmortemData>(`${V1}/demo/postmortems/${contest_id}`),
  demoCalendar: (year: number, month: number) =>
    request<CalendarMonth>(`${V1}/demo/calendar?year=${year}&month=${month}`),
  demoCalendarDay: (day: string) =>
    request<{ date: string; submissions: SubmissionRow[] }>(
      `${V1}/demo/calendar/day?day=${encodeURIComponent(day)}`,
    ),
  demoWeeklyReport: () => request<WeeklyReportData>(`${V1}/demo/reports/weekly`),
  demoProblemDetail: (contest_id: number, index: string) =>
    request<ProblemDetailData>(`${V1}/demo/problems/${contest_id}/${index}`),
  demoSettings: () => request<SettingsData>(`${V1}/demo/settings`),
  demoMlStatus: () => request<MlStatus>(`${V1}/demo/ml/status`),
  demoMlPredictions: (limit = 24) =>
    request<MlPredictionsResponse>(`${V1}/demo/ml/predictions?limit=${limit}`),
  demoExport: () => request<Record<string, unknown>>(`${V1}/demo/export`),
};
