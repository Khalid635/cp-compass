/* Landing — hero + preview, features, showcase, how it works, "Why this
   problem?" score breakdown, FAQ, roadmap, CTA + footer.
   No fake testimonials, no fake user counts, no fake badges.
   The preview numbers are a snapshot of the live demo account
   (/api/demo/dashboard, 2026-11-27): 1478 rating, 138 solved, 2-day
   streak, 3 due. They drift as the demo seed ages (the streak is
   date-relative) — update them when they visibly disagree with /demo.
   The hero preview is a REAL capture of the demo dashboard
   (public/showcase-dashboard.png); the showcase images are real captures
   from the dev server (/demo). The "Why this problem?" totals use the
   one shared score (lib/score — same formula as the demo and the real
   app, totals computed, never hand-written). Picks below 25 are dropped,
   so the demo shows 2 picks today. */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { ChevronDown, Compass, GitBranch, ListChecks, Target, X } from 'lucide-react';
import { Button, Card, Tabs } from '../components/ui';
import { GlassPanel } from '../components/glass';
import { CountUp } from '../components/CountUp';
import { TextEffect } from '../components/TextEffect';
import {
  MIN_SCORE_THRESHOLD,
  SCORE_WEIGHTS,
  explainFactors,
  scoreFromFactors,
} from '../lib/score';
import type { ScoreFactors } from '../lib/score';
import { LandingHeader } from '../components/layout';
import Hero3D from '../components/Hero3D';
import { formatWhy, useLanguage } from '../i18n';
import type { WhyInfo } from '../i18n/dict';
import type { Theme } from '../hooks/useTheme';

/* "Why this problem?" — the demo account's picks, scored with the ONE
   shared formula (lib/score, same as backend/app/services.py recommend()
   and backend/app/seed.py): Score = 0.35W + 0.30D + 0.20R + 0.15P.
   The factors below are the demo seed's real values (2026-11-27): rating
   1478, dp the only weak tag (weak_score 0.566, acceptance 45%, recent
   acceptance 27%), difficulty target 1578. Totals are COMPUTED from the
   factors (scoreFromFactors), never hand-written. Picks below
   MIN_SCORE_THRESHOLD (25) are dropped — 1367C Social Distance scored
   19 (the 19 floor: R=50, P=60, W=D=0), so the demo shows 2 picks today.
   1360E sits below the app's usual rating band (1300 < 1478) — below-band
   practice for a weak tag, said plainly. */
const WHY_PICKS: {
  id: string;
  name: string;
  rating: number;
  why: WhyInfo;
  factors: ScoreFactors;
}[] = [
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
    factors: { w: 56.6, d: 0, r: 73, p: 60 },
  },
  {
    id: '1366C',
    name: 'Palindromic Paths',
    rating: 1500,
    why: { kind: 'near_rating', user_rating: 1478, problem_rating: 1500 },
    factors: { w: 0, d: 61, r: 50, p: 60 },
  },
];
const WHY_TOTALS = WHY_PICKS.map((p) => ({
  ...p,
  total: scoreFromFactors(p.factors),
})).filter((p) => p.total >= MIN_SCORE_THRESHOLD);

/* FAQ accordion — hand-written in CP Compass's own stack, following the
   21st.dev registry patterns found in the search (Faq1 FAQ accordion
   section; Base UI Accordion): a heading beside an accessible accordion
   list, single-open, one item open by default, button + region with
   aria-expanded / aria-controls, chevron that rotates. No new dep. */
function FaqAccordion({ items }: { items: { q: string; a: string }[] }) {
  const [open, setOpen] = useState(0);
  return (
    <div className="mt-6 flex flex-col gap-3">
      {items.map((f, i) => {
        const isOpen = open === i;
        return (
          <div
            key={f.q}
            className="rounded-lg border border-border bg-surface px-4 pb-3"
          >
            <button
              type="button"
              onClick={() => setOpen(isOpen ? -1 : i)}
              aria-expanded={isOpen}
              aria-controls={`faq-panel-${i}`}
              id={`faq-button-${i}`}
              className="flex min-h-11 w-full cursor-pointer items-center justify-between gap-3 py-3 text-left text-base font-semibold"
            >
              {f.q}
              <ChevronDown
                size={18}
                aria-hidden
                className={`shrink-0 text-muted transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {isOpen && (
              <p
                id={`faq-panel-${i}`}
                role="region"
                aria-labelledby={`faq-button-${i}`}
                className="mt-2 text-sm text-muted"
              >
                {f.a}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

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

  /* Small visuals for the feature cards — real demo numbers, not
     decoration: dp acceptance 45% vs graphs 60% vs math 94%; the two
     scored picks; a 1/3/7/14/30-day revision ladder. */
  const FEATURE_VISUALS = [
    <div key="v1" aria-hidden className="mt-4 flex flex-col gap-1.5">
      {[
        ['dp', 45, 'var(--danger)'],
        ['graphs', 60, 'var(--warning)'],
        ['math', 94, 'var(--success)'],
      ].map(([tag, pct, color]) => (
        <div key={tag as string} className="flex items-center gap-2">
          <span className="w-14 font-mono text-[11px] text-muted">{tag}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full"
              style={{ width: `${pct}%`, background: color as string }}
            />
          </div>
          <span className="w-8 text-right font-mono text-[11px] text-muted">
            {pct}%
          </span>
        </div>
      ))}
    </div>,
    <div key="v2" aria-hidden className="mt-4 flex flex-col gap-1.5 font-mono text-[11px]">
      {[
        ['1360E', '43'],
        ['1366C', '37'],
      ].map(([id, score]) => (
        <div
          key={id}
          className="flex items-center justify-between rounded border border-border bg-bg px-2 py-1.5"
        >
          <span>{id}</span>
          <span className="text-primary">score {score}</span>
        </div>
      ))}
    </div>,
    <div key="v3" aria-hidden className="mt-4 flex items-end gap-1.5">
      {[1, 3, 7, 14, 30].map((d, i) => (
        <div key={d} className="flex flex-col items-center gap-1">
          <div
            className="w-6 rounded-sm bg-primary"
            style={{ height: `${8 + i * 7}px`, opacity: 0.35 + i * 0.13 }}
          />
          <span className="font-mono text-[11px] text-muted">{d}d</span>
        </div>
      ))}
    </div>,
  ];
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

  /* Showcase tabs + lightbox (landing v2, + Practice/Revision in v3).
     One big screenshot at a time; click to zoom. Esc or backdrop click
     closes. All four are real captures from the dev server (/demo). */
  type ShowTab = 'dashboard' | 'analytics' | 'practice' | 'revision';
  const SHOW_TABS: { id: ShowTab; src: string; caption: string }[] = [
    { id: 'dashboard', src: '/showcase-dashboard.png', caption: '' },
    { id: 'analytics', src: '/showcase-analytics.png', caption: '' },
    { id: 'practice', src: '/showcase-practice.png', caption: '' },
    { id: 'revision', src: '/showcase-revision.png', caption: '' },
  ];
  const [showTab, setShowTab] = useState<ShowTab>('dashboard');
  const [zoom, setZoom] = useState<null | ShowTab>(null);
  useEffect(() => {
    if (!zoom) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setZoom(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoom]);
  const showCaptionFor = (id: ShowTab) =>
    id === 'dashboard'
      ? t.showcaseDashboardCaption
      : id === 'analytics'
        ? t.showcaseAnalyticsCaption
        : id === 'practice'
          ? t.showcasePracticeCaption
          : t.showcaseRevisionCaption;
  const showSrc = SHOW_TABS.find((s) => s.id === showTab)!.src;
  const showCaption = showCaptionFor(showTab);
  const zoomSrc = zoom ? SHOW_TABS.find((s) => s.id === zoom)!.src : '';
  const zoomCaption = zoom ? showCaptionFor(zoom) : '';

  const whyFactors = (p: (typeof WHY_TOTALS)[number]) =>
    ([
      { key: 'w', label: t.whyW, explain: t.whyWExplain, value: p.factors.w },
      { key: 'd', label: t.whyD, explain: t.whyDExplain, value: p.factors.d },
      { key: 'r', label: t.whyR, explain: t.whyRExplain, value: p.factors.r },
      { key: 'p', label: t.whyP, explain: t.whyPExplain, value: p.factors.p },
    ] as const).map((f) => ({ ...f, weight: SCORE_WEIGHTS[f.key] }));

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
            {/* Beta chip: --muted outline, NOT teal (v3) — a status chip,
                not an accent. */}
            <p className="rounded-full border border-muted/50 bg-surface px-3 py-1 text-xs font-semibold text-muted">
              {t.betaBadge}
            </p>
          </motion.div>
          <motion.h1
            {...rise(0.08)}
            className="font-display relative z-[1] mx-auto mt-5 max-w-[26ch] text-[clamp(2.25rem,5vw,3.5rem)] font-normal leading-[1.15]"
          >
            {t.landingTitlePre}
            <span className="text-outline">{t.landingTitleOutline}</span>
            {t.landingTitleMid}
            <span className="text-gradient-gold">{t.landingTitleGold}</span>
            {t.landingTitlePost}
          </motion.h1>
          {reduceMotion ? (
            <p className="mx-auto mt-4 max-w-xl text-base text-muted md:text-lg">
              {t.landingSub}
            </p>
          ) : (
            <TextEffect
              per="word"
              preset="fade-in-blur"
              delay={0.16}
              className="mx-auto mt-4 max-w-xl text-base text-muted md:text-lg"
            >
              {t.landingSub}
            </TextEffect>
          )}
          <motion.div {...rise(0.24)} className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <Link to="/demo" className="glass-btn glass-btn--lg">
              <span className="glass-btn__label">{t.tryDemoNoLogin}</span>
            </Link>
            <Link to="/register" className="glass-btn glass-btn--ghost glass-btn--lg">
              <span className="glass-btn__label">{t.createAccount}</span>
            </Link>
          </motion.div>

          <motion.p {...rise(0.3)} className="mt-4 text-sm text-muted">
            {t.freeLine}
          </motion.p>

          {/* Browser-frame dashboard preview — a REAL screenshot of the demo
              dashboard (public/showcase-dashboard.png, cropped to its top),
              with a count-up stat strip above it. The numbers are the demo
              account's snapshot (1478 rating, 138 solved, 2-day streak,
              3 due); they drift as the seed ages. */}
          <div
            ref={previewRef}
            className="mx-auto mt-10 max-w-4xl overflow-hidden rounded-lg border border-border bg-surface text-left shadow-2xl"
          >
            <div className="flex items-center gap-1.5 border-b border-border bg-surface-2 px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-danger/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
              <span className="ml-3 font-mono text-xs text-muted">demo</span>
              <span className="ml-auto rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-muted">
                {t.demoDataChip}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">
              {[
                [t.previewRating, 1478],
                [t.previewSolved, 138],
                [t.previewStreak, 2],
                [t.previewDue, 3],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded-md border border-border bg-bg p-3">
                  <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
                  <p className="mt-1 font-mono text-xl font-semibold">
                    <CountUp value={value as number} />
                    {label === t.previewStreak ? ` ${t.previewStreakValue.replace(/^\d+\s*/, '')}` : ''}
                  </p>
                </div>
              ))}
            </div>
            <Link
              to="/demo"
              className="block border-t border-border"
              aria-label={t.showcaseDashboardCaption}
            >
              <img
                src="/showcase-dashboard.png"
                alt={t.showcaseDashboardCaption}
                loading="lazy"
                className="h-[240px] w-full object-cover object-top sm:h-[340px]"
              />
            </Link>
            <p className="border-t border-border px-4 py-2 text-center text-xs text-muted">
              {t.previewCaption}
            </p>
          </div>
        </div>
      </section>

      {/* Features — banded, to break the 3-card-grid monotony */}
      <section id="features" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-[1280px] px-4 py-16 md:px-6">
          <h2 className="sr-only">{t.navFeatures}</h2>
          <motion.div {...fadeUp} className="grid gap-4 md:grid-cols-3">
            {FEATURES.map((f, i) => (
              <GlassPanel key={f.title} className="p-5">
                <f.icon size={20} className="text-primary" aria-hidden />
                <h3 className="mt-3 text-base font-semibold">{f.title}</h3>
                <p className="mt-1 text-sm text-muted">{f.text}</p>
                {FEATURE_VISUALS[i]}
              </GlassPanel>
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
              { id: 'practice', label: t.navPractice },
              { id: 'revision', label: t.navRevision },
            ]}
            active={showTab}
            onChange={setShowTab}
          />
          <motion.figure
            key={showTab}
            {...fadeUp}
            className="glass-panel mt-4 overflow-hidden"
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
            {WHY_TOTALS.map((p) => (
              <GlassPanel
                key={p.id}
                className="p-4 sm:p-5"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="min-w-0 font-mono text-base font-semibold">
                    {p.id} {p.name} · {p.rating}
                  </h3>
                  {/* Score is always right-aligned, never wrapped under. */}
                  <p className="ml-auto shrink-0 whitespace-nowrap font-mono text-sm">
                    <span className="text-muted">{t.whyTotal} </span>
                    <span className="text-xl font-semibold text-primary">{p.total}</span>
                    <span className="text-muted"> / 100</span>
                  </p>
                </div>
                <p className="mt-1 text-sm text-muted">{formatWhy(p.why, t)}</p>
                {/* Generated from the factor values (lib/score), not
                    hand-written: the top factor names the reason. */}
                <p className="mt-1 text-[13px] text-muted">
                  {explainFactors(p.factors, {
                    weakTag: p.why.tag,
                    acceptance: p.why.acceptance,
                    userRating: p.why.user_rating,
                    problemRating: p.why.problem_rating,
                  }, t)}
                </p>
                <div className="mt-4 flex flex-col gap-2.5">
                  {whyFactors(p).map((f) => (
                    <div
                      key={f.label}
                      title={f.explain}
                      className="grid grid-cols-[9.5rem_1fr_auto] items-center gap-2"
                    >
                      <span className="whitespace-nowrap text-[13px] text-muted">
                        {f.label}{' '}
                        <span className="font-mono text-xs">×{f.weight.toFixed(2)}</span>
                      </span>
                      <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${f.value}%` }}
                        />
                      </div>
                      <span className="font-mono text-[13px] tabular-nums">
                        {f.value.toFixed(1)}{' '}
                        <span className="text-muted">→ +{(f.weight * f.value).toFixed(1)}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </GlassPanel>
            ))}
          </div>
          <motion.p {...fadeUp} className="mt-6 flex flex-wrap items-center gap-2 text-sm text-muted">
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
        <FaqAccordion
          items={[
            { q: t.faqQ1, a: t.faqA1 },
            { q: t.faqQ2, a: t.faqA2 },
            { q: t.faqQ3, a: t.faqA3 },
            { q: t.faqQ4, a: t.faqA4 },
            { q: t.faqQ5, a: t.faqA5 },
            { q: t.faqQ6, a: t.faqA6 },
          ]}
        />
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
                <span className="rounded-full border border-muted/50 px-2 py-0.5 text-[11px] font-semibold text-muted">
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
                className="inline-flex min-h-11 items-center font-medium text-primary hover:underline sm:min-h-0"
              >
                {t.githubLink} ↗
              </a>
              <Link to="/privacy" className="inline-flex min-h-11 items-center text-muted hover:text-primary sm:min-h-0">
                {t.privacyLink}
              </Link>
              <a
                href="https://codeforces.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 items-center text-muted hover:text-primary sm:min-h-0"
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
