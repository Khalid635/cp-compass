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
    (112, "A", "Petya and Strings", 800, ["implementation", "strings"]),
    (339, "A", "Helpful Maths", 800, ["greedy", "implementation", "sortings", "strings"]),
    (977, "A", "Wrong Subtraction", 800, ["implementation"]),
    (705, "A", "Hulk", 800, ["implementation"]),
    (546, "A", "Soldier and Bananas", 800, ["brute force", "implementation", "math"]),
    (1360, "A", "Minimal Square", 800, ["greedy", "math"]),
    (1433, "A", "Boring Apartments", 800, ["implementation", "math"]),
    (1520, "A", "Do Not Be Distracted!", 800, ["brute force", "implementation"]),
    (1703, "A", "YES or YES?", 800, ["brute force", "implementation", "strings"]),
    (1742, "A", "Sum", 800, ["implementation"]),
    (1791, "A", "Codeforces Checking", 800, ["implementation", "strings"]),
    (1807, "A", "Plus or Minus", 800, ["implementation"]),
    (1873, "A", "Short Sort", 800, ["brute force", "implementation"]),
    (1890, "A", "Doremy's Paint 3", 800, ["constructive algorithms"]),
    (1742, "B", "Increasing", 800, ["greedy", "implementation", "sortings"]),
    (1741, "A", "Compare T-Shirt Sizes", 800, ["implementation", "strings"]),
    (1741, "B", "Funny Permutation", 800, ["constructive algorithms", "math"]),
    (1741, "C", "Minimize the Thickness", 1100, ["brute force", "greedy", "math", "two pointers"]),
    (1731, "B", "Kill Demodogs", 1100, ["greedy", "math"]),
    (1360, "C", "Similar Pairs", 1100, ["constructive algorithms", "graph matchings", "greedy", "sortings"]),
    (1367, "C", "Social Distance", 1300, ["constructive algorithms", "greedy", "math"]),
    (1360, "E", "Polygon", 1300, ["dp", "graphs", "implementation", "shortest paths"]),
    (1366, "C", "Palindromic Paths", 1500, ["greedy", "math"]),
]

# Per-tag solve probability (dp and graphs are the demo persona's weak tags).
TAG_ACCEPT = {
    "dp": 0.32, "graphs": 0.41, "greedy": 0.72, "math": 0.78,
    "implementation": 0.85, "strings": 0.74, "brute force": 0.80,
    "sorting": 0.76, "binary search": 0.58, "data structures": 0.55,
}
ALL_TAGS = list(TAG_ACCEPT)

# Extra problem pool for history (contest 1500-1950). Names are REAL
# Codeforces titles, verified against the public problemset API (2026-11-26).
# Contests the API does not list are skipped, never faked. Ratings stay
# synthetic (rng) and tags stay index-based so the demo persona's weak-tag
# profile (dp/graphs weak) is preserved.
POOL_NAMES = {
    (1500, 'A'): 'Going Home',
    (1500, 'B'): 'Two chandeliers',
    (1500, 'C'): 'Matrix Sorting',
    (1500, 'D'): 'Tiles for Bathroom',
    (1500, 'E'): 'Subset Trick',
    (1514, 'A'): 'Perfectly Imperfect Array',
    (1514, 'B'): 'AND 0, Sum Big',
    (1514, 'C'): 'Product 1 Modulo N',
    (1514, 'D'): 'Cut and Stick',
    (1514, 'E'): "Baby Ehab's Hyper Apartment",
    (1521, 'A'): 'Nastia and Nearly Good Numbers',
    (1521, 'B'): 'Nastia and a Good Array',
    (1521, 'C'): 'Nastia and a Hidden Permutation',
    (1521, 'D'): 'Nastia Plays with a Tree',
    (1521, 'E'): 'Nastia and a Beautiful Matrix',
    (1528, 'A'): "Parsa's Humongous Tree",
    (1528, 'B'): 'Kavi on Pairing Duty',
    (1528, 'C'): 'Trees of Tranquillity',
    (1528, 'D'): "It's a bird! No, it's a plane! No, it's AaParsa!",
    (1528, 'E'): 'Mashtali and Hagh Trees',
    (1535, 'A'): 'Fair Playoff',
    (1535, 'B'): 'Array Reodering',
    (1535, 'C'): 'Unstable String',
    (1535, 'D'): 'Playoff Tournament',
    (1535, 'E'): 'Gold Transfer',
    (1542, 'A'): 'Odd Set',
    (1542, 'B'): 'Plus and Multiply',
    (1542, 'C'): 'Strange Function',
    (1542, 'D'): 'Priority Queue',
    (1549, 'A'): 'Gregor and Cryptography',
    (1549, 'B'): 'Gregor and the Pawn Game',
    (1556, 'A'): 'A Variety of Operations',
    (1556, 'B'): 'Take Your Places!',
    (1556, 'C'): 'Compressed Bracket Sequence',
    (1556, 'D'): 'Take a Guess',
    (1556, 'E'): 'Equilibrium',
    (1584, 'A'): 'Mathematical Addition',
    (1584, 'B'): 'Coloring Rectangles',
    (1584, 'C'): 'Two Arrays',
    (1584, 'D'): 'Guess the Permutation',
    (1584, 'E'): 'Game with Stones',
    (1598, 'A'): 'Computer Game',
    (1598, 'B'): 'Groups',
    (1598, 'C'): 'Delete Two Elements',
    (1598, 'D'): 'Training Session',
    (1598, 'E'): 'Staircases',
    (1605, 'A'): 'A.M. Deviation',
    (1605, 'B'): 'Reverse Sort',
    (1605, 'C'): 'Dominant Character',
    (1605, 'D'): 'Treelabeling',
    (1605, 'E'): 'Array Equalizer',
    (1612, 'A'): 'Distance',
    (1612, 'B'): 'Special Permutation',
    (1612, 'C'): 'Chat Ban',
    (1612, 'D'): 'X-Magic Pair',
    (1612, 'E'): 'Messages',
    (1619, 'A'): 'Square String?',
    (1619, 'B'): 'Squares and Cubes',
    (1619, 'C'): 'Wrong Addition',
    (1619, 'D'): "New Year's Problem",
    (1619, 'E'): 'MEX and Increments',
    (1626, 'A'): 'Equidistant Letters',
    (1626, 'B'): 'Minor Reduction',
    (1626, 'C'): 'Monsters And Spells',
    (1626, 'D'): 'Martial Arts Tournament',
    (1626, 'E'): 'Black and White Tree',
    (1633, 'A'): 'Div. 7',
    (1633, 'B'): 'Minority',
    (1633, 'C'): 'Kill the Monster',
    (1633, 'D'): 'Make Them Equal',
    (1633, 'E'): 'Spanning Tree Queries',
    (1647, 'A'): 'Madoka and Math Dad',
    (1647, 'B'): 'Madoka and the Elegant Gift',
    (1647, 'C'): 'Madoka and Childish Pranks',
    (1647, 'D'): 'Madoka and the Best School in Russia',
    (1647, 'E'): 'Madoka and the Sixth-graders',
    (1654, 'A'): 'Maximum Cake Tastiness',
    (1654, 'B'): 'Prefix Removals',
    (1654, 'C'): 'Alice and the Cake',
    (1654, 'D'): 'Potion Brewing Class',
    (1654, 'E'): 'Arithmetic Operations',
    (1661, 'A'): 'Array Balancing',
    (1661, 'B'): 'Getting Zero',
    (1661, 'C'): 'Water the Trees',
    (1661, 'D'): 'Progressions Covering',
    (1661, 'E'): 'Narrow Components',
    (1668, 'A'): 'Direction Change',
    (1668, 'B'): 'Social Distance',
    (1675, 'A'): 'Food for Animals',
    (1675, 'B'): 'Make It Increasing',
    (1675, 'C'): 'Detective Task',
    (1675, 'D'): 'Vertical Paths',
    (1675, 'E'): 'Replace With the Previous, Minimize',
    (1682, 'A'): 'Palindromic Indices',
    (1682, 'B'): 'AND Sorting',
    (1682, 'C'): 'LIS or Reverse LIS?',
    (1682, 'D'): 'Circular Spanning Tree',
    (1682, 'E'): 'Unordered Swaps',
    (1689, 'A'): 'Lex String',
    (1689, 'B'): 'Mystic Permutation',
    (1689, 'C'): 'Infected Tree',
    (1689, 'D'): 'Lena and Matrix',
    (1689, 'E'): 'ANDfinity',
    (1696, 'A'): 'NIT orz!',
    (1696, 'B'): 'NIT Destroys the Universe',
    (1696, 'C'): 'Fishingprince Plays With Array',
    (1696, 'D'): 'Permutation Graph',
    (1696, 'E'): 'Placing Jinas',
    (1703, 'A'): 'YES or YES?',
    (1703, 'B'): 'ICPC Balloons',
    (1703, 'C'): 'Cypher',
    (1703, 'D'): 'Double Strings',
    (1703, 'E'): 'Mirror Grid',
    (1710, 'A'): 'Color the Picture',
    (1710, 'B'): 'Rain',
    (1710, 'C'): 'XOR Triangle',
    (1710, 'D'): 'Recover the Tree',
    (1710, 'E'): 'Two Arrays',
    (1717, 'A'): 'Madoka and Strange Thoughts',
    (1717, 'B'): 'Madoka and Underground Competitions',
    (1717, 'C'): 'Madoka and Formal Statement',
    (1717, 'D'): 'Madoka and The Corruption Scheme',
    (1717, 'E'): 'Madoka and The Best University',
    (1731, 'A'): 'Joey Takes Money',
    (1731, 'B'): 'Kill Demodogs',
    (1731, 'C'): 'Even Subarrays',
    (1731, 'D'): "Valiant's New Map",
    (1731, 'E'): 'Graph Cost',
    (1738, 'A'): 'Glory Addicts',
    (1738, 'B'): 'Prefix Sum Addicts',
    (1738, 'C'): 'Even Number Addicts',
    (1738, 'D'): 'Permutation Addicts',
    (1738, 'E'): 'Balance Addicts',
    (1759, 'A'): 'Yes-Yes?',
    (1759, 'B'): 'Lost Permutation',
    (1759, 'C'): 'Thermostat',
    (1759, 'D'): 'Make It Round',
    (1759, 'E'): 'The Humanoid',
    (1766, 'A'): 'Extremely Round',
    (1766, 'B'): 'Notepad#',
    (1766, 'C'): 'Hamiltonian Wall',
    (1766, 'D'): 'Lucky Chains',
    (1766, 'E'): 'Decomposition',
    (1773, 'A'): 'Amazing Trick',
    (1773, 'B'): 'BinCoin',
    (1773, 'C'): 'Cactus Meets Torus',
    (1773, 'D'): 'Dominoes',
    (1773, 'E'): 'Easy Assembly',
    (1780, 'A'): 'Hayato and School',
    (1780, 'B'): 'GCD Partition',
    (1780, 'D'): 'Bit Guessing Game',
    (1780, 'E'): 'Josuke and Complete Graph',
    (1787, 'A'): 'Exponential Equation',
    (1787, 'B'): 'Number Factorization',
    (1787, 'C'): 'Remove the Bracket',
    (1787, 'D'): 'Game on Axis',
    (1787, 'E'): 'The Harmonization of XOR',
    (1794, 'A'): 'Prefix and Suffix Array',
    (1794, 'B'): 'Not Dividing',
    (1794, 'C'): 'Scoring Subsequences',
    (1794, 'D'): 'Counting Factorizations',
    (1794, 'E'): 'Labeling the Tree with Distances',
    (1801, 'A'): 'The Very Beautiful Blanket',
    (1801, 'B'): 'Buying gifts',
    (1801, 'C'): 'Music Festival',
    (1801, 'D'): 'The way home',
    (1801, 'E'): 'Gasoline prices',
    (1808, 'A'): 'Lucky Numbers',
    (1808, 'B'): 'Playing in a Casino',
    (1808, 'C'): 'Unlucky Numbers',
    (1808, 'D'): 'Petya, Petya, Petr, and Palindromes',
    (1815, 'A'): 'Ian and Array Sorting',
    (1815, 'B'): 'Sum Graph',
    (1815, 'C'): 'Between',
    (1815, 'D'): 'XOR Counting',
    (1815, 'E'): 'Bosco and Particle',
    (1822, 'A'): 'TubeTube Feed',
    (1822, 'B'): 'Karina and Array',
    (1822, 'C'): 'Bun Lover',
    (1822, 'D'): 'Super-Permutation',
    (1822, 'E'): 'Making Anti-Palindromes',
    (1829, 'A'): 'Love Story',
    (1829, 'B'): 'Blank Space',
    (1829, 'C'): 'Mr. Perfectly Fine',
    (1829, 'D'): 'Gold Rush',
    (1829, 'E'): 'The Lakes',
    (1836, 'A'): 'Destroyer',
    (1836, 'B'): 'Astrophysicists',
    (1843, 'A'): 'Sasha and Array Coloring',
    (1843, 'B'): 'Long Long',
    (1843, 'C'): 'Sum in Binary Tree',
    (1843, 'D'): 'Apple Tree',
    (1843, 'E'): 'Tracking Segments',
    (1850, 'A'): 'To My Critics',
    (1850, 'B'): 'Ten Words of Wisdom',
    (1850, 'C'): 'Word on the Paper',
    (1850, 'D'): 'Balanced Round',
    (1850, 'E'): 'Cardboard for Pictures',
    (1857, 'A'): 'Array Coloring',
    (1857, 'B'): 'Maximum Rounding',
    (1857, 'C'): 'Assembly via Minimums',
    (1857, 'D'): 'Strong Vertices',
    (1857, 'E'): 'Power of Points',
    (1864, 'A'): 'Increasing and Decreasing',
    (1864, 'B'): 'Swap and Reverse',
    (1864, 'C'): 'Divisor Chain',
    (1864, 'D'): 'Matrix Cascade',
    (1864, 'E'): 'Guess Game',
    (1878, 'A'): 'How Much Does Daytona Cost?',
    (1878, 'B'): 'Aleksa and Stack',
    (1878, 'C'): 'Vasilije in Cacak',
    (1878, 'D'): 'Reverse Madness',
    (1878, 'E'): 'Iva & Pav',
    (1885, 'A'): 'Deterministic Scheduling for Extended Reality over 5G and Beyond',
    (1899, 'A'): 'Game with Integers',
    (1899, 'B'): '250 Thousand Tons of TNT',
    (1899, 'C'): 'Yarik and Array',
    (1899, 'D'): 'Yarik and Musical Notes',
    (1899, 'E'): 'Queue Sort',
    (1906, 'A'): 'Easy As ABC',
    (1906, 'B'): 'Button Pressing',
    (1906, 'C'): 'Cursed Game',
    (1906, 'D'): 'Spaceship Exploration',
    (1906, 'E'): 'Merge Not Sort',
    (1913, 'A'): 'Rating Increase',
    (1913, 'B'): 'Swap and Delete',
    (1913, 'C'): 'Game with Multiset',
    (1913, 'D'): 'Array Collapse',
    (1913, 'E'): 'Matrix Problem',
    (1920, 'A'): 'Satisfying Constraints',
    (1920, 'B'): 'Summation Game',
    (1920, 'C'): 'Partitioning the Array',
    (1920, 'D'): 'Array Repetition',
    (1920, 'E'): 'Counting Binary Strings',
    (1927, 'A'): 'Make it White',
    (1927, 'B'): 'Following the String',
    (1927, 'C'): 'Choose the Different Ones!',
    (1927, 'D'): 'Find the Different Ones!',
    (1927, 'E'): 'Klever Permutation',
    (1934, 'A'): 'Too Min Too Max',
    (1934, 'B'): 'Yet Another Coin Problem',
    (1934, 'C'): 'Find a Mine',
    (1934, 'E'): 'Weird LCM Operations',
    (1941, 'A'): 'Rudolf and the Ticket',
    (1941, 'B'): 'Rudolf and 121',
    (1941, 'C'): 'Rudolf and the Ugly String',
    (1941, 'D'): 'Rudolf and the Ball Game',
    (1941, 'E'): 'Rudolf and k Bridges',
    (1948, 'A'): 'Special Characters',
    (1948, 'B'): 'Array Fix',
    (1948, 'C'): 'Arrow Path',
    (1948, 'D'): 'Tandem Repeats?',
    (1948, 'E'): 'Clique Partition',
}

POOL = []
for cid in range(1500, 1951, 7):
    for idx, tag in [("A", "implementation"), ("B", "greedy"), ("C", "dp"),
                     ("D", "graphs"), ("E", "math")]:
        name = POOL_NAMES.get((cid, idx))
        if name is None:
            continue
        POOL.append((cid, idx, name, rng.choice([800, 900, 1000, 1100, 1200, 1300, 1400]), [tag]))


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
        # Structured "why" — the frontend renders the sentence in the active
        # locale (EN/BN). Never build a Bangla/English sentence here.
        hit = [t for t in tags if t in weak_names]
        if hit:
            w = next(x for x in weak if x["tag"] == hit[0])
            if w["acceptance"] < 0.5:
                return {"kind": "weak_acceptance", "tag": hit[0],
                        "acceptance": int(w["acceptance"] * 100),
                        "problem_rating": rating, "user_rating": RATING}
            return {"kind": "weak_wrong", "tag": hit[0],
                    "avg_wrong_attempts": w["avg_wrong_attempts"],
                    "problem_rating": rating, "user_rating": RATING}
        return {"kind": "near_rating", "user_rating": RATING,
                "problem_rating": rating}

    def score_for(tags, rating):
        # Demo mirror of the real 0-100 formula: weak-tag bonus + closeness
        # to the rating+100 sweet spot, on a 55 base.
        s = 55
        if any(t in weak_names for t in tags):
            s += 25
        s += max(0, 20 - abs(rating - (RATING + 100)) * 0.1)
        return min(99, int(s))

    def entry(cid, idx, name, rating, tags):
        return {"contest_id": cid, "index": idx, "name": name,
                "rating": rating, "tags": tags, "why": why_for(tags, rating),
                "score": score_for(tags, rating)}

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
        r["why"] = {**r["why"], "demo_out_of_band": True}
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


# ---------------------------------------------------------------------------
# Phase 2 — demo payloads for the new pages. All computed from the same
# deterministic SUBMISSIONS / RATING_HISTORY above, so demo numbers always
# agree with the demo dashboard. Nothing here is invented.
# ---------------------------------------------------------------------------

# One sample note so the Problem Detail notes feature is visible in demo.
DEMO_NOTES = {
    (1360, "E"): "DP on grid — the corner cells need their own base case.",
    (1366, "C"): "Greedy works here because the path cost only depends on\n"
                 "the colour of the two ends. Check the editorial idea.",
}

DEMO_WEEKLY_GOAL = 5


def _demo_longest_streak():
    days = sorted({s["submitted_at"][:10] for s in SUBMISSIONS if s["verdict"] == "OK"})
    if not days:
        return 0
    best = run = 1
    prev = date.fromisoformat(days[0])
    for dstr in days[1:]:
        d = date.fromisoformat(dstr)
        run = run + 1 if (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d
    return best


def _demo_buckets():
    buckets = [("800-1199", 800, 1199), ("1200-1599", 1200, 1599),
               ("1600-1999", 1600, 1999), ("2000+", 2000, None)]
    per = {b[0]: {"attempted": set(), "solved": set()} for b in buckets}
    per["unrated"] = {"attempted": set(), "solved": set()}
    for s in SUBMISSIONS:
        rating = s["rating"]
        if rating is None:
            bucket = "unrated"
        else:
            bucket = next(
                (b[0] for b in buckets
                 if rating >= b[1] and (b[2] is None or rating <= b[2])),
                "unrated",
            )
        per[bucket]["attempted"].add((s["contest_id"], s["index"]))
        if s["verdict"] == "OK":
            per[bucket]["solved"].add((s["contest_id"], s["index"]))
    out = []
    for bid, _lo, _hi in buckets:
        attempted = len(per[bid]["attempted"])
        solved = len(per[bid]["solved"])
        out.append({"bucket": bid, "attempted": attempted, "solved": solved,
                    "acceptance": round(solved / attempted, 2) if attempted else 0.0})
    attempted = len(per["unrated"]["attempted"])
    solved = len(per["unrated"]["solved"])
    out.append({"bucket": "unrated", "attempted": attempted, "solved": solved,
                "acceptance": round(solved / attempted, 2) if attempted else 0.0})
    return out


def _demo_contests():
    by_day = {}
    for s in SUBMISSIONS:
        day = s["submitted_at"][:10]
        cell = by_day.setdefault(day, {"solved": set(), "attempted": set(), "tags": {}})
        cell["attempted"].add((s["contest_id"], s["index"]))
        if s["verdict"] == "OK":
            cell["solved"].add((s["contest_id"], s["index"]))
        for tag in s["tags"]:
            t = cell["tags"].setdefault(tag, [0, 0])
            t[1] += 1
            if s["verdict"] == "OK":
                t[0] += 1
    out = []
    prev = None
    for p in RATING_HISTORY:
        day = p["date"][:10]
        cell = by_day.get(day, {"solved": set(), "attempted": set(), "tags": {}})
        weak_tags = sorted(
            tag for tag, (s, a) in cell["tags"].items() if a >= 2 and s / a < 0.5)
        out.append({
            "contest_id": int(p["contest"].replace("Round #", "")),
            "contest_name": p["contest"],
            "date": day,
            "old_rating": prev,
            "new_rating": p["rating"],
            "delta": p["rating"] - prev if prev is not None else None,
            "solved_that_day": len(cell["solved"]),
            "attempted_that_day": len(cell["attempted"]),
            "weak_tags_that_day": weak_tags,
        })
        prev = p["rating"]
    out.reverse()
    return out


def analytics_payload():
    return {
        "peak_rating": max(p["rating"] for p in RATING_HISTORY),
        "current_rating": RATING,
        "streak": _streak(),
        "longest_streak": _demo_longest_streak(),
        "solved": len(SOLVED_KEYS),
        "buckets": _demo_buckets(),
        "tag_strengths": TAG_STRENGTHS,
        "milestones": [
            {"threshold": th, "unlocked": len(SOLVED_KEYS) >= th,
             "solved": len(SOLVED_KEYS)}
            for th in (10, 25, 50, 100, 200)
        ],
        "contests": _demo_contests(),
    }


def calendar_payload(year, month):
    from calendar import monthrange

    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    per_day = {}
    for s in SUBMISSIONS:
        d = date.fromisoformat(s["submitted_at"][:10])
        if first <= d <= last:
            cell = per_day.setdefault(d.isoformat(), {"solved": 0, "attempted": 0})
            cell["attempted"] += 1
            if s["verdict"] == "OK":
                cell["solved"] += 1
    days = [{"date": d, **c} for d, c in sorted(per_day.items())]
    return {"year": year, "month": month, "days": days}


def day_submissions(d):
    rows = [s for s in SUBMISSIONS if s["submitted_at"][:10] == d.isoformat()]
    rows.sort(key=lambda s: s["submitted_at"], reverse=True)
    return [_recent_row(s) for s in rows]


def _demo_week_stats(monday):
    start = monday
    end = monday + timedelta(days=7)
    attempted, solved = set(), set()
    tag_attempted, tag_solved = {}, {}
    for s in SUBMISSIONS:
        d = date.fromisoformat(s["submitted_at"][:10])
        if not (start <= d < end):
            continue
        key = (s["contest_id"], s["index"])
        attempted.add(key)
        if s["verdict"] == "OK":
            solved.add(key)
        for tag in s["tags"]:
            tag_attempted.setdefault(tag, set()).add(key)
            if s["verdict"] == "OK":
                tag_solved.setdefault(tag, set()).add(key)
    tag_acc = {
        tag: {"solved": len(tag_solved.get(tag, set())),
              "attempted": len(a),
              "acceptance": round(len(tag_solved.get(tag, set())) / len(a), 2) if a else 0.0}
        for tag, a in tag_attempted.items()
    }
    return {
        "week_start": monday.isoformat(),
        "solved": len(solved),
        "attempted": len(attempted),
        "acceptance": round(len(solved) / len(attempted), 2) if attempted else 0.0,
        "tag_acceptance": tag_acc,
    }


def weekly_report_payload():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    prev_monday = monday - timedelta(days=7)
    current = _demo_week_stats(monday)
    previous = _demo_week_stats(prev_monday)
    weak = [t for t in TAG_STRENGTHS if t["weak"]]
    movement = []
    for w in weak:
        tag = w["tag"]
        cur = current["tag_acceptance"].get(tag)
        prv = previous["tag_acceptance"].get(tag)
        movement.append({
            "tag": tag,
            "this_week": cur["acceptance"] if cur else None,
            "last_week": prv["acceptance"] if prv else None,
            "delta": (round(cur["acceptance"] - prv["acceptance"], 2)
                      if cur and prv else None),
            "weak_score": w.get("weak_score", 0.5),
        })
    movement.sort(key=lambda m: (m["delta"] is None,
                                 m["delta"] if m["delta"] is not None else 0))
    focus = [t["tag"] for t in sorted(weak, key=lambda t: t["acceptance"])[:3]]
    top_tags = sorted(
        current["tag_acceptance"].items(), key=lambda kv: -kv[1]["attempted"])[:5]
    archive = []
    for i in range(8):
        ws = _demo_week_stats(monday - timedelta(days=7 * (i + 1)))
        if ws["attempted"] > 0:
            archive.append(ws)
    return {
        "current": current,
        "previous": previous,
        "weak_movement": movement,
        "focus": focus,
        "top_tags": [{"tag": tag, **vals} for tag, vals in top_tags],
        "archive": archive,
    }


def _demo_problem_lookup(contest_id, index):
    for cid, idx, name, rating, tags in FAMOUS:
        if cid == contest_id and idx == index:
            return {"contest_id": cid, "index": idx, "name": name,
                    "rating": rating, "tags": tags}
    for cid, idx, name, rating, tags in POOL:
        if cid == contest_id and idx == index:
            return {"contest_id": cid, "index": idx, "name": name,
                    "rating": rating, "tags": tags}
    for s in SUBMISSIONS:
        if s["contest_id"] == contest_id and s["index"] == index:
            return {"contest_id": contest_id, "index": index, "name": s["name"],
                    "rating": s["rating"], "tags": s["tags"]}
    return None


def problem_detail_payload(contest_id, index):
    prob = _demo_problem_lookup(contest_id, index)
    if prob is None:
        return None
    subs = [s for s in SUBMISSIONS
            if s["contest_id"] == contest_id and s["index"] == index]
    subs.sort(key=lambda s: s["submitted_at"], reverse=True)
    solved = any(s["verdict"] == "OK" for s in subs)
    note_body = DEMO_NOTES.get((contest_id, index), "")
    return {
        "problem": prob,
        "attempts": len(subs),
        "wrong_attempts": sum(1 for s in subs if s["verdict"] != "OK"),
        "solved": solved,
        "first_attempt": subs[-1]["submitted_at"] if subs else None,
        "last_attempt": subs[0]["submitted_at"] if subs else None,
        "submissions": [{
            "verdict": s["verdict"], "language": s["language"],
            "submitted_at": s["submitted_at"],
            "time_consumed": None, "memory_consumed": None,
        } for s in subs],
        "revision": None,
        "note": {"body": note_body, "updated_at": None},
        "preference": None,
    }


def settings_payload():
    monday = date.today() - timedelta(days=date.today().weekday())
    week = _demo_week_stats(monday)
    return {
        "email": None,
        "cf_handle": HANDLE,
        "rank": RANK,
        "current_rating": RATING,
        "weekly_goal": DEMO_WEEKLY_GOAL,
        "solved_this_week": week["solved"],
        "week_start": monday.isoformat(),
    }


def export_payload():
    return {
        "handle": HANDLE,
        "email": None,
        "exported_at": datetime.utcnow().isoformat(),
        "submissions": [
            {"cf_id": s["id"], "verdict": s["verdict"],
             "submitted_at": s["submitted_at"]} for s in SUBMISSIONS],
        "tag_stats": TAG_STRENGTHS,
        "revisions": REVISIONS["due"] + REVISIONS["upcoming"] + REVISIONS["done"],
        "rating_history": [
            {"contest_id": int(p["contest"].replace("Round #", "")),
             "contest_name": p["contest"], "old_rating": None,
             "new_rating": p["rating"], "date": p["date"][:10]}
            for p in RATING_HISTORY],
        "preferences": [],
        "notes": [{"contest_id": cid, "index": idx, "body": body,
                   "updated_at": None}
                  for (cid, idx), body in DEMO_NOTES.items()],
        "daily_stats": [],
        "weekly_reports": [],
    }
