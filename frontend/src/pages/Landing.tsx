/* Landing — one promise, one blurred hero glow, 3 feature cards, 3 steps.
   No fake testimonials, no fake user counts, no fake badges. */
import { Link } from 'react-router-dom';
import { Compass, GitBranch, ListChecks, Target } from 'lucide-react';
import { Button, Card } from '../components/ui';
import { LandingHeader } from '../components/layout';
import type { Theme } from '../hooks/useTheme';

const FEATURES = [
  {
    icon: Target,
    title: 'Weak topics, proven by numbers',
    text: 'Acceptance rate and wrong attempts per tag — not a guess. See exactly where you bleed rating.',
  },
  {
    icon: ListChecks,
    title: 'Smart picks, with a reason',
    text: 'Every day, problems near your rating, on your weak tags, that you have not solved — each with one line saying why.',
  },
  {
    icon: GitBranch,
    title: 'Revision that sticks',
    text: 'Hard-won problems come back on a 1 / 3 / 7 / 14 / 30-day schedule, so what you learned stays learned.',
  },
];

const STEPS = [
  { n: '1', title: 'Connect handle', text: 'Register and add your Codeforces handle. We verify it against the Codeforces API.' },
  { n: '2', title: 'Sync', text: 'Your submissions sync in the background — incremental, resumable, never duplicated.' },
  { n: '3', title: 'Practice', text: 'Open the dashboard and follow today’s plan. Solve on Codeforces, not here.' },
];

export default function Landing({ theme, toggleTheme }: { theme: Theme; toggleTheme: () => void }) {
  return (
    <div className="min-h-screen">
      <LandingHeader theme={theme} toggleTheme={toggleTheme} />

      {/* Hero */}
      <section className="relative mx-auto max-w-[1280px] px-4 pb-16 pt-16 text-center md:px-6 md:pt-24">
        <div
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-0 h-[300px] w-[600px] -translate-x-1/2 rounded-full blur-3xl"
          style={{
            background:
              'radial-gradient(600px circle at 50% 0%, color-mix(in srgb, var(--primary) 18%, transparent), transparent)',
          }}
        />
        <div className="relative">
          <p className="mx-auto flex w-fit items-center gap-2 rounded-full border border-border bg-surface-2 px-3 py-1 text-xs text-muted">
            <Compass size={14} className="text-primary" aria-hidden />
            Codeforces only · 100% free
          </p>
          <h1 className="mx-auto mt-6 max-w-3xl text-5xl font-semibold leading-[1.1] tracking-tight md:text-6xl">
            Your Codeforces data knows what to practice next.
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base text-muted md:text-lg">
            CP Compass turns your submissions into a daily plan: which topic is
            weak, which problem to solve today, and what to revise.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link to="/demo">
              <Button className="h-11 px-6 text-base">Try demo — no login</Button>
            </Link>
            <Link to="/register">
              <Button variant="secondary" className="h-11 px-6 text-base">
                Create account
              </Button>
            </Link>
          </div>

          {/* Browser-frame dashboard preview (static mock, labelled as illustration) */}
          <div className="mx-auto mt-12 max-w-4xl overflow-hidden rounded-lg border border-border bg-surface text-left shadow-2xl">
            <div className="flex items-center gap-1.5 border-b border-border bg-surface-2 px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-danger/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
              <span className="ml-3 font-mono text-xs text-muted">cp-compass.app/demo</span>
            </div>
            <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">
              {[
                ['Rating', '1478'],
                ['Solved', '156'],
                ['Streak', '2 days'],
                ['Due today', '3'],
              ].map(([label, value]) => (
                <div key={label} className="rounded-md border border-border bg-bg p-3">
                  <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
                  <p className="mt-1 font-mono text-xl font-semibold">{value}</p>
                </div>
              ))}
            </div>
            <div className="px-4 pb-4">
              <div className="rounded-md border border-border bg-bg p-4">
                <p className="text-sm font-medium">Today’s plan</p>
                <p className="mt-1 text-sm text-muted">
                  1366C Palindromic Paths · 1300 — dp-তে তোমার acceptance 32%
                </p>
                <p className="mt-1 text-sm text-muted">
                  1360C Similar Pairs · 1200 — তোমার rating-এর কাছাকাছি
                </p>
              </div>
            </div>
            <p className="border-t border-border px-4 py-2 text-center text-xs text-muted">
              Illustration from the demo account — try the live demo above.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <div className="grid gap-4 md:grid-cols-3">
          {FEATURES.map((f) => (
            <Card key={f.title}>
              <f.icon size={20} className="text-primary" aria-hidden />
              <h3 className="mt-3 text-base font-semibold">{f.title}</h3>
              <p className="mt-1 text-sm text-muted">{f.text}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-[1280px] px-4 pb-16 md:px-6">
        <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
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

      {/* Built with */}
      <section className="border-t border-border">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-4 px-4 py-8 md:px-6">
          <p className="text-sm text-muted">
            Built with <span className="font-medium text-text">FastAPI</span>,{' '}
            <span className="font-medium text-text">PostgreSQL</span> and{' '}
            <span className="font-medium text-text">React</span>. Data comes from the
            public Codeforces API.
          </p>
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
          <h2 className="text-2xl font-semibold tracking-tight">
            Stop picking problems at random.
          </h2>
          <div className="mt-6 flex justify-center gap-3">
            <Link to="/demo">
              <Button className="h-11 px-6 text-base">Try demo</Button>
            </Link>
            <Link to="/register">
              <Button variant="secondary" className="h-11 px-6 text-base">
                Create account
              </Button>
            </Link>
          </div>
          <p className="mt-8 text-xs text-muted">
            CP Compass is a personal project. It is not affiliated with Codeforces.
          </p>
        </div>
      </footer>
    </div>
  );
}
