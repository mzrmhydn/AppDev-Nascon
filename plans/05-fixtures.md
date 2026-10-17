# 05 — Fixture algorithms — spec FR-1.3, §5.7 (6 pts, all pure functions)

`POST /audit/v1/fixtures` stores **nothing**. Route: validate `format`, `teams` (unique strings, id rules, size limits: RR 2–40, swiss 2–64, single 2–128, double 3–128 → else 400) → call the pure function → return. **No fixture libraries.** Order of work: **RR → single elim → double elim → Swiss** (Swiss round ≥2 is the hardest).

## A. Round robin — `domain/fixtures_round_robin.py`
- Circle method: if n odd add a `None` "BYE" slot → N even. Fix position 0, rotate the rest each round. Round r pairs `arr[i]` with `arr[N-1-i]`. Pair with `None` → that team goes into `byes`.
- **Home/away balance:** alternate who is home: e.g. for i = 0 (the fixed team) home if r is even else away; for others home = `arr[i]` if i is odd-ish… Simplest proven trick: in round r, for pair i, swap home/away when `(r + i) % 2 == 1`. **Write a unit test asserting |home − away| ≤ 1 for every team for n = 2..12** and adjust until green.
- Leg 2 = leg 1 with home/away swapped; round numbers continue (global).
- `match_id = f"RR-L{leg}-R{round}-M{index}"`, index from 1 within the round.
- Withdrawals: unknown team or `after_round` ∉ 0..round_count → 400. `forfeit_remaining` (default): fixtures with that team and `round > after_round` → `status:"forfeit"`, `awarded_to` = opponent. `void_all`: every fixture with that team → `voided`, `awarded_to:null`. Both teams withdrawn → voided. Never delete fixtures; byes unaffected.
- `summary`: total/scheduled/forfeit/voided counts. `round_count` = total rounds over all legs.

## B. Single elimination — `domain/fixtures_single_elim.py` (EXACT)
- B = next power of two ≥ n. `order(2)=[1,2]`; `order(2k) = flatten([s, 2k+1-s] for s in order(k))` → order(8) = [1,8,4,5,2,7,3,6].
- Round 1 match i takes entries 2i−1, 2i; lower seed = home; seed > n is missing → `bye:true`, `away:null`, `winner` = present team (propagate immediately).
- Rounds = log2 B. `match_id = f"R{r}M{i}"`; winner_to = `R{r+1}M{ceil(i/2)}`, slot `home` if i odd else `away`; final winner_to null.
- MATCH object fields (all mandatory): `match_id, bracket:"main", round, index, home, away, home_seed, away_seed, bye, winner, loser, winner_to, loser_to`. Unknown team slots = null.
- `results`: apply in order; unknown match_id or winner not a participant → 400. Fill winner/loser, propagate.
- `third_place_match:true` → match `TP` (bracket `third_place`); both semifinals' `loser_to` = TP home/away.

## C. Double elimination — `domain/fixtures_double_elim.py`
- k = log2 B. Winners `WR{r}M{i}`: round r has B/2^r matches; WR1 seeding = single elim (exact).
- Losers `LR{r}M{i}`: rounds 1..2(k−1); rounds 2j−1 and 2j each have B/2^(j+1) matches. Total = B−2.
- Routing (recommended in spec): WR1 losers pair up in LR1 (`loser_to` of WR1M(2m−1), WR1M(2m) → LR1Mm home/away). WRr (r≥2) losers drop into LR(2r−2) as the `away` slot; LR odd rounds (≥3) are LB-internal (winners of previous LR round pair up); LR even rounds = previous LR winners (home) vs dropped WR losers (away). Check: every slot except WR1 fed exactly once.
- WR final winner → GF1.home; WR final loser → LB final away; LB final winner → GF1.away.
- `grand_final`: GF1 (+ GF2 only if `bracket_reset:true`). GF2: `conditional:true`, same two teams as GF1, `required: null` until GF1 has a result, then `true` iff the GF1 winner is GF1.away (LB champion), else `false`.
- Every non-terminal match has `winner_to`; all winners-bracket matches have `loser_to`; losers-bracket `loser_to:null`.
- Unit test: build the graph for B = 4, 8, 16 and assert each slot has exactly one source.

## D. Swiss — `domain/fixtures_swiss.py`
- Validate `total_rounds` 1..n−1 (default ceil(log2 n)), `round` 1..total, `history` has exactly rounds 1..round−1 → else 400.
- Scores from history: win 1, draw 0.5, loss 0, bye 1. Buchholz = sum of **current** scores of opponents actually played (bye contributes 0). Standings sorted score desc, buchholz desc, seed asc; `rank` 1..n. Use floats `1.0`, `0.5`.
- **Round 1 exact:** m = n//2; odd n → last seed bye; pair seed i with seed i+m (home = lower seed). `match_id = f"SW-R{round}-M{index}"`.
- **Round ≥ 2:**
  1. Bye candidates (odd n): teams that never had a bye, ordered lowest score first, ties → **lowest seed = largest index** first.
  2. For each candidate (or no bye if n even): find a perfect rematch-free matching of the rest **minimising Σ|score difference|**. Use backtracking with pruning: sort teams by score desc, take the first unpaired team, try partners in order of |diff| ascending, recurse, keep the best total; prune when current total ≥ best. n ≤ 64 but rounds are few → OK. (Alternative: min-cost perfect matching — overkill.)
  3. First candidate with a valid matching wins. None → 409 `NO_VALID_PAIRING`, `details: {"round": round}`.
- Home/away not checked.

## Tests (area `fixtures` — these modules are pure → easy ≥ 85 % coverage)
Property tests: RR every pair meets `legs` times, one game per team per round, balance; single elim example n=6 from spec; double elim counts + routing graph; Swiss round 1 exact, no rematches, minimal Σ|diff| (compare with brute force for n ≤ 8), NO_VALID_PAIRING case.
