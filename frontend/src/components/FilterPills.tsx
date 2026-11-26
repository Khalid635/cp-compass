/* Filter pills with counts + Clear-all — the getlayers-style interaction
   (pills carry their counts, union behaviour, one Clear button) in the
   CP Compass look. Used on Practice for tags and rating bands. */
import { X } from 'lucide-react';
import { useLanguage } from '../i18n';

export interface PillCount {
  id: string;
  label: string;
  count: number;
}

export const RATING_BANDS = [
  { id: '800-1199', label: '800–1199', min: '800', max: '1199' },
  { id: '1200-1599', label: '1200–1599', min: '1200', max: '1599' },
  { id: '1600-1999', label: '1600–1999', min: '1600', max: '1999' },
  { id: '2000+', label: '2000+', min: '2000', max: '' },
] as const;

export function bandIdFor(minRating: string, maxRating: string): string | null {
  const band = RATING_BANDS.find((b) => b.min === minRating && b.max === maxRating);
  return band ? band.id : null;
}

function Pill({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? 'border-primary bg-primary text-on-primary'
          : 'border-border bg-surface-2 text-muted hover:border-primary/50 hover:text-text'
      }`}
    >
      {label}
      {count !== undefined && (
        <span className={`font-mono text-[11px] ${active ? 'opacity-80' : 'text-muted'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

export function FilterPills({
  tags,
  activeTag,
  onTag,
  bands,
  activeBand,
  onBand,
  activeCount,
  onClear,
}: {
  tags: PillCount[];
  activeTag: string;
  onTag: (tag: string) => void;
  bands: PillCount[];
  activeBand: string | null;
  onBand: (bandId: string | null) => void;
  activeCount: number;
  onClear: () => void;
}) {
  const { t } = useLanguage();
  return (
    <div className="flex flex-col gap-3">
      {tags.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-xs font-medium text-muted">{t.filterTag}</span>
          {tags.map((tg) => (
            <Pill
              key={tg.id}
              label={tg.label}
              count={tg.count}
              active={activeTag === tg.id}
              onClick={() => onTag(activeTag === tg.id ? '' : tg.id)}
            />
          ))}
        </div>
      )}
      {bands.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-xs font-medium text-muted">{t.filterRatingBand}</span>
          {bands.map((b) => (
            <Pill
              key={b.id}
              label={b.label}
              count={b.count}
              active={activeBand === b.id}
              onClick={() => onBand(activeBand === b.id ? null : b.id)}
            />
          ))}
        </div>
      )}
      {activeCount > 0 && (
        <div>
          <button
            type="button"
            onClick={onClear}
            className="inline-flex cursor-pointer items-center gap-1 rounded-full border border-border bg-surface-2 px-3 py-1 text-xs font-medium text-muted transition-colors hover:border-danger/50 hover:text-danger"
          >
            <X size={12} aria-hidden /> {t.clearFilters(activeCount)}
          </button>
        </div>
      )}
    </div>
  );
}
