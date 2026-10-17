# AppDev-Nascon — Multi-Sport League & Club Operations Platform (NaSCon'26 Part I)

## Run the backend
```bash
cp .env.example .env            # optional; set your DAY1_SALT
DAY1_SALT=<your-salt> docker compose up -d --build
curl http://localhost:8080/health   # {"status":"ok"}
```
API on port **8080**. Interactive docs: `http://localhost:8080/docs`.

## Run the tests
```bash
./run_tests.sh      # runs pytest with coverage and writes COVERAGE.json
```

## Mobile app
- APK: `mobile/release/app-release.apk` (Android 10+).
- Settings screen → server address: emulator `http://10.0.2.2:8080`, phone `http://<laptop-LAN-IP>:8080`.

## Demo accounts (password for all: `Nascon@26`)
| Role | Email |
|---|---|
| Platform Super-Admin | admin@nascon.test |
| League Organizer (league-alpha-1) | organizer@nascon.test |
| Club Manager (club-alpha-1) | manager@nascon.test |
| Player (player-alpha-1) | player@nascon.test |
| General Viewer | viewer@nascon.test |

## Repo map
`backend/` FastAPI service · `mobile/` React Native (Expo) app · `tests/` backend tests · `contracts/API.md` app ↔ backend contract · `plans/` implementation plans · `TRACEABILITY.md` requirement → code → tests.
