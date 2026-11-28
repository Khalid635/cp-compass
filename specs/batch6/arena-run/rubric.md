# Batch 6 arena rubric — cookie + CSRF design

Score each solution /100:

- Correctness /30: does the design actually work for this app?
  Cross-site prod cookies (Vercel → Render), plain-HTTP localhost
  dev, SSE stream, Google OAuth, TOTP second step, refresh rotation
  + reuse → revoke-family, logout clearing cookies. Any wrong claim
  about how browsers/cookies/CORS/EventSource work loses points.
- Completeness /25: all six questions decided explicitly; cookie
  names + flags for prod AND dev; backend + frontend change lists;
  live-session migration; legacy localStorage cleanup.
- Specificity /15: concrete values (names, flags, header names,
  endpoint paths, Max-Age numbers) instead of generic advice.
  Code sketches where they decide something.
- Robustness /20: the three failure modes + patches; third-party
  cookies blocked; CSRF bypass attempts considered (stolen
  double-submit token? Origin spoofing? SameSite bypass via
  top-level GET?); what happens when a check fails.
- Clarity /10: a builder can implement it without guessing.

The highest scorer is the design the N4 build follows. This is a
spawn-probe pick, NOT a tournament winner: no attack/defend/judge
rounds run in this host.
