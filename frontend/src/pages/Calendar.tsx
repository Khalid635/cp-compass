/* Practice calendar — month grid from daily_stats, click a day to see
   that day's submissions. Streak days get a ring. Month navigation and
   a Today button; the grid starts on Monday like the heatmap. */
import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { CalendarDays, ChevronLeft, ChevronRight, Download, Flame, RefreshCw } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useLanguage } from '../i18n';
import { RecentSubmissions } from '../components/cards';
import { Button, Card, EmptyState, Skeleton } from '../components/ui';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function heatLevel(count: number): number {
  if (count === 0) return 0;
  if (count === 1) return 1;
  if (count <= 3) return 2;
  if (count <= 5) return 3;
  return 4;
}

function monthName(year: number, month: number, lang: string): string {
  return new Date(year, month - 1, 1).toLocaleString(lang === 'bn' ? 'bn-u-nu-latn' : 'en', {
    month: 'long',
    year: 'numeric',
  });
}

export default function Calendar({ demo = false }: { demo?: boolean }) {
  const { t, lang } = useLanguage();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [selected, setSelected] = useState<string | null>(now.toISOString().slice(0, 10));

  const icsExport = useMutation({
    mutationFn: api.exportCalendarIcs,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'codeforces-contests.ics';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast(t.icsExported);
    },
    onError: (e) => {
      toast(e instanceof ApiError ? e.message : t.icsExportFailed);
    },
  });

  const query = useQuery({
    queryKey: demo ? ['demo-calendar', year, month] : ['calendar', year, month],
    queryFn: demo ? () => api.demoCalendar(year, month) : () => api.calendar(year, month),
    staleTime: 60_000,
  });

  const dayQuery = useQuery({
    queryKey: demo ? ['demo-calendar-day', selected] : ['calendar-day', selected],
    queryFn: () =>
      selected
        ? demo
          ? api.demoCalendarDay(selected)
          : api.calendarDay(selected)
        : Promise.resolve({ date: '', submissions: [] }),
    enabled: selected !== null,
    staleTime: 60_000,
  });

  const cells = useMemo(() => {
    const daysInMonth = new Date(year, month, 0).getDate();
    const first = new Date(year, month - 1, 1);
    const offset = (first.getDay() + 6) % 7; // days since Monday
    const byDate = new Map((query.data?.days ?? []).map((d) => [d.date, d]));
    const out: ({ date: string; solved: number; attempted: number } | null)[] = [];
    for (let i = 0; i < offset; i++) out.push(null);
    for (let day = 1; day <= daysInMonth; day++) {
      const iso = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const row = byDate.get(iso);
      out.push({ date: iso, solved: row?.solved ?? 0, attempted: row?.attempted ?? 0 });
    }
    return out;
  }, [query.data, year, month]);

  // Streak days: consecutive days (ending today) with >= 1 solved.
  const streakDays = useMemo(() => {
    const solved = new Set(
      (query.data?.days ?? []).filter((d) => d.solved > 0).map((d) => d.date),
    );
    const days = new Set<string>();
    const cursor = new Date();
    const todayIso = cursor.toISOString().slice(0, 10);
    if (!solved.has(todayIso)) cursor.setDate(cursor.getDate() - 1);
    while (solved.has(cursor.toISOString().slice(0, 10))) {
      days.add(cursor.toISOString().slice(0, 10));
      cursor.setDate(cursor.getDate() - 1);
    }
    return days;
  }, [query.data]);

  const goMonth = (delta: number) => {
    let y = year;
    let m = month + delta;
    if (m < 1) {
      m = 12;
      y -= 1;
    } else if (m > 12) {
      m = 1;
      y += 1;
    }
    setYear(y);
    setMonth(m);
  };

  const todayIso = now.toISOString().slice(0, 10);
  const selectedDay = cells.find((c) => c !== null && c.date === selected) ?? null;

  return (
    <div className="page-enter flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{t.calendarTitle}</h1>
        <div className="flex items-center gap-2">
          <Button variant="secondary" className="h-8 px-3 text-xs" onClick={() => goMonth(-1)} aria-label="Previous month">
            <ChevronLeft size={15} aria-hidden />
          </Button>
          <span className="min-w-28 text-center font-mono text-sm font-medium">
            {monthName(year, month, lang)}
          </span>
          <Button variant="secondary" className="h-8 px-3 text-xs" onClick={() => goMonth(1)} aria-label="Next month">
            <ChevronRight size={15} aria-hidden />
          </Button>
          <Button
            variant="ghost"
            className="h-8 px-3 text-xs"
            onClick={() => {
              setYear(now.getFullYear());
              setMonth(now.getMonth() + 1);
              setSelected(todayIso);
            }}
          >
            {t.calendarToday}
          </Button>
          {!demo && (
            <Button
              variant="secondary"
              className="h-8 px-3 text-xs"
              loading={icsExport.isPending}
              onClick={() => icsExport.mutate()}
            >
              <Download size={14} aria-hidden /> {t.icsExport}
            </Button>
          )}
        </div>
      </div>

      {query.isPending ? (
        <Skeleton className="h-[380px] w-full" />
      ) : query.isError ? (
        <Card>
          <EmptyState
            icon={<RefreshCw size={40} aria-hidden />}
            title={t.cfNoResponse}
            text={t.cfRetryAuto}
            action={
              <Button onClick={() => void query.refetch()}>
                <RefreshCw size={14} aria-hidden /> {t.retry}
              </Button>
            }
          />
        </Card>
      ) : (
        <Card className="min-w-0">
          <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-muted">
            {WEEKDAYS.map((d) => (
              <div key={d} className="py-1">
                {d}
              </div>
            ))}
          </div>
          <div className="mt-1 grid grid-cols-7 gap-1">
            {cells.map((cell, i) => {
              if (cell === null) return <div key={`pad-${i}`} />;
              const isToday = cell.date === todayIso;
              const isSelected = cell.date === selected;
              const isStreak = streakDays.has(cell.date);
              return (
                <button
                  key={cell.date}
                  type="button"
                  onClick={() => setSelected(cell.date)}
                  aria-pressed={isSelected}
                  aria-label={`${cell.date}: ${cell.solved} solved, ${cell.attempted} attempted`}
                  className={`relative flex min-h-14 cursor-pointer flex-col items-start rounded-md border p-1.5 text-left transition-colors sm:min-h-20 ${
                    isSelected
                      ? 'border-primary bg-primary/10'
                      : 'border-border bg-bg hover:bg-hover'
                  }`}
                >
                  <span
                    className={`font-mono text-xs font-medium ${
                      isToday ? 'flex h-5 w-5 items-center justify-center rounded-full bg-primary text-on-primary' : ''
                    }`}
                  >
                    {Number(cell.date.slice(-2))}
                  </span>
                  {cell.attempted > 0 && (
                    <span
                      className="mt-auto inline-block h-2 w-full rounded-full"
                      style={{ background: `var(--heat-${heatLevel(cell.solved)})` }}
                    />
                  )}
                  {cell.solved > 0 && (
                    <span className="mt-1 font-mono text-[11px] text-muted">{cell.solved}</span>
                  )}
                  {isStreak && (
                    <Flame
                      size={12}
                      aria-hidden
                      className="absolute right-1 top-1.5 text-primary"
                    />
                  )}
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex items-center justify-end gap-1 text-xs text-muted">
            {t.heatLess}
            {[0, 1, 2, 3, 4].map((l) => (
              <span
                key={l}
                className="inline-block h-3 w-3 rounded-[2px]"
                style={{ background: `var(--heat-${l})` }}
              />
            ))}
            {t.heatMore}
            <span className="ml-3 inline-flex items-center gap-1">
              <Flame size={12} aria-hidden className="text-primary" /> {t.calendarStreakDay}
            </span>
          </div>
        </Card>
      )}

      {/* Selected day */}
      <Card title={selected ? `${t.daySubmissions} — ${selected}` : t.daySubmissions} className="min-w-0">
        {selected === null ? (
          <p className="py-6 text-center text-sm text-muted">{t.calendarSelectDay}</p>
        ) : dayQuery.isPending ? (
          <Skeleton className="h-[120px] w-full" />
        ) : (dayQuery.data?.submissions.length ?? 0) === 0 ? (
          <EmptyState
            icon={<CalendarDays size={40} aria-hidden />}
            title={t.noActivityYet}
            text={selectedDay ? t.calendarAttempted(selectedDay.attempted) : t.calendarSelectDay}
          />
        ) : (
          <>
            <p className="mb-3 text-sm text-muted">
              {selectedDay &&
                `${t.calendarSolved(selectedDay.solved)} · ${t.calendarAttempted(selectedDay.attempted)}`}
            </p>
            <RecentSubmissions rows={dayQuery.data!.submissions} />
          </>
        )}
      </Card>

      {demo && <p className="text-center text-xs text-muted">{t.demoFootnote}</p>}
    </div>
  );
}
