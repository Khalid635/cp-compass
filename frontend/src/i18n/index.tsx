/* Language state: EN default, persisted in localStorage, overridable with
   ?lang=en|bn (handy for screenshots). The <html lang> attribute follows,
   so screen readers and the Bengali font pick the right language. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { bn } from './bn';
import type { Dict, Locale, WhyInfo } from './dict';
import { en } from './en';

const STORAGE_KEY = 'cp_lang';

function initialLang(): Locale {
  if (typeof window !== 'undefined') {
    const q = new URLSearchParams(window.location.search).get('lang');
    if (q === 'bn' || q === 'en') return q;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'bn' || saved === 'en') return saved;
  }
  return 'en';
}

interface LanguageState {
  lang: Locale;
  setLang: (l: Locale) => void;
  t: Dict;
}

const LanguageContext = createContext<LanguageState | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Locale>(initialLang);

  const setLang = useCallback((l: Locale) => {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
    document.documentElement.lang = l;
  }, []);

  // ?lang= in the URL wins once and is remembered.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('lang');
    if (q === 'bn' || q === 'en') localStorage.setItem(STORAGE_KEY, q);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const t = lang === 'bn' ? bn : en;
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageState {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used inside LanguageProvider');
  return ctx;
}

/** EN | বাংলা segmented toggle. */
export function LanguageToggle() {
  const { lang, setLang, t } = useLanguage();
  const btn = (active: boolean) =>
    `h-7 cursor-pointer rounded px-2 text-xs font-medium transition-colors ${
      active ? 'bg-primary text-on-primary' : 'text-muted hover:text-text'
    }`;
  return (
    <div
      className="flex items-center rounded-md border border-border bg-surface-2 p-0.5"
      role="group"
      aria-label={t.switchLanguage}
    >
      <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')} className={btn(lang === 'en')}>
        EN
      </button>
      <button type="button" aria-pressed={lang === 'bn'} onClick={() => setLang('bn')} className={btn(lang === 'bn')}>
        বাংলা
      </button>
    </div>
  );
}

/** Render the backend's structured "why" in the active locale. */
export function formatWhy(why: WhyInfo, t: Dict): string {
  let s: string;
  switch (why.kind) {
    case 'weak_acceptance':
      s = t.whyWeakAcceptance(why.tag ?? '', why.acceptance ?? 0, why.problem_rating);
      break;
    case 'weak_wrong':
      s = t.whyWeakWrong(why.tag ?? '', why.avg_wrong_attempts ?? 0, why.problem_rating);
      break;
    default:
      s = t.whyNearRating(why.user_rating, why.problem_rating);
  }
  return s;
}

export function formatTimeAgo(iso: string | null, t: Dict): string {
  if (!iso) return t.never;
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return t.justNow;
  if (s < 3600) return t.minAgo(Math.floor(s / 60));
  if (s < 86400) return t.hoursAgo(Math.floor(s / 3600));
  return t.daysAgo(Math.floor(s / 86400));
}

/** Dates use the active locale; Bengali keeps Latin digits (nu-latn) so they
    match the mono numerals used everywhere else. */
export function formatDateTime(iso: string, lang: Locale): string {
  return new Intl.DateTimeFormat(lang === 'bn' ? 'bn-u-nu-latn' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso));
}

export function formatDate(iso: string, lang: Locale): string {
  return new Intl.DateTimeFormat(lang === 'bn' ? 'bn-u-nu-latn' : 'en-GB', {
    day: 'numeric',
    month: 'short',
  }).format(new Date(iso));
}
