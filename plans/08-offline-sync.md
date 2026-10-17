# 08 — Offline sync — spec NFR-4, §5.14 (4 pts; the app depends on this exact shape)

**Reuse, don't duplicate:** each action calls the **same** service functions as `/events` (plan 03) and `/roster/transfer` (plan 07). Refactor those services to return `(status_code, body)` or raise `AppError`, so sync can catch the error code.

## `POST /audit/v1/offline-sync` (and the `/api/v1/offline-sync` twin with auth)
- Envelope: `device_id` string, `actions` array 1–100, each `{action_id, type ∈ score_event|roster_transfer, queued_at timestamp, base_version int ≥ 0, payload object}` → else **400** `VALIDATION_ERROR`. Everything else is HTTP **200**.
- Processing order: sort by `queued_at` asc, ties by array index. Process one by one. Return results in **request order** with `processed_order` (1-based processing position).
- Per action, in this exact order (first match wins):
  1. `(device_id, action_id)` already in `offline_actions` → `duplicate` / `skipped_duplicate` / `error_code: null`.
  2. `payload` fails the single route's schema check (plan 03 step 1 / plan 07 step 1) → `rejected` / `server_wins` / `VALIDATION_ERROR`. **Never a whole-request 400** — only the envelope can 400.
  3. score_event whose `payload.event_id` already exists with an identical body → `duplicate` / `skipped_duplicate`.
  4. Referenced id unknown (match for score_event; league/player/squad for roster_transfer) → `rejected` / `server_wins` / the matching `*_NOT_FOUND`. (Exception: a `match_init` score_event creates the match — its current version is 0.)
  5. Compute the current version (roster: after `materialize_loan_returns` as of `effective_date`). `base_version > current` → `rejected` / `server_wins` / `INVALID_BASE_VERSION`.
  6. Call the real service (`append_event` / the transfer service). It raises `AppError` → `rejected` / `server_wins` / that error's `code`.
  7. Success → `applied`; `resolution` = `appended` if `base_version == current` (from step 5), else `rebased_append`.
  - current version: score_event → `match_version(db, match_id)`; roster_transfer → number of audit entries of the player.
  - `server_version` for **every** status = the entity's version right after this action was processed (for rejected/duplicate that is simply the current version; for an unknown entity use 0).
  - Each action runs in its **own** transaction (a rejected action must not roll back earlier applied ones). Save every result (all statuses) in `offline_actions` keyed by `(device_id, action_id)`.
- `server_version` = version after processing (unchanged for rejected/duplicate). `signature` = event signature for applied score_event, else null.
- Because every result is saved, re-sending the same request returns `duplicate` for every action and changes nothing.
- `summary {applied, rejected, duplicate}`.
- Broadcast `match_updated` for applied score events.

## What the app sends (so you can test with the same data)
The app stores queued actions in SQLite in exactly this format and calls `POST /api/v1/offline-sync` with `device_id` = a UUID generated once per install. It shows each result: applied → "Synced", rejected → friendly text for `error_code`, duplicate → "Already synced".

## Tests (offline-sync is graded by script — 4 pts)
appended vs rebased_append, duplicate on resend, INVALID_BASE_VERSION, rule rejection codes, processing order by queued_at, 1–100 envelope limits.
