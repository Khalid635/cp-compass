/* Charts: RatingChart (Recharts, rank bands), TopicRadar, Heatmap (hand SVG). */
import { useMemo } from 'react';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { HeatDay, RatingPoint, TagStrength } from '../api/types';
import { useLanguage } from '../i18n';

/* Rank bands for the rating chart background (6% opacity). */
const BANDS = [
  { from: 0, to: 1199, color: 'var(--rank-newbie)' },
  { from: 1200, to: 1399, color: 'var(--rank-pupil)' },
  { from: 1400, to: 1599, color: 'var(--rank-specialist)' },
  { from: 1600, to: 1899, color: 'var(--rank-expert)' },
  { from: 1900, to: 2099, color: 'var(--rank-cm)' },
  { from: 2100, to: 2299, color: 'var(--rank-master)' },
  { from: 2300, to: 4000, color: 'var(--rank-gm)' },
];

function ChartTooltip({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: { value?: number | string }[];
  label?: string;
  unit?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="font-medium text-text">{label}</div>
      <div className="font-mono text-muted">
        {payload[0]?.value}
        {unit ?? ''}
      </div>
    </div>
  );
}

export function RatingChart({ data }: { data: RatingPoint[] }) {
  const { t } = useLanguage();
  const points = useMemo(
    () =>
      data.map((d) => ({
        name: d.contest.replace('Round #', '#'),
        rating: d.rating,
        date: d.date,
      })),
    [data],
  );
  if (points.length < 2) {
    return (
      <p className="py-8 text-center text-sm text-muted">
        {t.notEnoughContests}
      </p>
    );
  }
  return (
    <div className="h-64 w-full min-w-0" role="img" aria-label="Rating history chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <defs>
            <linearGradient id="ratingFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.2} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            domain={['dataMin - 50', 'dataMax + 50']}
            width={48}
          />
          <Tooltip content={<ChartTooltip />} />
          {BANDS.map((b) => (
            <ReferenceArea
              key={b.from}
              y1={b.from}
              y2={b.to}
              fill={b.color}
              fillOpacity={0.06}
              strokeOpacity={0}
            />
          ))}
          <Area
            type="monotone"
            dataKey="rating"
            stroke="none"
            fill="url(#ratingFill)"
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="rating"
            stroke="var(--primary)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: 'var(--primary)', stroke: 'var(--surface)' }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TopicRadar({ tags }: { tags: TagStrength[] }) {
  const { t } = useLanguage();
  const top = useMemo(() => [...tags].sort((a, b) => b.attempted - a.attempted).slice(0, 8), [tags]);
  if (top.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted">
        {t.noTagData}
      </p>
    );
  }
  const data = top.map((t) => ({ tag: t.tag, acceptance: Math.round(t.acceptance * 100) }));
  if (top.length > 6) {
    // More than 6 tags: horizontal bars read better than a crowded radar.
    return (
      <div className="h-64 w-full min-w-0" role="img" aria-label="Topic acceptance bar chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 100]}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            />
            <YAxis
              type="category"
              dataKey="tag"
              width={110}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<ChartTooltip unit="%" />} />
            <Bar dataKey="acceptance" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {data.map((d) => (
                <Cell
                  key={d.tag}
                  fill={d.acceptance < 50 ? 'var(--danger)' : 'var(--primary)'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  return (
    <div className="h-64 w-full min-w-0" role="img" aria-label="Topic strength radar chart">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis
            dataKey="tag"
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
          />
          <Tooltip content={<ChartTooltip unit="%" />} />
          <Radar
            dataKey="acceptance"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.15}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---------- Heatmap (hand-built SVG, no library) ---------- */
function heatLevel(count: number): number {
  if (count === 0) return 0;
  if (count === 1) return 1;
  if (count <= 3) return 2;
  if (count <= 5) return 3;
  return 4;
}

export function Heatmap({ days }: { days: HeatDay[] }) {
  const { t, lang } = useLanguage();
  const { columns, monthLabels } = useMemo(() => {
    if (days.length === 0) return { columns: [] as (HeatDay | null)[][], monthLabels: [] as { x: number; label: string }[] };
    const first = new Date(`${days[0].date}T00:00:00`);
    const offset = (first.getDay() + 6) % 7; // days since Monday
    const cells: (HeatDay | null)[] = [...Array<HeatDay | null>(offset).fill(null), ...days];
    const cols: (HeatDay | null)[][] = [];
    for (let i = 0; i < cells.length; i += 7) cols.push(cells.slice(i, i + 7));
    const labels: { x: number; label: string }[] = [];
    let prevMonth = -1;
    cols.forEach((col, ci) => {
      const firstReal = col.find((c) => c !== null);
      if (!firstReal) return;
      const m = new Date(`${firstReal.date}T00:00:00`).getMonth();
      if (m !== prevMonth) {
        labels.push({
          x: ci * 15,
          label: new Date(`${firstReal.date}T00:00:00`).toLocaleString(
            lang === 'bn' ? 'bn-u-nu-latn' : 'en',
            { month: 'short' },
          ),
        });
        prevMonth = m;
      }
    });
    return { columns: cols, monthLabels: labels };
  }, [days, lang]);

  if (days.length === 0) {
    return <p className="py-8 text-center text-sm text-muted">{t.noActivityYet}</p>;
  }
  const width = columns.length * 15;
  const total = days.reduce((a, d) => a + d.count, 0);
  return (
    <div className="min-w-0 overflow-x-auto" role="img" aria-label={`Activity heatmap, ${total} accepted submissions`}>
      <svg width={width} height={132} className="block">
        {monthLabels.map((l) => (
          <text key={l.label + l.x} x={l.x} y={10} fontSize={11} fill="var(--muted)">
            {l.label}
          </text>
        ))}
        {columns.map((col, ci) =>
          col.map((day, ri) => {
            if (!day) return null;
            const level = heatLevel(day.count);
            return (
              <rect
                key={day.date}
                x={ci * 15}
                y={18 + ri * 15}
                width={12}
                height={12}
                rx={2}
                style={{ fill: `var(--heat-${level})` }}
              >
                <title>
                  {t.heatTooltip(day.date, day.count)}
                </title>
              </rect>
            );
          }),
        )}
      </svg>
      <div className="mt-2 flex items-center justify-end gap-1 text-xs text-muted">
        {t.heatLess}
        {[0, 1, 2, 3, 4].map((l) => (
          <span
            key={l}
            className="inline-block h-3 w-3 rounded-[2px]"
            style={{ background: `var(--heat-${l})` }}
          />
        ))}
        {t.heatMore}
      </div>
    </div>
  );
}
