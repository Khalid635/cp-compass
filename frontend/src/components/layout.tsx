/* AppShell: sidebar (240px, collapses to a bottom tab bar on mobile),
   topbar (56px) with sync status, language + theme toggles, account menu. */
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  BarChart3,
  CalendarDays,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  Moon,
  RefreshCw,
  RotateCw,
  Settings,
  Sun,
  Target,
  Users,
  Zap,
} from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { SyncStatus } from '../api/types';
import { formatTimeAgo, LanguageToggle, useLanguage } from '../i18n';
import type { Dict } from '../i18n/dict';
import { useAuth } from '../hooks/useAuth';
import type { Theme } from '../hooks/useTheme';
import { PaletteTrigger } from './CommandPalette';
import { Button } from './ui';

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold">
      <img src="/favicon.svg" width={size} height={size} alt="" aria-hidden className="shrink-0" />
      <span className="font-display text-base">CP Compass</span>
    </span>
  );
}

function navItems(base: string, t: Dict) {
  return [
    { to: base, label: t.navDashboard, icon: LayoutDashboard, end: true, mobile: true },
    { to: `${base}/practice`, label: t.navPractice, icon: Target, mobile: true },
    { to: `${base}/revision`, label: t.navRevision, icon: RotateCw, mobile: true },
    { to: `${base}/analytics`, label: t.navAnalytics, icon: BarChart3, mobile: false },
    { to: `${base}/calendar`, label: t.navCalendar, icon: CalendarDays, mobile: true },
    { to: `${base}/reports/weekly`, label: t.navWeekly, icon: FileText, mobile: false },
    { to: `${base}/postmortems`, label: t.navPostmortems, icon: History, mobile: false },
    { to: `${base}/compare`, label: t.navCompare, icon: Users, mobile: false },
    { to: `${base}/settings`, label: t.navSettings, icon: Settings, mobile: true },
  ];
}

/* Batch 5 — SSE sync progress: while a sync runs, an EventSource
   streams live progress (total_synced) instead of the 15 s poll.
   Batch 6, N4: the access token no longer travels as ?token= — the
   cookie goes with withCredentials. On a stream error the chip
   reconnects with backoff (a010: 1s -> 2s -> 5s cap, max 5 attempts
   per sync), refreshing the session once via api.me(); after that the
   poll is the fallback and the source of truth, so a stale live state
   can never mask a finished sync. */
function SyncChip() {
  const { t } = useLanguage();
  const qc = useQueryClient();
  const [live, setLive] = useState<SyncStatus | null>(null);
  const [streaming, setStreaming] = useState(false);
  const { data } = useQuery({
    queryKey: ['sync-status'],
    queryFn: api.syncStatus,
    refetchInterval: streaming ? false : 15000,
  });
  const sync = useMutation({
    mutationFn: api.startSync,
    onSettled: () => void qc.invalidateQueries({ queryKey: ['sync-status'] }),
  });

  useEffect(() => {
    if (!data) return;
    if (data.status !== 'pending' && data.status !== 'running') {
      setLive(null);
      setStreaming(false);
      return;
    }
    setLive(null); // a stale live state must not mask the new sync
    if (typeof EventSource === 'undefined') return; // poll fallback
    const url = api.syncStreamUrl();
    setStreaming(true);
    let closed = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let es: EventSource | null = null;
    const open = () => {
      if (closed) return;
      es = new EventSource(url, { withCredentials: true });
      const onEvent = (e: MessageEvent) => {
        try {
          setLive(JSON.parse(e.data) as SyncStatus);
        } catch {
          /* ignore a malformed event; the poll still refreshes */
        }
      };
      es.addEventListener('state', onEvent);
      es.addEventListener('progress', onEvent);
      es.addEventListener('done', (e: MessageEvent) => {
        onEvent(e);
        es?.close();
        setStreaming(false);
        void qc.invalidateQueries({ queryKey: ['sync-status'] });
        void qc.invalidateQueries({ queryKey: ['dashboard'] });
      });
      es.addEventListener('failed', (e: MessageEvent) => {
        onEvent(e);
        es?.close();
        setStreaming(false);
        void qc.invalidateQueries({ queryKey: ['sync-status'] });
      });
      es.onerror = () => {
        es?.close();
        if (closed) return;
        if (attempts >= 5) {
          setStreaming(false); // fall back to the 15 s poll
          return;
        }
        attempts += 1;
        const delay = Math.min(1000 * 2 ** (attempts - 1), 5000);
        timer = setTimeout(() => {
          // A 401 (expired cookie) refreshes once via api.me() — if
          // the session is alive the stream reopens, else the poll
          // fallback covers progress.
          void api.me().then(
            () => {
              if (!closed) open();
            },
            () => setStreaming(false),
          );
        }, delay);
      };
    };
    open();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      es?.close();
      setStreaming(false);
    };
    // Re-open only when the poll first reports a running sync.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.status]);

  const status = live ?? data;

  /* Toast once when a running sync finishes. */
  const prevStatus = useRef<string | null>(null);
  useEffect(() => {
    if (!status) return;
    const prev = prevStatus.current;
    prevStatus.current = status.status;
    if (prev === 'running' && status.status === 'done') toast(t.toastSynced);
  }, [status, t]);

  if (!status) return null;
  if (status.status === 'running') {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-2 px-3 py-1.5 text-xs">
        <span className="pulse-dot inline-block h-2 w-2 rounded-full bg-success" />
        {status.total_synced > 0 ? t.syncingSubmissions(status.total_synced) : t.syncing}
      </span>
    );
  }
  if (status.status === 'failed') {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-danger/40 bg-danger/10 px-3 py-1.5 text-xs text-danger">
        {t.syncFailed(status.error)}
        <button
          onClick={() => sync.mutate()}
          className="cursor-pointer font-medium underline"
        >
          {t.retry}
        </button>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-2 px-3 py-1.5 text-xs text-muted">
      <span className="inline-block h-2 w-2 rounded-full bg-success" />
      {status.status === 'never'
        ? t.notSyncedYet
        : t.syncedAgo(formatTimeAgo(status.last_synced_at, t))}
      <button
        onClick={() => sync.mutate()}
        disabled={sync.isPending}
        className="inline-flex cursor-pointer items-center gap-1 font-medium text-text hover:text-primary disabled:opacity-50"
      >
        <RefreshCw size={12} aria-hidden /> {t.syncNow}
      </button>
    </span>
  );
}

/* Batch 5 — offline pill: shows in the app shell whenever the browser
   reports offline (online/offline events). The PWA shell still loads;
   data views show their own offline state. */
function OfflinePill() {
  const { t } = useLanguage();
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine,
  );
  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);
  if (online) return null;
  return (
    <span
      role="status"
      className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary"
    >
      {t.pwaOffline}
    </span>
  );
}

export function ColdStartBanner() {
  const { t } = useLanguage();
  return (
    <div
      className="banner-enter border-b border-border bg-surface px-4 py-3"
      role="status"
    >
      <p className="text-center text-sm">{t.coldStart}</p>
      <div className="mx-auto mt-2 h-1 max-w-xs overflow-hidden rounded-full bg-surface-2">
        <div className="skeleton h-full w-full" />
      </div>
    </div>
  );
}

/* Demo banner — in-flow, NOT sticky: the sticky version slid over the
   "Topic goals" heading and the topic-strength chart while scrolling
   (translucent frost made the covered text look broken). It scrolls away
   with the page; the "Demo mode" pill in the topbar keeps demo labelled
   persistently. (Colour-fix 2026-11-27.) */
export function DemoBanner() {
  const { t } = useLanguage();
  return (
    <div className="frost-primary border-b border-primary/40 px-4 py-2.5 text-center text-sm">
      {t.demoBanner}{' '}
      <Link to="/login" className="font-medium underline">
        {t.createAccount}
      </Link>
    </div>
  );
}

export function AppShell({
  children,
  theme,
  toggleTheme,
  demo = false,
  base = '/app',
}: {
  children: ReactNode;
  theme: Theme;
  toggleTheme: () => void;
  demo?: boolean;
  base?: string;
}) {
  const { t } = useLanguage();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const NAV = navItems(base, t);

  // Close the account menu on navigation.
  useEffect(() => setMenuOpen(false), [location.pathname]);

  return (
    <div className="flex min-h-screen">
      {/* Sidebar — desktop */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-surface px-3 py-4 md:flex">
        <Link to={base} className="px-2 py-1 hover:no-underline">
          <Logo />
        </Link>
        <nav className="mt-6 flex flex-col gap-1" aria-label="Main">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-hover hover:no-underline ${
                  isActive ? 'bg-active text-text' : 'text-muted'
                }`
              }
            >
              <item.icon size={18} aria-hidden />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-3 text-xs text-muted">
          <p>{t.sidebarNote1}</p>
          <p className="mt-1">{t.sidebarNote2}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header className="frost sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border px-4 md:gap-3 md:px-6">
          <Link to={base} className="md:hidden hover:no-underline">
            <img src="/favicon.svg" width={24} height={24} alt="" aria-hidden className="shrink-0" />
          </Link>
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            <OfflinePill />
            {demo ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary">
                <Zap size={12} aria-hidden /> {t.demoMode}
              </span>
            ) : (
              <SyncChip />
            )}
          </div>
          <PaletteTrigger />
          <LanguageToggle />
          <button
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? t.switchToLight : t.switchToDark}
            className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-md border border-border bg-surface-2 text-muted transition-colors hover:bg-hover hover:text-text"
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          {!demo && user && (
            <div className="relative">
              <button
                onClick={() => setMenuOpen((o) => !o)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-full bg-primary font-mono text-sm font-semibold text-on-primary"
                title={user.email}
              >
                {user.email[0]?.toUpperCase()}
              </button>
              {menuOpen && (
                <div
                  role="menu"
                  className="frost absolute right-0 mt-2 w-56 rounded-lg border border-border p-2 shadow-lg"
                >
                  <p className="truncate px-2 py-1.5 text-xs text-muted">{user.email}</p>
                  {user.cf_handle && (
                    <p className="px-2 pb-1.5 font-mono text-xs text-muted">
                      {t.cfHandleLine(user.cf_handle)}
                    </p>
                  )}
                  <Link
                    to={`${base}/settings`}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-text hover:bg-hover hover:no-underline"
                  >
                    <Settings size={14} aria-hidden /> {t.navSettings}
                  </Link>
                  <button
                    onClick={() => {
                      logout();
                      navigate('/');
                    }}
                    className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm text-danger hover:bg-hover"
                  >
                    <LogOut size={14} aria-hidden /> {t.logOut}
                  </button>
                </div>
              )}
            </div>
          )}
        </header>

        {demo && <DemoBanner />}

        <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-6 md:px-6">
          {children}
        </main>

        {/* Bottom tab bar — mobile. Five primary pages; Analytics and the
            Weekly report live in the sidebar on desktop, in the "/" palette
            and in Dashboard links on mobile. */}
        <nav
          className="frost sticky bottom-0 z-20 flex border-t border-border md:hidden"
          aria-label="Main"
        >
          {NAV.filter((item) => item.mobile).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium hover:no-underline ${
                  isActive ? 'text-primary' : 'text-muted'
                }`
              }
            >
              <item.icon size={20} aria-hidden />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}

export function LandingHeader({ theme, toggleTheme }: { theme: Theme; toggleTheme: () => void }) {
  const { t } = useLanguage();
  return (
    <header className="mx-auto flex min-h-14 w-full max-w-[1280px] flex-wrap items-center justify-between gap-x-2 gap-y-2 px-4 py-2 md:px-6">
      <Link to="/" className="hover:no-underline">
        <Logo />
      </Link>
      {/* In-page anchors (landing v2). The "/" palette trigger was removed
          here — search belongs to the app, not the landing page. */}
      <nav className="hidden items-center gap-1 md:flex" aria-label="Landing">
        <a
          href="#features"
          className="rounded-md px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-hover hover:text-text hover:no-underline"
        >
          {t.navFeatures}
        </a>
        <a
          href="#showcase"
          className="rounded-md px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-hover hover:text-text hover:no-underline"
        >
          {t.navDemo}
        </a>
        <a
          href="#faq"
          className="rounded-md px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-hover hover:text-text hover:no-underline"
        >
          {t.navFaq}
        </a>
      </nav>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <a
          href="https://github.com/Khalid635/cp-compass"
          target="_blank"
          rel="noreferrer"
          className="flex h-9 items-center rounded-md border border-border bg-surface-2 px-3 text-sm font-medium text-muted transition-colors hover:bg-hover hover:text-text hover:no-underline"
        >
          {t.githubLink} ↗
        </a>
        <LanguageToggle />
        <button
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? t.switchToLight : t.switchToDark}
          className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-md border border-border bg-surface-2 text-muted transition-colors hover:bg-hover hover:text-text"
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <Link to="/login">
          <Button variant="ghost">{t.login}</Button>
        </Link>
        <Link to="/demo">
          <Button>{t.tryDemo}</Button>
        </Link>
      </div>
    </header>
  );
}
