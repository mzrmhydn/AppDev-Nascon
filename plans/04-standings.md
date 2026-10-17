# 04 — Leagues + standings — spec FR-1.4, §5.8, §5.10 (6 pts)

## A. `POST /audit/v1/leagues` (`services/leagues.py`)
Validation order: 400 (required fields, types, teams unique 2–40, fixture teams ∈ teams, home ≠ away, `qualification.spots` int 1..len(teams), tie_break tokens valid) → 404 `SPORT_NOT_FOUND` → 409 `LEAGUE_EXISTS` → 409 `MATCH_EXISTS` (any fixture match_id already used anywhere).
- `points` default 3/1/0; `tie_break_order` default = sport's; `lots_seed` default = seed of last `/reset` (42).
- Each fixture → a `matches` row (`league_id`, `sport_id`, home, away) = a match stream with status `upcoming` (no events yet; projection of an empty log = upcoming).
- 201 `{"league_id","status":"created","team_count","fixture_count"}`.

## B. `domain/standings.py` — `compute_standings(league, sport_config, results)` PURE
`results` = for each fixture: `{match_id, home, away, status, outcome, home_score, away_score, home_balls, away_balls, home_wickets, away_wickets, home_fp, away_fp, winner_team_id}` (from `project()`).
1. **Played** = completed and outcome ≠ undecided. Others are "remaining".
2. Per team: played/won/drawn/lost, scored/conceded, points = won·W + drawn·D + lost·L (a tiebreak win is a win), fair_play = sum of active discipline points over **completed league matches**.
3. `diff` by model (branch on `scoring_model`, never on names):
   - event: scored − conceded. round: rounds won − rounds lost.
   - innings: NRR = runs_scored / overs_faced − runs_conceded / overs_bowled, round(…, 3). overs = legal balls / bpo (decimal). **If the innings ended all-out (wickets ≥ wickets_per_innings·innings_per_team) count overs as the full `overs_per_innings`.** Overs bowled = opponent's overs faced. Guard division by zero (0 overs → that term = 0).
4. **h2h**: for every ordered pair (a, b) incl. never-met (zeros): played, points earned by a, scored, conceded.
5. **Ordering (exact):** sort by points desc; equal-points groups → `resolve(group)`:
   ```
   resolve(group):
     for criterion in tie_break_order (+ draw_lots last):
        values = {t: value(criterion, t, group)}
        if not all equal: split into sub-groups by value (best first);
                          each sub-group of size>1 → resolve(sub) FROM THE FIRST CRITERION; return
     (draw_lots always splits fully)
   ```
   - `h2h_points` / `h2h_diff` computed **only over completed matches among the teams of the current group** (NRR for innings over those matches).
   - `overall_diff`, `scored`, `fair_play` over all completed league matches. Higher is better.
   - `draw_lots`: ascending `sha256_hex(f"{lots_seed}|{league_id}|{team_id}")` — first is best (Appendix A vector 2 = unit test).
   - `resolved_by` = the criterion that separated this team from **the next team below it** in the final order, if they were tied on points; else null. Simplest: record, for each adjacent pair in final order with equal points, the criterion at which they ended up in different sub-groups (track it during recursion).
6. **Qualification (points only):** W = win points, R(T) remaining fixtures, max(T) = points + W·R(T), k = spots.
   `clinched` if fewer than k **other** teams have max(X) ≥ points(T); else `eliminated` if ≥ k other teams have points(X) > max(T); else `still_possible`.
7. `rank` 1..n.

## C. `GET /audit/v1/standings/{league_id}` — 404 `LEAGUE_NOT_FOUND`. Load league + sport + project every fixture → `compute_standings` → response exactly per spec (`league_id, sport_id, qualification_spots, table[], h2h{}`). Recompute from scratch every call (edge case 5: a compensation after qualification must flip status).

## Tests (area `standings`)
3-way H2H mini-league (edge case 4), restart-on-split, draw_lots vector, NRR with all-out, clinched/eliminated, compensation changes table.

## Viva notes
Why recursion restarts from the first criterion (FIFA/UEFA-style mini-league); complexity O(n log n) sort + O(m) per group; recomputing from scratch avoids stale tables.
