# Spec tables — hand-checked against the PDF

`NaSCon26-AppDev-Part1-spec.txt` is a machine extraction of the PDF. **Tables whose cells wrap onto several lines come out scrambled in the .txt** (rows get mixed up). For those tables, use THIS file. If this file and the PDF ever disagree, the PDF wins.

---

## §5.2 HTTP status codes and validation order
- Validation order: **1) malformed JSON / schema → 400; 2) referenced id does not exist → 404; 3) business rule violated → 409 (or 402 for payment). The first failing step wins.**
- Unknown fields → ignored. Missing required fields or wrong types → 400.
- Idempotency: where a request carries a client id (`event_id`, `order_id`, `request_id`, `action_id`), replaying the identical request returns the stored result (HTTP 200) and changes nothing.
- Rate limiting: `/audit/v1/*` and `/health` exempt (grader may send 200 req/s). `/api/v1/*` limited to 100 requests per rolling 10 s per client IP.
- Performance: every request < 5 s (reset < 10 s). The 20-request checkout burst must fully finish within 10 s.
- Body > 1 MB → 413 `PAYLOAD_TOO_LARGE`.
- Ids: strings, 1–64 chars from `A-Za-z0-9_.:-`, never contain `|`, case-sensitive, stored and returned verbatim.
- Timestamps `YYYY-MM-DDTHH:MM:SSZ` (UTC). Dates `YYYY-MM-DD`. Money = integer minor units (paisa), currency always `"PKR"`.

| Code | Meaning |
|---|---|
| 200 | Success for reads, and for an idempotent replay of an earlier success |
| 201 | A new resource/record was created or an action was applied for the first time |
| 400 | Malformed JSON, schema violation, bad value |
| 401 | Missing, malformed, tampered, expired, or alg:none token |
| 402 | Mock payment declined / capture failed (checkout only) |
| 403 | Authenticated but not allowed (role or tenant/ownership boundary) |
| 404 | A referenced id does not exist |
| 409 | Business-rule or state conflict |
| 413 | Body too large |
| 429 | Rate limit exceeded (`/api/v1/*` only) |

Error body (all non-2xx): `{"error":{"code":"OUT_OF_STOCK","message":"…","details":{"variant_id":"var-jersey-001-M"}}}`. `details` is always an object (may be `{}`). For `VALIDATION_ERROR`, `details.fields` is an array of the offending field names.

## §5.6 Sport config field rules
| Field | Type | Rules |
|---|---|---|
| `sport_id` | string | Required. Regex `^[a-z0-9_-]{2,40}$`. Duplicate → 409 `SPORT_EXISTS` |
| `name` | string | Required, 1–80 chars |
| `scoring_model` | enum | Required: `event`, `innings`, or `round` |
| `periods` | object | Required. event: `count` ≥ 1, `duration_minutes` ≥ 1. innings: `innings_per_team`, `overs_per_innings`, `balls_per_over`, `wickets_per_innings` (integers ≥ 1). round: `best_of` (odd integer ≥ 1) |
| `scoring_events` | object | Required, ≥ 1 key; key regex `^[a-z0-9_]{1,40}$`. Value per model — event: `{points}` (int ≥ 1); innings: `runs` (int ≥ 0), `legal_ball` (bool), `wicket` (bool); round: `{rounds}` (int ≥ 1) |
| `draw_allowed` | boolean | Required |
| `overtime` | object | Required: `policy` one of `none`, `extra_time`, `shootout`, `golden_score`, `super_over`; optional `duration_minutes` (int ≥ 0) |
| `tie_break_order` | array | Optional. Items from `h2h_points`, `h2h_diff`, `overall_diff`, `scored`, `fair_play`, `draw_lots` (no repeats). Default = the full list. `draw_lots` is always applied last, even if omitted |
| `roster` | object | Required: `min_squad_size`, `max_squad_size` (ints ≥ 1, min ≤ max), `required_positions` (position → minimum count, may be `{}`) |

Responses: 201 `{"sport_id":"kabaddi","status":"created","config":{…stored config echoed…}}`; 400 `VALIDATION_ERROR` (`details.fields` lists bad fields); 409 `SPORT_EXISTS`.

## §5.9 Event types
| type | payload | Allowed when / rule |
|---|---|---|
| `match_init` | `{sport_id, home_team_id, away_team_id}` (+ optional `league_id`) | Creates a stand-alone match, status `upcoming`. Unknown sport → 404 `SPORT_NOT_FOUND` |
| `match_start` | `{}` | Status must be `upcoming` → becomes `in_progress`; else 409 `ILLEGAL_TRANSITION` |
| `score` | `{team_id, event_type}` | Status `in_progress` (else 409 `MATCH_NOT_IN_PROGRESS`). `team_id` must be home or away (else 400). `event_type` must exist in the sport's `scoring_events` (else 400 `UNKNOWN_EVENT_TYPE`). Points/runs/rounds come from the sport config |
| `discipline` | `{team_id, points}` (integer, usually negative) | Status `in_progress`. Adds to the team's fair-play total (higher is better) |
| `tiebreak_winner` | `{team_id}` | Status `in_progress`. Declares the winner of a shootout / overtime / super over without changing the score |
| `match_end` | `{}` | Status must be `in_progress` (else 409 `ILLEGAL_TRANSITION`) → `completed`. If the score is level, `draw_allowed` is false, and no active `tiebreak_winner` exists → 409 `TIE_NOT_ALLOWED` |
| `compensation` | `{compensates, reason}` | Any status after init, including completed. `compensates` = `event_id` of a `score`, `discipline`, or `tiebreak_winner` event of the same match. Unknown → 404 `EVENT_NOT_FOUND`; already compensated, other type, or other match → 409 `INVALID_COMPENSATION` |

- A match stream exists if it is a league fixture (§5.8) or its `match_init` was accepted. `match_init` for an existing stream → 409 `MATCH_EXISTS`; any other event for a missing stream → 404 `MATCH_NOT_FOUND`.
- innings model: a team's legal balls ≥ innings_per_team × overs_per_innings × balls_per_over, or wickets ≥ innings_per_team × wickets_per_innings → further score events **for that team** are 409 `INNINGS_COMPLETE`.
- round model: once a team has ≥ (best_of + 1) / 2 rounds, further score events → 409 `SERIES_ALREADY_DECIDED`.
- Compensated events do not count toward these limits.
- Same `event_id` + identical body → 200 with the stored response. Same `event_id` + different body → 409 `DUPLICATE_EVENT_ID`.
- Event response 201 (200 on replay): `{"event_id","match_id","type","sequence","match_version","signature"}`. `sequence` = 1-based position in that match's log (every type counts). `match_version` = number of events in the log after this append.

## §5.9 Score fields
| Field | Definition |
|---|---|
| `status` | `upcoming`, `in_progress`, or `completed` (derived from the log) |
| `outcome` | `pending` while not completed; when completed: `home_win`, `away_win`, `draw`, or `undecided` (level score, draw_allowed false, no active tie-break winner — e.g. after the tie-break event was compensated) |
| `score` | event model: sum of points. innings model: total runs. round model: rounds won. Active (non-compensated) events only |
| `wickets`, `balls`, `overs` | innings model only (else `null`). `balls` = legal balls faced by that team; `overs` = string `"{balls div bpo}.{balls mod bpo}"`, e.g. `"3.2"` |
| `winner_team_id` | Higher score; if level, the active `tiebreak_winner` team; else `null` |
| `events` | All events in sequence order, including compensated ones and compensations. `compensated` is true for a targeted event; `compensated_by` holds the compensating `event_id` |

## §5.10 Standings fields
| Field | Definition |
|---|---|
| `points` | won × win + drawn × draw + lost × loss. A win decided by `tiebreak_winner` counts as a win |
| `scored`/`conceded` | Sum of score for / against (goals, points, runs, rounds) |
| `diff` (event) | scored − conceded |
| `diff` (round) | Rounds won − rounds lost |
| `diff` (innings) | Net run rate = runs scored ÷ overs faced − runs conceded ÷ overs bowled, rounded to 3 decimals. Overs = legal balls ÷ balls_per_over (decimal). An innings that ended with wickets ≥ wickets_per_innings counts as the full overs_per_innings. Overs bowled = the opponent's overs faced |
| `fair_play` | Sum of the team's active discipline points |
| `h2h` | `h2h[a][b]` = results of a against b over all completed matches between them: `played`, `points` earned by a, `scored` by a, `conceded` by a. Present for every ordered pair of teams (zeros when never met) |
| `resolved_by` | Name of the criterion that placed this team above the next team it was tied with on points, or `null` if it was not tied |

## §5.11 Transfer rule checks — evaluated in this exact order; the first failure is returned
| # | Check | Result |
|---|---|---|
| 1 | Schema, dates, `loan_end_date` > `effective_date`, `to_squad_id` present unless release | 400 `VALIDATION_ERROR` |
| 2 | League / player / squads exist | 404 `LEAGUE_NOT_FOUND`, `PLAYER_NOT_FOUND`, `SQUAD_NOT_FOUND` |
| 3 | From and to squads belong to the league's tenant | 409 `CROSS_TENANT_TRANSFER` |
| 4 | Player's current squad in this league equals `from_squad_id` | 409 `NOT_IN_SQUAD` |
| 5 | transfer/loan: `effective_date` inside the window (inclusive). Release is allowed on any date | 409 `TRANSFER_WINDOW_CLOSED` |
| 6 | Player is not currently on loan (transfer/loan/release of a loaned player is refused) | 409 `PLAYER_ON_LOAN` |
| 7 | transfer/loan: destination squad count + 1 ≤ `max_squad_size` | 409 `SQUAD_FULL` |
| 8 | After the move, the from squad still has ≥ the required count for the player's position | 409 `MIN_POSITION_VIOLATION` |

## §5.13 Probe routes
| # | Probe route | Path variable |
|---|---|---|
| P1 | `POST /audit/v1/rbac/tenants` | — |
| P2 | `POST /audit/v1/rbac/leagues/{league_id}/fixtures` | league |
| P3 | `POST /audit/v1/rbac/clubs/{club_id}/roster` | club |
| P4 | `POST /audit/v1/rbac/clubs/{club_id}/products` | club |
| P5 | `PATCH /audit/v1/rbac/players/{player_id}` | player |
| P6 | `GET /audit/v1/rbac/clubs/{club_id}` | club |
| P7 | `GET /audit/v1/rbac/platform/config` | — |

Expected matrix (A = allowed → 200 `{"authorized":true}`; D = denied → exactly 403 `FORBIDDEN`):

| Probe (target) | Super Admin | Organizer | Club Mgr | Player | Viewer |
|---|---|---|---|---|---|
| P1 | A | D | D | D | D |
| P2 own_league | A | A | D | D | D |
| P2 other_league (same tenant) | A | D | D | D | D |
| P2 foreign_league | A | D | D | D | D |
| P3 / P4 own_club | A | D | A | D | D |
| P3 / P4 other_club (same tenant) | A | D | D | D | D |
| P3 / P4 foreign_club | A | D | D | D | D |
| P5 own_player | A | D | A (own club's players) | A (self only) | D |
| P5 other_player (other club) | A | D | D | D | D |
| P5 foreign_player | A | D | D | D | D |
| P6 own_club / other_club (tenant-alpha) | A | A | A | A | A |
| P6 foreign_club | A | D | D | D | D |
| P7 | A | D | D | D | D |

Cross-tenant access by a non-super-admin is always 403 (not 404). 404 is reserved for ids that do not exist at all. Authorization is evaluated before anything else about the request.

| Additional probe | Expected |
|---|---|
| P7 with no Authorization header | 401 `UNAUTHENTICATED` |
| P7 with a super-admin token whose signature was altered, or with `alg: none` | 401 `UNAUTHENTICATED` |
| Rate limit: 150 requests to `GET /api/v1/ping` within 5 s from one client | First request 200 `{"pong":true}`; at least 40 of the 150 return 429 (`RATE_LIMITED`) with a `Retry-After` header; 11 s later a request is 200 again |
| Input validation: `sport_id = x'; DROP TABLE sports;--`, or a `customer_id` containing quotes/`<script>` | Never a 5xx. Sport id → 400 `VALIDATION_ERROR`. Strings are stored/returned as plain data |
| Body larger than 1 MB to any `/audit/v1/*` POST | 413 `PAYLOAD_TOO_LARGE` |

## §5.14 Offline sync — per-action result and conflict resolution (exact)
| Situation (when this action is processed) | status | resolution | error_code |
|---|---|---|---|
| Rules allow it and `base_version` == current version | `applied` | `appended` | `null` |
| Rules allow it but `base_version` < current version (stale device) | `applied` | `rebased_append` | `null` |
| (`device_id`, `action_id`) already processed before, or the same `event_id` already exists with an identical payload | `duplicate` | `skipped_duplicate` | `null` |
| Any rule of 5.9 / 5.11 would reject the action (e.g. `MATCH_NOT_IN_PROGRESS`, `INVALID_COMPENSATION`, `NOT_IN_SQUAD`, `SQUAD_FULL`, `DUPLICATE_EVENT_ID`) | `rejected` | `server_wins` | that rule's code |
| `base_version` > current version | `rejected` | `server_wins` | `INVALID_BASE_VERSION` |
| Unknown id referenced (match, player, squad) | `rejected` | `server_wins` | the matching `*_NOT_FOUND` |

- `base_version`: score_event → the match's version (number of events); roster_transfer → the number of audit entries of that player.
- Server sorts actions by `queued_at` ascending (ties: array order), processes one by one, each against the state left by the previous one. Results returned in **request order**.
- `server_version` = version of the affected match/player after processing (unchanged for rejected/duplicate). `signature` = event signature for applied score_event actions, else `null`.
- Re-sending the same request must return `duplicate` for every action and change nothing. Whole request is always HTTP 200; only a malformed envelope is 400. `actions`: 1–100 items.

## §8.2 Required mobile screens
| Screen | Must show |
|---|---|
| Login | Email + password; role-aware home after login |
| Fixtures | List of matches with status and time; tap to open a match |
| Match detail | Live score (updates in real time), event timeline, pinned product showcase |
| Standings | Points table for a league with qualification status |
| Club profile | Club info, roster, staff, home venue |
| Store | Catalogue, variant picker, cart, checkout with the mock gateway, receipt view/download |
| Roster management | For Club Manager: add / transfer / loan / release a player |
| Scoring entry | For League Organizer: append a score event and a compensating event |
| Sync status | Always-visible online / offline / syncing indicator and the pending-action queue |

## Appendix B — error code catalogue
| HTTP | Code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Schema/type/range problem (`details.fields`), bad dates, bad limits |
| 400 | `UNKNOWN_EVENT_TYPE` | score `event_type` not defined in the sport |
| 400 | `INVALID_DISCOUNT_CODE` | Unknown discount code |
| 401 | `UNAUTHENTICATED` | Missing / invalid / tampered / expired / alg:none token |
| 402 | `PAYMENT_DECLINED`, `PAYMENT_CAPTURE_FAILED` | Mock gateway failure |
| 403 | `FORBIDDEN` | Role or tenant/ownership boundary |
| 404 | `SPORT_NOT_FOUND`, `MATCH_NOT_FOUND`, `LEAGUE_NOT_FOUND`, `EVENT_NOT_FOUND`, `PLAYER_NOT_FOUND`, `SQUAD_NOT_FOUND`, `VARIANT_NOT_FOUND` | Referenced id does not exist |
| 409 | `SPORT_EXISTS`, `LEAGUE_EXISTS`, `MATCH_EXISTS` | Id already used |
| 409 | `DUPLICATE_EVENT_ID`, `DUPLICATE_ORDER_ID` | Same id re-used with a different body |
| 409 | `ILLEGAL_TRANSITION`, `MATCH_NOT_IN_PROGRESS`, `TIE_NOT_ALLOWED` | Match state-machine violations |
| 409 | `INNINGS_COMPLETE`, `SERIES_ALREADY_DECIDED` | Config-driven scoring limits |
| 409 | `INVALID_COMPENSATION` | Target already compensated, wrong type, or other match |
| 409 | `NO_VALID_PAIRING` | Swiss: no rematch-free pairing exists |
| 409 | `OUT_OF_STOCK` | Not enough stock |
| 409 | `CROSS_TENANT_TRANSFER`, `NOT_IN_SQUAD`, `TRANSFER_WINDOW_CLOSED`, `PLAYER_ON_LOAN`, `SQUAD_FULL`, `MIN_POSITION_VIOLATION` | Roster rules (checked in the order of 5.11) |
| — | `INVALID_BASE_VERSION` | Only inside an offline-sync per-action result (5.14) |
| 413 | `PAYLOAD_TOO_LARGE` | Body over 1 MB |
| 429 | `RATE_LIMITED` | `/api/v1/*` limit exceeded |

Codes the spec does not define but our team uses: `INTERNAL_ERROR` (500, should never happen). Nothing else — never invent codes.
