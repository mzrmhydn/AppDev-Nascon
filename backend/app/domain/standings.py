# League table: points, differentials, H2H, recursive tie-break, qualification status (FR-1.4, spec §5.10).
# Pure function over score projections — recomputed from scratch on every call. Branches only on scoring_model.
import hashlib

from app.domain.sport_config import normalize_tie_break_order


def lots_key(seed, league_id, team_id):
    # Spec Appendix A, draw_lots: ascending key = better.
    return hashlib.sha256(f"{seed}|{league_id}|{team_id}".encode("utf-8")).hexdigest()


# ---------- per-match lines ----------

def _overs_faced(sport_config, side):
    """Decimal overs for one team in one match; an all-out innings counts as the full overs."""
    p = sport_config["periods"]
    if side["wickets"] >= p["wickets_per_innings"] * p["innings_per_team"]:
        return p["overs_per_innings"] * p["innings_per_team"]
    return side["balls"] / p["balls_per_over"]


def _lines(sport_config, projection):
    """Two lines (home view, away view) of one PLAYED match."""
    home = projection["home"]
    away = projection["away"]
    winner = projection["winner_team_id"]
    lines = []
    for me, opp in ((home, away), (away, home)):
        if winner is None:
            result = "draw"
        elif winner == me["team_id"]:
            result = "win"
        else:
            result = "loss"
        line = {
            "team": me["team_id"], "opp": opp["team_id"], "result": result,
            "scored": me["score"], "conceded": opp["score"], "fair_play": me["fair_play"],
            "overs_faced": 0, "overs_bowled": 0,
        }
        if sport_config["scoring_model"] == "innings":
            line["overs_faced"] = _overs_faced(sport_config, me)
            line["overs_bowled"] = _overs_faced(sport_config, opp)
        lines.append(line)
    return lines


def _points(line, pts):
    return pts[line["result"]]


def _diff(sport_config, lines):
    """event / round: scored - conceded. innings: net run rate, 3 decimals."""
    scored = sum(l["scored"] for l in lines)
    conceded = sum(l["conceded"] for l in lines)
    if sport_config["scoring_model"] != "innings":
        return scored - conceded
    faced = sum(l["overs_faced"] for l in lines)
    bowled = sum(l["overs_bowled"] for l in lines)
    rate_for = scored / faced if faced > 0 else 0
    rate_against = conceded / bowled if bowled > 0 else 0
    return round(rate_for - rate_against, 3)


# ---------- main ----------

def compute_standings(league, sport_config, projections):
    """league = {league_id, teams, points{win,draw,loss}, tie_break_order, qualification_spots, lots_seed}
    projections = project() output for every fixture of the league."""
    teams = league["teams"]
    pts = {"win": league["points"]["win"], "draw": league["points"]["draw"], "loss": league["points"]["loss"]}
    order = normalize_tie_break_order(league.get("tie_break_order") or sport_config["tie_break_order"])

    # Played = completed and not undecided; everything else is "remaining".
    lines_by_team = {t: [] for t in teams}
    remaining = {t: 0 for t in teams}
    for proj in projections:
        if proj["status"] == "completed" and proj["outcome"] != "undecided":
            for line in _lines(sport_config, proj):
                lines_by_team[line["team"]].append(line)
        else:
            remaining[proj["home"]["team_id"]] += 1
            remaining[proj["away"]["team_id"]] += 1

    rows = {}
    for t in teams:
        lines = lines_by_team[t]
        rows[t] = {
            "rank": 0, "team_id": t,
            "played": len(lines),
            "won": sum(1 for l in lines if l["result"] == "win"),
            "drawn": sum(1 for l in lines if l["result"] == "draw"),
            "lost": sum(1 for l in lines if l["result"] == "loss"),
            "scored": sum(l["scored"] for l in lines),
            "conceded": sum(l["conceded"] for l in lines),
            "diff": _diff(sport_config, lines),
            "points": sum(_points(l, pts) for l in lines),
            "fair_play": sum(l["fair_play"] for l in lines),
            "status": None, "resolved_by": None,
        }

    def criterion_value(criterion, team, group):
        """Higher is better for every criterion."""
        if criterion in ("h2h_points", "h2h_diff"):
            mini = [l for l in lines_by_team[team] if l["opp"] in group]
            if criterion == "h2h_points":
                return sum(_points(l, pts) for l in mini)
            return _diff(sport_config, mini)
        if criterion == "overall_diff":
            return rows[team]["diff"]
        if criterion == "scored":
            return rows[team]["scored"]
        if criterion == "fair_play":
            return rows[team]["fair_play"]
        # draw_lots: smaller hash is better -> negate so higher is better
        return -int(lots_key(league["lots_seed"], league["league_id"], team), 16)

    def resolve(group):
        """Order a group tied on points. Each split restarts from the first criterion."""
        for criterion in order:
            values = {t: criterion_value(criterion, t, group) for t in group}
            if len(set(values.values())) == 1:
                continue
            ordered_values = sorted(set(values.values()), reverse=True)
            result = []
            for v in ordered_values:
                sub = sorted(t for t in group if values[t] == v)
                sub = resolve(sub) if len(sub) > 1 else sub
                if result:
                    # the team just above this sub-group was separated from it by this criterion
                    rows[result[-1]]["resolved_by"] = criterion
                result.extend(sub)
            return result
        return sorted(group)  # unreachable in practice: draw_lots always splits

    final = []
    for p in sorted({rows[t]["points"] for t in teams}, reverse=True):
        group = sorted(t for t in teams if rows[t]["points"] == p)
        final.extend(resolve(group) if len(group) > 1 else group)

    # Qualification: points only.
    k = league["qualification_spots"]
    max_pts = {t: rows[t]["points"] + pts["win"] * remaining[t] for t in teams}
    for t in teams:
        others = [x for x in teams if x != t]
        if sum(1 for x in others if max_pts[x] >= rows[t]["points"]) < k:
            rows[t]["status"] = "clinched"
        elif sum(1 for x in others if rows[x]["points"] > max_pts[t]) >= k:
            rows[t]["status"] = "eliminated"
        else:
            rows[t]["status"] = "still_possible"

    table = []
    for i, t in enumerate(final):
        rows[t]["rank"] = i + 1
        table.append(rows[t])

    h2h = {}
    for a in teams:
        h2h[a] = {}
        for b in teams:
            if a == b:
                continue
            met = [l for l in lines_by_team[a] if l["opp"] == b]
            h2h[a][b] = {
                "played": len(met),
                "points": sum(_points(l, pts) for l in met),
                "scored": sum(l["scored"] for l in met),
                "conceded": sum(l["conceded"] for l in met),
            }

    return {
        "league_id": league["league_id"],
        "sport_id": sport_config["sport_id"],
        "qualification_spots": k,
        "table": table,
        "h2h": h2h,
    }
