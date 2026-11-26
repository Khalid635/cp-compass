/* AppShell: sidebar (240px, collapses to a bottom tab bar on mobile),
   topbar (56px) with sync status, language + theme toggles, account menu. */
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Compass,
  LayoutDashboard,
  LogOut,
  Moon,
  RefreshCw,
  RotateCw,
  Sun,
  Target,
  Zap,
} from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { formatTimeAgo, LanguageToggle, useLanguage } from '../i18n';
import type { Dict } from '../i18n/dict';
import { useAuth } from '../hooks/useAuth';
import type { Theme } from '../hooks/useTheme';
import { PaletteTrigger } from './CommandPalette';
import { Button } from './ui';

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold">
      <Compass size={size} className="text-primary" aria-hidden />
      <span className="text-base tracking-tight">CP Compass</span>
    </span>
  );
}

function navItems(base: string, t: Dict) {
  return [
    { to: base, label: t.navDashboard, icon: LayoutDashboard, end: true },
    { to: `${base}/practice`, label: t.navPractice, icon: Target },
    { to: `${base}/revision`, label: t.navRevision, icon: RotateCw },
  ];
}

function SyncChip() {
  const { t } = useLanguage();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ['sync-status'],
    queryFn: api.syncStatus,
    refetchInterval: 15000,
  });
  const sync = useMutation({
    mutationFn: api.startSync,
    onSettled: () => void qc.invalidateQueries({ queryKey: ['sync-status'] }),
  });

  /* Toast once when a running sync finishes. */
  const prevStatus = useRef<string | null>(null);
  useEffect(() => {
    if (!data) return;
    const prev = prevStatus.current;
    prevStatus.current = data.status;
    if (prev === 'running' && data.status === 'done') toast(t.toastSynced);
  }, [data, t]);

  if (!data) return null;
  if (data.status === 'running') {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-2 px-3 py-1.5 text-xs">
        <span className="pulse-dot inline-block h-2 w-2 rounded-full bg-success" />
        {data.total_synced > 0 ? t.syncingSubmissions(data.total_synced) : t.syncing}
      </span>
    );
  }
  if (data.status === 'failed') {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-danger/40 bg-danger/10 px-3 py-1.5 text-xs text-danger">
        {t.syncFailed(data.error)}
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
      {data.status === 'never'
        ? t.notSyncedYet
        : t.syncedAgo(formatTimeAgo(data.last_synced_at, t))}
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

export function DemoBanner() {
  const { t } = useLanguage();
  return (
    <div className="frost-primary sticky top-14 z-10 border-b border-primary/40 px-4 py-2.5 text-center text-sm">
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
            <Compass size={24} className="text-primary" aria-hidden />
          </Link>
          <div className="min-w-0 flex-1">
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

        {/* Bottom tab bar — mobile */}
        <nav
          className="frost sticky bottom-0 z-20 flex border-t border-border md:hidden"
          aria-label="Main"
        >
          {NAV.map((item) => (
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
      <div className="flex flex-wrap items-center justify-end gap-2">
        <PaletteTrigger />
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
