# CLAUDE.md / AGENTS.md — rules for every human and AI agent in this repo

**Project:** NaSCon'26 App Dev, Part I — Multi-Sport League & Club Operations Platform.
**Binding spec:** `docs/NaSCon26-AppDev-Part1-spec.pdf` (read it — it wins over everything). Competition rules: `docs/NaSCon26-Rules-Booklet.pdf`.
**Deadline:** final push ≤ **15:05:00 PKT** Day 1 (aim 14:45). Push at least once in each window **10:45–11:45, 11:45–12:45, 12:45–13:45, 13:45–14:45** (−2 per missed window).

## 0. Read order for an agent starting work
1. This file.
2. `contracts/API.md` — the FE↔BE contract. **Never change it silently** (§4).
3. `plans/00-OVERVIEW.md` → then the plan file for your task.
4. The spec section the plan points to. Copy field names / codes from the spec character-for-character.
5. Your human's `notes/DECISIONS-*.md` (if it exists) so you stay consistent.

## 1. Who owns what
| Folder | Owner |
|---|---|
| `backend/`, `tests/`, `run_tests.sh`, `COVERAGE.json`, `docker-compose.yml`, `.env.example` | Backend team |
| `mobile/` (incl. `mobile/release/app-release.apk`) | the frontend dev |
| `contracts/API.md` | Shared — changes only via `plans/FRONTEND-CONTRACT-GUARD.md` |
| `README.md`, `TRACEABILITY.md`, `ADR.md`, `plans/`, `docs/` | Whoever is free; small edits, pull first |

Agents work **only** inside their human's folders. Need something elsewhere → stop and tell your human.

## 2. Hard rules from the spec (each one costs points if broken)
- `DAY1_SALT=<salt> docker compose up -d --build` on a clean Ubuntu box, ≤ 10 min, `/health` 200 within 120 s, **no manual steps**. API on host port **8080**. Compose forwards `DAY1_SALT: ${DAY1_SALT}`. (−10 if broken)
- **Never hard-code sport or event names** (`"football"`, `"goal"`, `"wicket"`…) in domain logic. Branch only on `scoring_model` (`event`/`innings`/`round`) and config values. Sport names may appear **only** in seed data. (−8)
- No Firebase/Supabase/BaaS; no fixture-generation libraries. Web frameworks, ORMs, JWT and PDF libraries are fine.
- `DAY1_SALT` only from env, never committed. `.env.example` has a placeholder.
- Error body for every non-2xx: `{"error":{"code","message","details"}}`. Validation order: 400 → 404 → 409/402.
- Field names, types, status codes and error codes are compared **literally** by the grader.

## 3. How to write code (we must explain and change it live)
- Plain and obvious beats clever. No metaprogramming, no generic base classes, no premature abstraction.
- Small files, one job each. Descriptive names. Each file starts with a 1–3 line comment: what it does + which FR/NFR it serves.
- **Algorithms are pure functions** (no DB, no HTTP) in `backend/app/domain/` — easy to unit-test and to explain. Routes are thin: parse → call domain/service → return.
- Settings only in `backend/app/config.py`.
- Comment the *why* of non-obvious lines only.
- New dependency only if it clearly saves time — log it as a decision.

## 4. Contract guard (frontend ↔ backend)
Before finishing any task that touches an endpoint used by the app (anything in `contracts/API.md` §1), the agent compares its response with the contract. If they differ, or a field must change, the agent **stops and tells its human**:
> "⚠ CONTRACT DEVIATION — tell the frontend dev: `<route>` now returns/needs `<X>` instead of `<Y>` because `<reason>`."
Details: `plans/FRONTEND-CONTRACT-GUARD.md`.

## 5. Explain every decision (private notes, gitignored)
After each task append to `notes/DECISIONS-<BE|FE|LEAD>.md` (one entry per decision where a reasonable developer could have chosen differently):
```
## D-BE-007 — <title> (FR-x.x)
Files: … | Decision: … | Why: … | Alternatives rejected: A (why), B (why)
How it works (plain words): … | How to change it: <file:function> | Edge cases / complexity: … | Likely viva question: … | ADR candidate: yes/no
```
Keep `notes/WALKTHROUGH-<BE|FE|LEAD>.md` current: file map, request flow per feature, data model, "where would I change X" cheat-sheet, hidden-complexity notes (spec §6). Then give your human a 3-line chat summary: what's done, files, how to test (curl).

## 6. Git
- Everyone on `main`. `git pull --rebase` before every push. Small commits: `[BE] FR-2.3 checkout`, `[FE] standings screen`.
- **Never** `--force`, never rewrite pushed commits.
- **No co-authors.** Never add `Co-Authored-By:` (or any AI attribution / "Generated with" line) to commit messages or PRs. Each clone runs once: `git config core.hooksPath .githooks` (the hook strips such lines automatically). `.claude/settings.json` also turns off Claude Code's attribution.
- Remind your human to push if 40+ min have passed.
