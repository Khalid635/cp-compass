/* Landing hero backdrop — lazy 3D compass, with a static poster as the
   first paint, the prefers-reduced-motion render, and the no-WebGL /
   context-lost fallback. The canvas layer is pointer-events-none; mouse
   parallax is read from window pointer moves. The demand loop pauses
   while the hero is off-screen and restarts on return. */
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import HeroPoster from './HeroPoster';
import type { HeroPointer } from './HeroScene';
import type { Theme } from '../hooks/useTheme';

const HeroScene = lazy(() => import('./HeroScene'));

function webglAvailable(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}

export default function Hero3D({ theme }: { theme: Theme }) {
  const [mode, setMode] = useState<'poster' | 'canvas'>('poster');
  const [lost, setLost] = useState(false);
  const pointerRef = useRef<HeroPointer>({ x: 0, y: 0 });
  const pausedRef = useRef(false);
  const invalidateRef = useRef<(() => void) | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduced && webglAvailable()) setMode('canvas');
  }, []);

  /* Pointer parallax — normalized to [-1, 1] across the hero box. */
  useEffect(() => {
    if (mode !== 'canvas') return;
    const onMove = (e: PointerEvent) => {
      const el = boxRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width) * 2 - 1;
      const y = ((e.clientY - r.top) / r.height) * 2 - 1;
      pointerRef.current = { x: Math.max(-1, Math.min(1, x)), y: Math.max(-1, Math.min(1, y)) };
    };
    const onLeave = () => {
      pointerRef.current = { x: 0, y: 0 };
    };
    window.addEventListener('pointermove', onMove);
    document.documentElement.addEventListener('pointerleave', onLeave);
    return () => {
      window.removeEventListener('pointermove', onMove);
      document.documentElement.removeEventListener('pointerleave', onLeave);
    };
  }, [mode]);

  /* Pause the demand loop off-screen; kick one frame on return. */
  useEffect(() => {
    if (mode !== 'canvas') return;
    const el = boxRef.current;
    if (!el || !('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        pausedRef.current = !entry.isIntersecting;
        if (entry.isIntersecting) invalidateRef.current?.();
      },
      { threshold: 0 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [mode]);

  const showCanvas = mode === 'canvas' && !lost;
  return (
    <div ref={boxRef} className="pointer-events-none absolute inset-0 z-0" aria-hidden>
      {/* Soft glow behind poster + canvas (same as the old static hero). */}
      <div
        className="absolute left-1/2 top-0 h-[300px] w-[600px] -translate-x-1/2 rounded-full blur-3xl"
        style={{
          background:
            'radial-gradient(600px circle at 50% 0%, color-mix(in oklch, var(--primary) 10%, transparent), transparent)',
        }}
      />
      {/* Compass layer: faint, centre masked out so no ring crosses the
          heading text; the outer ring arc stays visible around the copy. */}
      <div
        className="absolute inset-x-0 top-0 h-[480px] opacity-10 md:h-[600px]"
        style={{
          maskImage:
            'radial-gradient(closest-side, transparent 0%, transparent 40%, black 75%, black 100%)',
          WebkitMaskImage:
            'radial-gradient(closest-side, transparent 0%, transparent 40%, black 75%, black 100%)',
        }}
      >
        <div
          className="absolute inset-0"
          style={{
            maskImage: 'linear-gradient(to bottom, black 55%, transparent 98%)',
            WebkitMaskImage: 'linear-gradient(to bottom, black 55%, transparent 98%)',
          }}
        >
        {showCanvas ? (
          <Suspense fallback={<HeroPoster />}>
            <HeroScene
              theme={theme}
              pointerRef={pointerRef}
              pausedRef={pausedRef}
              invalidateRef={invalidateRef}
              onContextLost={() => setLost(true)}
            />
          </Suspense>
        ) : (
          <HeroPoster />
        )}
        </div>
      </div>
    </div>
  );
}
