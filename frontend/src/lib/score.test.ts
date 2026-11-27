/* Unit tests for the shared score module (premium-apply batch).
   Run with the project's own toolchain — Node 24 strips types, no
   extra runner needed: `npm test` (node --test src/lib/score.test.ts).
   The dict is stubbed: explainFactors only needs the five explain*
   functions, so the stub carries exactly those. */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  MIN_SCORE_THRESHOLD,
  aboveThreshold,
  explainFactors,
  rankedContributions,
  scoreFromFactors,
} from './score.ts';
import type { Dict } from '../i18n/dict';

const t = {
  explainWeakTop: (tag: string, pct: number, pts: number) =>
    `Weak topic leads: ${tag} at ${pct}% adds ${pts.toFixed(1)}.`,
  explainDifficultyTop: (rating: number, user: number, pts: number) =>
    `Difficulty leads: rated ${rating} near ${user} adds ${pts.toFixed(1)}.`,
  explainRecentTop: (pts: number) => `Recent need leads: adds ${pts.toFixed(1)}.`,
  explainPracticeTop: (pts: number) =>
    `Practice priority leads: adds ${pts.toFixed(1)}.`,
  explainBalanced: (pts: number) => `Balanced: top factor adds ${pts.toFixed(1)}.`,
} as unknown as Dict;

const ctx = { userRating: 1478, problemRating: 1300 };

describe('scoreFromFactors', () => {
  it('matches the production formula on the demo picks', () => {
    // 1360E Polygon: 0.35*56.6 + 0.30*0 + 0.20*73 + 0.15*60 = 43.4
    assert.equal(
      scoreFromFactors({ w: 56.6, d: 0, r: 73, p: 60 }),
      43,
    );
    // 1366C Palindromic Paths: 0.35*0 + 0.30*61 + 0.20*50 + 0.15*60 = 37.3
    assert.equal(
      scoreFromFactors({ w: 0, d: 61, r: 50, p: 60 }),
      37,
    );
  });

  it('gives the 19 floor when nothing applies', () => {
    // W=D=0, R=50, P=60 -> 0 + 0 + 10 + 9 = 19
    assert.equal(scoreFromFactors({ w: 0, d: 0, r: 50, p: 60 }), 19);
  });

  it('caps at 100 for a perfect pick', () => {
    assert.equal(
      scoreFromFactors({ w: 100, d: 100, r: 100, p: 100 }),
      100,
    );
  });
});

describe('MIN_SCORE_THRESHOLD', () => {
  it('is 25, above the 19 floor', () => {
    assert.equal(MIN_SCORE_THRESHOLD, 25);
    assert.equal(aboveThreshold(25), true);
    assert.equal(aboveThreshold(24), false);
    assert.equal(aboveThreshold(19), false);
    assert.equal(aboveThreshold(43), true);
  });
});

describe('rankedContributions', () => {
  it('orders factors by weight × value', () => {
    const ranked = rankedContributions({ w: 56.6, d: 0, r: 73, p: 60 });
    assert.deepEqual(
      ranked.map((c) => c.key),
      ['w', 'r', 'p', 'd'],
    );
    assert.equal(ranked[0].points.toFixed(1), '19.8');
  });
});

describe('explainFactors', () => {
  it('names the weak tag when W dominates', () => {
    const s = explainFactors({ w: 56.6, d: 0, r: 73, p: 60 }, { ...ctx, weakTag: 'dp', acceptance: 45 }, t);
    assert.match(s, /dp/);
    assert.match(s, /45%/);
    assert.match(s, /19\.8/);
  });

  it('names difficulty when D dominates', () => {
    const s = explainFactors(
      { w: 0, d: 61, r: 50, p: 60 },
      { ...ctx, problemRating: 1500 },
      t,
    );
    assert.match(s, /1500/);
    assert.match(s, /18\.3/);
  });

  it('names recent need when R dominates', () => {
    const s = explainFactors({ w: 0, d: 0, r: 100, p: 60 }, ctx, t);
    assert.match(s, /Recent need/);
  });

  it('names practice priority when P dominates', () => {
    const s = explainFactors({ w: 0, d: 0, r: 50, p: 100 }, ctx, t);
    assert.match(s, /Practice priority/);
  });

  it('says balanced when no factor dominates', () => {
    // W 0.35*40=14, D 0.30*50=15, R 0.20*50=10, P 0.15*60=9 — top gap 1 < 2
    const s = explainFactors({ w: 40, d: 50, r: 50, p: 60 }, ctx, t);
    assert.match(s, /Balanced/);
  });
});
