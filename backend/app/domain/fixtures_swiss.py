# Swiss pairing for one round: standings from history, bye choice, rematch-free pairing with
# minimum total |score difference| via branch-and-bound (FR-1.3, spec §5.7-B). Pure, no libraries.
import math

from app.domain.fixtures_common import bad_request
from app.domain.rule_error import RuleError

RESULTS = ["home", "away", "draw"]


def _read_params(teams, params):
    if not isinstance(params, dict):
        raise bad_request(["params"])
    n = len(teams)
    total = params.get("total_rounds", max(1, math.ceil(math.log2(n))))
    if type(total) is not int or not (1 <= total <= n - 1):
        raise bad_request(["total_rounds"])
    round_no = params.get("round", 1)
    if type(round_no) is not int or not (1 <= round_no <= total):
        raise bad_request(["round"])
    history = params.get("history", [])
    if not isinstance(history, list):
        raise bad_request(["history"])

    rounds_seen = []
    for h in history:
        if not isinstance(h, dict) or type(h.get("round")) is not int or not isinstance(h.get("matches"), list):
            raise bad_request(["history"])
        if h.get("bye") is not None and h["bye"] not in teams:
            raise bad_request(["history"], "unknown bye team")
        for m in h["matches"]:
            if (not isinstance(m, dict) or m.get("home") not in teams or m.get("away") not in teams
                    or m["home"] == m["away"] or m.get("result") not in RESULTS):
                raise bad_request(["history"], "bad history match")
        rounds_seen.append(h["round"])
    if sorted(rounds_seen) != list(range(1, round_no)):
        raise bad_request(["history"], "history must contain exactly rounds 1..round-1")
    return total, round_no, history


def swiss_standings(teams, history):
    """Return (standings rows, score dict, met pairs set, had_bye set) from history only."""
    score = {t: 0.0 for t in teams}
    opponents = {t: [] for t in teams}
    met = set()
    had_bye = set()
    for h in history:
        if h.get("bye") is not None:
            score[h["bye"]] += 1.0  # a bye counts as a win
            had_bye.add(h["bye"])
        for m in h["matches"]:
            home, away = m["home"], m["away"]
            if m["result"] == "home":
                score[home] += 1.0
            elif m["result"] == "away":
                score[away] += 1.0
            else:
                score[home] += 0.5
                score[away] += 0.5
            opponents[home].append(away)
            opponents[away].append(home)
            met.add(frozenset((home, away)))

    seed = {t: i for i, t in enumerate(teams)}
    buchholz = {t: float(sum(score[o] for o in opponents[t])) for t in teams}
    ordered = sorted(teams, key=lambda t: (-score[t], -buchholz[t], seed[t]))
    rows = [{"rank": i + 1, "team_id": t, "score": score[t], "buchholz": buchholz[t]}
            for i, t in enumerate(ordered)]
    return rows, score, met, had_bye


def _lower_bound(remaining, score):
    """Cheapest pairing ignoring rematches: neighbours in score order (remaining is score-sorted)."""
    return sum(abs(score[remaining[i]] - score[remaining[i + 1]]) for i in range(0, len(remaining) - 1, 2))


def best_pairing(players, score, met):
    """players in standings order. Return the rematch-free pairs with minimum sum |score diff|, or None.

    Branch and bound: take the first unpaired player, try partners by (|diff|, standings order),
    prune when cost so far + lower bound can't beat the best found. Ties keep the first found,
    i.e. the partner earliest in standings order.
    """
    best = {"cost": math.inf, "pairs": None}
    # Dominance pruning: the cheapest cost at which each set of still-unpaired teams was reached.
    # Reaching the same set again at an equal or higher cost can't give a better (or earlier) answer.
    seen = {}

    def search(remaining, pairs, cost):
        if cost + _lower_bound(remaining, score) >= best["cost"]:
            return
        key = frozenset(remaining)
        if key in seen and seen[key] <= cost:
            return
        seen[key] = cost
        if not remaining:
            best["cost"], best["pairs"] = cost, list(pairs)
            return
        a = remaining[0]
        rest = remaining[1:]
        partners = sorted(range(len(rest)), key=lambda j: (abs(score[a] - score[rest[j]]), j))
        for j in partners:
            b = rest[j]
            if frozenset((a, b)) in met:
                continue
            pairs.append((a, b))
            search(rest[:j] + rest[j + 1:], pairs, cost + abs(score[a] - score[b]))
            pairs.pop()

    search(list(players), [], 0.0)
    return best["pairs"]


def generate_swiss(teams, params):
    total, round_no, history = _read_params(teams, params)
    rows, score, met, had_bye = swiss_standings(teams, history)
    n = len(teams)

    if round_no == 1:
        # Exact: seed i vs seed i + m, home = lower seed; odd n -> last seed has the bye.
        m = n // 2
        pairs = [(teams[i], teams[i + m]) for i in range(m)]
        bye = teams[-1] if n % 2 == 1 else None
    else:
        order = [row["team_id"] for row in rows]
        if n % 2 == 0:
            candidates = [None]
        else:
            seed = {t: i for i, t in enumerate(teams)}
            # lowest score first; equal scores -> lowest seed (largest index) first
            candidates = sorted((t for t in teams if t not in had_bye), key=lambda t: (score[t], -seed[t]))
        pairs, bye = None, None
        for candidate in candidates:
            players = [t for t in order if t != candidate]
            pairs = best_pairing(players, score, met)
            if pairs is not None:
                bye = candidate
                break
        if pairs is None:
            raise RuleError(409, "NO_VALID_PAIRING", "no rematch-free pairing exists", {"round": round_no})

    return {
        "format": "swiss",
        "round": round_no,
        "total_rounds": total,
        "pairings": [{"match_id": f"SW-R{round_no}-M{i}", "home": home, "away": away}
                     for i, (home, away) in enumerate(pairs, start=1)],
        "bye": bye,
        "standings": rows,
    }
