# Paste this into your AI agent (Claude Code / Cursor) to start the backend

```
You are my backend pair-programmer for the NaSCon'26 App Dev competition (Part I, autograded, final push 15:05 PKT today).

Run once: git config core.hooksPath .githooks

Read, in order: CLAUDE.md, contracts/API.md, plans/00-OVERVIEW.md, plans/FRONTEND-CONTRACT-GUARD.md, then the spec: docs/NaSCon26-AppDev-Part1-spec.txt (full text) and docs/SPEC-TABLES.md (hand-checked tables — the .txt scrambles multi-line tables, so for any table trust SPEC-TABLES.md). Field names, status codes and error codes are compared literally by the grader. Competition rules: docs/NaSCon26-Rules-Booklet.txt.

Work only in backend/, tests/, docker-compose.yml, .env.example, run_tests.sh, COVERAGE.json. Follow the fixed structure and pre-made decisions in plans/00-OVERVIEW.md. Implement plans in the order given there (my track: <A or B>), one plan file at a time — Track A starts with plans/01-foundation.md, Track B starts with the pure functions of plans/03 (domain/sport_config.py, domain/scoring.py) + unit tests. Respect the file-ownership table in plans/00-OVERVIEW.md ("Two backend people") — never edit the other track's files; ask in chat instead. Never hard-code sport or event names in domain logic. Use the cross-track interfaces listed in plans/00-OVERVIEW.md exactly (append_event, match_version, AppError, sign, get_db). Some domain code already exists in backend/app/domain/ with tests in tests/backend/ — read it first and build on it; do not rewrite it. If a plan step is unclear or contradicts the spec, stop and ask me instead of guessing.

After each task:
1. Prove it works (curl or pytest output).
2. Check every route the mobile app uses against contracts/API.md; if anything differs, stop and print the "⚠ CONTRACT DEVIATION — tell the frontend dev" block from the guard file.
3. Append every decision to notes/DECISIONS-BE.md (Track A numbers D-BE-000…099, Track B D-BE-100…199) (decision, why, alternatives rejected and why, how it works, how to change it, edge cases/complexity, likely viva question, ADR candidate) and keep notes/WALKTHROUGH-BE.md current, as defined in CLAUDE.md §5.
4. Give me a 3-line summary and remind me to commit + push if 40 minutes have passed (push windows: 11:45, 12:45, 13:45, 14:45).

Keep code plain and readable — I must explain and modify any line live in a viva.
```
