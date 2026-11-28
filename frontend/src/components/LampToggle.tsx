/* Floor-lamp theme toggle for the login page (Batch 5, from the Code with
   Mahesh reel). The lamp IS a real <button>: keyboard accessible (native
   button, Enter/Space), aria-pressed reflects the theme, and the cord
   swings only when the user has not asked for reduced motion. Lamp ON =
   light theme (glow), lamp OFF = dark theme. Login page ONLY — never the
   dashboard. */
import { useEffect, useState } from 'react';
import { useLanguage } from '../i18n';
import type { Theme } from '../hooks/useTheme';

export function LampToggle({
  theme,
  onToggle,
}: {
  theme: Theme;
  onToggle: () => void;
}) {
  const { t } = useLanguage();
  const [reduceMotion, setReduceMotion] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduceMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduceMotion(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  const on = theme === 'light';
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={on}
      aria-label={on ? t.lampTurnOff : t.lampTurnOn}
      title={on ? t.lampTurnOff : t.lampTurnOn}
      className="group flex h-64 w-40 shrink-0 cursor-pointer items-end justify-center rounded-xl bg-transparent focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
    >
      <svg viewBox="0 0 160 256" className="h-full w-full" aria-hidden>
        <defs>
          <radialGradient id="lamp-glow">
            <stop offset="0%" stopColor="#fbbf24" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#fbbf24" stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* warm glow, visible only when the lamp is on */}
        <circle
          cx="80"
          cy="88"
          r="72"
          fill="url(#lamp-glow)"
          style={{ opacity: on ? 1 : 0, transition: 'opacity 400ms' }}
        />
        {/* pole + base */}
        <rect x="77" y="118" width="6" height="126" rx="3" style={{ fill: 'var(--muted)' }} />
        <ellipse cx="80" cy="246" rx="36" ry="8" style={{ fill: 'var(--surface-2)', stroke: 'var(--border)' }} />
        {/* bulb */}
        <circle
          cx="80"
          cy="104"
          r="9"
          style={{ fill: on ? '#fbbf24' : 'var(--muted)', transition: 'fill 400ms' }}
        />
        {/* shade — warm when lit, plain surface when off */}
        <path
          d="M48 116 L112 116 L122 68 L38 68 Z"
          style={{
            fill: on ? '#fde68a' : 'var(--surface-2)',
            stroke: 'var(--border)',
            transition: 'fill 400ms',
          }}
        />
        {/* pull cord hanging from the shade's right edge — it swings */}
        <g
          className={on && !reduceMotion ? 'lamp-swing' : undefined}
          style={{ transformOrigin: '112px 116px' }}
        >
          <path
            d="M112 116 C 120 134, 104 146, 112 162"
            fill="none"
            strokeWidth="2"
            style={{ stroke: 'var(--muted)' }}
          />
          <circle cx="112" cy="166" r="5" style={{ fill: 'var(--muted)' }} />
        </g>
      </svg>
      <span className="sr-only">{on ? t.lampTurnOff : t.lampTurnOn}</span>
    </button>
  );
}
