/* Saved views — named filter sets for the Practice page, stored in
   localStorage (server-backed later). A view remembers tag + rating band +
   hide-solved, so one click re-applies a favourite filter combination. */
import { useCallback, useState } from 'react';

export interface SavedView {
  id: string;
  name: string;
  tag: string;
  minRating: string;
  maxRating: string;
  hideSolved: boolean;
}

export type SavedViewDraft = Omit<SavedView, 'id'>;

const KEY = 'cp_saved_views_v1';

function load(): SavedView[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (v): v is SavedView =>
        typeof v === 'object' && v !== null && typeof (v as SavedView).id === 'string',
    );
  } catch {
    return [];
  }
}

export function useSavedViews() {
  const [views, setViews] = useState<SavedView[]>(load);

  const save = useCallback((draft: SavedViewDraft) => {
    const next: SavedView[] = [...load(), { ...draft, id: `${Date.now()}` }];
    localStorage.setItem(KEY, JSON.stringify(next));
    setViews(next);
  }, []);

  const remove = useCallback((id: string) => {
    const next = load().filter((v) => v.id !== id);
    localStorage.setItem(KEY, JSON.stringify(next));
    setViews(next);
  }, []);

  return { views, save, remove };
}
