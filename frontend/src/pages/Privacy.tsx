/* Privacy — plain, honest: what is stored, what is never asked for,
   cookies/local storage, and what you can do about your data. */
import { LandingHeader } from '../components/layout';
import { useLanguage } from '../i18n';
import type { Theme } from '../hooks/useTheme';

export default function Privacy({ theme, toggleTheme }: { theme: Theme; toggleTheme: () => void }) {
  const { t } = useLanguage();
  const sections = [
    { title: t.privacyWhatTitle, text: t.privacyWhatText },
    { title: t.privacyNotTitle, text: t.privacyNotText },
    { title: t.privacyCookiesTitle, text: t.privacyCookiesText },
    { title: t.privacyRightsTitle, text: t.privacyRightsText },
  ];
  return (
    <div className="min-h-screen">
      <LandingHeader theme={theme} toggleTheme={toggleTheme} />
      <main className="mx-auto max-w-[768px] px-4 pb-16 pt-10 md:px-6">
        <h1 className="text-3xl font-semibold tracking-tight">{t.privacyTitle}</h1>
        <p className="mt-2 text-sm text-muted">{t.privacyUpdated}</p>
        <p className="mt-4 text-base text-muted">{t.privacyIntro}</p>
        <div className="mt-8 flex flex-col gap-8">
          {sections.map((s) => (
            <section key={s.title}>
              <h2 className="text-xl font-semibold tracking-tight">{s.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted sm:text-base">{s.text}</p>
            </section>
          ))}
        </div>
      </main>
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-3 px-4 py-5 md:px-6">
          <p className="text-sm font-medium">{t.builtBy}</p>
          <p className="text-xs text-muted">{t.footerNote}</p>
        </div>
      </footer>
    </div>
  );
}
