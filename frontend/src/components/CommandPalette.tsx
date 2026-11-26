/* ⌘K command palette (cmdk) — the "/" search dialog. Opens with "/" or
   Cmd/Ctrl+K from anywhere, Esc closes, arrow keys navigate. Groups:
   Pages, Actions (Sync now, theme, language, demo/home) and Problems
   (today's plan + recent submissions, from the dashboard data). Selecting
   a problem opens it on Codeforces. One component covers both the palette
   and the "/" search dialog — there is no separate search UI. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Command } from 'cmdk';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Compass,
  Home,
  LayoutDashboard,
  Moon,
  RefreshCw,
  RotateCw,
  Search,
  Sun,
  Target,
} from 'lucide-react';
import { api } from '../api/client';
import { cfUrl, rankOf } from '../api/types';
import type { ProblemRef } from '../api/types';
import { useLanguage } from '../i18n';
import type { Theme } from '../hooks/useTheme';

/* ---------- context: any topbar button can open the palette ---------- */
interface PaletteState {
  openPalette: () => void;
}

const PaletteContext = createContext<PaletteState | null>(null);

export function usePalette(): PaletteState {
  const ctx = useContext(PaletteContext);
  if (!ctx) throw new Error('usePalette must be used inside PaletteProvider');
  return ctx;
}

export function PaletteProvider({
  children,
  theme,
  toggleTheme,
}: {
  children: ReactNode;
  theme: Theme;
  toggleTheme: () => void;
}) {
  const [open, setOpen] = useState(false);
  const openPalette = useCallback(() => setOpen(true), []);
  const value = useMemo(() => ({ openPalette }), [openPalette]);
  return (
    <PaletteContext.Provider value={value}>
      {children}
      <CommandPaletteInner open={open} setOpen={setOpen} theme={theme} toggleTheme={toggleTheme} />
    </PaletteContext.Provider>
  );
}

/** Small search trigger for the topbar / landing header. */
export function PaletteTrigger() {
  const { t } = useLanguage();
  const { openPalette } = usePalette();
  return (
    <button
      type="button"
      onClick={openPalette}
      title={t.paletteSearchHint}
      aria-label={t.paletteSearchHint}
      className="hidden h-9 cursor-pointer items-center gap-2 rounded-md border border-border bg-surface-2 px-3 text-sm text-muted transition-colors hover:bg-hover hover:text-text sm:flex"
    >
      <Search size={15} aria-hidden />
      <span className="kbd">/</span>
    </button>
  );
}

function CommandPaletteInner({
  open,
  setOpen,
  theme,
  toggleTheme,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  theme: Theme;
  toggleTheme: () => void;
}) {
  const { t, lang, setLang } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();

  const inApp = location.pathname.startsWith('/app') || location.pathname.startsWith('/demo');
  const base = location.pathname.startsWith('/demo') ? '/demo' : '/app';

  // "/" or Cmd/Ctrl+K opens from anywhere (unless typing in a field).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.isContentEditable;
      if (typing) return;
      if (e.key === '/' || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setOpen]);

  // Problems come from the dashboard data, only while inside the app/demo.
  const dashQuery = useQuery({
    queryKey: base === '/demo' ? ['demo-dashboard'] : ['dashboard'],
    queryFn: base === '/demo' ? api.demoDashboard : api.dashboard,
    enabled: open && inApp,
    staleTime: 60_000,
  });

  const problems = useMemo(() => {
    const d = dashQuery.data;
    if (!d) return [];
    const seen = new Set<string>();
    const out: ProblemRef[] = [];
    for (const p of d.today_plan.problems) {
      const key = `${p.contest_id}${p.index}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(p);
    }
    for (const r of d.recent) {
      const key = `${r.problem.contest_id}${r.problem.index}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(r.problem);
    }
    return out.slice(0, 8);
  }, [dashQuery.data]);

  const go = (to: string) => {
    setOpen(false);
    navigate(to);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label={t.palettePlaceholder}
      shouldFilter
    >
      <Command.Input placeholder={t.palettePlaceholder} autoFocus />
      <Command.List>
        <Command.Empty>{t.paletteNoResults}</Command.Empty>
        <Command.Group heading={t.palettePages}>
          <Command.Item onSelect={() => go(base)}>
            <LayoutDashboard size={16} aria-hidden /> {t.navDashboard}
          </Command.Item>
          <Command.Item onSelect={() => go(`${base}/practice`)}>
            <Target size={16} aria-hidden /> {t.navPractice}
          </Command.Item>
          <Command.Item onSelect={() => go(`${base}/revision`)}>
            <RotateCw size={16} aria-hidden /> {t.navRevision}
          </Command.Item>
        </Command.Group>
        <Command.Group heading={t.paletteActions}>
          {inApp && base === '/app' && (
            <Command.Item
              onSelect={() => {
                setOpen(false);
                void api.startSync();
              }}
            >
              <RefreshCw size={16} aria-hidden /> {t.syncNow}
            </Command.Item>
          )}
          <Command.Item
            onSelect={() => {
              setOpen(false);
              setLang(lang === 'en' ? 'bn' : 'en');
            }}
          >
            <Compass size={16} aria-hidden /> {t.paletteSwitchLanguage}
          </Command.Item>
          <Command.Item
            onSelect={() => {
              setOpen(false);
              toggleTheme();
            }}
          >
            {theme === 'dark' ? <Sun size={16} aria-hidden /> : <Moon size={16} aria-hidden />}{' '}
            {t.paletteToggleTheme}
          </Command.Item>
          <Command.Item onSelect={() => go('/demo')}>
            <Compass size={16} aria-hidden /> {t.paletteGoDemo}
          </Command.Item>
          <Command.Item onSelect={() => go('/')}>
            <Home size={16} aria-hidden /> {t.paletteGoHome}
          </Command.Item>
        </Command.Group>
        {problems.length > 0 && (
          <Command.Group heading={t.paletteProblems}>
            {problems.map((p) => (
              <Command.Item
                key={`${p.contest_id}${p.index}`}
                value={`${p.contest_id}${p.index} ${p.name} ${p.tags.join(' ')}`}
                onSelect={() => {
                  setOpen(false);
                  window.open(cfUrl(p), '_blank', 'noreferrer');
                }}
              >
                <span className="font-mono text-xs text-muted">
                  {p.contest_id}
                  {p.index}
                </span>
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
                {p.rating !== null && (
                  <span
                    className="shrink-0 font-mono text-xs"
                    style={{ color: rankOf(p.rating).token }}
                  >
                    {p.rating}
                  </span>
                )}
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
      <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[11px] text-muted">
        <span>
          <span className="kbd">↑↓</span> {t.paletteNavigate}
        </span>
        <span>
          <span className="kbd">↵</span> {t.paletteOpen}
        </span>
        <span>
          <span className="kbd">esc</span> {t.paletteClose}
        </span>
      </div>
    </Command.Dialog>
  );
}
