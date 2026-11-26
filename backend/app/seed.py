"""Deterministic demo dataset — labelled honestly as demo data everywhere it
is shown. The demo persona ('demo_coder', Specialist, 1478) has ~6 months of
practice: ~340 submissions, ~145 solved. The user's own Codeforces data is
thin (28 solved), so this seed is what makes the demo worth looking at.
"""
import random
from datetime import date, datetime, timedelta

rng = random.Random(42)

HANDLE = "demo_coder"
RATING = 1478
RANK = "Specialist"

# Famous, real Codeforces problems (contest, index, name, rating, tags).
FAMOUS = [
    (4, "A", "Watermelon", 800, ["brute force", "math"]),
    (71, "A", "Way Too Long Words", 800, ["strings"]),
    (231, "A", "Team", 800, ["brute force", "greedy"]),
    (158, "A", "Next Round", 800, ["implementation"]),
    (282, "A", "Bit++", 800, ["implementation"]),
    (50, "A", "Domino piling", 800, ["greedy", "math"]),
    (112, "A", "Petya and Strings", 800, ["strings"]),
    (339, "A", "Helpful Maths", 800, ["greedy", "implementation", "sorting"]),
    (977, "A", "Wrong Subtraction", 800, ["implementation"]),
    (705, "A", "Hulk", 800, ["implementation"]),
    (546, "A", "Soldier and Bananas", 800, ["brute force", "math"]),
    (1360, "A", "Minimal Square", 800, ["brute force", "math"]),
    (1433, "A", "Boring Apartments", 800, ["implementation", "math"]),
    (1520, "A", "Do Not Be Distracted!", 800, ["brute force", "implementation"]),
    (1703, "A", "YES or YES?", 800, ["implementation", "strings"]),
    (1742, "A", "Sum", 800, ["implementation"]),
    (1791, "A", "Codeforces Checking", 800, ["implementation"]),
    (1807, "A", "Plus or Minus", 800, ["implementation", "math"]),
    (1873, "A", "Short Sort", 800, ["implementation", "strings"]),
    (1890, "A", "Doremy's Paint 3", 800, ["implementation"]),
    (1742, "B", "Increasing", 800, ["greedy", "sorting"]),
    (1741, "A", "Compare T-Shirt Sizes", 800, ["implementation", "strings"]),
    (1741, "B", "Fun with Even Subarrays", 900, ["greedy", "implementation"]),
    (1741, "C", "Mini-Max Sum", 1000, ["greedy", "math"]),
    (1731, "B", "Kill Demodogs", 1000, ["greedy", "math"]),
    (1360, "C", "Similar Pairs", 1200, ["greedy", "math"]),
    (1367, "C", "Social Distance", 1200, ["greedy", "implementation"]),
    (1360, "E", "Polygon", 1200, ["brute force", "greedy"]),
    (1366, "C", "Palindromic Paths", 1300, ["dp", "math"]),
]

# Per-tag solve probability (dp and graphs are the demo persona's weak tags).
TAG_ACCEPT = {
    "dp": 0.32, "graphs": 0.41, "greedy": 0.72, "math": 0.78,
    "implementation": 0.85, "strings": 0.74, "brute force": 0.80,
    "sorting": 0.76, "binary search": 0.58, "data structures": 0.55,
}
ALL_TAGS = list(TAG_ACCEPT)

# Extra synthetic problem pool for history (contest 1500–1950).
POOL = []
for cid in range(1500, 1951, 7):
    for idx, tag in [("A", "implementation"), ("B", "greedy"), ("C", "dp"),
                     ("D", "graphs"), ("E", "math")]:
        POOL.append((cid, idx, f"Problem {cid}{idx}", rng.choice([800, 900, 1000, 1100, 1200, 1300, 1400]), [tag]))


def _gen_submissions():
    subs = []
    today = date.today()
    sid = 900000
    for day_offset in range(179, -1, -1):
        d = today - timedelta(days=day_offset)
        # Practice ~5 days a week, 1–5 submissions a day.
        if rng.random() > 0.65:
            continue
        for _ in range(rng.randint(1, 5)):
            # History uses the synthetic pool only — the famous problems stay
            # unsolved so they can be recommended.
            contest_id, idx, name, rating, tags = rng.choice(POOL)
            tag = tags[0]
            ok = rng.random() < TAG_ACCEPT.get(tag, 0.7)
            verdict = "OK" if ok else rng.choice(
                ["WRONG_ANSWER", "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "RUNTIME_ERROR"])
            ts = datetime(d.year, d.month, d.day, rng.randint(9, 22), rng.randint(0, 59))
            sid += 1
            subs.append({
                "id": sid, "contest_id": contest_id, "index": idx, "name": name,
                "rating": rating, "tags": tags, "verdict": verdict,
                "language": rng.choice(["GNU C++17", "GNU C++17", "GNU C++17", "Python 3"]),
                "submitted_at": ts.isoformat(),
            })
    subs.sort(key=lambda s: s["submitted_at"], reverse=True)
    # Guarantee a live streak: an accepted submission today and yesterday.
    for day_offset in (0, 1):
        d = today - timedelta(days=day_offset)
        if not any(s["submitted_at"][:10] == d.isoformat() and s["verdict"] == "OK" for s in subs):
            cid, idx, name, rating, tags = FAMOUS[day_offset % len(FAMOUS)]
            sid += 1
            subs.append({
                "id": sid, "contest_id": cid, "index": idx, "name": name,
                "rating": rating, "tags": tags, "verdict": "OK",
                "language": "GNU C++17",
                "submitted_at": datetime(d.year, d.month, d.day, 18, 30).isoformat(),
            })
    subs.sort(key=lambda s: s["submitted_at"], reverse=True)
    return subs


SUBMISSIONS = _gen_submissions()
SOLVED_KEYS = {(s["contest_id"], s["index"]) for s in SUBMISSIONS if s["verdict"] == "OK"}


def _rating_history():
    points = []
    rating = 1120
    d = date.today() - timedelta(days=178)
    for i in range(14):
        rating += rng.randint(-40, 95)
        rating = max(1050, min(1520, rating))
        points.append({"contest": f"Round #{1700 + i * 7}", "rating": rating,
                       "date": (d + timedelta(days=i * 13)).isoformat()})
    points[-1]["rating"] = RATING
    return points


RATING_HISTORY = _rating_history()


def _tag_strengths():
    per = {}
    for s in SUBMISSIONS:
        for t in s["tags"]:
            st = per.setdefault(t, {"attempted": set(), "solved": set(), "wrong": 0})
            st["attempted"].add((s["contest_id"], s["index"]))
            if s["verdict"] == "OK":
                st["solved"].add((s["contest_id"], s["index"]))
            else:
                st["wrong"] += 1
    out = []
    for t, st in per.items():
        attempted, solved = len(st["attempted"]), len(st["solved"])
        acc = solved / attempted if attempted else 0
        out.append({
            "tag": t, "attempted": attempted, "solved": solved,
            "acceptance": round(acc, 2),
            "avg_wrong_attempts": round(st["wrong"] / attempted, 1) if attempted else 0,
            "weak": attempted >= 5 and (acc < 0.5 or st["wrong"] / attempted >= 2),
        })
    out.sort(key=lambda x: x["acceptance"])
    return out


TAG_STRENGTHS = _tag_strengths()


def _heatmap(weeks=26):
    start = date.today() - timedelta(days=weeks * 7 - 1)
    counts = {}
    for s in SUBMISSIONS:
        if s["verdict"] == "OK":
            day = s["submitted_at"][:10]
            counts[day] = counts.get(day, 0) + 1
    days, d = [], start
    while d <= date.today():
        days.append({"date": d.isoformat(), "count": counts.get(d.isoformat(), 0)})
        d += timedelta(days=1)
    return days


HEATMAP = _heatmap()


def _streak():
    days = {s["submitted_at"][:10] for s in SUBMISSIONS if s["verdict"] == "OK"}
    today = date.today()
    cursor = today if today.isoformat() in days else today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _recommendations():
    """In-band first (rating .. rating+200, weak tags first); top up with the
    closest-rated unsolved famous problems so the demo always has a full list.
    The top-up 'why' says so plainly — below-band practice for a weak tag."""
    weak = [t for t in TAG_STRENGTHS if t["weak"]]
    weak_names = {w["tag"] for w in weak}

    def why_for(tags, rating):
        hit = [t for t in tags if t in weak_names]
        if hit:
            w = next(x for x in weak if x["tag"] == hit[0])
            return (f"{hit[0]}-তে তোমার acceptance {int(w['acceptance'] * 100)}% — "
                    f"এই প্রবলেমটি {rating} rating-এর।")
        return f"তোমার rating {RATING}-এর কাছাকাছি — এই প্রবলেমটি {rating} rating-এর।"

    def entry(cid, idx, name, rating, tags):
        return {"contest_id": cid, "index": idx, "name": name,
                "rating": rating, "tags": tags, "why": why_for(tags, rating)}

    in_band, rest = [], []
    for cid, idx, name, rating, tags in FAMOUS:
        if (cid, idx) in SOLVED_KEYS:
            continue
        (in_band if RATING <= rating <= RATING + 200 else rest).append(
            entry(cid, idx, name, rating, tags))
    in_band.sort(key=lambda r: (any(t in weak_names for t in r["tags"]),
                                -abs(r["rating"] - RATING)), reverse=True)
    rest.sort(key=lambda r: (any(t in weak_names for t in r["tags"]),
                             -abs(r["rating"] - RATING)), reverse=True)
    for r in rest[:max(0, 12 - len(in_band))]:
        r["why"] = r["why"] + " (ডেমো: rating-ব্যান্ডের বাইরের প্র্যাকটিস)"
    return (in_band + rest)[:12]


RECOMMENDATIONS = _recommendations()


def _revisions():
    due, upcoming, done = [], [], []
    hard = [s for s in SUBMISSIONS if s["verdict"] != "OK"][:8]
    seen = set()
    for s in hard:
        key = (s["contest_id"], s["index"])
        if key in seen:
            continue
        seen.add(key)
        item = {"id": len(due) + len(upcoming) + len(done) + 1,
                "problem": {"contest_id": s["contest_id"], "index": s["index"],
                            "name": s["name"], "rating": s["rating"], "tags": s["tags"]},
                "interval_days": 3, "wrong_attempts": 4,
                "due_date": (date.today() - timedelta(days=1)).isoformat(),
                "last_result": None, "done": False}
        (due if len(due) < 3 else upcoming).append(item)
    for s in [x for x in SUBMISSIONS if x["verdict"] == "OK"][:2]:
        done.append({"id": 100 + len(done),
                     "problem": {"contest_id": s["contest_id"], "index": s["index"],
                                 "name": s["name"], "rating": s["rating"], "tags": s["tags"]},
                     "interval_days": 7, "wrong_attempts": 3,
                     "due_date": (date.today() - timedelta(days=2)).isoformat(),
                     "last_result": "good", "done": True})
    return {"due": due, "upcoming": upcoming, "done": done}


REVISIONS = _revisions()


def _recent_row(s):
    """Nested shape the frontend expects — same as services.recent_submissions."""
    return {
        "problem": {"contest_id": s["contest_id"], "index": s["index"],
                    "name": s["name"], "rating": s["rating"], "tags": s["tags"]},
        "verdict": s["verdict"],
        "language": s["language"],
        "submitted_at": s["submitted_at"],
    }


def dashboard_payload():
    solved = len(SOLVED_KEYS)
    return {
        "user": {"handle": HANDLE, "rating": RATING, "rank": RANK},
        "stats": {"rating": RATING, "solved": solved, "streak": _streak(),
                  "revisions_due": len(REVISIONS["due"])},
        "rating_history": RATING_HISTORY,
        "today_plan": {"problems": RECOMMENDATIONS[:3],
                       "revisions": REVISIONS["due"][:2]},
        "tag_strengths": TAG_STRENGTHS,
        "heatmap": HEATMAP,
        "recent": [_recent_row(s) for s in SUBMISSIONS[:10]],
        "has_handle": True,
        "synced": True,
        "demo": True,
    }
