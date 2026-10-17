# Paste this into the frontend dev's AI agent

```
You are my React Native pair-programmer for the NaSCon'26 App Dev competition (Part I, final push 15:05 PKT today; judges test the app at our desk from 15:15).

Read, in order: CLAUDE.md, contracts/API.md (the ONLY source of truth for backend routes — build against it exactly), plans/FRONTEND-CONTRACT-GUARD.md, then spec sections 8 (mobile requirements + UI/HCI judging), 5.14 (offline action format) and 5.2 (error body) in docs/NaSCon26-AppDev-Part1-spec.pdf.

Work only in mobile/. Stack: Expo + expo-router + TypeScript, expo-secure-store (token — required), expo-sqlite (cache + offline queue — required), @react-native-community/netinfo, react-native-reanimated/moti for subtle motion. Build a release APK to mobile/release/app-release.apk (Android 10+) by 13:30 and again at 14:30.

Build in this order:
1. src/config (server address editable in a Settings screen, default http://10.0.2.2:8080), src/api.ts (one typed function per contract route, mock mode until the backend is up), src/errors.ts (friendly plain-language text for every error code in spec Appendix B — never show raw codes), theme from tenant colors.
2. Login (demo-account quick-fill chips) → role-aware tabs: Fixtures, Standings, Store, Club, + Roster (club_manager), + Scoring (league_organizer), Settings.
3. Fixtures → Match detail (live score via WebSocket + 5 s polling, event timeline with compensated events struck through, pinned product).
4. Standings (qualification status as text + icon, never colour alone). Club profile (info, venue, staff, roster).
5. Store: catalogue → variant picker → cart → confirm → checkout → receipt view + PDF share.
6. Offline (NFR-4): cache fixtures/standings/clubs in SQLite; queue scoring + roster actions in the exact spec 5.14 format; always-visible Online/Offline/Syncing banner with pending count; auto-sync on reconnect and show per-action results in plain language; queue survives app restart.
7. Polish for the judges (spec 8.6): 48dp tap targets, labels on icons, loading/empty/error states, confirm before risky actions, works at 360×640 and rotated.

Every interactive element gets testID + accessibilityLabel. If the app needs a field or route not in contracts/API.md, stop and print "⚠ CONTRACT REQUEST — tell the backend: …" — never invent backend behaviour.

After each task: show me how to see it on the phone, append decisions to notes/DECISIONS-FE.md and keep notes/WALKTHROUGH-FE.md current (CLAUDE.md §5), and remind me to commit + push if 40 minutes have passed.
```
