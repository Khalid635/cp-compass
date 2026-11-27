/* Landing — hero + preview, 3 feature cards, showcase, 3 steps, FAQ, roadmap.
   No fake testimonials, no fake user counts, no fake badges.
   The preview numbers match the live demo account (verified against
   /api/demo/dashboard): 1478 rating, 144 solved, 3-day streak, 3 due.
   Showcase + og images are real captures from the dev server (/demo). */
import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { Compass, GitBranch, ListChecks, Target } from 'lucide-react';
import { Button, Card } from '../components/ui';
import { LandingHeader } from '../components/layout';
import Hero3D from '../components/Hero3D';
import { formatWhy, useLanguage } from '../i18n';
import type { WhyInfo } from '../i18n/dict';
import type { Theme } from '../hooks/useTheme';

/* Static rating sparkline for the preview — the demo account's climb from
   1120 to 1478, drawn from the seeded history (illustration, not a chart). */
const SPARK_POINTS =
  '0,45 20,48 40,43 60,36 80,29 100,24 120,19 140,15 160,16 180,13 200,10 220,11 240,8 260,8';

export default function Landing({ theme, toggleTheme }: { theme: Theme; toggleTheme: () => void }) {
  const { t } = useLanguage();
  const reduceMotion = useReducedMotion();
  /* One subtle Rise & Settle entrance for the hero copy (getlayers pick:
     a single preset, headings only, 450 ms, staggered). Skipped entirely
     under prefers-reduced-motion. */
  const rise = (delay: number) =>
    reduceMotion
      ? {}
      : {
          initial: { opacity: 0, y: 12 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.45, delay, ease: 'easeOut' as const },
        };

  const FEATURES = [
    { icon: Target, title: t.feature1Title, text: t.feature1Text },
    { icon: ListChecks, title: t.feature2Title, text: t.feature2Text },
    { icon: GitBranch, title: t.feature3Title, text: t.feature3Text },
  ];

  /* Section headings fade up once on scroll into view (same 450 ms Rise &
     Settle as the hero, headings only). Skipped under reduced motion. */
  const fadeUp = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, y: 12 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, margin: '-40px' },
        transition: { duration: 0.45, ease: 'easeOut' as const },
      };

  /* Scroll-assembled hero preview (landing batch 2026-11-27): the browser
     mock settles in and the rating sparkline draws itself once, when it
     scrolls into view. GSAP/CSS only — no frame video (too heavy for
     low-end phones). Transform/opacity only, so it stays cheap on mobile.
     GSAP loads lazily (dynamic import) so it never blocks first paint.
     Skipped entirely under prefers-reduced-motion. */
  const previewRef = useRef<HTMLDivElement>(null);
  const sparkRef = useRef<SVGPolylineElement>(null);
  useEffect(() => {
    if (reduceMotion || !previewRef.current) return;
    let ctx: { revert: () => void } | undefined;
    let cancelled = false;
    (async () => {
      const gsapMod = (await import('gsap')).default;
      const { ScrollTrigger } = await import('gsap/ScrollTrigger');
      if (cancelled) return;
      gsapMod.registerPlugin(ScrollTrigger);
      ctx = gsapMod.context(() => {
        gsapMod.from(previewRef.current, {
          y: 48,
          opacity: 0,
          scale: 0.985,
          duration: 0.7,
          ease: 'power3.out',
          scrollTrigger: { trigger: previewRef.current, start: 'top 88%', once: true },
        });
        const line = sparkRef.current;
        if (line) {
          const len = line.getTotalLength();
          gsapMod.fromTo(
            line,
            { strokeDasharray: len, strokeDashoffset: len },
            {
              strokeDashoffset: 0,
              duration: 1.2,
              ease: 'power2.inOut',
              scrollTrigger: { trigger: previewRef.current, start: 'top 85%', once: true },
            },
          );
        }
      });
    })();
    return () => {
      cancelled = true;
      ctx?.revert();
    };
  }, [reduceMotion]);

  const STEPS = [
    { n: '1', title: t.step1Title, text: t.step1Text },
    { n: '2', title: t.step2Title, text: t.step2Text },
    { n: '3', title: t.step3Title, text: t.step3Text },
  ];

  /* Today's plan preview — the demo account's actual top 2, with structured
     "why" rendered in the active locale (same data as /demo). */
  const PREVIEW_PLAN: { id: string; name: string; rating: number; why: WhyInfo }[] = [
    {
      id: '1366C',
      name: 'Palindromic Paths',
      rating: 1500,
      why: { kind: 'near_rating', user_rating: 1478, problem_rating: 1500 },
    },
    {
      id: '1360E',
      name: 'Polygon',
      rating: 1300,
      why: {
        kind: 'weak_acceptance',
        tag: 'graphs',
        acceptance: 49,
        problem_rating: 1300,
        user_rating: 1478,
        demo_out_of_band: true,
      },
    },
  ];

  return (
    <div className="min-h-screen">
      <LandingHeader theme={theme} toggleTheme={toggleTheme} />

      {/* Hero — 3D compass backdrop (lazy canvas, static poster fallback) */}
      <section className="relative mx-auto max-w-[1280px] overflow-x-clip px-4 pb-14 pt-10 text-center md:px-6 md:pt-14">
        <Hero3D theme={theme} />
        <div className="relative">
          <motion.div {...rise(0)} className="mx-auto flex w-fit items-center gap-2">
            <p className="flex items-center gap-2 rounded-full border border-border bg-surface-2 px-3 py-1 text-xs text-muted">
              <Compass size={14} className="text-primary" aria-hidden />
              {t.landingBadge}
            </p>
            <p className="rounded-full border border-primary/50 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              {t.betaBadge}
            </p>
          </motion.div>
          <motion.h1
            {...rise(0.08)}
            className="hero-shimmer relative z-[1] mx-auto mt-5 max-w-[26ch] text-[clamp(2.25rem,5vw,3.5rem)] font-semibold leading-[1.1] tracking-tight"
          >
            {t.landingTitle}
          </motion.h1>
          <motion.p {...rise(0.16)} className="mx-auto mt-4 max-w-xl text-base text-muted md:text-lg">
            {t.landingSub}
          </motion.p>
          <motion.div {...rise(0.24)} className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <Link to="/demo">
              <Button className="h-11 px-6 text-base">{t.tryDemoNoLogin}</Button>
            </Link>
            <Link to="/register">
              <Button variant="secondary" className="h-11 px-6 text-base">
                {t.createAccount}
              </Button>
            </Link>
          </motion.div>

          <motion.p {...rise(0.3)} className="mt-4 text-sm text-muted">
            {t.freeLine}
          </motion.p>

          {/* Browser-frame dashboard preview (static mock, labelled as illustration) */}
          <div
            ref={previewRef}
            className="mx-auto mt-10 max-w-4xl overflow-hidden rounded-lg border border-border bg-surface text-left shadow-2xl"
          >
            <div className="flex items-center gap-1.5 border-b border-border bg-surface-2 px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-danger/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
              <span className="ml-3 font-mono text-xs text-muted">demo</span>
            </div>
            <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">
              {[
                [t.previewRating, '1478'],
                [t.previewSolved, '144'],
                [t.previewStreak, t.previewStreakValue],
                [t.previewDue, '3'],
              ].map(([label, value]) => (
                <div key={label} className="rounded-md border border-border bg-bg p-3">
                  <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
                  <p className="mt-1 font-mono text-xl font-semibold">{value}</p>
                </div>
              ))}
            </div>
            <div className="grid gap-3 px-4 pb-4 sm:grid-cols-5">
              <div className="rounded-md border border-border bg-bg p-4 sm:col-span-3">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{t.previewTodayPlan}</p>
                  <span className="rounded-full border border-border bg-surface-2 px-2 py-0.5 text-[11px] text-muted">
                    {t.demoDataChip}
                  </span>
                </div>
                {PREVIEW_PLAN.map((p) => (
                  <p key={p.id} className="mt-2 text-sm text-muted">
                    <span className="font-mono font-medium text-text">
                      {p.id} {p.name} · {p.rating}
                    </span>
                    {' — '}
                    {formatWhy(p.why, t)}
                  </p>
                ))}
              </div>
              <div className="rounded-md border border-border bg-bg p-4 sm:col-span-2">
                <p className="text-sm font-medium">{t.previewRatingTrend}</p>
                <svg
                  viewBox="0 0 260 56"
                  className="mt-2 h-14 w-full"
                  preserveAspectRatio="none"
                  aria-hidden
                >
                  <defs>
                    <linearGradient id="previewFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <polygon points={`${SPARK_POINTS} 260,56 0,56`} fill="url(#previewFill)" />
                  <polyline
                    ref={sparkRef}
                    points={SPARK_POINTS}
                    fill="none"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                </svg>
                <p className="mt-1 font-mono text-xs text-muted">1120 → 1478</p>
              </div>
            </div>
            <p className="border-t border-border px-4 py-2 text-center text-xs text-muted">
              {t.previewCaption}
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <motion.div {...fadeUp} className="grid gap-4 md:grid-cols-3">
          {FEATURES.map((f) => (
            <Card key={f.title}>
              <f.icon size={20} className="text-primary" aria-hidden />
              <h3 className="mt-3 text-base font-semibold">{f.title}</h3>
              <p className="mt-1 text-sm text-muted">{f.text}</p>
            </Card>
          ))}
        </motion.div>
      </section>

      {/* Showcase — real captures from the demo account */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
          {t.showcaseTitle}
        </motion.h2>
        <motion.p {...fadeUp} className="mt-2 max-w-2xl text-sm text-muted">
          {t.showcaseCaption}
        </motion.p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <motion.figure
            {...fadeUp}
            className="overflow-hidden rounded-lg border border-border bg-surface"
          >
            <img
              src="/showcase-dashboard.png"
              alt={t.showcaseDashboardCaption}
              loading="lazy"
              className="w-full"
            />
            <figcaption className="border-t border-border px-4 py-3 text-sm text-muted">
              {t.showcaseDashboardCaption}
            </figcaption>
          </motion.figure>
          <motion.figure
            {...fadeUp}
            className="overflow-hidden rounded-lg border border-border bg-surface"
          >
            <img
              src="/showcase-analytics.png"
              alt={t.showcaseAnalyticsCaption}
              loading="lazy"
              className="w-full"
            />
            <figcaption className="border-t border-border px-4 py-3 text-sm text-muted">
              {t.showcaseAnalyticsCaption}
            </figcaption>
          </motion.figure>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
          {t.howItWorks}
        </motion.h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {STEPS.map((s) => (
            <Card key={s.n}>
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary font-mono text-sm font-semibold text-on-primary">
                {s.n}
              </span>
              <h3 className="mt-3 text-base font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-muted">{s.text}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* FAQ — true answers only */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
          {t.faqTitle}
        </motion.h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            { q: t.faqQ1, a: t.faqA1 },
            { q: t.faqQ2, a: t.faqA2 },
            { q: t.faqQ3, a: t.faqA3 },
          ].map((f) => (
            <Card key={f.q}>
              <h3 className="text-base font-semibold">{f.q}</h3>
              <p className="mt-1 text-sm text-muted">{f.a}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Roadmap — approved Batch 2-5 items only, no dates promised */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
          {t.roadmapTitle}
        </motion.h2>
        <motion.p {...fadeUp} className="mt-2 text-sm text-muted">
          {t.roadmapNote}
        </motion.p>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            { title: t.roadmap1Title, text: t.roadmap1Text },
            { title: t.roadmap2Title, text: t.roadmap2Text },
            { title: t.roadmap3Title, text: t.roadmap3Text },
          ].map((r) => (
            <Card key={r.title}>
              <span className="rounded-full border border-primary/50 bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
                {t.comingSoon}
              </span>
              <h3 className="mt-3 text-base font-semibold">{r.title}</h3>
              <p className="mt-1 text-sm text-muted">{r.text}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Built with */}
      <section className="border-t border-border">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-4 px-4 py-8 md:px-6">
          <p className="text-sm text-muted">{t.builtWith('FastAPI', 'PostgreSQL', 'React')}</p>
          <a
            href="https://codeforces.com"
            target="_blank"
            rel="noreferrer"
            className="text-sm text-muted hover:text-primary"
          >
            codeforces.com ↗
          </a>
        </div>
      </section>

      {/* CTA + footer */}
      <footer className="border-t border-border">
        <div className="mx-auto max-w-[1280px] px-4 py-12 text-center md:px-6">
          <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
            {t.ctaTitle}
          </motion.h2>
          <div className="mt-6 flex justify-center gap-3">
            <Link to="/demo">
              <Button className="h-11 px-6 text-base">{t.tryDemo}</Button>
            </Link>
            <Link to="/register">
              <Button variant="secondary" className="h-11 px-6 text-base">
                {t.createAccount}
              </Button>
            </Link>
          </div>
          <p className="mt-8 text-xs text-muted">{t.footerNote}</p>
          <p className="mt-3 text-xs">
            <a
              href="https://github.com/Khalid635/cp-compass"
              target="_blank"
              rel="noreferrer"
              className="text-muted hover:text-primary"
            >
              {t.githubLink} ↗
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
