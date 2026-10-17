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

## B. `POST /audit/v1/events` — `services/events.py` (DB glue) + `domain/scoring.py` (rules, already written)
`services.events.append_event(db, body: dict) -> tuple[int, dict]` is the ONE function used by `/audit/v1/events`, `/api/v1/events`, offline-sync and the demo seed. `body` is the **raw JSON dict** as received (never a Pydantic dump — the signature and the idempotency comparison must use exactly what the client sent).
Do these steps in this exact order, in one DB transaction:
1. **Envelope schema → 400 `VALIDATION_ERROR`:** `event_id` and `match_id` are strings matching `^[A-Za-z0-9_.:-]{1,64}$`; `type` is one of the 7 types; `payload` is an object. Then `payload_bad_fields(type, payload)` (already in `domain/scoring.py`) — non-empty list → 400 with `details.fields`. For `match_init` also: `home_team_id != away_team_id` else 400.
2. **Idempotency:** `SELECT` the row with this `event_id` (event ids are unique across ALL matches).
   - found and `canonical(stored_request) == canonical(body)` → return `(200, stored_response)` — stop.
   - found and different → 409 `DUPLICATE_EVENT_ID` — stop.
   - Only **successful** appends are stored. A request that was rejected before stored nothing, so re-sending it simply runs again.
3. **Stream existence:**
   - `match_init`: match row exists → 409 `MATCH_EXISTS`; sport unknown → 404 `SPORT_NOT_FOUND`; else insert the `matches` row (league_id from payload if given). If two identical `match_init` requests race, the PK insert raises `IntegrityError` → rollback and redo step 2 (gives 200 replay or 409).
   - every other type: no match row → 404 `MATCH_NOT_FOUND`.
4. **Lock:** `SELECT … FROM matches WHERE match_id = :id FOR UPDATE` (serialises appends to one match so sequence numbers never collide).
5. Load the match's events ordered by `sequence`, build `projection = project(sport_config, match, events)`.
6. For `compensation`: look up the target with `SELECT … WHERE event_id = payload.compensates` across **all** matches (target in another match → 409, not 404).
7. Call `check_event(sport_config, projection, type, payload, target_event, match_id)` (already written). It raises `RuleError(status, code, message, details)` in the spec's order (400 → 404 → 409). Convert it to `AppError` with the same fields.
8. Insert: `sequence = len(events) + 1`, `signature = sign(event_id, body["payload"])` (raw payload), the raw request, and the response.
9. Return `(201, {"event_id", "match_id", "type", "sequence", "match_version": sequence, "signature"})`.
10. After commit: broadcast `{"type":"match_updated","match_id","version":sequence}` (plan 09; wrapped in try/except).

`services.events.match_version(db, match_id) -> int` = number of events of that match (0 for a league fixture with no events). Offline sync uses it.

## C. `domain/scoring.py` — `project(sport_config, match, events) -> dict` (PURE, already written — returns the full `/score` body)
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

## D. `GET /audit/v1/score/{match_id}` → load match + sport + events, return `project(...)` (rebuilt every call, no counters). Unknown match → 404 `MATCH_NOT_FOUND`. `version` = number of events. `league_id` null for stand-alone matches.

## E. `POST /audit/v1/sports` route (`services/sports.py`)
1. `fields = validate_sport_config(body)` (already written) → non-empty → 400 `VALIDATION_ERROR`, `details: {"fields": fields}`.
2. Sport id exists → 409 `SPORT_EXISTS`.
3. Store `normalize_sport_config(body)`; return 201 `{"sport_id", "status": "created", "config": <stored>}`. No restart needed: every request reads the sport from the DB.

## Tests (coverage area `scoring` = `domain/scoring.py`, `domain/sport_config.py`, `services/events.py`)
Kabaddi example from spec; cricket overs `"3.2"`; compensation after completion changes outcome; idempotent replay 200; duplicate id 409; illegal transitions; `TIE_NOT_ALLOWED`; mystery sport usable immediately.

## Viva notes to log
Why append-only + compensation (audit trail, replay, no lost history); why rebuild on read (correctness > speed; O(events) per read, cache later if needed); how a new sport needs zero code.
