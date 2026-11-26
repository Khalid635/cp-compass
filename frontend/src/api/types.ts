/* Shared types — shapes match the FastAPI responses in backend/app/main.py. */
import type { WhyInfo } from '../i18n/dict';

export type { WhyInfo };

export interface ProblemRef {
  contest_id: number;
  index: string;
  name: string;
  rating: number | null;
  tags: string[];
}

export interface Recommendation extends ProblemRef {
  why: WhyInfo;
}

export interface SubmissionRow {
  problem: ProblemRef;
  verdict: string;
  language: string | null;
  submitted_at: string;
}

export interface TagStrength {
  tag: string;
  attempted: number;
  solved: number;
  acceptance: number;
  avg_wrong_attempts: number;
  last_solve: string | null;
  weak: boolean;
}

export interface RatingPoint {
  contest: string;
  rating: number;
  date: string;
}

export interface HeatDay {
  date: string;
  count: number;
}

export interface RevisionItem {
  id: number;
  problem: ProblemRef;
  interval_days: number;
  due_date: string;
  last_result: string | null;
  wrong_attempts: number;
  done: boolean;
}

export interface DashboardData {
  user: { handle: string | null; rating: number | null; rank?: string };
  stats: { rating: number | null; solved: number; streak: number; revisions_due: number } | null;
  rating_history: RatingPoint[];
  today_plan: { problems: Recommendation[]; revisions: RevisionItem[] };
  tag_strengths: TagStrength[];
  heatmap: HeatDay[];
  recent: SubmissionRow[];
  has_handle: boolean;
  synced: boolean;
  demo?: boolean;
}

export interface SyncStatus {
  status: 'never' | 'pending' | 'running' | 'done' | 'failed';
  total_synced: number;
  last_synced_at: string | null;
  error: string | null;
}

/** Codeforces rank from rating — colours come from the --rank-* tokens. */
export function rankOf(rating: number | null): { name: string; token: string } {
  if (rating === null || rating === undefined) return { name: 'Unrated', token: 'var(--rank-newbie)' };
  if (rating < 1200) return { name: 'Newbie', token: 'var(--rank-newbie)' };
  if (rating < 1400) return { name: 'Pupil', token: 'var(--rank-pupil)' };
  if (rating < 1600) return { name: 'Specialist', token: 'var(--rank-specialist)' };
  if (rating < 1900) return { name: 'Expert', token: 'var(--rank-expert)' };
  if (rating < 2100) return { name: 'Candidate Master', token: 'var(--rank-cm)' };
  if (rating < 2300) return { name: 'Master', token: 'var(--rank-master)' };
  if (rating < 2400) return { name: 'International Master', token: 'var(--rank-master)' };
  if (rating < 2600) return { name: 'Grandmaster', token: 'var(--rank-gm)' };
  if (rating < 3000) return { name: 'International Grandmaster', token: 'var(--rank-gm)' };
  return { name: 'Legendary Grandmaster', token: 'var(--rank-gm)' };
}

export function cfUrl(p: ProblemRef): string {
  return `https://codeforces.com/problemset/problem/${p.contest_id}/${p.index}`;
}
