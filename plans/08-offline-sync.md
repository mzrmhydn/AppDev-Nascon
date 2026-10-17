# 08 — Offline sync — spec NFR-4, §5.14 (4 pts; the app depends on this exact shape)

**Reuse, don't duplicate:** each action calls the **same** service functions as `/events` (plan 03) and `/roster/transfer` (plan 07). Refactor those services to return `(status_code, body)` or raise `AppError`, so sync can catch the error code.

## `POST /audit/v1/offline-sync` (and the `/api/v1/offline-sync` twin with auth)
- Envelope: `device_id` string, `actions` array 1–100, each `{action_id, type ∈ score_event|roster_transfer, queued_at timestamp, base_version int ≥ 0, payload object}` → else **400** `VALIDATION_ERROR`. Everything else is HTTP **200**.
- Processing order: sort by `queued_at` asc, ties by array index. Process one by one. Return results in **request order** with `processed_order` (1-based processing position).
- Per action, in this order:
  1. `(device_id, action_id)` already processed → `duplicate` / `skipped_duplicate` / `error_code:null` (return stored server_version? spec: unchanged → current version).
  2. score_event with an `event_id` that already exists with identical body → `duplicate` / `skipped_duplicate`.
  3. Unknown match / player / squad → `rejected` / `server_wins` / `MATCH_NOT_FOUND` | `PLAYER_NOT_FOUND` | `SQUAD_NOT_FOUND` …
  4. `base_version > current version` → `rejected` / `server_wins` / `INVALID_BASE_VERSION`.
  5. Run the real service. Rule failure (any 4xx code from 5.9/5.11, e.g. `MATCH_NOT_IN_PROGRESS`, `SQUAD_FULL`, `DUPLICATE_EVENT_ID`) → `rejected` / `server_wins` / that code.
  6. Success → `applied`; resolution `appended` if base_version == version before applying, else `rebased_append`.
  - current version: score_event → number of events of the match; roster_transfer → number of audit entries of the player.
  - ⚠ Decide and log: the order of checks 3 vs 4 (spec lists both; we check existence first because version needs the entity).
- `server_version` = version after processing (unchanged for rejected/duplicate). `signature` = event signature for applied score_event, else null.
- Record every processed `(device_id, action_id)` → result, so re-sending the same request returns `duplicate` for every action and changes nothing.
- `summary {applied, rejected, duplicate}`.
- Broadcast `match_updated` for applied score events.

## What the app sends (so you can test with the same data)
The app stores queued actions in SQLite in exactly this format and calls `POST /api/v1/offline-sync` with `device_id` = a UUID generated once per install. It shows each result: applied → "Synced", rejected → friendly text for `error_code`, duplicate → "Already synced".

## Tests (offline-sync is graded by script — 4 pts)
appended vs rebased_append, duplicate on resend, INVALID_BASE_VERSION, rule rejection codes, processing order by queued_at, 1–100 envelope limits.
