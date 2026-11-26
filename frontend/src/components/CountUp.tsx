/* Animated numbers — count up on load / on value change, ease-out cubic,
   ~700 ms. Skipped entirely under prefers-reduced-motion (value renders
   instantly). Used by StatCard and anywhere a headline number changes. */
import { useEffect, useRef, useState } from 'react';

export function useCountUp(target: number, duration = 700): number {
  const [value, setValue] = useState(0);
  const fromRef = useRef(0);

  useEffect(() => {
    if (
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      setValue(target);
      fromRef.current = target;
      return;
    }
    const from = fromRef.current;
    fromRef.current = target;
    if (from === target) {
      setValue(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}

export function CountUp({ value, duration }: { value: number; duration?: number }) {
  const v = useCountUp(value, duration);
  return <>{v}</>;
}
