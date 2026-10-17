# 04 — Leagues + standings — spec FR-1.4, §5.8, §5.10 (6 pts)

## A. `POST /audit/v1/leagues` (`services/leagues.py`)
Validation order (first failure wins):
1. 400 `VALIDATION_ERROR` — required: `league_id` (id pattern), `sport_id` (string), `teams` (array of unique id strings, length 2–40), `fixtures` (array of `{match_id, home, away}`; home/away ∈ teams; home ≠ away; match_ids unique **within the request**), `qualification.spots` (int 1..len(teams)). Optional: `points` `{win, draw, loss}` ints; `tie_break_order` (same tokens as §5.6, no repeats); `lots_seed` int.
2. 404 `SPORT_NOT_FOUND`.
3. 409 `LEAGUE_EXISTS` (league_id already in the `leagues` table — note the 3 baseline RBAC leagues live in the same table).
4. 409 `MATCH_EXISTS` (any fixture match_id already exists as a match stream).
Then insert the league (`tenant_id` NULL) + one `matches` row per fixture, in one transaction.
- `points` default 3/1/0; `tie_break_order` default = sport's; `lots_seed` default = seed of last `/reset` (42).
- Each fixture → a `matches` row (`league_id`, `sport_id`, home, away) = a match stream with status `upcoming` (no events yet; projection of an empty log = upcoming).
- 201 `{"league_id","status":"created","team_count","fixture_count"}`.

## B. `domain/standings.py` — `compute_standings(league, sport_config, projections)` PURE (already written)
`league` = dict of the league row (`league_id`, `teams`, `points`, `tie_break_order`, `qualification_spots`, `lots_seed`); `projections` = list of `project()` outputs, one per fixture of the league (fixtures with no events project to `upcoming`).
1. **Played** = completed and outcome ≠ undecided. Others are "remaining".
2. Per team: played/won/drawn/lost, scored/conceded, points = won·W + drawn·D + lost·L (a tiebreak win is a win), fair_play = sum of active discipline points over **completed league matches**.
3. `diff` by model (branch on `scoring_model`, never on names):
   - event: scored − conceded. round: rounds won − rounds lost.
   - innings: NRR = runs_scored / overs_faced − runs_conceded / overs_bowled, round(…, 3). overs = legal balls / bpo (decimal). **If the innings ended all-out (wickets ≥ wickets_per_innings·innings_per_team) count overs as the full `overs_per_innings`.** Overs bowled = opponent's overs faced. Guard division by zero (0 overs → that term = 0).
4. **h2h**: for every ordered pair (a, b) **with a ≠ b** (no `h2h[a][a]`), incl. never-met (zeros): played, points earned by a, scored, conceded. (Already implemented this way in `domain/standings.py`.)
   - `tie_break_order` normalisation: `draw_lots` always last (use `normalize_tie_break_order` from `domain/sport_config.py`).
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
