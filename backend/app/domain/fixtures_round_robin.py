# Round-robin schedule with the circle method + withdrawals (FR-1.3, spec §5.7-A). Pure, no libraries.
from app.domain.fixtures_common import bad_request

POLICIES = ["forfeit_remaining", "void_all"]


def circle_rounds(teams):
    """One leg: list of rounds, each = (pairs [(home, away)], byes [team]).

    Circle method: position 0 is fixed, the others rotate one step per round. For odd n a None
    slot is added; whoever meets None has the bye. Home/away: the fixed team's pair swaps on odd
    rounds, every other pair keeps arr[i] at home — this keeps |home - away| <= 1 for every team
    (checked by a unit test for n = 2..40).
    """
    arr = list(teams)
    if len(arr) % 2 == 1:
        arr.append(None)
    size = len(arr)
    rounds = []
    for r in range(size - 1):
        pairs = []
        byes = []
        for i in range(size // 2):
            home, away = arr[i], arr[size - 1 - i]
            if home is None or away is None:
                byes.append(home if away is None else away)
                continue
            if i == 0 and r % 2 == 1:
                home, away = away, home
            pairs.append((home, away))
        rounds.append((pairs, byes))
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]  # rotate everyone except position 0
    return rounds


def _read_params(params):
    legs = params.get("legs", 1)
    if type(legs) is not int or legs not in (1, 2):
        raise bad_request(["legs"])
    policy = params.get("withdrawal_policy", "forfeit_remaining")
    if policy not in POLICIES:
        raise bad_request(["withdrawal_policy"])
    withdrawals = params.get("withdrawals", [])
    if not isinstance(withdrawals, list):
        raise bad_request(["withdrawals"])
    return legs, policy, withdrawals


def generate_round_robin(teams, params):
    if not isinstance(params, dict):
        raise bad_request(["params"])
    legs, policy, withdrawals = _read_params(params)

    one_leg = circle_rounds(teams)
    round_count = len(one_leg) * legs

    # withdrawn team -> after_round (last global round it still plays)
    withdrawn = {}
    for w in withdrawals:
        if not isinstance(w, dict):
            raise bad_request(["withdrawals"])
        team, after = w.get("team_id"), w.get("after_round")
        if team not in teams or team in withdrawn:
            raise bad_request(["withdrawals"], "unknown or repeated withdrawn team")
        if type(after) is not int or not (0 <= after <= round_count):
            raise bad_request(["withdrawals"], "after_round out of range")
        withdrawn[team] = after

    rounds = []
    summary = {"total": 0, "scheduled": 0, "forfeit": 0, "voided": 0}
    number = 0
    for leg in range(1, legs + 1):
        for pairs, byes in one_leg:
            number += 1
            matches = []
            for index, (home, away) in enumerate(pairs, start=1):
                if leg == 2:
                    home, away = away, home  # leg 2 mirrors leg 1
                status, awarded_to = _withdrawal_status(home, away, number, withdrawn, policy)
                summary["total"] += 1
                summary[status] += 1
                matches.append({
                    "match_id": f"RR-L{leg}-R{number}-M{index}",
                    "leg": leg, "home": home, "away": away,
                    "status": status, "awarded_to": awarded_to,
                })
            rounds.append({"round": number, "matches": matches, "byes": list(byes)})

    return {
        "format": "round_robin", "legs": legs, "team_count": len(teams),
        "round_count": round_count, "rounds": rounds, "summary": summary,
    }


def _withdrawal_status(home, away, round_number, withdrawn, policy):
    """Return (status, awarded_to) for one fixture."""
    if policy == "void_all":
        if home in withdrawn or away in withdrawn:
            return "voided", None
        return "scheduled", None
    home_out = home in withdrawn and round_number > withdrawn[home]
    away_out = away in withdrawn and round_number > withdrawn[away]
    if home_out and away_out:
        return "voided", None
    if home_out:
        return "forfeit", away
    if away_out:
        return "forfeit", home
    return "scheduled", None
