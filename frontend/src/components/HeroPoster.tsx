/* Static compass poster — the landing hero's first paint, the
   prefers-reduced-motion render, and the no-WebGL fallback.
   Pure SVG; the headline copy stays in the DOM, never in the art. */
const TICKS = Array.from({ length: 60 }, (_, i) => {
  const a = (i / 60) * Math.PI * 2;
  const long = i % 15 === 0;
  const r1 = long ? 92 : 98;
  const r2 = 108;
  return {
    key: i,
    long,
    x1: 150 + Math.sin(a) * r1,
    y1: 150 - Math.cos(a) * r1,
    x2: 150 + Math.sin(a) * r2,
    y2: 150 - Math.cos(a) * r2,
  };
});

export default function HeroPoster() {
  return (
    <div className="absolute inset-0 flex items-start justify-center overflow-hidden">
      <svg
        viewBox="0 0 300 300"
        className="mt-[-30px] h-[340px] w-[340px] md:h-[430px] md:w-[430px]"
        aria-hidden
      >
        <circle cx="150" cy="150" r="118" fill="none" stroke="var(--primary)" strokeOpacity="0.5" strokeWidth="1" />
        <circle cx="150" cy="150" r="92" fill="none" stroke="var(--primary)" strokeOpacity="0.22" strokeWidth="1" />
        <circle cx="150" cy="150" r="132" fill="none" stroke="var(--primary)" strokeOpacity="0.25" strokeWidth="1" strokeDasharray="1 7" />
        {TICKS.map((t) => (
          <line
            key={t.key}
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            stroke="var(--primary)"
            strokeOpacity={t.long ? 0.6 : 0.35}
            strokeWidth={t.long ? 1.5 : 1}
          />
        ))}
        <polygon points="150,58 143,150 157,150" fill="var(--primary)" fillOpacity="0.85" />
        <polygon points="150,242 143,150 157,150" fill="var(--muted)" fillOpacity="0.5" />
        <circle cx="150" cy="150" r="5" fill="var(--primary)" />
        <circle cx="150" cy="18" r="3.5" fill="var(--primary)" />
        <circle cx="262" cy="215" r="3" fill="var(--primary)" fillOpacity="0.7" />
        <circle cx="52" cy="230" r="2.5" fill="var(--muted)" />
      </svg>
    </div>
  );
}
