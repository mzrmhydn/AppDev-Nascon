# 03 — Mystery sports, event sourcing, score projection — spec FR-1.1, §5.6, §5.9 (6 pts)

## A. `POST /audit/v1/sports` — `domain/sport_config.py`
- Validate exactly per the field table in §5.6. Collect **all** bad field names into `details.fields` (top-level names like `"periods"`, `"scoring_events"` are fine) → 400 `VALIDATION_ERROR`.
  - `sport_id` regex `^[a-z0-9_-]{2,40}$`; `name` 1–80; `scoring_model` in {event, innings, round}.
  - `periods` per model (event: count ≥1, duration_minutes ≥1; innings: 4 ints ≥1; round: best_of odd ≥1).
  - `scoring_events` ≥1 key, key regex `^[a-z0-9_]{1,40}$`, value per model (event `{points:int≥1}`; innings `{runs:int≥0, legal_ball:bool, wicket:bool}`; round `{rounds:int≥1}`).
  - `draw_allowed` bool; `overtime.policy` in {none, extra_time, shootout, golden_score, super_over}, optional `duration_minutes` int ≥0.
  - `tie_break_order` optional, items from the 6 tokens, no repeats; default full list; `draw_lots` always last even if omitted (store normalized list).
  - `roster`: min/max ints ≥1, min ≤ max, `required_positions` object of ints.
  - Use **strict** checks: `True` is not an int, `"1"` is not an int. Write a tiny `is_int(x) = type(x) is int`.
- Duplicate → 409 `SPORT_EXISTS` (validation first, then existence).
- 201 `{"sport_id", "status":"created", "config": <stored config>}`.
- Seed sports use the **same** stored format (plan 01).

## B. `POST /audit/v1/events` — `services/events.py` + `domain/scoring.py`
Order of work inside one DB transaction:
1. Schema check (event_id, match_id strings matching id rules; type in the 7 types; payload object with the fields for that type; correct JSON types) → 400 `VALIDATION_ERROR`.
2. **Idempotency:** look up `event_id`. Exists with identical request (compare canonical JSON of the whole body) → return stored response with **200**. Exists with different body → 409 `DUPLICATE_EVENT_ID`.
3. `match_init`: stream exists → 409 `MATCH_EXISTS`; sport unknown → 404 `SPORT_NOT_FOUND`; else create `matches` row.
   Other types: no stream → 404 `MATCH_NOT_FOUND`.
4. **Lock the match row** (`SELECT … FOR UPDATE`) so sequence numbers can't collide.
5. Load all events of the match, compute current projection with `project()`, then apply the rule table of §5.9:
   - `match_start` needs `upcoming` else 409 `ILLEGAL_TRANSITION`.
   - `score` needs `in_progress` else 409 `MATCH_NOT_IN_PROGRESS`; team_id ∉ {home, away} → 400 `VALIDATION_ERROR`; event_type ∉ sport scoring_events → 400 `UNKNOWN_EVENT_TYPE`; innings limit reached → 409 `INNINGS_COMPLETE`; round series decided → 409 `SERIES_ALREADY_DECIDED`.
   - `discipline` (`points` int), `tiebreak_winner` need `in_progress`.
   - `match_end` needs `in_progress` else 409 `ILLEGAL_TRANSITION`; level score + draw not allowed + no active tiebreak_winner → 409 `TIE_NOT_ALLOWED`.
   - `compensation`: target event_id unknown → 404 `EVENT_NOT_FOUND`; target already compensated / not score|discipline|tiebreak_winner / other match → 409 `INVALID_COMPENSATION`. Allowed in any status after init (incl. completed).
   - ⚠ Order of 400 vs 404 checks follows spec §5.2: 400 (schema + team_id + event_type) before 404? **event_type check needs the sport → do it after the 404 check for the match** — that's fine because 404 only happens when the match doesn't exist.
6. Insert row: `sequence = count+1`, `signature = sign(event_id, payload)` (payload = the **request's** payload object), store `request_hash` and the response.
7. Response 201 `{event_id, match_id, type, sequence, match_version: sequence, signature}`.
8. After commit: `realtime.broadcast(match_id, {"type":"match_updated","match_id","version"})`.

## C. `domain/scoring.py` — `project(sport_config, events) -> dict` (PURE)
- Walk events in sequence. Build `compensated_by = {target_event_id: compensation_event_id}` first; compensated events **and** compensation events are neutral.
- Status: `upcoming` after init; `in_progress` after an active `match_start`; `completed` after `match_end`.
- Score per model — **use only config values, never names**:
  - event: `score += scoring_events[event_type]["points"]`
  - innings: `score += runs`; if `legal_ball` → `balls += 1`; if `wicket` → `wickets += 1`; `overs = f"{balls // bpo}.{balls % bpo}"`. wickets/balls/overs are `null` for other models.
  - round: `score += rounds`.
- `fair_play` = sum of active discipline points.
- `tiebreak_winner_team_id` = team of the last **active** tiebreak_winner, else null.
- Outcome: `pending` until completed; then higher score wins; level → tiebreak winner if any; level + draw_allowed → `draw`; else `undecided`. `winner_team_id` accordingly (null for draw/undecided/pending).
- Limits (used by the validator): innings complete when `balls ≥ innings_per_team*overs*bpo` or `wickets ≥ innings_per_team*wickets_per_innings`; round decided when a team has `≥ (best_of+1)//2`.
- Events list in response: every event incl. compensations, with `compensated` and `compensated_by`.

## D. `GET /audit/v1/score/{match_id}` → rebuild from the log every time (no counters). 404 `MATCH_NOT_FOUND`. `version` = number of events. `league_id` null for stand-alone matches.

## Tests (coverage area `scoring` = `domain/scoring.py`, `domain/sport_config.py`, `services/events.py`)
Kabaddi example from spec; cricket overs `"3.2"`; compensation after completion changes outcome; idempotent replay 200; duplicate id 409; illegal transitions; `TIE_NOT_ALLOWED`; mystery sport usable immediately.

## Viva notes to log
Why append-only + compensation (audit trail, replay, no lost history); why rebuild on read (correctness > speed; O(events) per read, cache later if needed); how a new sport needs zero code.
