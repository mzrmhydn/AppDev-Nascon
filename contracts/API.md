# API Contract — Frontend ↔ Backend (v1)

> **Single source of truth between `mobile/` (Talha) and `backend/`.**
> Two families of routes:
> 1. **`/audit/v1/*` + `/health`** — defined **byte-for-byte** by the Part I spec (`docs/NaSCon26-AppDev-Part1-spec.pdf`, §5). Not repeated here. The spec wins over everything.
> 2. **`/api/v1/*`** — routes the **mobile app** needs that the spec doesn't define. Defined below. Backend must match these exactly; the app is being built against them in parallel.
>
> **Changing anything in this file:** see `plans/FRONTEND-CONTRACT-GUARD.md`. Short version: don't silently change it — tell Talha first, then add a line to the CHANGELOG at the bottom.

---

## 0. Conventions (same as spec §5.2)

- Base URL: `http://<laptop-LAN-IP>:8080` (the app has a Settings screen to change it).
- JSON, UTF-8. Timestamps `YYYY-MM-DDTHH:MM:SSZ`. Dates `YYYY-MM-DD`. Money = integer paisa, currency `"PKR"`.
- **Every non-2xx** (both families): `{"error":{"code":"UPPER_SNAKE","message":"human text","details":{}}}`.
  The app shows its **own** friendly text per `code` (it never shows `message` raw), so **codes must be exact**.
- `/api/v1/*` needs `Authorization: Bearer <token>` **except** `POST /api/v1/auth/login`, `GET /api/v1/ping`, `POST /api/v1/dev/demo-seed`.
  Missing/invalid token → 401 `UNAUTHENTICATED`. Not allowed → 403 `FORBIDDEN`.
- `/api/v1/*` is rate limited (100 req / 10 s / IP) → 429 `RATE_LIMITED` + `Retry-After`.
- Role names (everywhere): `super_admin`, `league_organizer`, `club_manager`, `player`, `viewer`.
- **Tenant isolation:** every list below returns only the caller's tenant. `super_admin` sees all tenants.

## 1. Which route the app uses for what (decided — don't change without the guard process)

| App screen / action | Route | Auth |
|---|---|---|
| Login | `POST /api/v1/auth/login` | none |
| Restore session | `GET /api/v1/me` | yes |
| League picker | `GET /api/v1/leagues` | yes |
| Fixtures list | `GET /api/v1/leagues/{league_id}/fixtures` | yes |
| Match detail – score + timeline | `GET /audit/v1/score/{match_id}` (spec §5.9) | none |
| Match detail – pinned product | `GET /api/v1/matches/{match_id}/showcase` | yes |
| Match detail – live updates | WebSocket `/ws/matches/{match_id}` **+** app polls score every 5 s as fallback | none |
| Standings | `GET /audit/v1/standings/{league_id}` (spec §5.10) | none |
| Club profile | `GET /api/v1/clubs`, `GET /api/v1/clubs/{club_id}` | yes |
| Store catalogue | `GET /api/v1/products` | yes |
| Stock refresh | `GET /audit/v1/inventory/{variant_id}` (spec §5.12) | none |
| Checkout | `POST /api/v1/checkout` (= spec §5.12 body/response) | yes |
| Roster mgmt – options | `GET /api/v1/leagues/{league_id}/roster-config` | yes |
| Roster mgmt – action | `POST /api/v1/roster/transfer` (= spec §5.11 body/response) | yes |
| Roster history / base_version | `GET /audit/v1/roster/history/{player_id}` (spec §5.11) | none |
| Scoring entry | `POST /api/v1/events` (= spec §5.9 body/response) | yes |
| Offline sync | `POST /api/v1/offline-sync` (= spec §5.14 body/response) | yes |
| Pin a product (organizer/manager) | `POST /api/v1/matches/{match_id}/showcase` | yes |

**Rule:** reads that the spec already defines → app calls `/audit/v1/*` directly. **Writes** → app calls the `/api/v1/*` twin, which is the **same service function** plus auth + RBAC. Request and response bodies of the twins are **identical** to the audit route.

---

## 2. `/api/v1` routes

### 2.1 `POST /api/v1/auth/login`
Request `{ "email": "manager@nascon.test", "password": "Nascon@26" }`
200:
```json
{
  "token": "<jwt, valid ≥ 12 h>",
  "user": {
    "user_id": "user-manager", "email": "manager@nascon.test", "display_name": "Club Manager",
    "role": "club_manager", "tenant_id": "tenant-alpha",
    "league_id": null, "club_id": "club-alpha-1", "player_id": null
  },
  "tenant": {
    "tenant_id": "tenant-alpha", "name": "Alpha Sports",
    "primary_color": "#0B5FFF", "accent_color": "#FFB020", "logo_url": null
  }
}
```
- `league_id` set only for `league_organizer` (`league-alpha-1`); `club_id` for `club_manager` (`club-alpha-1`) and `player` (`club-alpha-1`); `player_id` for `player` (`player-alpha-1`).
- `super_admin`: `tenant_id: null`, `tenant: null` (app uses its default theme).
- Wrong email/password → 401 `UNAUTHENTICATED`. Bad body → 400 `VALIDATION_ERROR`.
- Same JWT format/secret as `/audit/v1/rbac-matrix` tokens (one auth system).
- `logo_url` is always `null` in v1 — the app bundles tenant logos itself (keyed by `tenant_id`).

### 2.2 `GET /api/v1/me` → 200 `{ "user": {...same as login}, "tenant": {...|null} }`

### 2.3 `GET /api/v1/leagues`
200:
```json
{ "leagues": [
  { "league_id": "league-alpha-1", "tenant_id": "tenant-alpha", "name": "Alpha Premier League",
    "sport_id": "football", "season": "2026",
    "teams": [ { "team_id": "club-alpha-1", "name": "Alpha United" } ] }
] }
```
- `sport_id` may be `null` for a league with no fixtures yet. `teams` may be `[]`. Team ids are club ids.

### 2.4 `GET /api/v1/leagues/{league_id}/fixtures`
200:
```json
{ "league_id": "league-alpha-1", "sport_id": "football",
  "fixtures": [
    { "match_id": "demo-m1", "round": 1,
      "home": { "team_id": "club-alpha-1", "name": "Alpha United" },
      "away": { "team_id": "club-alpha-2", "name": "Alpha Rovers" },
      "status": "completed", "scheduled_at": "2026-10-17T14:00:00Z", "venue": "Alpha Arena",
      "home_score": 2, "away_score": 1, "version": 7 }
  ] }
```
- `status` = from the event log: `upcoming` | `in_progress` | `completed`.
- `home_score`/`away_score` = projection scores (`null` when `upcoming`). `round`, `scheduled_at`, `venue` may be `null`.
- Sorted by `scheduled_at` then `match_id`. 404 `LEAGUE_NOT_FOUND`; other tenant → 403 `FORBIDDEN`.

### 2.5 `GET /api/v1/clubs` → 200 `{ "clubs": [ { "club_id", "tenant_id", "name", "short_name", "primary_color" } ] }`

### 2.6 `GET /api/v1/clubs/{club_id}`
200:
```json
{
  "club_id": "club-alpha-1", "tenant_id": "tenant-alpha", "name": "Alpha United", "short_name": "AUN",
  "primary_color": "#0B5FFF",
  "home_venue": { "name": "Alpha Arena", "city": "Islamabad", "lat": 33.6844, "lng": 73.0479 },
  "socials": { "instagram": "@alphaunited", "x": "@alphaunited", "facebook": null },
  "staff": [ { "name": "Usman Tariq", "role": "coach" } ],
  "stats": [ { "season": "2025", "played": 18, "won": 11, "drawn": 4, "lost": 3, "trophies": 1 } ],
  "roster": [
    { "player_id": "player-alpha-1", "name": "Ali Khan", "position": "gk", "role": "captain",
      "league_id": "league-alpha-1", "squad_id": "club-alpha-1",
      "registration_type": "transfer", "parent_squad_id": null }
  ]
}
```
- `staff[].role`: `coach` | `manager` | `physio`. `roster` = players whose **current** squad (today) belongs to this club; `registration_type`: `initial` | `transfer` | `loan`.
- Unknown club → 404 `SQUAD_NOT_FOUND` (closest code in the spec catalogue). Other tenant → 403 `FORBIDDEN`.

### 2.7 `GET /api/v1/products`
200:
```json
{ "products": [
  { "product_id": "prod-jersey-001", "tenant_id": "tenant-alpha", "club_id": "club-alpha-1",
    "name": "Home Jersey 2026", "category": "apparel", "description": "Official home kit.",
    "image_url": null,
    "variants": [ { "variant_id": "var-jersey-001-M", "size": "M", "color": "Blue",
                    "price_minor": 450000, "currency": "PKR", "stock": 1 } ] }
] }
```
- `category`: `apparel` | `accessory` | `digital`. `size`/`color` may be `null`. `price_minor` = current price (after any scheduled price change). `image_url` null in v1 (app shows a category icon).

### 2.8 `GET /api/v1/matches/{match_id}/showcase` → 200 `{ "match_id": "demo-m1", "product": <product object of 2.7> | null, "pinned_at": "…Z" | null }`
### 2.9 `POST /api/v1/matches/{match_id}/showcase`
Request `{ "product_id": "prod-jersey-001" }` → 200, same shape as 2.8. Allowed: `super_admin`, `league_organizer` (own league's match), `club_manager` (product of own club). Else 403. Unknown match → 404 `MATCH_NOT_FOUND`; unknown product → 404 `VARIANT_NOT_FOUND` (closest spec code). Broadcasts `showcase_updated` on the WebSocket.

### 2.10 `GET /api/v1/leagues/{league_id}/roster-config`
200:
```json
{ "league_id": "league-alpha-1",
  "transfer_window": { "open": "2026-10-01", "close": "2026-10-31" },
  "max_squad_size": 25, "required_positions": { "gk": 1 },
  "squads": [ { "squad_id": "club-alpha-1", "club_id": "club-alpha-1", "name": "Alpha United", "player_count": 12 } ] }
```
404 `LEAGUE_NOT_FOUND` if the league has no roster setup.

### 2.11 Write twins (identical bodies/responses/error codes to the spec route)
| Twin | Spec route | Who is allowed (else 403 `FORBIDDEN`, checked **before** validation) |
|---|---|---|
| `POST /api/v1/events` | `/audit/v1/events` | `super_admin`; `league_organizer` whose `league_id` == the match's league |
| `POST /api/v1/roster/transfer` | `/audit/v1/roster/transfer` | `super_admin`; `club_manager` whose club owns `from_squad_id` (or `to_squad_id` for a loan return) |
| `POST /api/v1/checkout` | `/audit/v1/checkout` | any logged-in role (server sets nothing extra; app sends `customer_id` = `user_id`) |
| `POST /api/v1/offline-sync` | `/audit/v1/offline-sync` | any logged-in role; **each action** is authorized like its single twin — a forbidden action → `status:"rejected"`, `resolution:"server_wins"`, `error_code:"FORBIDDEN"` |

### 2.12 `GET /api/v1/ping` → spec §5.13 (`{"pong":true}`, rate-limit probe).

### 2.13 `POST /api/v1/dev/demo-seed` (no auth, dev only)
Adds the demo data from `plans/09-app-api-demo-realtime.md` on top of the baseline. Idempotent. Also run automatically at startup. Response 200 `{"status":"demo_seeded"}`. **Never called by `/audit/v1/reset`** (reset must equal the spec baseline exactly).

### 2.14 WebSocket `GET /ws/matches/{match_id}` (no auth)
Server → client JSON messages only:
- `{"type":"match_updated","match_id":"demo-m1","version":8}` — after any event append (incl. compensation, offline-sync).
- `{"type":"showcase_updated","match_id":"demo-m1"}` — after a pin.
The app re-fetches `/audit/v1/score/{match_id}` or the showcase on each message. Messages from the client are ignored.

---

## 3. Seeded demo users (spec §8.3) — the app's Login screen shows these as quick-fill chips

| Role | Email | Password | user_id |
|---|---|---|---|
| super_admin | admin@nascon.test | Nascon@26 | user-admin |
| league_organizer | organizer@nascon.test | Nascon@26 | user-organizer |
| club_manager | manager@nascon.test | Nascon@26 | user-manager |
| player | player@nascon.test | Nascon@26 | user-player |
| viewer | viewer@nascon.test | Nascon@26 | user-viewer |

---

## CHANGELOG (append only — every change must be told to Talha in chat first)
- v1 (11:20 Day 1) — initial contract.
