/* Landing — hero + preview, features, showcase, how it works, "Why this
   problem?" score breakdown, FAQ, roadmap, CTA + footer.
   No fake testimonials, no fake user counts, no fake badges.
   The preview numbers are a snapshot of the live demo account
   (/api/demo/dashboard, 2026-11-27): 1478 rating, 138 solved, 2-day
   streak, 3 due. They drift as the demo seed ages (the streak is
   date-relative) — update them when they visibly disagree with /demo.
   Showcase + og images are real captures from the dev server (/demo).
   The "Why this problem?" totals use the production formula on demo
   data (see WHY_PICKS) — demo pages show a simplified mirror score. */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { Compass, GitBranch, ListChecks, Target, X } from 'lucide-react';
import { Button, Card, Tabs } from '../components/ui';
import { LandingHeader } from '../components/layout';
import Hero3D from '../components/Hero3D';
import { formatWhy, useLanguage } from '../i18n';
import type { WhyInfo } from '../i18n/dict';
import type { Theme } from '../hooks/useTheme';

/* Static rating sparkline for the preview — the demo account's climb from
   1120 to 1478, drawn from the seeded history (illustration, not a chart). */
const SPARK_POINTS =
  '0,45 20,48 40,43 60,36 80,29 100,24 120,19 140,15 160,16 180,13 200,10 220,11 240,8 260,8';

/* "Why this problem?" — real-formula breakdowns for the demo account's top
   3 picks. Computed 2026-11-27 from the deterministic demo seed
   (backend/app/seed.py) with the production formula in
   backend/app/services.py recommend(): Score = 0.35W + 0.30D + 0.20R +
   0.15P, totals rounded. W/D/R/P are 0–100; the points column is
   weight × value. The demo account that day: rating 1478, dp the only
   weak tag (weak_score 0.566, acceptance 45%, recent acceptance 27%),
   difficulty target 1578. NOTE: demo pages show a simplified mirror
   score (55 base + 25 weak-tag bonus + closeness: 67/80/55), so these
   production totals differ — same order, different scale. 1360E/1367C
   sit below the real recommender's band (1300 < 1478); the demo tops up
   with below-band practice for a weak tag. */
const WHY_PICKS: {
  id: string;
  name: string;
  rating: number;
  why: WhyInfo;
  w: number;
  d: number;
  r: number;
  p: number;
  total: number;
}[] = [
  {
    id: '1366C',
    name: 'Palindromic Paths',
    rating: 1500,
    why: { kind: 'near_rating', user_rating: 1478, problem_rating: 1500 },
    w: 0,
    d: 61,
    r: 50,
    p: 60,
    total: 37,
  },
  {
    id: '1360E',
    name: 'Polygon',
    rating: 1300,
    why: {
      kind: 'weak_acceptance',
      tag: 'dp',
      acceptance: 45,
      problem_rating: 1300,
      user_rating: 1478,
      demo_out_of_band: true,
    },
    w: 56.6,
    d: 0,
    r: 73,
    p: 60,
    total: 43,
  },
  {
    id: '1367C',
    name: 'Social Distance',
    rating: 1300,
    why: {
      kind: 'near_rating',
      user_rating: 1478,
      problem_rating: 1300,
      demo_out_of_band: true,
    },
    w: 0,
    d: 0,
    r: 50,
    p: 60,
    total: 19,
  },
];

export default function Landing({ theme, toggleTheme }: { theme: Theme; toggleTheme: () => void }) {
  const { t } = useLanguage();
  const reduceMotion = useReducedMotion();
  /* One subtle Rise & Settle entrance for the hero copy (getlayers pick:
     a single preset, headings only, 300 ms, staggered). Starts at 60%
     opacity so the first paint is never washed out (colour-fix 2026-11-27).
     Skipped entirely under prefers-reduced-motion. */
  const rise = (delay: number) =>
    reduceMotion
      ? {}
      : {
          initial: { opacity: 0.6, y: 6 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.3, delay, ease: 'easeOut' as const },
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
     "why" rendered in the active locale (same data as /demo). The 1360E
     "why" matches the live demo recommendations (dp, 45%) — the v1 copy
     said graphs/49%, which was wrong. */
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
        tag: 'dp',
        acceptance: 45,
        problem_rating: 1300,
        user_rating: 1478,
        demo_out_of_band: true,
      },
    },
  ];

  /* Showcase tabs + lightbox (landing v2). One big screenshot at a time;
     click to zoom. Esc or backdrop click closes. */
  const [showTab, setShowTab] = useState<'dashboard' | 'analytics'>('dashboard');
  const [zoom, setZoom] = useState<null | 'dashboard' | 'analytics'>(null);
  useEffect(() => {
    if (!zoom) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setZoom(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoom]);
  const showSrc = showTab === 'dashboard' ? '/showcase-dashboard.png' : '/showcase-analytics.png';
  const showCaption =
    showTab === 'dashboard' ? t.showcaseDashboardCaption : t.showcaseAnalyticsCaption;
  const zoomSrc = zoom === 'dashboard' ? '/showcase-dashboard.png' : '/showcase-analytics.png';
  const zoomCaption =
    zoom === 'dashboard' ? t.showcaseDashboardCaption : t.showcaseAnalyticsCaption;

  const whyFactors = (p: (typeof WHY_PICKS)[number]) =>
    [
      { label: t.whyW, weight: 0.35, value: p.w },
      { label: t.whyD, weight: 0.3, value: p.d },
      { label: t.whyR, weight: 0.2, value: p.r },
      { label: t.whyP, weight: 0.15, value: p.p },
    ] as const;

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
            {/* Beta badge: bg-surface, NOT bg-primary/10 — primary text on
                the 10% tint fails contrast in light mode (4.47:1, checked
                2026-11-27); on surface it passes in both themes. */}
            <p className="rounded-full border border-primary/50 bg-surface px-3 py-1 text-xs font-semibold text-primary">
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
                [t.previewSolved, '138'],
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

      {/* Features — banded, to break the 3-card-grid monotony */}
      <section id="features" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-[1280px] px-4 py-16 md:px-6">
          <motion.div {...fadeUp} className="grid gap-4 md:grid-cols-3">
            {FEATURES.map((f) => (
              <Card key={f.title}>
                <f.icon size={20} className="text-primary" aria-hidden />
                <h3 className="mt-3 text-base font-semibold">{f.title}</h3>
                <p className="mt-1 text-sm text-muted">{f.text}</p>
              </Card>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Showcase — real captures from the demo account, tabbed + zoomable */}
      <section id="showcase" className="mx-auto max-w-[1280px] px-4 pb-16 pt-16 md:px-6">
        <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
          {t.showcaseTitle}
        </motion.h2>
        <motion.p {...fadeUp} className="mt-2 max-w-2xl text-sm text-muted">
          {t.showcaseCaption}
        </motion.p>
        <div className="mt-6">
          <Tabs
            tabs={[
              { id: 'dashboard', label: t.navDashboard },
              { id: 'analytics', label: t.navAnalytics },
            ]}
            active={showTab}
            onChange={setShowTab}
          />
          <motion.figure
            key={showTab}
            {...fadeUp}
            className="mt-4 overflow-hidden rounded-lg border border-border bg-surface"
          >
            <button
              onClick={() => setZoom(showTab)}
              title={t.showcaseZoom}
              aria-label={`${showCaption} — ${t.showcaseZoom}`}
              className="block w-full cursor-zoom-in"
            >
              <img src={showSrc} alt={showCaption} loading="lazy" className="w-full" />
            </button>
            <figcaption className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3 text-sm text-muted">
              <span>{showCaption}</span>
              <span className="text-xs">{t.showcaseZoom}</span>
            </figcaption>
          </motion.figure>
        </div>
        {zoom && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label={zoomCaption}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4"
            onClick={() => setZoom(null)}
          >
            <button
              onClick={() => setZoom(null)}
              aria-label={t.lightboxClose}
              autoFocus
              className="absolute right-4 top-4 flex h-10 w-10 cursor-pointer items-center justify-center rounded-md border border-border bg-surface text-text"
            >
              <X size={20} aria-hidden />
            </button>
            <img
              src={zoomSrc}
              alt={zoomCaption}
              className="max-h-[90vh] max-w-full rounded-lg border border-border"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}
      </section>

      {/* How it works — numbered steps, no card chrome (varied treatment) */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
          {t.howItWorks}
        </motion.h2>
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          {STEPS.map((s) => (
            <motion.div
              key={s.n}
              {...fadeUp}
              className="border-t-2 border-primary/60 pt-4"
            >
              <span className="font-mono text-2xl font-semibold text-primary">{s.n}</span>
              <h3 className="mt-2 text-base font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-muted">{s.text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Why this problem? — the score breakdown, real formula, demo data */}
      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-[1280px] px-4 py-16 md:px-6">
          <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
            {t.whyTitle}
          </motion.h2>
          <motion.p {...fadeUp} className="mt-2 max-w-2xl text-sm text-muted">
            {t.whyCaption}
          </motion.p>
          <motion.p {...fadeUp} className="mt-2 font-mono text-sm text-primary">
            {t.whyFormula}
          </motion.p>
          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {WHY_PICKS.map((p) => (
              <motion.div
                key={p.id}
                {...fadeUp}
                className="rounded-lg border border-border bg-bg p-4 sm:p-5"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="font-mono text-base font-semibold">
                    {p.id} {p.name} · {p.rating}
                  </h3>
                  <p className="font-mono text-sm">
                    <span className="text-muted">{t.whyTotal} </span>
                    <span className="text-xl font-semibold text-primary">{p.total}</span>
                    <span className="text-muted"> / 100</span>
                  </p>
                </div>
                <p className="mt-1 text-sm text-muted">{formatWhy(p.why, t)}</p>
                <div className="mt-4 flex flex-col gap-2.5">
                  {whyFactors(p).map((f) => (
                    <div
                      key={f.label}
                      className="grid grid-cols-[6.5rem_1fr_auto] items-center gap-3 sm:grid-cols-[9rem_1fr_auto]"
                    >
                      <span className="text-xs text-muted sm:text-sm">
                        {f.label}{' '}
                        <span className="font-mono text-[11px]">×{f.weight.toFixed(2)}</span>
                      </span>
                      <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${f.value}%` }}
                        />
                      </div>
                      <span className="font-mono text-xs tabular-nums sm:text-sm">
                        {f.value.toFixed(1)}{' '}
                        <span className="text-muted">→ +{(f.weight * f.value).toFixed(1)}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
          <motion.p {...fadeUp} className="mt-6 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="rounded-full border border-border bg-surface-2 px-2 py-0.5 text-[11px]">
              {t.demoDataChip}
            </span>
            {t.whyFootnote}
          </motion.p>
        </div>
      </section>

      {/* FAQ — true answers only, as accordions */}
      <section id="faq" className="mx-auto max-w-[1280px] px-4 pb-16 pt-16 md:px-6">
        <motion.h2 {...fadeUp} className="text-2xl font-semibold tracking-tight">
          {t.faqTitle}
        </motion.h2>
        <div className="mt-6 flex flex-col gap-3">
          {[
            { q: t.faqQ1, a: t.faqA1 },
            { q: t.faqQ2, a: t.faqA2 },
            { q: t.faqQ3, a: t.faqA3 },
          ].map((f) => (
            <motion.details
              key={f.q}
              {...fadeUp}
              className="rounded-lg border border-border bg-surface px-4 py-3"
            >
              <summary className="cursor-pointer text-base font-semibold">{f.q}</summary>
              <p className="mt-2 text-sm text-muted">{f.a}</p>
            </motion.details>
          ))}
        </div>
      </section>

      {/* Roadmap — approved Batch 2-5 items only, no dates promised */}
      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-[1280px] px-4 py-16 md:px-6">
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
        </div>
      </section>

      {/* Built with + under the hood */}
      <section className="border-t border-border">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-4 px-4 py-8 md:px-6">
          <div>
            <p className="text-sm text-muted">{t.builtWith('React', 'FastAPI', 'PostgreSQL')}</p>
            <p className="mt-1 text-sm text-muted">{t.underHood}</p>
          </div>
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

      {/* CTA + footer — tightened: no more empty black space below the CTA */}
      <footer className="border-t border-border">
        <div className="mx-auto max-w-[1280px] px-4 py-8 text-center md:px-6">
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
        </div>
        <div className="border-t border-border">
          <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-3 px-4 py-5 md:px-6">
            <p className="text-sm font-medium">{t.builtBy}</p>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <a
                href="https://github.com/Khalid635/cp-compass"
                target="_blank"
                rel="noreferrer"
                className="font-medium text-primary hover:underline"
              >
                {t.githubLink} ↗
              </a>
              <Link to="/privacy" className="text-muted hover:text-primary">
                {t.privacyLink}
              </Link>
              <a
                href="https://codeforces.com"
                target="_blank"
                rel="noreferrer"
                className="text-muted hover:text-primary"
              >
                codeforces.com ↗
              </a>
            </div>
            <p className="w-full text-xs text-muted md:w-auto">{t.footerNote}</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
