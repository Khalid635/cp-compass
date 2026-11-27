/* Shared types — shapes match the FastAPI responses in backend/app/main.py. */
import type { Dict, WhyInfo } from '../i18n/dict';

export type { WhyInfo };

export interface ProblemRef {
  contest_id: number;
  index: string;
  name: string;
  rating: number | null;
  tags: string[];
  /** Codeforces for now — other OJs later (Phase 3 scaffolding). */
  platform?: string;
}

export interface Recommendation extends ProblemRef {
  why: WhyInfo;
  /** Rule-based score 0–100 (blueprint §6). Absent on old demo payloads. */
  score?: number;
}

/* ---------- Phase 3 — ML solvability prediction ---------- */

/** Held-out metrics for the rule-based baseline (as a probability). */
export interface MlBaselineEval {
  accuracy: number;
  brier: number;
  auc: number | null;
}

/** Held-out metrics for one ML candidate (CV + test split). */
export interface MlModelEval {
  cv_auc: number | null;
  cv_brier: number;
  test_accuracy: number;
  test_brier: number;
  test_auc: number | null;
}

export interface MlStatus {
  trained: boolean;
  reason?: string;
  model_type?: string;
  trained_at?: string;
  n_rows?: number;
  n_solved?: number;
  demo_rows?: number;
  real_rows?: number;
  sources?: Record<string, number>;
  features?: string[];
  shipped?: boolean;
  ship_reason?: string;
  bias_note?: string;
  evaluation?: {
    baseline: MlBaselineEval;
    random_forest: MlModelEval;
    logreg: MlModelEval;
    hist_gb: MlModelEval;
    calibration: {
      tried: string;
      cv_brier_uncalibrated: number;
      cv_brier_calibrated: number;
      shipped_calibrated: boolean;
    };
  };
}

export interface MlPredictionsResponse {
  recommendations: (Recommendation & { solvability?: number | null })[];
  model: MlStatus;
}

/** Honest trained-on label: demo data, real data, or both. */
export function trainedOnLabel(m: MlStatus, t: Dict): string {
  const real = m.real_rows ?? 0;
  const demo = m.demo_rows ?? 0;
  if (real > 0 && demo > 0) return t.predTrainedLabelMixed;
  if (real > 0) return t.predTrainedLabelReal;
  return t.predTrainedLabelDemo;
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
  /** Weighted weakness 0–1 (blueprint §5). Absent on old demo payloads. */
  weak_score?: number;
  factors?: {
    acceptance: number;
    wrong_ratio: number;
    recent_acceptance: number;
    avg_attempted_rating: number | null;
  };
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

export interface CumulativePoint {
  date: string;
  solved: number;
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
  cumulative: CumulativePoint[];
  recent_total: number;
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

/* ---------- Phase 2 ---------- */

export interface DifficultyBucket {
  bucket: string;
  attempted: number;
  solved: number;
  acceptance: number;
}

export interface Milestone {
  threshold: number;
  unlocked: boolean;
  solved: number;
}

export interface ContestAnalysis {
  contest_id: number;
  contest_name: string;
  date: string;
  old_rating: number | null;
  new_rating: number;
  delta: number | null;
  solved_that_day: number;
  attempted_that_day: number;
  weak_tags_that_day: string[];
}

export interface AnalyticsData {
  peak_rating: number | null;
  current_rating: number | null;
  streak: number;
  longest_streak: number;
  solved: number;
  buckets: DifficultyBucket[];
  tag_strengths: TagStrength[];
  milestones: Milestone[];
  contests: ContestAnalysis[];
}

export interface CalendarDay {
  date: string;
  solved: number;
  attempted: number;
}

export interface CalendarMonth {
  year: number;
  month: number;
  days: CalendarDay[];
}

export interface WeekStats {
  week_start: string;
  solved: number;
  attempted: number;
  acceptance: number;
  tag_acceptance: Record<string, { solved: number; attempted: number; acceptance: number }>;
}

export interface WeakMovement {
  tag: string;
  this_week: number | null;
  last_week: number | null;
  delta: number | null;
  weak_score: number;
}

export interface WeeklyReportData {
  current: WeekStats;
  previous: WeekStats;
  weak_movement: WeakMovement[];
  focus: string[];
  top_tags: { tag: string; solved: number; attempted: number; acceptance: number }[];
  archive: WeekStats[];
}

export interface ProblemNote {
  body: string;
  updated_at: string | null;
}

export interface ProblemDetailData {
  problem: ProblemRef;
  attempts: number;
  wrong_attempts: number;
  solved: boolean;
  first_attempt: string | null;
  last_attempt: string | null;
  submissions: {
    verdict: string;
    language: string | null;
    submitted_at: string;
    time_consumed: number | null;
    memory_consumed: number | null;
  }[];
  revision: {
    id: number;
    interval_days: number;
    due_date: string;
    last_result: string | null;
  } | null;
  note: ProblemNote;
  preference: string | null;
}

export interface SettingsData {
  email: string | null;
  cf_handle: string | null;
  rank: string | null;
  current_rating: number | null;
  weekly_goal: number;
  solved_this_week: number;
  week_start: string;
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
