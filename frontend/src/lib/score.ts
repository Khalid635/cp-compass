/* One score() for demo + landing + real app (premium-apply batch).
   The recommendation score is Score = 0.35W + 0.30D + 0.20R + 0.15P
   (blueprint §6), every factor normalised 0–100:
   - W — weak-topic relevance: the problem's weakest tag's weak_score.
   - D — difficulty suitability: 100 at rating+100, 0 at ±200 away.
   - R — recent learning need: how badly the tag went lately.
   - P — practice priority: 100 tried-but-unsolved, 60 otherwise.
   The backend (services.recommend / seed._recommendations) computes the
   same formula and returns the same four factors with every pick; this
   module is the frontend mirror, used by the landing "Why this problem?"
   cards and the Practice cards. No simplified mirror score anywhere.
   Picks below MIN_SCORE_THRESHOLD are dropped; showing 2 picks is fine. */
import type { Dict } from '../i18n/dict';

export interface ScoreFactors {
  w: number;
  d: number;
  r: number;
  p: number;
}

export const SCORE_WEIGHTS: Record<keyof ScoreFactors, number> = {
  w: 0.35,
  d: 0.3,
  r: 0.2,
  p: 0.15,
} as const;

/** Picks below this are dropped, in the real app and in the demo alike.
    The formula floor is 19 (R=50, P=60, W=D=0). */
export const MIN_SCORE_THRESHOLD = 25;

export function scoreFromFactors(f: ScoreFactors): number {
  return Math.round(
    SCORE_WEIGHTS.w * f.w +
      SCORE_WEIGHTS.d * f.d +
      SCORE_WEIGHTS.r * f.r +
      SCORE_WEIGHTS.p * f.p,
  );
}

export function aboveThreshold(score: number): boolean {
  return score >= MIN_SCORE_THRESHOLD;
}

/** Each factor's contribution to the total, highest first. */
export function rankedContributions(f: ScoreFactors): {
  key: keyof ScoreFactors;
  points: number;
}[] {
  return (Object.keys(SCORE_WEIGHTS) as (keyof ScoreFactors)[])
    .map((key) => ({ key, points: SCORE_WEIGHTS[key] * f[key] }))
    .sort((a, b) => b.points - a.points);
}

export interface ExplainContext {
  /** Weakest tag on the problem, when the pick targets one. */
  weakTag?: string;
  /** That tag's acceptance %, when known. */
  acceptance?: number;
  userRating: number;
  problemRating: number;
}

/** Generate the "why this pick" sentence FROM the factor values —
    the top contributing factor names the reason; nothing hand-written
    per problem. The sentence is rendered in the active locale via the
    dict functions, so EN and BN stay in step. */
export function explainFactors(
  f: ScoreFactors,
  ctx: ExplainContext,
  t: Dict,
): string {
  const [top, second] = rankedContributions(f);
  // No single factor dominates — the pick is balanced across factors.
  if (top.points - second.points < 2) {
    return t.explainBalanced(top.points);
  }
  switch (top.key) {
    case 'w':
      return t.explainWeakTop(
        ctx.weakTag ?? '',
        ctx.acceptance ?? 0,
        top.points,
      );
    case 'd':
      return t.explainDifficultyTop(
        ctx.problemRating,
        ctx.userRating,
        top.points,
      );
    case 'r':
      return t.explainRecentTop(top.points);
    case 'p':
      return t.explainPracticeTop(top.points);
  }
}
