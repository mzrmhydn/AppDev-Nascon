# Backend test guide — step by step (for the other laptop)

This guide checks that the backend works **exactly the way the grader will run it**, and that every graded
backend feature gives the right answers. Do the steps **in order**. Don't skip any.

- Total time: about **30–40 minutes** (the first Docker build is the slowest part).
- You type every command in a **terminal**:
  - **Windows:** press the Windows key, type `PowerShell`, press Enter. Commands marked **(PowerShell)** are for this.
  - **Ubuntu / Linux / Mac:** open "Terminal". Commands marked **(Linux)** are for this.
  - A command with no mark works in both.
- Copy one command at a time. Paste it, press Enter, and **wait** until the prompt (`PS C:\...>` or `$`) comes back.
- When a step says "you should see", compare carefully. If you see something else, go to
  [Section 12 — If something goes wrong](#12-if-something-goes-wrong).

> **The one rule:** never type the real salt into a file that gets committed (any file except `.env`).
> The salt only goes into the terminal command, or into a file named exactly `.env`, which git ignores.

---

## 0. What the grader does (so you know why each step exists)

1. It clones our GitHub repo at the **last commit pushed before 15:05:00**.
2. In the repo folder it runs: `DAY1_SALT=<our salt> docker compose up -d --build`. This must finish in **under 10 minutes**.
3. It calls `GET http://localhost:8080/health` every 2 seconds. It must get `200 {"status":"ok"}` within **120 seconds**.
4. It calls `POST /audit/v1/reset` and then sends hundreds of test requests ("vectors") to `/audit/v1/...`.
   Each vector passes only if **everything** matches the spec exactly: status code, error code, every field and signature.
5. If the stack does not start (after one retry), we lose **10 points**.

Our checker script (`tests/verify_backend.py`) does step 4 itself: about **300 checks** across all graded areas.

---

## 1. Check that the tools are installed

Run each command below. You should see a version number (any recent version is fine).

```
docker --version
```
You should see something like `Docker version 27.x.x`. If you see "not recognized" or "command not found", install Docker:
- **Windows:** download **Docker Desktop** from https://www.docker.com/products/docker-desktop/, install it,
  **restart the laptop**, then open Docker Desktop and wait until it says **"Engine running"** (green, bottom left).
- **Ubuntu:** `sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2`, then
  `sudo usermod -aG docker $USER`, then **log out and log back in**.

```
docker compose version
```
You should see `Docker Compose version v2.x.x`. (It must be `docker compose` with a space, not `docker-compose`.)

```
git --version
```
You should see `git version 2.x`. If it's missing on Windows, install from https://git-scm.com/download/win
(keep all default options; this also installs **Git Bash**, which you need in step 8).

Check Python. Windows **(PowerShell)**:
```
py --version
```
Linux:
```
python3 --version
```
You should see `Python 3.10` or newer. If it's missing on Windows, install from https://www.python.org/downloads/ and
**tick "Add python.exe to PATH"** on the first installer screen.

**Windows only:** Docker Desktop must be **running** (whale icon in the taskbar, "Engine running") before any
`docker` command works. Check it:
```
docker info
```
You should see many lines of information. If you see `error during connect` or `Cannot connect to the Docker daemon`, start Docker Desktop and wait 1 minute.

---

## 2. Get the latest code

Go to a folder where you keep projects, e.g. **(PowerShell)** `cd $HOME\Desktop` or **(Linux)** `cd ~/Desktop`.

**First time on this laptop:**
```
git clone https://github.com/mzrmhydn/AppDev-Nascon.git
cd AppDev-Nascon
```

**If the folder already exists:**
```
cd AppDev-Nascon
git pull
```

Check that you have the newest commit:
```
git log --oneline -3
```
The top line must match the newest commit on GitHub (open https://github.com/mzrmhydn/AppDev-Nascon/commits/main
in a browser). If it doesn't, run `git pull` again.

**Windows only, once per clone.** This stops Windows from changing line endings in shell scripts:
```
git config core.autocrlf false
```

> From now on, **every command is typed inside the `AppDev-Nascon` folder**. Check with `pwd`: the path must end with `AppDev-Nascon`.

---

## 3. Pick the salt

The salt is the secret on our team slip (`DAY1_SALT`). The backend uses it to sign score events and receipts.
The checker needs **the same salt** so it can recompute the signatures and compare them.

- For testing you can use the real salt or a test value such as `demo-salt`. **Use the same value in step 4 and step 6.**
- Below, replace `YOUR_SALT` with your chosen value.

---

## 4. Start the backend exactly like the grader does

First, make sure nothing old is running (it's fine if this prints "no resources" or nothing):
```
docker compose down -v
```

Start a stopwatch (phone timer) now. This step must take under 10 minutes.

**(Linux / Mac / Git Bash):**
```
DAY1_SALT=YOUR_SALT docker compose up -d --build
```
**(PowerShell):**
```
$env:DAY1_SALT="YOUR_SALT"; docker compose up -d --build
```

What you'll see: a lot of build output (downloading images, `pip install ...`). At the end:
```
 ✔ Container appdev-nascon-db-1     Healthy
 ✔ Container appdev-nascon-redis-1  Healthy
 ✔ Container appdev-nascon-api-1    Started
```
(The names may differ slightly. "Started" / "Healthy" is what matters.)

Write down the stopwatch time: **______ minutes**. Must be **< 10**. The first build is the slowest; on a normal
connection it takes 2–5 minutes.

Check that all 3 containers are running:
```
docker compose ps
```
You should see 3 lines (`api`, `db`, `redis`), each with `STATUS` "Up" (db and redis also say "(healthy)").

---

## 5. Health check (must be OK within 120 seconds)

Open a browser and go to: **http://localhost:8080/health**

You should see exactly:
```
{"status":"ok"}
```
If the page doesn't load, wait 20 seconds and refresh. If it still fails after **2 minutes**, go to Section 12.

Also open **http://localhost:8080/docs**. You should see a page titled "NaSCon'26 League Platform" listing every endpoint.
You'll use this page in step 9.

Terminal alternative: **(Linux)** `curl http://localhost:8080/health`, **(PowerShell)** `curl.exe http://localhost:8080/health`.

---

## 6. Run the automatic checker (the most important step)

The checker sends about 300 requests that copy the grader's tests and compares every answer with the spec.
It uses only built-in Python, so there's nothing to install.

**(PowerShell):**
```
py tests\verify_backend.py --salt YOUR_SALT
```
**(Linux / Mac):**
```
python3 tests/verify_backend.py --salt YOUR_SALT
```

It takes about **1–2 minutes**. It deliberately waits 22 seconds during the rate-limit test, so don't stop it.
Every line shows `PASS` or `FAIL`. At the end it prints a summary like:
```
================ SUMMARY ================
  setup       17 /  17 passed
  scoring     61 /  61 passed
  fixtures    63 /  63 passed
  standings   29 /  29 passed
  roster      31 /  31 passed
  store       27 /  27 passed
  rbac        11 /  11 passed
  offline     18 /  18 passed

ALL CHECKS PASSED
```
(Your numbers can be a little different if the script was updated. What matters is that each line reads `X / X`
and the last line says **ALL CHECKS PASSED**.)

What each area means (and how many points it is worth):

| Checker area | Graded area in the spec (§9.1) | Spec section |
|---|---|---|
| `setup` | health, reset, baseline data, demo accounts (needed by every area) | §5.4, §5.5, §8.3 |
| `scoring` | Event-sourced scoring engine + mystery sport (6 pts) | §5.6, §5.9 |
| `fixtures` | Round robin, Swiss, single elim, double elim (6 pts) | §5.7 |
| `standings` | Standings: 3-way H2H, differentials, clinched/eliminated (6 pts) | §5.8, §5.10 |
| `roster` | Roster, transfer window, loans, audit trail (6 pts) | §5.11 |
| `store` | Store: 20 simultaneous buyers, PDF receipt (6 pts) | §5.12 |
| `rbac` | RBAC 5-role matrix, tenant isolation, security probes (6 pts) | §5.13 |
| `offline` | Offline sync script part (part of the 4 offline pts) | §5.14 |

**If everything says PASS:** go to step 7.

**If something FAILS:**
1. Run it again once. A slow laptop can make a timing check fail.
2. Still failing? Copy the **whole output** (from "SUMMARY" to the end) and send it to the backend person / AI agent.
   Every FAIL line also shows `-> expected ..., got ...`, which says exactly what went wrong.
3. To re-check just one area after a fix: `py tests\verify_backend.py --salt YOUR_SALT --only store`
   (areas: `scoring,fixtures,standings,roster,store,rbac,offline`; several are allowed, separated by commas).

The checker also saves the receipt PDF it got as `receipt_check.pdf` in the current folder.
**Open it** (double-click). It must show the order id `ord-1` and the total `PKR 9000.00`.

> The checker resets the database at the start and at the end, so the backend is left in the clean baseline state.

---

## 7. Restart test (the data must come back by itself)

```
docker compose restart api
```
Wait 15 seconds, then open http://localhost:8080/health again. You should see `{"status":"ok"}`.

Run the checker again for one area (the `setup` checks — health, reset, demo logins — always run first):
```
py tests\verify_backend.py --salt YOUR_SALT --only scoring
```
(Linux: `python3 tests/verify_backend.py --salt YOUR_SALT --only scoring`.) All lines must PASS.

---

## 8. Unit tests + the coverage file (worth 10% of each area)

The grader reads `COVERAGE.json`. Judges may run `./run_tests.sh`. If the real number is **more than 2 points lower**
than the number in the file, we lose that area's bonus. So we regenerate the file from a real run.

`run_tests.sh` is a bash script:
- **Windows:** open **Git Bash** (Start menu → "Git Bash"), then `cd` to the folder,
  e.g. `cd ~/Desktop/AppDev-Nascon`.
- **Linux / Mac:** use the normal terminal.

Run:
```
DAY1_SALT=YOUR_SALT ./run_tests.sh
```
It takes 1–3 minutes. You should see pytest output ending with something like `231 passed`. The last line prints the
new `COVERAGE.json`, e.g.:
```
{"fixtures": 97.2, "scoring": 93.0, "standings": 97.0, "store": 97.1, "roster": 94.0, "rbac": 97.5}
```
**Every number must be ≥ 85.**

If the script says `Permission denied`, run `bash run_tests.sh` instead. If it says `bash\r: No such file or directory`,
see Section 12 (line endings).

Now check whether the file changed:
```
git status
```
- If `COVERAGE.json` is **not** listed, the committed numbers are already correct. Nothing to do.
- If `COVERAGE.json` **is** listed as modified, commit and push it (step 11), so GitHub has the real figures.

---

## 9. Manual checks in the browser (to see it with your own eyes)

The checker already tests all of this; this step is so **you understand** what the grader sees (useful for the viva).
Use **http://localhost:8080/docs**. For each endpoint: click it → **"Try it out"** → paste the JSON body →
**"Execute"** → scroll to **"Server response"** and look at **Code** and **Response body**.

Start every session with a reset: `POST /audit/v1/reset`, body `{}` → Code **200**, body contains `"status": "reset_complete"`.

### 9.1 Mystery sport + scoring (scoring area)
1. `POST /audit/v1/sports` with:
   ```json
   {"sport_id":"kabaddi","name":"Kabaddi","scoring_model":"event","periods":{"count":2,"duration_minutes":20},
    "scoring_events":{"raid_point":{"points":1},"all_out":{"points":2}},"draw_allowed":false,
    "overtime":{"policy":"golden_score","duration_minutes":5},
    "roster":{"min_squad_size":7,"max_squad_size":12,"required_positions":{"raider":2}}}
   ```
   → **201**, `"status": "created"`. Send it again → **409** `SPORT_EXISTS`.
2. `POST /audit/v1/events` four times, one body each:
   ```json
   {"event_id":"e1","match_id":"m1","type":"match_init","payload":{"sport_id":"kabaddi","home_team_id":"t1","away_team_id":"t2"}}
   {"event_id":"e2","match_id":"m1","type":"match_start","payload":{}}
   {"event_id":"e3","match_id":"m1","type":"score","payload":{"team_id":"t1","event_type":"all_out"}}
   {"event_id":"e4","match_id":"m1","type":"match_end","payload":{}}
   ```
   Each → **201** with `sequence` 1, 2, 3, 4 and a 64-character `signature`.
3. `GET /audit/v1/score/{match_id}` with `m1` → `"outcome": "home_win"`, home `"score": 2`.
4. Correction: `POST /audit/v1/events`
   `{"event_id":"e5","match_id":"m1","type":"compensation","payload":{"compensates":"e3","reason":"review"}}` → **201**.
   Score again → home score **0**, `"outcome": "undecided"` (level, draws not allowed). Event `e3` is still listed, with `"compensated": true`.
5. Send `e3` again with a different body, e.g. type `match_start` → **409** `DUPLICATE_EVENT_ID`.

### 9.2 Fixtures (fixtures area)
`POST /audit/v1/fixtures`:
```json
{"format":"single_elim","teams":["t1","t2","t3","t4","t5","t6"],"params":{}}
```
→ **200**, `"bracket_size": 8`. Match `R1M1` has `"bye": true` and winner `t1`. Match `R1M2` is `t4` vs `t5`.
Also try `"format":"round_robin"` with 5 teams (every round has 1 team in `byes`), `"format":"double_elim"`, and
`"format":"swiss"` (round 1 pairs t1–t3 and t2–t4, with bye t5).

### 9.3 Standings (standings area)
`POST /audit/v1/leagues`:
```json
{"league_id":"lg-1","sport_id":"football","teams":["t1","t2","t3"],"fixtures":[],"qualification":{"spots":1}}
```
→ **201**. `GET /audit/v1/standings/{league_id}` with `lg-1` → order **t1, t3, t2** (drawing of lots with seed 42,
exactly as spec Appendix A vector 2). `resolved_by` is `"draw_lots"`.

### 9.4 Roster (roster area)
`POST /audit/v1/roster/setup` with the example from spec §5.11 (league `lg-r1`, squads `sq-a`, `sq-b`) → **201**
`"status":"configured"`. Then `POST /audit/v1/roster/transfer` with the spec example (`tr-001`, player `p2`,
sq-a → sq-b, `2026-09-30`). Because `sq-a` is in the in-progress match `m-live`, you get **201** with
`"state": "deferred_until_match_end"` and `"blocking_match_id": "m-live"`. (This is hidden edge case 6.)

### 9.5 Store (store area)
`POST /audit/v1/checkout`:
```json
{"order_id":"ord-001","customer_id":"cust-001","items":[{"variant_id":"var-jersey-001-M","quantity":1}],
 "discount_code":null,"payment":{"token":"tok_success"}}
```
→ **201**, `"total_minor": 450000`, and a `receipt` with `signature` and `pdf_base64`. Same request again → **200**
(same answer, no second purchase). A new order id for the same variant → **409** `OUT_OF_STOCK` (stock was 1).
`GET /audit/v1/inventory/{variant_id}` with `var-jersey-001-M` → `"stock": 0, "reserved": 0`.

### 9.6 RBAC (rbac area)
`POST /audit/v1/rbac-matrix` → 5 tokens. Copy the `viewer` token. At the top of the docs page click **"Authorize"**
(if shown), or test the probe with curl:
**(Linux)** `curl -i -H "Authorization: Bearer PASTE_TOKEN" http://localhost:8080/audit/v1/rbac/platform/config`
**(PowerShell)** `curl.exe -i -H "Authorization: Bearer PASTE_TOKEN" http://localhost:8080/audit/v1/rbac/platform/config`
→ viewer: **403** `FORBIDDEN`. With the `super_admin` token → **200** `{"authorized":true}`. With no token → **401**.

---

## 10. Fresh-clone test (exactly the grader's situation; protects the −10 penalty)

This proves nothing on this laptop is "secretly" making it work: no old volumes, no local files, no `.env`.

```
docker compose down -v
cd ..
git clone https://github.com/mzrmhydn/AppDev-Nascon.git fresh-check
cd fresh-check
```
Then the grader's exact command, with the stopwatch running:

**(Linux / Git Bash):** `DAY1_SALT=YOUR_SALT docker compose up -d --build`
**(PowerShell):** `$env:DAY1_SALT="YOUR_SALT"; docker compose up -d --build`

- Must finish in **< 10 minutes**.
- http://localhost:8080/health must show `{"status":"ok"}` within **120 seconds** after the command returns.
- Then run the checker from this folder: `py tests\verify_backend.py --salt YOUR_SALT` → **ALL CHECKS PASSED**.

When done:
```
docker compose down -v
cd ..
```
You can delete the `fresh-check` folder. Go back to the normal folder (`cd AppDev-Nascon`) and start the stack again
(step 4) if you need it running for the judges.

---

## 11. Final repository checks before 15:05

1. Required files are committed. This must print each one:
   **(Linux / Git Bash)** `git ls-files docker-compose.yml .env.example README.md TRACEABILITY.md run_tests.sh COVERAGE.json mobile/release/app-release.apk`
   If one is missing, tell the team (the APK belongs to the frontend person).
2. The salt is **not** in git:
   `git ls-files | grep -i "\.env"` → must show **only** `.env.example`.
   `git grep -n "YOUR_REAL_SALT"` (type the real salt) → must print **nothing**.
3. Everything is pushed:
   ```
   git status
   git log origin/main --oneline -1
   ```
   `git status` must say `Your branch is up to date with 'origin/main'` and `nothing to commit` (except files you meant
   to leave). To commit and push a changed file (for example `COVERAGE.json`):
   ```
   git add COVERAGE.json
   git commit -m "[BE] real coverage figures"
   git pull --rebase
   git push origin main
   ```
4. The repo is public: open https://github.com/mzrmhydn/AppDev-Nascon in a **private / incognito** window.
   You must see the code without logging in.
5. The last push must be **before 15:05:00**. Anything later is ignored by the grader.

---

## 12. If something goes wrong

| What you see | What it means / what to do |
|---|---|
| `docker: command not found` / "not recognized" | Docker isn't installed or the terminal is older than the install. Install (step 1), then close and reopen the terminal. |
| `error during connect` / `Cannot connect to the Docker daemon` | Docker Desktop isn't running. Start it, wait until "Engine running". |
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Something else uses port 8080 (an old stack or another app). Run `docker ps`; if an old container shows `8080`, run `docker stop <its id>`. Then repeat step 4. |
| Build fails while downloading (`pip`, `pull access denied`, timeout) | Internet problem. Check the Wi-Fi and run the step 4 command again. |
| `/health` doesn't load or shows 503 | See what the API says: `docker compose logs api --tail 80`. Send the output to the backend person. Often `docker compose down -v` then step 4 again fixes it. |
| `bash\r: No such file or directory` when running `run_tests.sh` | Windows changed the line endings. Run `git config core.autocrlf false`, then `git rm --cached -r . -q` and `git reset --hard`, then try again. |
| `./run_tests.sh: Permission denied` | Run `bash run_tests.sh` instead. |
| Checker: `<no response: ... Connection refused>` | The backend isn't running, or it runs on another port. Do step 4 / step 5 first. |
| Checker: only signature checks fail | The `--salt` value doesn't match the salt used in `docker compose up`. Restart with the same value (step 4). |
| Checker: the burst test fails (more than one 201) | Real concurrency bug in checkout. Send the output to the backend person immediately; this is 6 points. |
| Anything else | Copy the full command and its full output, and send them to the backend person / AI agent. |

Useful commands:
- See the API logs live: `docker compose logs -f api` (stop watching with Ctrl+C; the API keeps running).
- Stop everything, keep data: `docker compose down`
- Stop everything and wipe the database (clean start): `docker compose down -v`

---

## 13. For the judges' desk (15:15) — backend side

1. Start the stack (step 4) and check `/health` (step 5) **before** the judges arrive.
2. Connect the laptop and the phone to the **same hotspot / Wi-Fi**.
3. Find the laptop's IP address: **(PowerShell)** `ipconfig` → "IPv4 Address" under the Wi-Fi adapter
   (e.g. `192.168.43.120`). **(Linux)** `hostname -I`.
4. On the **phone's browser**, open `http://<that IP>:8080/health` → `{"status":"ok"}`.
   If it doesn't load on Windows, allow port 8080 through the firewall. Run once in an **Administrator** PowerShell:
   `New-NetFirewallRule -DisplayName "NaSCon 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow`
5. In the app's settings screen, set the server address to `http://<that IP>:8080`.
6. Demo accounts (password for all: `Nascon@26`): `admin@`, `organizer@`, `manager@`, `player@`, `viewer@nascon.test`.

---

## What this guide does NOT cover
- The grader's hidden vectors are different from ours. Our checker covers every rule and error code in the spec,
  but passing it doesn't guarantee 100%.
- The mobile app screens, offline desk check and UI/HCI are checked on the phone by the judges (frontend guide).
- WebSocket live updates are not tested by the script. They're tested by the app (match detail screen updates by itself).
