# Frontend ↔ Backend contract guard

**Why:** the mobile app (Talha) and the backend are built at the same time by different people and different AI agents. The app is coded against `contracts/API.md`. Any silent difference = a broken screen in front of the judges (10 UI/HCI points + 4 offline points).

## What the frontend assumes (backend agents: treat this as a checklist)
1. **Base URL** `http://<LAN-IP>:8080`, editable in the app's Settings. Backend binds `0.0.0.0:8080`.
2. **Error body** `{"error":{"code","message","details"}}` on every non-2xx — the app maps `code` → friendly text. A new/renamed code = an unexplained error on screen.
3. **Auth:** `POST /api/v1/auth/login` returns `token`, `user`, `tenant` (contract §2.1). App stores the token in secure storage and sends `Authorization: Bearer`. A 401 anywhere → app logs the user out.
4. **Role-aware UI** is driven by `user.role` + `user.league_id` / `club_id` / `player_id`. Changing role names or these fields breaks navigation.
5. **Tenant theme** from `tenant.primary_color` / `accent_color` (hex `#RRGGBB`).
6. **Score/standings** read from `/audit/v1/score/{id}` and `/audit/v1/standings/{id}` exactly as the spec.
7. **Writes** go to the `/api/v1/*` twins with bodies identical to the spec's audit routes.
8. **Offline queue** = spec §5.14 action format; `base_version` from `score.version` (matches) and `history.length` (players).
9. **Lists are never `null`** — empty arrays `[]`. Optional scalars are `null`, not missing.
10. **Ids are strings**, money is integer paisa, timestamps end with `Z`.
11. **Live updates:** WebSocket `/ws/matches/{id}` messages `match_updated` / `showcase_updated`; app also polls every 5 s.

## Rule for backend AI agents
Before you finish any task touching a route listed in `contracts/API.md` §1:
1. Call the route (curl / TestClient) and compare the JSON **keys, types, nesting, status codes, error codes** with the contract.
2. If anything differs — or you believe the contract should change — **do not quietly "fix" the frontend's expectation**. Stop and print to your human:

```
⚠ CONTRACT DEVIATION — please tell Talha (frontend) before continuing:
Route:    GET /api/v1/clubs/{club_id}
Contract: roster[].registration_type ∈ initial|transfer|loan
Backend:  roster[].registration_type ∈ initial|transfer|loan|loan_return
Reason:   loan returns create a new registration type
Proposal: map loan_return → "transfer" in the response (no app change)  OR  app adds a label for it
```
3. Prefer the option that needs **no frontend change**. If the app must change, the human tells Talha in chat; once agreed, update `contracts/API.md` and add a CHANGELOG line with the time.
4. Removing/dropping a feature the app uses (e.g. WebSocket) also counts — report it.

## Rule for the frontend agent (Talha's side)
Same in reverse: if the app needs a field/route not in the contract, print `⚠ CONTRACT REQUEST — tell the backend: …`, and don't invent backend behaviour.

## Quick sync ritual (each push window)
Backend posts in chat: "routes done: …, deviations: none / …". Frontend replies: "switched these screens from mocks to live: …".
