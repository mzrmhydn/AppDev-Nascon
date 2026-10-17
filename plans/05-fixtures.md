# 05 — Fixture algorithms — spec FR-1.3, §5.7 (6 pts, all pure functions)

`POST /audit/v1/fixtures` stores **nothing**. Route: validate `format`, `teams` (unique strings, id rules, size limits: RR 2–40, swiss 2–64, single 2–128, double 3–128 → else 400) → call the pure function → return. **No fixture libraries.** Order of work: **RR → single elim → double elim → Swiss** (Swiss round ≥2 is the hardest).

## A. Round robin — `domain/fixtures_round_robin.py`
- Circle method: if n odd add a `None` "BYE" slot → N even. Fix position 0, rotate the rest each round. Round r pairs `arr[i]` with `arr[N-1-i]`. Pair with `None` → that team goes into `byes`.
- **Home/away balance (already implemented in `circle_rounds`):** pair i = (arr[i], arr[N−1−i]) with arr[i] at home, except the fixed team's pair (i = 0) is swapped on odd rounds. Unit test proves |home − away| ≤ 1 for n = 2..40.
- Leg 2 = leg 1 with home/away swapped; round numbers continue (global).
- `match_id = f"RR-L{leg}-R{round}-M{index}"`, index from 1 within the round.
- Withdrawals: unknown team or `after_round` ∉ 0..round_count → 400. `forfeit_remaining` (default): fixtures with that team and `round > after_round` → `status:"forfeit"`, `awarded_to` = opponent. `void_all`: every fixture with that team → `voided`, `awarded_to:null`. Under `forfeit_remaining`, a fixture where **both** teams are past their `after_round` → `voided`, `awarded_to:null` (already implemented in `_withdrawal_status`). ⚠ Ambiguous in the spec — if there is time before 13:00, ask the organisers in writing. Never delete fixtures; byes unaffected.
- `summary`: total/scheduled/forfeit/voided counts. `round_count` = total rounds over all legs.

## B. Single elimination — `domain/fixtures_single_elim.py` (EXACT)
- B = next power of two ≥ n. `order(2)=[1,2]`; `order(2k) = flatten([s, 2k+1-s] for s in order(k))` → order(8) = [1,8,4,5,2,7,3,6].
- Round 1 match i takes entries 2i−1, 2i; lower seed = home; seed > n is missing → `bye:true`, `away:null`, `winner` = present team (propagate immediately).
- Rounds = log2 B. `match_id = f"R{r}M{i}"`; winner_to = `R{r+1}M{ceil(i/2)}`, slot `home` if i odd else `away`; final winner_to null.
- MATCH object fields (all mandatory): `match_id, bracket:"main", round, index, home, away, home_seed, away_seed, bye, winner, loser, winner_to, loser_to`. Unknown team slots = null.
- `results`: apply in order; unknown match_id or winner not a participant → 400. Fill winner/loser, propagate.
- `third_place_match:true` → match `TP` (bracket `third_place`, `round` = final round number, `index` 1, `winner_to`/`loser_to` null); semifinal M1 `loser_to` = TP home, semifinal M2 `loser_to` = TP away. Ignored when there is no semifinal (B = 2).
- Seeds in later rounds: when a team is placed into a later-round slot, also set that slot's `home_seed`/`away_seed` to the team's original seed (decision: a seed belongs to the team; null only while the slot is unknown). ⚠ The current code leaves them null — change `place()` to also copy the seed.

## C. Double elimination — `domain/fixtures_double_elim.py`
Build on the single-elim helpers (`seed_order`, `first_round`, `new_match`, `link`, `place`, `set_winner`, `apply_results`). k = log2 B (B ≥ 4 because n ≥ 3).
1. **Winners bracket** `WR{r}M{i}` (bracket `"winners"`): exactly the single-elim tree with prefix `WR` (round r has B/2^r matches). WR1 seeding and byes identical to single elim.
2. **Losers bracket** `LR{r}M{i}` (bracket `"losers"`), rounds 1..2(k−1). With j = 1..k−1, rounds 2j−1 and 2j each have B/2^(j+1) matches (total B−2). Wire it like this (every slot gets exactly one source):
   - LR1 Mm: home ← loser of WR1 M(2m−1), away ← loser of WR1 M(2m).
   - Even round LR(2j) Mi: home ← winner of LR(2j−1) Mi; away ← loser of WR(j+1) Mi.
   - Odd round LR(2j+1) Mi (j ≥ 1): home ← winner of LR(2j) M(2i−1); away ← winner of LR(2j) M(2i).
   - So WR r (r ≥ 2) losers drop into LR(2r−2) away slots, and the WR final's loser goes to the LB final's **away** slot (spec rule).
   - Every winners-bracket match has `loser_to`; every losers-bracket match has `loser_to: null`.
3. **Grand final** (bracket `"grand_final"`): `GF1` (round 1, index 1): home ← WR final winner, away ← LB final winner (LR(2k−2) M1).
   - `bracket_reset:false` → only GF1; GF1 `winner_to`/`loser_to` null.
   - `bracket_reset:true` → add `GF2` (round 2, index 1) with `"conditional": true` and `"required"`: `null` until GF1 has a result; then `true` iff GF1's winner is GF1.away (the losers-bracket champion), else `false`. GF1 `winner_to` = GF2 home, `loser_to` = GF2 away (so GF2 has "the same two teams"). Only GF2 carries `conditional`/`required`.
4. Response: `{"format":"double_elim","bracket_size":B,"bracket_reset":…,"winners":[rounds],"losers":[rounds],"grand_final":[GF1(,GF2)]}`; each round `{"round": r, "matches": [...]}`.
5. `results` work exactly like single elim (winner + loser propagate along `winner_to`/`loser_to`). Unknown match_id or winner not in that match → 400.
6. Unit tests: for B = 4, 8, 16 count matches per round, assert every slot except WR1 has exactly one source, and play a full bracket where the LB champion wins GF1 → `GF2.required == true`.

## D. Swiss — `domain/fixtures_swiss.py`
- Validate `total_rounds` 1..n−1 (default ceil(log2 n)), `round` 1..total, `history` has exactly rounds 1..round−1 → else 400.
- Scores from history: win 1, draw 0.5, loss 0, bye 1. Buchholz = sum of **current** scores of opponents actually played (bye contributes 0). Standings sorted score desc, buchholz desc, seed asc; `rank` 1..n. Use floats `1.0`, `0.5`.
- **Round 1 exact:** m = n//2; odd n → last seed bye; pair seed i with seed i+m (home = lower seed). `match_id = f"SW-R{round}-M{index}"`.
- **Round ≥ 2:**
  1. Bye candidates (odd n only): teams that never had a bye, ordered **lowest score first**; equal scores → **largest index first** (lowest seed). Even n → `"bye": null`.
  2. For each candidate in that order: remove it, then find the rematch-free perfect matching of the remaining teams with the **minimum Σ|score difference|**. Algorithm (exact, simple to explain): memoised recursion `best(remaining: frozenset) -> (cost, pairs) | None`: if empty → (0, []); else take the first team `a` of `remaining` in standings order, and for every partner `b` in `remaining` that `a` has not met: `sub = best(remaining - {a, b})`; candidate cost = |score(a) − score(b)| + sub.cost; return the cheapest (ties → the partner that comes first in standings order). Return None if no partner works. Decorate with `functools.lru_cache`.
  3. The first candidate that has any valid matching wins (bye = that candidate). If no candidate works → 409 `NO_VALID_PAIRING`, `details: {"round": round}`.
  4. Output pairs in order of the higher-ranked team (standings order); `home` = the higher-ranked team; `match_id = SW-R{round}-M{index}`.
- `standings` in the response reflect **history only** (before this round). `score` and `buchholz` are floats (`1.0`, `0.5`) and compared exactly.
- Home/away not checked.

## Tests (area `fixtures` — these modules are pure → easy ≥ 85 % coverage)
Property tests: RR every pair meets `legs` times, one game per team per round, balance; single elim example n=6 from spec; double elim counts + routing graph; Swiss round 1 exact, no rematches, minimal Σ|diff| (compare with brute force for n ≤ 8), NO_VALID_PAIRING case.
