# Single-elimination bracket: exact seeding, byes, result propagation, third-place match (FR-1.3, spec §5.7-C).
# Seeding and match helpers are reused by fixtures_double_elim.py.
from app.domain.fixtures_common import bad_request


def bracket_size(n):
    """Next power of two >= n."""
    size = 1
    while size < n:
        size *= 2
    return size


def seed_order(size):
    """order(2) = [1, 2]; order(2k) = for each s in order(k): [s, 2k + 1 - s]."""
    order = [1, 2]
    while len(order) < size:
        k2 = len(order) * 2
        order = [x for s in order for x in (s, k2 + 1 - s)]
    return order[:size]


def new_match(match_id, bracket, round_no, index):
    return {
        "match_id": match_id, "bracket": bracket, "round": round_no, "index": index,
        "home": None, "away": None, "home_seed": None, "away_seed": None,
        "bye": False, "winner": None, "loser": None,
        "winner_to": None, "loser_to": None,
    }


def link(match_id, slot):
    return {"match_id": match_id, "slot": slot}


def first_round(teams, prefix, bracket):
    """Round-1 matches in bracket order with seeds filled in and byes marked (winner not yet propagated)."""
    n = len(teams)
    order = seed_order(bracket_size(n))
    matches = []
    for i in range(len(order) // 2):
        m = new_match(f"{prefix}1M{i + 1}", bracket, 1, i + 1)
        s1, s2 = order[2 * i], order[2 * i + 1]
        home_seed, away_seed = min(s1, s2), max(s1, s2)  # lower seed number is home
        m["home"], m["home_seed"] = teams[home_seed - 1], home_seed
        if away_seed <= n:
            m["away"], m["away_seed"] = teams[away_seed - 1], away_seed
        else:
            m["bye"] = True  # away seed is missing; home advances
        matches.append(m)
    return matches


def place(by_id, target, team, seed):
    """Put a team (and its original seed) into the slot a link points to (no-op for null links)."""
    if target is not None:
        match = by_id[target["match_id"]]
        match[target["slot"]] = team
        match[target["slot"] + "_seed"] = seed


def seed_of(match, team):
    if team is None:
        return None
    return match["home_seed"] if team == match["home"] else match["away_seed"]


def set_winner(by_id, match, winner):
    """Record a result and push winner/loser (with their seeds) along winner_to/loser_to."""
    match["winner"] = winner
    if match["bye"]:
        match["loser"] = None
    else:
        match["loser"] = match["away"] if winner == match["home"] else match["home"]
    place(by_id, match["winner_to"], winner, seed_of(match, winner))
    place(by_id, match["loser_to"], match["loser"], seed_of(match, match["loser"]))


def apply_results(by_id, results):
    """Apply params.results in order. Unknown match_id or a winner who isn't playing -> 400."""
    if not isinstance(results, list):
        raise bad_request(["results"])
    for r in results:
        if not isinstance(r, dict) or r.get("match_id") not in by_id:
            raise bad_request(["results"], "unknown match_id")
        match = by_id[r["match_id"]]
        winner = r.get("winner")
        if winner is None or winner not in (match["home"], match["away"]):
            raise bad_request(["results"], "winner is not a participant of that match")
        set_winner(by_id, match, winner)


def generate_single_elim(teams, params):
    if not isinstance(params, dict):
        raise bad_request(["params"])
    third_place = params.get("third_place_match", False)
    if type(third_place) is not bool:
        raise bad_request(["third_place_match"])

    size = bracket_size(len(teams))
    round_count = size.bit_length() - 1  # log2(size)
    rounds = [first_round(teams, "R", "main")]
    for r in range(2, round_count + 1):
        rounds.append([new_match(f"R{r}M{i}", "main", r, i) for i in range(1, size // 2 ** r + 1)])

    # Winner of R{r}M{i} -> R{r+1}M{ceil(i/2)}, home if i is odd else away.
    for r in range(1, round_count):
        for m in rounds[r - 1]:
            i = m["index"]
            m["winner_to"] = link(f"R{r + 1}M{(i + 1) // 2}", "home" if i % 2 == 1 else "away")

    if third_place and round_count >= 2:
        tp = new_match("TP", "third_place", round_count, 1)
        semis = rounds[round_count - 2]
        semis[0]["loser_to"] = link("TP", "home")
        semis[1]["loser_to"] = link("TP", "away")
        rounds[-1].append(tp)

    by_id = {m["match_id"]: m for rnd in rounds for m in rnd}
    for m in rounds[0]:
        if m["bye"]:
            set_winner(by_id, m, m["home"])  # bye winners advance immediately
    apply_results(by_id, params.get("results", []))

    return {
        "format": "single_elim",
        "bracket_size": size,
        "rounds": [{"round": r + 1, "matches": rnd} for r, rnd in enumerate(rounds)],
    }
