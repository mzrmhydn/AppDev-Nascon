# End-to-end checker for a RUNNING backend: calls every graded /audit/v1 route like the grader would
# and compares against the spec (status codes, error codes, fields, signatures). Python stdlib only.
#
#   python tests/verify_backend.py --salt <the DAY1_SALT you started docker with>
#   python tests/verify_backend.py --salt demo-salt --base http://localhost:8080 --only scoring,fixtures
#
# Prints PASS / FAIL per check and a summary per area. Exit code 0 = everything passed.
import argparse
import base64
import hashlib
import hmac
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import zlib
from itertools import combinations

AREAS = ["setup", "scoring", "fixtures", "standings", "roster", "store", "rbac", "offline"]
RESULTS = []          # (area, name, ok, detail)
CURRENT = {"area": "setup"}
ARGS = None


# ---------------------------------------------------------------- helpers

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(id_, payload):
    msg = (id_ + "|" + canonical(payload)).encode("utf-8")
    return hmac.new(ARGS.salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def call(method, path, body=None, token=None, raw=None, timeout=30):
    """Return (status, parsed_json_or_text, headers)."""
    url = ARGS.base.rstrip("/") + path
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, text, headers = resp.status, resp.read().decode("utf-8", "replace"), resp.headers
    except urllib.error.HTTPError as err:
        try:
            text = err.read().decode("utf-8", "replace")
        except Exception as read_err:  # server closed the connection while we were still reading
            text = f"<body unreadable: {read_err}>"
        status, headers = err.code, err.headers
    except Exception as err:  # connection refused, timeout ...
        return 0, f"<no response: {err}>", {}
    try:
        return status, json.loads(text), headers
    except ValueError:
        return status, text, headers


def check(name, ok, detail=""):
    RESULTS.append((CURRENT["area"], name, bool(ok), detail))
    mark = "PASS" if ok else "FAIL"
    line = f"  {mark}  {name}"
    if not ok and detail:
        line += f"\n        -> {detail}"
    print(line)
    return ok


def short(x, n=300):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + " ..."


def expect(name, resp, status, code=None, fields=None):
    """Check status (and error code / details.fields subset) of a response from call()."""
    got_status, body, _ = resp
    ok = got_status == status
    if ok and code is not None:
        ok = isinstance(body, dict) and isinstance(body.get("error"), dict) and body["error"].get("code") == code
        if ok:
            ok = isinstance(body["error"].get("details"), dict) and isinstance(body["error"].get("message"), str)
    if ok and fields:
        got = body["error"]["details"].get("fields", [])
        ok = all(f in got for f in fields)
    want = f"{status}" + (f" {code}" if code else "") + (f" fields {fields}" if fields else "")
    return check(name, ok, f"expected {want}, got {got_status} {short(body)}")


def section(area, title):
    CURRENT["area"] = area
    print(f"\n=== [{area}] {title}")


def reset(seed=None, stock=None):
    body = {}
    if seed is not None:
        body["seed"] = seed
    if stock is not None:
        body["stock"] = stock
    return call("POST", "/audit/v1/reset", body)


def ev(event_id, match_id, etype, payload):
    return {"event_id": event_id, "match_id": match_id, "type": etype, "payload": payload}


def post_event(event_id, match_id, etype, payload):
    return call("POST", "/audit/v1/events", ev(event_id, match_id, etype, payload))


def score(match_id):
    return call("GET", f"/audit/v1/score/{match_id}")


# ---------------------------------------------------------------- setup / health / reset

def test_setup():
    section("setup", "health, reset, baseline")
    s, body, _ = call("GET", "/health")
    if not check("GET /health -> 200 {status: ok}", s == 200 and body == {"status": "ok"}, f"got {s} {short(body)}"):
        print("\n  The backend is not reachable / not healthy. Start it first (see the guide). Stopping.")
        return False
    t0 = time.time()
    s, body, _ = reset()
    took = time.time() - t0
    expected = {"status": "reset_complete", "seed": 42, "sports": ["football", "basketball", "cricket", "esports"],
                "tenants": ["tenant-alpha", "tenant-beta"],
                "stock": {"var-jersey-001-M": 1, "var-jersey-001-L": 5}}
    check("POST /audit/v1/reset (no body) -> exact spec response", s == 200 and body == expected,
          f"got {s} {short(body)}")
    check("reset finishes in < 10 s", took < 10, f"took {took:.1f} s")
    s, body, _ = reset(seed=7, stock={"var-jersey-001-M": 3, "var-jersey-001-L": 0})
    check("reset with seed 7 + custom stock echoes them", s == 200 and body.get("seed") == 7 and
          body.get("stock") == {"var-jersey-001-M": 3, "var-jersey-001-L": 0}, f"got {s} {short(body)}")
    s, inv, _ = call("GET", "/audit/v1/inventory/var-jersey-001-M")
    check("custom stock really applied (inventory M = 3)", s == 200 and inv.get("stock") == 3, f"got {s} {short(inv)}")
    expect("reset with seed \"x\" -> 400 VALIDATION_ERROR", reset(seed="x"), 400, "VALIDATION_ERROR")
    expect("reset with negative stock -> 400 VALIDATION_ERROR",
           reset(stock={"var-jersey-001-M": -1}), 400, "VALIDATION_ERROR")
    a = reset()[1]
    b = reset()[1]
    check("reset twice gives identical responses", a == b == expected, f"{short(a)} vs {short(b)}")
    s, body, _ = call("POST", "/audit/v1/reset", raw=b"")
    check("reset with empty body works", s == 200, f"got {s} {short(body)}")
    s, body, _ = call("POST", "/audit/v1/sports", raw=b"{not json")
    expect("malformed JSON -> 400 VALIDATION_ERROR", (s, body, {}), 400, "VALIDATION_ERROR")
    s, body, _ = call("GET", "/no/such/route")
    check("unknown route -> error body shape {error:{code,message,details}}",
          s == 404 and isinstance(body, dict) and "error" in body, f"got {s} {short(body)}")
    # demo accounts must exist after reset
    for email in ["admin@nascon.test", "organizer@nascon.test", "manager@nascon.test",
                  "player@nascon.test", "viewer@nascon.test"]:
        s, body, _ = call("POST", "/api/v1/auth/login", {"email": email, "password": "Nascon@26"})
        check(f"demo login {email} works", s == 200, f"got {s} {short(body)}")
    s, body, _ = call("POST", "/api/v1/auth/login", {"email": "admin@nascon.test", "password": "wrong"})
    check("login with wrong password is refused (401)", s == 401, f"got {s} {short(body)}")
    return True


# ---------------------------------------------------------------- scoring (sports + events + score)

KABADDI = {
    "sport_id": "kabaddi", "name": "Kabaddi", "scoring_model": "event",
    "periods": {"count": 2, "duration_minutes": 20},
    "scoring_events": {"raid_point": {"points": 1}, "tackle_point": {"points": 1}, "all_out": {"points": 2}},
    "draw_allowed": False, "overtime": {"policy": "golden_score", "duration_minutes": 5},
    "tie_break_order": ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"],
    "roster": {"min_squad_size": 7, "max_squad_size": 12, "required_positions": {"raider": 2, "defender": 3}},
}
TINY_INNINGS = {
    "sport_id": "mini_cricket", "name": "Mini Cricket", "scoring_model": "innings",
    "periods": {"innings_per_team": 1, "overs_per_innings": 2, "balls_per_over": 6, "wickets_per_innings": 2},
    "scoring_events": {"super_six": {"runs": 6, "legal_ball": True, "wicket": False},
                       "one": {"runs": 1, "legal_ball": True, "wicket": False},
                       "bye_run": {"runs": 1, "legal_ball": False, "wicket": False},
                       "out": {"runs": 0, "legal_ball": True, "wicket": True}},
    "draw_allowed": True, "overtime": {"policy": "super_over"},
    "roster": {"min_squad_size": 5, "max_squad_size": 11, "required_positions": {}},
}
BO5 = {
    "sport_id": "chess_bo5", "name": "Chess BO5", "scoring_model": "round",
    "periods": {"best_of": 5}, "scoring_events": {"map_win": {"rounds": 1}},
    "draw_allowed": False, "overtime": {"policy": "none"},
    "roster": {"min_squad_size": 1, "max_squad_size": 3, "required_positions": {}},
}


def check_event_ok(name, resp, event_id, match_id, etype, payload, seq, status=201):
    s, body, _ = resp
    expected = {"event_id": event_id, "match_id": match_id, "type": etype, "sequence": seq, "match_version": seq}
    ok = s == status and isinstance(body, dict) and all(body.get(k) == v for k, v in expected.items())
    ok = ok and set(body) == set(expected) | {"signature"}
    if ok and ARGS.salt:
        ok = body.get("signature") == sign(event_id, payload)
    return check(name, ok, f"expected {status} {expected} + correct signature, got {s} {short(body)}")


def test_scoring():
    section("scoring", "mystery sport, events, compensation, score projection")
    reset()
    s, body, _ = call("POST", "/audit/v1/sports", KABADDI)
    ok = s == 201 and body.get("sport_id") == "kabaddi" and body.get("status") == "created" \
        and isinstance(body.get("config"), dict) and body["config"].get("tie_break_order", [None])[-1] == "draw_lots"
    check("create mystery sport kabaddi -> 201 {sport_id, status:created, config}", ok, f"got {s} {short(body)}")
    expect("same sport again -> 409 SPORT_EXISTS", call("POST", "/audit/v1/sports", KABADDI), 409, "SPORT_EXISTS")
    expect("seed sport football again -> 409 SPORT_EXISTS",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="football")), 409, "SPORT_EXISTS")
    no_tb = dict(KABADDI, sport_id="kabaddi_two")
    del no_tb["tie_break_order"]
    s, body, _ = call("POST", "/audit/v1/sports", no_tb)
    check("tie_break_order omitted -> default full list ending with draw_lots",
          s == 201 and body["config"]["tie_break_order"] == ["h2h_points", "h2h_diff", "overall_diff",
                                                             "scored", "fair_play", "draw_lots"], f"got {s} {short(body)}")
    expect("bad sport_id 'Bad Id' -> 400 with fields [sport_id]",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="Bad Id")), 400, "VALIDATION_ERROR", ["sport_id"])
    expect("SQL-injection sport_id -> 400 VALIDATION_ERROR (never 5xx)",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="x'; DROP TABLE sports;--")), 400,
           "VALIDATION_ERROR", ["sport_id"])
    expect("periods.count \"2\" (string) -> 400 fields [periods]",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="k3", periods={"count": "2", "duration_minutes": 20})),
           400, "VALIDATION_ERROR", ["periods"])
    expect("round model best_of 4 (even) -> 400 fields [periods]",
           call("POST", "/audit/v1/sports", dict(BO5, sport_id="bo4", periods={"best_of": 4})),
           400, "VALIDATION_ERROR", ["periods"])
    expect("empty scoring_events -> 400 fields [scoring_events]",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="k4", scoring_events={})),
           400, "VALIDATION_ERROR", ["scoring_events"])
    expect("roster min > max -> 400 fields [roster]",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="k5", roster={"min_squad_size": 9, "max_squad_size": 2,
                                                                               "required_positions": {}})),
           400, "VALIDATION_ERROR", ["roster"])
    expect("overtime policy 'penalties' -> 400 fields [overtime]",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="k6", overtime={"policy": "penalties"})),
           400, "VALIDATION_ERROR", ["overtime"])
    expect("draw_allowed 0 (not a boolean) -> 400 fields [draw_allowed]",
           call("POST", "/audit/v1/sports", dict(KABADDI, sport_id="k7", draw_allowed=0)),
           400, "VALIDATION_ERROR", ["draw_allowed"])
    expect("empty body {} -> 400 listing all required fields", call("POST", "/audit/v1/sports", {}), 400,
           "VALIDATION_ERROR", ["sport_id", "name", "scoring_model", "periods", "scoring_events", "draw_allowed",
                                "overtime", "roster"])
    check("create innings mystery sport -> 201", call("POST", "/audit/v1/sports", TINY_INNINGS)[0] == 201)
    check("create round mystery sport (best of 5) -> 201", call("POST", "/audit/v1/sports", BO5)[0] == 201)

    # --- event stream of a stand-alone kabaddi match
    init = {"sport_id": "kabaddi", "home_team_id": "t1", "away_team_id": "t2"}
    check_event_ok("match_init -> 201 seq 1 + signature", post_event("k-1", "km1", "match_init", init),
                   "k-1", "km1", "match_init", init, 1)
    check_event_ok("same request again -> 200 identical (idempotent replay)",
                   post_event("k-1", "km1", "match_init", init), "k-1", "km1", "match_init", init, 1, status=200)
    expect("same event_id, different body -> 409 DUPLICATE_EVENT_ID",
           post_event("k-1", "km1", "match_start", {}), 409, "DUPLICATE_EVENT_ID")
    expect("match_init for existing match -> 409 MATCH_EXISTS",
           post_event("k-x", "km1", "match_init", init), 409, "MATCH_EXISTS")
    expect("match_init unknown sport -> 404 SPORT_NOT_FOUND",
           post_event("k-y", "km9", "match_init", dict(init, sport_id="nosuch")), 404, "SPORT_NOT_FOUND")
    expect("event for unknown match -> 404 MATCH_NOT_FOUND",
           post_event("k-z", "nomatch", "match_start", {}), 404, "MATCH_NOT_FOUND")
    expect("score before match_start -> 409 MATCH_NOT_IN_PROGRESS",
           post_event("k-2", "km1", "score", {"team_id": "t1", "event_type": "raid_point"}), 409, "MATCH_NOT_IN_PROGRESS")
    expect("match_end before start -> 409 ILLEGAL_TRANSITION",
           post_event("k-3", "km1", "match_end", {}), 409, "ILLEGAL_TRANSITION")
    expect("bad type 'goal_scored' -> 400 VALIDATION_ERROR",
           post_event("k-4", "km1", "goal_scored", {}), 400, "VALIDATION_ERROR")
    expect("event_id with '|' -> 400 VALIDATION_ERROR",
           post_event("k|5", "km1", "match_start", {}), 400, "VALIDATION_ERROR")
    check_event_ok("match_start -> 201 seq 2 (rejected events took no sequence number)",
                   post_event("k-6", "km1", "match_start", {}), "k-6", "km1", "match_start", {}, 2)
    expect("match_start again -> 409 ILLEGAL_TRANSITION", post_event("k-7", "km1", "match_start", {}), 409,
           "ILLEGAL_TRANSITION")
    expect("score for team not in match -> 400 VALIDATION_ERROR",
           post_event("k-8", "km1", "score", {"team_id": "t9", "event_type": "raid_point"}), 400, "VALIDATION_ERROR")
    expect("score with event_type 'goal' (not in kabaddi) -> 400 UNKNOWN_EVENT_TYPE",
           post_event("k-9", "km1", "score", {"team_id": "t1", "event_type": "goal"}), 400, "UNKNOWN_EVENT_TYPE")
    expect("discipline with points \"-1\" (string) -> 400",
           post_event("k-10", "km1", "discipline", {"team_id": "t1", "points": "-1"}), 400, "VALIDATION_ERROR")
    p = {"team_id": "t1", "event_type": "raid_point"}
    check_event_ok("score raid_point t1 -> 201 seq 3", post_event("k-11", "km1", "score", p), "k-11", "km1", "score", p, 3)
    post_event("k-12", "km1", "score", {"team_id": "t2", "event_type": "all_out"})
    post_event("k-13", "km1", "discipline", {"team_id": "t2", "points": -2})
    s, sc, _ = score("km1")
    check("live score: home 1, away 2, away fair_play -2, status in_progress, outcome pending",
          s == 200 and sc["home"]["score"] == 1 and sc["away"]["score"] == 2 and sc["away"]["fair_play"] == -2
          and sc["status"] == "in_progress" and sc["outcome"] == "pending", f"got {s} {short(sc)}")
    check_event_ok("match_end -> 201 seq 6", post_event("k-14", "km1", "match_end", {}), "k-14", "km1", "match_end", {}, 6)
    s, sc, _ = score("km1")
    check("completed: away_win, winner t2", sc.get("outcome") == "away_win" and sc.get("winner_team_id") == "t2",
          short(sc))
    comp = {"compensates": "k-12", "reason": "video review"}
    check_event_ok("compensate the all_out AFTER match_end -> 201 seq 7",
                   post_event("k-15", "km1", "compensation", comp), "k-15", "km1", "compensation", comp, 7)
    s, sc, _ = score("km1")
    check("after compensation: away score 0, outcome home_win (rebuilt from log)",
          sc["away"]["score"] == 0 and sc["outcome"] == "home_win" and sc["winner_team_id"] == "t1", short(sc))
    evs = sc.get("events", [])
    target = next((e for e in evs if e.get("event_id") == "k-12"), {})
    check("original event still in the log, compensated:true, compensated_by k-15",
          target.get("compensated") is True and target.get("compensated_by") == "k-15", short(target))
    check("score.version = 7 and events listed in sequence 1..7",
          sc.get("version") == 7 and [e.get("sequence") for e in evs] == list(range(1, 8)), short(sc))
    keys = {"match_id", "sport_id", "league_id", "status", "outcome", "winner_team_id", "tiebreak_winner_team_id",
            "home", "away", "version", "events"}
    check("score response has exactly the spec fields", set(sc) == keys, f"got keys {sorted(sc)}")
    check("home/away objects have team_id, score, wickets, balls, overs, fair_play (null wickets for event model)",
          set(sc["home"]) == {"team_id", "score", "wickets", "balls", "overs", "fair_play"}
          and sc["home"]["wickets"] is None and sc["home"]["overs"] is None, short(sc["home"]))
    check("each event has sequence,event_id,type,payload,signature,compensated,compensated_by",
          all(set(e) == {"sequence", "event_id", "type", "payload", "signature", "compensated", "compensated_by"}
              for e in evs), short(evs[:1]))
    if ARGS.salt:
        check("every event signature in /score is correct", all(e["signature"] == sign(e["event_id"], e["payload"])
                                                              for e in evs))
    check("league_id is null for a stand-alone match", sc.get("league_id", "x") is None)
    expect("compensate the same event again -> 409 INVALID_COMPENSATION",
           post_event("k-16", "km1", "compensation", comp), 409, "INVALID_COMPENSATION")
    expect("compensate a match_start event -> 409 INVALID_COMPENSATION",
           post_event("k-17", "km1", "compensation", {"compensates": "k-6", "reason": "x"}), 409, "INVALID_COMPENSATION")
    expect("compensate unknown event -> 404 EVENT_NOT_FOUND",
           post_event("k-18", "km1", "compensation", {"compensates": "nope", "reason": "x"}), 404, "EVENT_NOT_FOUND")
    post_event("o-1", "km2", "match_init", init)
    post_event("o-2", "km2", "match_start", {})
    post_event("o-3", "km2", "score", {"team_id": "t1", "event_type": "raid_point"})
    expect("compensate an event of ANOTHER match -> 409 INVALID_COMPENSATION",
           post_event("k-19", "km1", "compensation", {"compensates": "o-3", "reason": "x"}), 409, "INVALID_COMPENSATION")
    expect("GET /score of unknown match -> 404 MATCH_NOT_FOUND", score("nomatch"), 404, "MATCH_NOT_FOUND")

    # --- tie rules
    post_event("t-1", "km3", "match_init", init)
    post_event("t-2", "km3", "match_start", {})
    expect("level score, draw not allowed, no tiebreak -> match_end 409 TIE_NOT_ALLOWED",
           post_event("t-3", "km3", "match_end", {}), 409, "TIE_NOT_ALLOWED")
    post_event("t-4", "km3", "tiebreak_winner", {"team_id": "t2"})
    check("after tiebreak_winner t2 -> match_end 201", post_event("t-5", "km3", "match_end", {})[0] == 201)
    s, sc, _ = score("km3")
    check("tiebreak decides: away_win, winner t2, tiebreak_winner_team_id t2, scores still 0-0",
          sc["outcome"] == "away_win" and sc["winner_team_id"] == "t2" and sc["tiebreak_winner_team_id"] == "t2"
          and sc["home"]["score"] == 0, short(sc))
    post_event("t-6", "km3", "compensation", {"compensates": "t-4", "reason": "replay"})
    s, sc, _ = score("km3")
    check("tiebreak compensated -> outcome undecided, winner null",
          sc["outcome"] == "undecided" and sc["winner_team_id"] is None and sc["tiebreak_winner_team_id"] is None,
          short(sc))
    finit = {"sport_id": "football", "home_team_id": "a", "away_team_id": "b"}
    post_event("f-1", "fm1", "match_init", finit)
    post_event("f-2", "fm1", "match_start", {})
    post_event("f-3", "fm1", "match_end", {})
    check("football 0-0 (draw allowed) -> outcome draw, winner null",
          score("fm1")[1].get("outcome") == "draw" and score("fm1")[1].get("winner_team_id") is None)

    # --- innings model
    cinit = {"sport_id": "cricket", "home_team_id": "c1", "away_team_id": "c2"}
    post_event("c-0", "cm1", "match_init", cinit)
    post_event("c-00", "cm1", "match_start", {})
    for i in range(20):
        post_event(f"c-{i + 1}", "cm1", "score", {"team_id": "c1", "event_type": "single"})
    post_event("c-w1", "cm1", "score", {"team_id": "c1", "event_type": "wide"})
    post_event("c-w2", "cm1", "score", {"team_id": "c1", "event_type": "wicket"})
    s, sc, _ = score("cm1")
    h = sc.get("home", {})
    check("cricket: 20 singles + wide + wicket -> score 21, balls 21, overs \"3.3\", wickets 1",
          h.get("score") == 21 and h.get("balls") == 21 and h.get("overs") == "3.3" and h.get("wickets") == 1, short(h))
    check("cricket away side: balls 0, overs \"0.0\"", sc["away"].get("balls") == 0 and sc["away"].get("overs") == "0.0",
          short(sc.get("away")))
    minit = {"sport_id": "mini_cricket", "home_team_id": "x1", "away_team_id": "x2"}
    post_event("m-0", "mm1", "match_init", minit)
    post_event("m-1", "mm1", "match_start", {})
    post_event("m-2", "mm1", "score", {"team_id": "x1", "event_type": "out"})
    post_event("m-3", "mm1", "score", {"team_id": "x1", "event_type": "out"})
    expect("mystery innings: 2 wickets = all out -> next x1 score 409 INNINGS_COMPLETE",
           post_event("m-4", "mm1", "score", {"team_id": "x1", "event_type": "one"}), 409, "INNINGS_COMPLETE")
    check("...but the other team can still bat (201)",
          post_event("m-5", "mm1", "score", {"team_id": "x2", "event_type": "one"})[0] == 201)
    post_event("m-6", "mm1", "compensation", {"compensates": "m-3", "reason": "no ball"})
    check("compensated wicket no longer counts -> x1 can bat again (201)",
          post_event("m-7", "mm1", "score", {"team_id": "x1", "event_type": "one"})[0] == 201)
    for i in range(11):
        post_event(f"m-b{i}", "mm1", "score", {"team_id": "x2", "event_type": "one"})
    expect("12 legal balls (2 overs x 6) used -> 409 INNINGS_COMPLETE",
           post_event("m-8", "mm1", "score", {"team_id": "x2", "event_type": "bye_run"}), 409, "INNINGS_COMPLETE")

    # --- round model
    rinit = {"sport_id": "chess_bo5", "home_team_id": "r1", "away_team_id": "r2"}
    post_event("r-0", "rm1", "match_init", rinit)
    post_event("r-1", "rm1", "match_start", {})
    for i in range(3):
        post_event(f"r-w{i}", "rm1", "score", {"team_id": "r1", "event_type": "map_win"})
    expect("best of 5: after 3 map wins -> next score 409 SERIES_ALREADY_DECIDED",
           post_event("r-x", "rm1", "score", {"team_id": "r2", "event_type": "map_win"}), 409, "SERIES_ALREADY_DECIDED")
    check("round model score = rounds won (3)", score("rm1")[1]["home"]["score"] == 3)


# ---------------------------------------------------------------- fixtures

def fx(fmt, teams, params=None):
    body = {"format": fmt, "teams": teams}
    if params is not None:
        body["params"] = params
    return call("POST", "/audit/v1/fixtures", body)


def rr_matches(r):
    return [m for rnd in r["rounds"] for m in rnd["matches"]]


def check_round_robin(n, legs):
    teams = [f"t{i}" for i in range(1, n + 1)]
    s, r, _ = fx("round_robin", teams, {"legs": legs})
    if not check(f"RR n={n} legs={legs} -> 200", s == 200, f"got {s} {short(r)}"):
        return
    per_leg = n - 1 if n % 2 == 0 else n
    ok = r["round_count"] == per_leg * legs and r["team_count"] == n and r["legs"] == legs
    for rnd in r["rounds"]:
        playing = [t for m in rnd["matches"] for t in (m["home"], m["away"])] + rnd["byes"]
        ok = ok and len(rnd["matches"]) == n // 2 and len(rnd["byes"]) == n % 2 and sorted(playing) == sorted(teams)
    pairs = {}
    for m in rr_matches(r):
        key = tuple(sorted((m["home"], m["away"])))
        pairs[key] = pairs.get(key, 0) + 1
    ok = ok and len(pairs) == n * (n - 1) // 2 and set(pairs.values()) == {legs}
    if legs == 2:
        ordered = {(m["home"], m["away"]) for m in rr_matches(r)}
        ok = ok and len(ordered) == n * (n - 1)
    for leg in range(1, legs + 1):
        home = {t: 0 for t in teams}
        away = {t: 0 for t in teams}
        for m in rr_matches(r):
            if m["leg"] == leg:
                home[m["home"]] += 1
                away[m["away"]] += 1
        ok = ok and all(abs(home[t] - away[t]) <= 1 for t in teams)
    ids_ok = all(re.fullmatch(r"RR-L\d+-R\d+-M\d+", m["match_id"]) for m in rr_matches(r))
    check(f"RR n={n} legs={legs}: rounds, byes, every pair {legs}x, home/away balance, ids", ok and ids_ok)


def test_fixtures():
    section("fixtures", "round robin, single elim, double elim, swiss")
    for n in (2, 3, 4, 5, 6, 7, 8, 11, 16):
        check_round_robin(n, 1)
    for n in (4, 5):
        check_round_robin(n, 2)
    teams5 = ["t1", "t2", "t3", "t4", "t5"]
    s, r, _ = fx("round_robin", teams5, {"legs": 1, "withdrawals": [{"team_id": "t3", "after_round": 2}],
                                         "withdrawal_policy": "forfeit_remaining"})
    ok = s == 200
    if ok:
        for rnd in r["rounds"]:
            for m in rnd["matches"]:
                has = "t3" in (m["home"], m["away"])
                if has and rnd["round"] > 2:
                    other = m["away"] if m["home"] == "t3" else m["home"]
                    ok = ok and m["status"] == "forfeit" and m["awarded_to"] == other
                else:
                    ok = ok and m["status"] == "scheduled" and m["awarded_to"] is None
        sm = r["summary"]
        ok = ok and sm["total"] == 10 and sm["scheduled"] + sm["forfeit"] + sm["voided"] == 10
    check("RR forfeit_remaining: t3 fixtures after round 2 forfeited to opponent, nothing removed", ok, short(r))
    s, r, _ = fx("round_robin", teams5, {"withdrawals": [{"team_id": "t3", "after_round": 2}],
                                         "withdrawal_policy": "void_all"})
    check("RR void_all: all 4 t3 fixtures voided (awarded_to null)",
          s == 200 and r["summary"]["voided"] == 4 and all(m["awarded_to"] is None for m in rr_matches(r)), short(r))
    s, r, _ = fx("round_robin", teams5, {"withdrawals": [{"team_id": "t1", "after_round": 0},
                                                         {"team_id": "t2", "after_round": 0}]})
    m12 = [m for m in rr_matches(r) if {m["home"], m["away"]} == {"t1", "t2"}]
    check("RR both teams withdrawn -> that fixture voided", s == 200 and m12 and m12[0]["status"] == "voided", short(m12))
    expect("RR withdrawal of unknown team -> 400", fx("round_robin", teams5, {"withdrawals": [
        {"team_id": "zz", "after_round": 1}]}), 400, "VALIDATION_ERROR")
    expect("RR after_round > round_count -> 400", fx("round_robin", teams5, {"withdrawals": [
        {"team_id": "t1", "after_round": 6}]}), 400, "VALIDATION_ERROR")
    expect("RR 1 team -> 400", fx("round_robin", ["t1"]), 400, "VALIDATION_ERROR")
    expect("RR 41 teams -> 400", fx("round_robin", [f"t{i}" for i in range(41)]), 400, "VALIDATION_ERROR")
    expect("duplicate team ids -> 400", fx("round_robin", ["t1", "t1", "t2"]), 400, "VALIDATION_ERROR")
    expect("unknown format -> 400", fx("league", teams5), 400, "VALIDATION_ERROR")

    # --- single elimination (exact)
    six = ["t1", "t2", "t3", "t4", "t5", "t6"]
    s, r, _ = fx("single_elim", six, {"third_place_match": False})
    ok = s == 200 and r.get("format") == "single_elim" and r.get("bracket_size") == 8 and len(r["rounds"]) == 3
    check("single elim n=6 -> bracket_size 8, 3 rounds", ok, short(r))
    if ok:
        m = {x["match_id"]: x for rnd in r["rounds"] for x in rnd["matches"]}
        check("R1M1 = seed 1 vs BYE (bye:true, away null, winner t1)",
              m["R1M1"]["home"] == "t1" and m["R1M1"]["away"] is None and m["R1M1"]["bye"] is True
              and m["R1M1"]["winner"] == "t1", short(m["R1M1"]))
        want = {"match_id": "R1M2", "bracket": "main", "round": 1, "index": 2, "home": "t4", "away": "t5",
                "home_seed": 4, "away_seed": 5, "bye": False, "winner": None, "loser": None,
                "winner_to": {"match_id": "R2M1", "slot": "away"}, "loser_to": None}
        check("R1M2 exactly equals the spec example object", m["R1M2"] == want, short(m["R1M2"]))
        check("R1M3 = seed 2 bye, R1M4 = seed 3 vs seed 6",
              m["R1M3"]["home"] == "t2" and m["R1M3"]["bye"] and (m["R1M4"]["home"], m["R1M4"]["away"]) == ("t3", "t6"))
        check("bye winners already propagated (R2M1.home t1, R2M2.home t2)",
              m["R2M1"]["home"] == "t1" and m["R2M2"]["home"] == "t2")
        check("final R3M1 winner_to null", m["R3M1"]["winner_to"] is None)
    s, r, _ = fx("single_elim", [f"t{i}" for i in range(1, 9)], {})
    if s == 200:
        r1 = r["rounds"][0]["matches"]
        check("single elim n=8 seeding order [1,8,4,5,2,7,3,6]",
              [(x["home_seed"], x["away_seed"]) for x in r1] == [(1, 8), (4, 5), (2, 7), (3, 6)], short(r1))
    s, r, _ = fx("single_elim", six, {"results": [{"match_id": "R1M2", "winner": "t5"},
                                                  {"match_id": "R2M1", "winner": "t5"}]})
    m = {x["match_id"]: x for rnd in r.get("rounds", []) for x in rnd["matches"]}
    check("results propagate: R1M2 winner t5 -> R2M1.away; R2M1 winner t5 -> R3M1.home",
          s == 200 and m["R2M1"]["away"] == "t5" and m["R1M2"]["loser"] == "t4" and m["R3M1"]["home"] == "t5", short(m))
    expect("result with a winner who isn't playing -> 400",
           fx("single_elim", six, {"results": [{"match_id": "R1M2", "winner": "t1"}]}), 400, "VALIDATION_ERROR")
    expect("result for unknown match_id -> 400",
           fx("single_elim", six, {"results": [{"match_id": "R9M9", "winner": "t1"}]}), 400, "VALIDATION_ERROR")
    s, r, _ = fx("single_elim", ["a", "b", "c", "d"], {"third_place_match": True})
    allm = [x for rnd in r.get("rounds", []) for x in rnd["matches"]]
    tp = [x for x in allm if x["match_id"] == "TP"]
    semis = [x for x in allm if x["round"] == 1]
    check("third_place_match: TP exists (bracket third_place), semifinal losers routed to TP home/away",
          s == 200 and tp and tp[0]["bracket"] == "third_place"
          and [x["loser_to"] for x in semis] == [{"match_id": "TP", "slot": "home"}, {"match_id": "TP", "slot": "away"}],
          short(allm))

    # --- double elimination
    for n in (3, 5, 8, 12, 16):
        teams = [f"t{i}" for i in range(1, n + 1)]
        s, r, _ = fx("double_elim", teams, {"bracket_reset": True})
        if not check(f"double elim n={n} -> 200", s == 200, f"got {s} {short(r)}"):
            continue
        b = r["bracket_size"]
        k = b.bit_length() - 1
        wr = [len(x["matches"]) for x in r["winners"]]
        lr = [len(x["matches"]) for x in r["losers"]]
        exp_lr = []
        for j in range(1, k):
            exp_lr += [b // 2 ** (j + 1)] * 2
        allm = [x for rr in r["winners"] + r["losers"] for x in rr["matches"]] + r["grand_final"]
        sources = {}
        for x in allm:
            for link in (x["winner_to"], x["loser_to"]):
                if link:
                    key = (link["match_id"], link["slot"])
                    sources[key] = sources.get(key, 0) + 1
        slots = {(x["match_id"], sl) for x in allm if not x["match_id"].startswith("WR1M") for sl in ("home", "away")}
        graph_ok = set(sources) == slots and set(sources.values()) == {1}
        loser_ok = all(x["loser_to"] for x in allm if x["bracket"] == "winners") and \
            all(x["loser_to"] is None for x in allm if x["bracket"] == "losers")
        gf = r["grand_final"]
        check(f"double elim n={n}: WR {wr}, LR {lr} (total {b - 2}), GF1+GF2, routing graph, loser_to rules",
              wr == [b // 2 ** j for j in range(1, k + 1)] and lr == exp_lr and sum(lr) == b - 2
              and [g["match_id"] for g in gf] == ["GF1", "GF2"] and gf[1].get("conditional") is True
              and gf[1].get("required", "x") is None and graph_ok and loser_ok and r.get("bracket_reset") is True,
              f"WR {wr} LR {lr} graph_ok={graph_ok} loser_ok={loser_ok} GF {short(gf)}")
    base = [{"match_id": "WR1M1", "winner": "a"}, {"match_id": "WR1M2", "winner": "b"},
            {"match_id": "WR2M1", "winner": "a"}, {"match_id": "LR1M1", "winner": "c"},
            {"match_id": "LR2M1", "winner": "c"}]
    s, r, _ = fx("double_elim", ["a", "b", "c", "d"], {"bracket_reset": True, "results": base + [
        {"match_id": "GF1", "winner": "c"}]})
    gf = {g["match_id"]: g for g in r.get("grand_final", [])}
    check("losers-bracket champion wins GF1 -> GF2.required true, same two teams",
          s == 200 and gf["GF2"]["required"] is True and {gf["GF2"]["home"], gf["GF2"]["away"]} == {"a", "c"}, short(gf))
    s, r, _ = fx("double_elim", ["a", "b", "c", "d"], {"bracket_reset": True, "results": base + [
        {"match_id": "GF1", "winner": "a"}]})
    gf = {g["match_id"]: g for g in r.get("grand_final", [])}
    check("winners-bracket champion wins GF1 -> GF2.required false", s == 200 and gf["GF2"]["required"] is False, short(gf))
    s, r, _ = fx("double_elim", ["a", "b", "c", "d"], {"bracket_reset": False})
    check("bracket_reset false -> only GF1", s == 200 and [g["match_id"] for g in r["grand_final"]] == ["GF1"], short(r))
    expect("double elim with 2 teams -> 400", fx("double_elim", ["a", "b"]), 400, "VALIDATION_ERROR")

    # --- swiss
    s, r, _ = fx("swiss", teams5, {"total_rounds": 3, "round": 1})
    check("swiss round 1 exact: t1-t3, t2-t4, bye t5 (last seed)",
          s == 200 and [(p["home"], p["away"]) for p in r["pairings"]] == [("t1", "t3"), ("t2", "t4")]
          and r["bye"] == "t5" and r["pairings"][0]["match_id"] == "SW-R1-M1", short(r))
    hist = [{"round": 1, "bye": "t5", "matches": [{"home": "t1", "away": "t3", "result": "home"},
                                                  {"home": "t2", "away": "t4", "result": "draw"}]}]
    s, r, _ = fx("swiss", teams5, {"total_rounds": 3, "round": 2, "history": hist})
    ok = s == 200
    if ok:
        scores = {x["team_id"]: x["score"] for x in r["standings"]}
        met = {frozenset(("t1", "t3")), frozenset(("t2", "t4"))}
        pairs = [(p["home"], p["away"]) for p in r["pairings"]]
        used = [t for p in pairs for t in p] + [r["bye"]]
        cost = sum(abs(scores[a] - scores[b]) for a, b in pairs)
        ok = sorted(used) == sorted(teams5) and all(frozenset(p) not in met for p in pairs) and cost == 1.0 \
            and r["bye"] == "t3"
        check("swiss round 2 (spec example): bye t3, no rematch, minimal sum |diff| = 1.0", ok, short(r))
        check("swiss standings: t1 1.0/0.0, t5 1.0/0.0, t2 0.5/0.5 (score, buchholz as floats)",
              r["standings"][:3] == [{"rank": 1, "team_id": "t1", "score": 1.0, "buchholz": 0.0},
                                     {"rank": 2, "team_id": "t5", "score": 1.0, "buchholz": 0.0},
                                     {"rank": 3, "team_id": "t2", "score": 0.5, "buchholz": 0.5}], short(r["standings"]))
    else:
        check("swiss round 2 -> 200", False, f"got {s} {short(r)}")
    six_t = ["a", "b", "c", "d", "e", "f"]
    blocked = [{"round": 1, "bye": None, "matches": [{"home": "a", "away": "d", "result": "home"},
                                                     {"home": "b", "away": "e", "result": "home"},
                                                     {"home": "c", "away": "f", "result": "home"}]},
               {"round": 2, "bye": None, "matches": [{"home": "a", "away": "e", "result": "home"},
                                                     {"home": "b", "away": "f", "result": "home"},
                                                     {"home": "c", "away": "d", "result": "home"}]},
               {"round": 3, "bye": None, "matches": [{"home": "a", "away": "f", "result": "home"},
                                                     {"home": "b", "away": "d", "result": "home"},
                                                     {"home": "c", "away": "e", "result": "home"}]}]
    s, r, _ = fx("swiss", six_t, {"total_rounds": 5, "round": 4, "history": blocked})
    ok = s == 409 and r.get("error", {}).get("code") == "NO_VALID_PAIRING" and r["error"]["details"].get("round") == 4
    check("swiss with no rematch-free pairing -> 409 NO_VALID_PAIRING details.round 4", ok, f"got {s} {short(r)}")
    expect("swiss history missing round 1 -> 400",
           fx("swiss", teams5, {"total_rounds": 3, "round": 2, "history": []}), 400, "VALIDATION_ERROR")
    expect("swiss total_rounds > n-1 -> 400", fx("swiss", teams5, {"total_rounds": 5}), 400, "VALIDATION_ERROR")
    t0 = time.time()
    s, r, _ = fx("swiss", [f"t{i}" for i in range(1, 65)], {"total_rounds": 6, "round": 1})
    check("swiss 64 teams round 1 answers in < 5 s", s == 200 and time.time() - t0 < 5)


# ---------------------------------------------------------------- standings

def league(league_id, sport, teams, fixtures, spots=2, **extra):
    body = {"league_id": league_id, "sport_id": sport, "teams": teams,
            "fixtures": [{"match_id": m, "home": h, "away": a} for m, h, a in fixtures],
            "qualification": {"spots": spots}}
    body.update(extra)
    return call("POST", "/audit/v1/leagues", body)


def play(match_id, home_goals, away_goals, home="", away="", event_type="goal", home_team=None, away_team=None):
    """Play a whole football-style match on a league fixture through /events."""
    post_event(f"{match_id}-s", match_id, "match_start", {})
    for i in range(home_goals):
        post_event(f"{match_id}-h{i}", match_id, "score", {"team_id": home_team, "event_type": event_type})
    for i in range(away_goals):
        post_event(f"{match_id}-a{i}", match_id, "score", {"team_id": away_team, "event_type": event_type})
    return post_event(f"{match_id}-e", match_id, "match_end", {})


def standings(league_id):
    return call("GET", f"/audit/v1/standings/{league_id}")


def test_standings():
    section("standings", "leagues, table, H2H mini-league, NRR, qualification")
    reset()
    fixtures = [("L1", "a", "b"), ("L2", "b", "c"), ("L3", "c", "a"), ("L4", "a", "d"), ("L5", "b", "d"),
                ("L6", "c", "d")]
    s, body, _ = league("lg-1", "football", ["a", "b", "c", "d"], fixtures)
    check("register league -> 201 {league_id, status:created, team_count 4, fixture_count 6}",
          s == 201 and body == {"league_id": "lg-1", "status": "created", "team_count": 4, "fixture_count": 6},
          f"got {s} {short(body)}")
    expect("same league_id again -> 409 LEAGUE_EXISTS", league("lg-1", "football", ["a", "b"], []), 409, "LEAGUE_EXISTS")
    expect("unknown sport -> 404 SPORT_NOT_FOUND", league("lg-x", "nosuch", ["a", "b"], []), 404, "SPORT_NOT_FOUND")
    expect("fixture match_id already used -> 409 MATCH_EXISTS",
           league("lg-y", "football", ["a", "b"], [("L1", "a", "b")]), 409, "MATCH_EXISTS")
    expect("1 team -> 400", league("lg-z", "football", ["a"], []), 400, "VALIDATION_ERROR")
    expect("fixture team not in teams -> 400", league("lg-z", "football", ["a", "b"], [("Z1", "a", "q")]), 400,
           "VALIDATION_ERROR")
    expect("fixture home == away -> 400", league("lg-z", "football", ["a", "b"], [("Z1", "a", "a")]), 400,
           "VALIDATION_ERROR")
    expect("qualification.spots 5 with 2 teams -> 400", league("lg-z", "football", ["a", "b"], [], spots=5), 400,
           "VALIDATION_ERROR")
    s, sc, _ = score("L1")
    check("league fixture is a match stream: /score L1 -> upcoming, version 0, league_id lg-1",
          s == 200 and sc.get("status") == "upcoming" and sc.get("version") == 0 and sc.get("league_id") == "lg-1",
          f"got {s} {short(sc)}")
    s, st, _ = standings("lg-1")
    check("standings before any match: 200, 4 rows, all played 0", s == 200 and len(st.get("table", [])) == 4
          and all(row["played"] == 0 for row in st["table"]), f"got {s} {short(st)}")
    # 3-way cycle a>b 3-0, b>c 2-0, c>a 1-0; everyone beats d
    play("L1", 3, 0, home_team="a", away_team="b")
    play("L2", 2, 0, home_team="b", away_team="c")
    play("L3", 1, 0, home_team="c", away_team="a")
    play("L4", 1, 0, home_team="a", away_team="d")
    play("L5", 1, 0, home_team="b", away_team="d")
    play("L6", 5, 0, home_team="c", away_team="d")
    s, st, _ = standings("lg-1")
    rows = {r["team_id"]: r for r in st.get("table", [])}
    order = [r["team_id"] for r in st.get("table", [])]
    check("3-way mini-league tie (edge case 4): order a, b, c, d", order == ["a", "b", "c", "d"], f"got {order}")
    check("resolved_by: a=h2h_diff, b=h2h_points (restart on split), c=null, d=null",
          [rows.get(t, {}).get("resolved_by") for t in "abcd"] == ["h2h_diff", "h2h_points", None, None],
          short(st.get("table")))
    row_keys = {"rank", "team_id", "played", "won", "drawn", "lost", "scored", "conceded", "diff", "points",
                "fair_play", "status", "resolved_by"}
    check("table rows have exactly the spec fields", all(set(r) == row_keys for r in st.get("table", [])),
          short(st.get("table", [])[:1]))
    check("a: played 3, won 2, lost 1, scored 4, conceded 1, diff 3, points 6",
          [rows["a"][k] for k in ("played", "won", "lost", "scored", "conceded", "diff", "points")] == [3, 2, 1, 4, 1, 3, 6],
          short(rows.get("a")))
    h2h = st.get("h2h", {})
    check("h2h a vs b = played 1, points 3, scored 3, conceded 0",
          h2h.get("a", {}).get("b") == {"played": 1, "points": 3, "scored": 3, "conceded": 0}, short(h2h.get("a")))
    check("h2h has every ordered pair (12 for 4 teams)",
          sum(len(v) for v in h2h.values()) == 12 and all(a not in h2h.get(a, {}) for a in "abcd"), short(h2h))
    check("top-level fields league_id, sport_id, qualification_spots, table, h2h",
          set(st) == {"league_id", "sport_id", "qualification_spots", "table", "h2h"} and st["qualification_spots"] == 2)
    check("all fixtures played -> statuses: a,b,c clinched? (top 2 of 3 on 6 pts) -> d eliminated",
          rows["d"]["status"] == "eliminated", short(st.get("table")))
    # edge case 5: compensation after completion flips the table
    post_event("L4-fix", "L4", "compensation", {"compensates": "L4-h0", "reason": "offside"})
    s, st2, _ = standings("lg-1")
    rows2 = {r["team_id"]: r for r in st2["table"]}
    check("compensating a goal of a completed match (a-d 1-0 -> 0-0 draw) recomputes the table",
          rows2["a"]["points"] == 4 and rows2["d"]["points"] == 1 and rows2["a"]["drawn"] == 1,
          short(st2["table"]))
    s, sc, _ = score("L4")
    check("...and /score L4 still lists the original goal (compensated:true)",
          any(e["event_id"] == "L4-h0" and e["compensated"] for e in sc["events"]))

    # draw lots (Appendix A vector 2) - seed comes from the last reset (42)
    league("lg-lots", "football", ["t1", "t2", "t3"], [], spots=1)
    s, st, _ = standings("lg-lots")
    order = [r["team_id"] for r in st.get("table", [])]
    check("all level -> draw_lots order t1, t3, t2 (seed 42, vector 2)", order == ["t1", "t3", "t2"], f"got {order}")
    check("resolved_by draw_lots for t1 and t3, null for last",
          [r["resolved_by"] for r in st["table"]] == ["draw_lots", "draw_lots", None], short(st.get("table")))
    league("lg-lots7", "football", ["t1", "t2", "t3"], [], spots=1, lots_seed=7)
    keys = {t: hashlib.sha256(f"7|lg-lots7|{t}".encode()).hexdigest() for t in ("t1", "t2", "t3")}
    order7 = [r["team_id"] for r in standings("lg-lots7")[1]["table"]]
    check("explicit lots_seed 7 is used", order7 == sorted(keys, key=keys.get), f"got {order7}")
    # qualification
    league("lg-q", "football", ["a", "b", "c", "d"], [("Q1", "a", "b"), ("Q2", "a", "c"), ("Q3", "b", "d"),
                                                      ("Q4", "c", "d")], spots=1)
    play("Q1", 1, 0, home_team="a", away_team="b")
    play("Q2", 1, 0, home_team="a", away_team="c")
    play("Q3", 1, 0, home_team="b", away_team="d")
    rows = {r["team_id"]: r for r in standings("lg-q")[1]["table"]}
    check("qualification k=1: a clinched, b/c/d eliminated (Q4 still remaining)",
          [rows[t]["status"] for t in "abcd"] == ["clinched", "eliminated", "eliminated", "eliminated"],
          short(list(rows.values())))
    league("lg-q2", "football", ["a", "b", "c", "d"], [("V1", "a", "b"), ("V2", "a", "c"), ("V3", "b", "d"),
                                                       ("V4", "c", "d")], spots=2)
    play("V1", 1, 0, home_team="a", away_team="b")
    play("V2", 1, 0, home_team="a", away_team="c")
    play("V3", 1, 0, home_team="b", away_team="d")
    rows = {r["team_id"]: r for r in standings("lg-q2")[1]["table"]}
    check("qualification k=2: a clinched, b/c/d still_possible",
          [rows[t]["status"] for t in "abcd"] == ["clinched", "still_possible", "still_possible", "still_possible"],
          short(list(rows.values())))
    # custom points
    league("lg-pts", "football", ["a", "b"], [("P1", "a", "b")], spots=1, points={"win": 2, "draw": 1, "loss": 0})
    play("P1", 1, 0, home_team="a", away_team="b")
    rows = {r["team_id"]: r for r in standings("lg-pts")[1]["table"]}
    check("custom points win=2 used", rows["a"]["points"] == 2, short(rows))
    # innings net run rate with all-out
    call("POST", "/audit/v1/sports", TINY_INNINGS)
    league("lg-nrr", "mini_cricket", ["h", "w"], [("N1", "h", "w")], spots=1)
    post_event("N1-s", "N1", "match_start", {})
    for i in range(12):
        post_event(f"N1-h{i}", "N1", "score", {"team_id": "h", "event_type": "one"})
    post_event("N1-a1", "N1", "score", {"team_id": "w", "event_type": "super_six"})
    post_event("N1-a2", "N1", "score", {"team_id": "w", "event_type": "out"})
    post_event("N1-a3", "N1", "score", {"team_id": "w", "event_type": "out"})
    post_event("N1-e", "N1", "match_end", {})
    rows = {r["team_id"]: r for r in standings("lg-nrr")[1]["table"]}
    check("NRR: h 12 off 2 overs, w 6 all out (counts as full 2 overs) -> h +3.0, w -3.0",
          rows["h"]["diff"] == 3.0 and rows["w"]["diff"] == -3.0, short(rows))
    expect("unknown league -> 404 LEAGUE_NOT_FOUND", standings("nope"), 404, "LEAGUE_NOT_FOUND")
    # mystery sport usable in standings at once
    call("POST", "/audit/v1/sports", KABADDI)
    s, body, _ = league("lg-kab", "kabaddi", ["k1", "k2"], [("KB1", "k1", "k2")], spots=1)
    play("KB1", 2, 1, home_team="k1", away_team="k2", event_type="raid_point")
    rows = {r["team_id"]: r for r in standings("lg-kab")[1]["table"]}
    check("mystery sport works in leagues/standings immediately", s == 201 and rows["k1"]["points"] == 3, short(rows))


# ---------------------------------------------------------------- roster

def roster_setup(league_id, squads, players, window=("2026-09-01", "2026-09-30"), max_size=3,
                 required=None, live=None, tenant="tenant-alpha"):
    league_obj = {"league_id": league_id, "tenant_id": tenant, "sport_id": "football",
                  "transfer_window": {"open": window[0], "close": window[1]}, "max_squad_size": max_size,
                  "required_positions": required if required is not None else {"gk": 1}}
    return call("POST", "/audit/v1/roster/setup", {
        "league": league_obj,
        "squads": [{"squad_id": sq, "club_id": "club-" + sq, "tenant_id": tn, "name": sq} for sq, tn in squads],
        "players": [{"player_id": p, "name": p.upper(), "position": pos, "squad_id": sq, "role": role}
                    for p, pos, sq, role in players],
        "matches_in_progress": live or []})


def transfer(request_id, league_id, player, ttype, from_sq, to_sq, date, loan_end=None, reason="test"):
    return call("POST", "/audit/v1/roster/transfer", {
        "request_id": request_id, "league_id": league_id, "player_id": player, "type": ttype,
        "from_squad_id": from_sq, "to_squad_id": to_sq, "effective_date": date, "loan_end_date": loan_end,
        "reason": reason, "requested_by": "user-77"})


def history(player, as_of=None):
    return call("GET", f"/audit/v1/roster/history/{player}" + (f"?as_of={as_of}" if as_of else ""))


def test_roster():
    section("roster", "setup, transfer rule order, loans, history, deferred transfer")
    reset()
    squads = [("sq-a", "tenant-alpha"), ("sq-b", "tenant-alpha"), ("sq-c", "tenant-alpha"), ("sq-x", "tenant-beta")]
    players = [("p1", "gk", "sq-a", "captain"), ("p2", "df", "sq-a", "starter"), ("p3", "df", "sq-b", "starter"),
               ("p4", "fw", "sq-b", "starter"), ("p5", "mf", "sq-b", "substitute")]
    s, body, _ = roster_setup("lg-r1", squads, players)
    check("roster setup -> 201 {league_id, status:configured, squad_counts}",
          s == 201 and body == {"league_id": "lg-r1", "status": "configured",
                                "squad_counts": {"sq-a": 2, "sq-b": 3, "sq-c": 0, "sq-x": 0}}, f"got {s} {short(body)}")
    expect("1) loan without loan_end_date -> 400", transfer("r1", "lg-r1", "p2", "loan", "sq-a", "sq-c", "2026-09-10"),
           400, "VALIDATION_ERROR")
    expect("1) loan_end_date not after effective_date -> 400",
           transfer("r1", "lg-r1", "p2", "loan", "sq-a", "sq-c", "2026-09-10", "2026-09-10"), 400, "VALIDATION_ERROR")
    expect("1) transfer without to_squad_id -> 400", transfer("r1", "lg-r1", "p2", "transfer", "sq-a", None, "2026-09-10"),
           400, "VALIDATION_ERROR")
    expect("1) bad date '2026-13-40' -> 400", transfer("r1", "lg-r1", "p2", "transfer", "sq-a", "sq-c", "2026-13-40"),
           400, "VALIDATION_ERROR")
    expect("1) type 'swap' -> 400", transfer("r1", "lg-r1", "p2", "swap", "sq-a", "sq-c", "2026-09-10"), 400,
           "VALIDATION_ERROR")
    expect("2) unknown league -> 404 LEAGUE_NOT_FOUND", transfer("r1", "nope", "p2", "transfer", "sq-a", "sq-c",
                                                                 "2026-09-10"), 404, "LEAGUE_NOT_FOUND")
    expect("2) unknown player -> 404 PLAYER_NOT_FOUND", transfer("r1", "lg-r1", "zz", "transfer", "sq-a", "sq-c",
                                                                 "2026-09-10"), 404, "PLAYER_NOT_FOUND")
    expect("2) unknown squad -> 404 SQUAD_NOT_FOUND", transfer("r1", "lg-r1", "p2", "transfer", "sq-a", "sq-zz",
                                                               "2026-09-10"), 404, "SQUAD_NOT_FOUND")
    expect("3) destination in other tenant -> 409 CROSS_TENANT_TRANSFER",
           transfer("r1", "lg-r1", "p2", "transfer", "sq-a", "sq-x", "2026-09-10"), 409, "CROSS_TENANT_TRANSFER")
    expect("4) wrong from_squad -> 409 NOT_IN_SQUAD", transfer("r1", "lg-r1", "p3", "transfer", "sq-a", "sq-c",
                                                               "2026-09-10"), 409, "NOT_IN_SQUAD")
    expect("5) date after window -> 409 TRANSFER_WINDOW_CLOSED",
           transfer("r1", "lg-r1", "p2", "transfer", "sq-a", "sq-c", "2026-10-01"), 409, "TRANSFER_WINDOW_CLOSED")
    expect("5) date before window -> 409 TRANSFER_WINDOW_CLOSED",
           transfer("r1", "lg-r1", "p2", "transfer", "sq-a", "sq-c", "2026-08-31"), 409, "TRANSFER_WINDOW_CLOSED")
    expect("7) destination full (3/3) -> 409 SQUAD_FULL", transfer("r1", "lg-r1", "p2", "transfer", "sq-a", "sq-b",
                                                                   "2026-09-10"), 409, "SQUAD_FULL")
    expect("8) releasing the only gk -> 409 MIN_POSITION_VIOLATION",
           transfer("r1", "lg-r1", "p1", "release", "sq-a", None, "2026-12-01"), 409, "MIN_POSITION_VIOLATION")
    s, h, _ = history("p2")
    check("rejected requests wrote no audit entry (history of p2 empty)", s == 200 and h.get("history") == [],
          f"got {s} {short(h)}")
    s, body, _ = transfer("r-loan", "lg-r1", "p2", "loan", "sq-a", "sq-c", "2026-09-10", "2026-09-20", "cover")
    reg = body.get("registration") or {}
    ae = body.get("audit_entry") or {}
    check("loan p2 sq-a -> sq-c -> 201 accepted, active, registration loan with parent sq-a",
          s == 201 and body.get("status") == "accepted" and body.get("state") == "active"
          and body.get("blocking_match_id", "x") is None and reg.get("registration_type") == "loan"
          and reg.get("squad_id") == "sq-c" and reg.get("parent_squad_id") == "sq-a"
          and reg.get("loan_end_date") == "2026-09-20" and reg.get("start_date") == "2026-09-10",
          f"got {s} {short(body)}")
    check("audit_entry: action loan, who=requested_by, why=reason, when=YYYY-MM-DDTHH:MM:SSZ",
          ae.get("action") == "loan" and ae.get("who") == "user-77" and ae.get("why") == "cover"
          and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", str(ae.get("when"))) is not None
          and ae.get("from_squad_id") == "sq-a" and ae.get("to_squad_id") == "sq-c", short(ae))
    check("response fields exactly request_id,status,state,blocking_match_id,registration,audit_entry",
          set(body) == {"request_id", "status", "state", "blocking_match_id", "registration", "audit_entry"},
          f"got {sorted(body)}")
    s2, body2, _ = transfer("r-loan", "lg-r1", "p2", "loan", "sq-a", "sq-c", "2026-09-10", "2026-09-20", "cover")
    check("replay same request_id -> 200 with identical body", s2 == 200 and body2 == body, f"got {s2} {short(body2)}")
    expect("6) moving a player who is on loan -> 409 PLAYER_ON_LOAN",
           transfer("r-ol", "lg-r1", "p2", "transfer", "sq-c", "sq-a", "2026-09-15"), 409, "PLAYER_ON_LOAN")
    s, h, _ = history("p2", "2026-09-15")
    check("history as_of 2026-09-15: current squad sq-c, parent sq-a, 1 entry",
          s == 200 and h.get("current_squad_id") == "sq-c" and h.get("parent_squad_id") == "sq-a"
          and len(h.get("history", [])) == 1, f"got {s} {short(h)}")
    s, h, _ = history("p2", "2026-09-21")
    entries = h.get("history", [])
    check("history as_of day after loan end: back at sq-a, loan_return entry written by 'system'",
          s == 200 and h.get("current_squad_id") == "sq-a" and [e.get("action") for e in entries] == ["loan", "loan_return"]
          and entries[-1].get("who") == "system", f"got {s} {short(h)}")
    s, h, _ = history("p2", "2026-09-25")
    check("history again: loan_return is NOT duplicated",
          [e.get("action") for e in h.get("history", [])] == ["loan", "loan_return"], short(h))
    check("history fields player_id, as_of, league_id, current_squad_id, parent_squad_id, history",
          set(h) == {"player_id", "as_of", "league_id", "current_squad_id", "parent_squad_id", "history"}
          and h.get("as_of") == "2026-09-25", f"got {sorted(h)}")
    s, body, _ = transfer("r-t4", "lg-r1", "p4", "transfer", "sq-b", "sq-c", "2026-09-30")
    reg = body.get("registration") or {}
    check("transfer on the last window day (inclusive) -> 201, role substitute, type transfer",
          s == 201 and reg.get("role") == "substitute" and reg.get("registration_type") == "transfer"
          and reg.get("squad_id") == "sq-c" and reg.get("parent_squad_id", "x") is None, f"got {s} {short(body)}")
    s, body, _ = transfer("r-rel", "lg-r1", "p3", "release", "sq-b", None, "2027-03-01")
    check("release outside window is allowed -> 201, registration null",
          s == 201 and body.get("registration", "x") is None and body.get("audit_entry", {}).get("action") == "release",
          f"got {s} {short(body)}")
    s, h, _ = history("p3", "2027-03-02")
    check("released player: current_squad_id null", s == 200 and h.get("current_squad_id", "x") is None, short(h))
    expect("history of unknown player -> 404 PLAYER_NOT_FOUND", history("nobody"), 404, "PLAYER_NOT_FOUND")
    # edge case 6: in-progress match on the last window day
    s, body, _ = roster_setup("lg-r2", [("sq-l1", "tenant-alpha"), ("sq-l2", "tenant-alpha")],
                              [("q1", "gk", "sq-l1", "captain"), ("q2", "df", "sq-l1", "starter"),
                               ("q3", "gk", "sq-l2", "starter")],
                              live=[{"match_id": "m-live", "home_squad_id": "sq-l1", "away_squad_id": "sq-l2"}])
    s, body, _ = transfer("r-def", "lg-r2", "q2", "transfer", "sq-l1", "sq-l2", "2026-09-30")
    check("player in an in-progress match, last window day -> 201 deferred_until_match_end, blocking m-live",
          s == 201 and body.get("state") == "deferred_until_match_end" and body.get("blocking_match_id") == "m-live",
          f"got {s} {short(body)}")
    s, body, _ = roster_setup("lg-r1", squads, players)
    check("re-sending setup for the same league replaces its state", s == 201 and body.get("squad_counts", {}).get("sq-b") == 3,
          f"got {s} {short(body)}")


# ---------------------------------------------------------------- store

def checkout(order_id, items, token="tok_success", discount=None, customer="cust-001"):
    return call("POST", "/audit/v1/checkout", {"order_id": order_id, "customer_id": customer, "items": items,
                                               "discount_code": discount, "payment": {"token": token}})


def inventory(variant):
    return call("GET", f"/audit/v1/inventory/{variant}")


def pdf_text_contains(pdf, needles):
    """Best effort: search raw + zlib-inflated streams for each needle."""
    blobs = [pdf]
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            blobs.append(zlib.decompress(m.group(1)))
        except Exception:
            pass
    joined = b"\n".join(blobs)
    return {n: n.encode() in joined for n in needles}


def test_store():
    section("store", "checkout, receipt signature + PDF, payment failures, 20-buyer burst")
    reset()
    s, inv, _ = inventory("var-jersey-001-M")
    check("inventory M after reset -> {variant_id, stock 1, reserved 0}",
          s == 200 and inv == {"variant_id": "var-jersey-001-M", "stock": 1, "reserved": 0}, f"got {s} {short(inv)}")
    expect("inventory unknown variant -> 404 VARIANT_NOT_FOUND", inventory("var-nope"), 404, "VARIANT_NOT_FOUND")
    items = [{"variant_id": "var-jersey-001-L", "quantity": 2}]
    s, body, _ = checkout("ord-1", items)
    ok = s == 201 and body.get("status") == "paid" and body.get("currency") == "PKR" \
        and body.get("subtotal_minor") == 900000 and body.get("discount_minor") == 0 and body.get("total_minor") == 900000 \
        and body.get("items") == [{"variant_id": "var-jersey-001-L", "quantity": 2, "unit_price_minor": 450000}] \
        and body.get("payment", {}).get("state") == "captured"
    check("checkout 2 x L -> 201 paid, PKR, subtotal 900000, total 900000, payment captured", ok, f"got {s} {short(body)}")
    check("response fields order_id,status,currency,items,subtotal_minor,discount_minor,total_minor,payment,receipt",
          set(body) == {"order_id", "status", "currency", "items", "subtotal_minor", "discount_minor", "total_minor",
                        "payment", "receipt"}, f"got {sorted(body) if isinstance(body, dict) else body}")
    rc = body.get("receipt", {}) if isinstance(body, dict) else {}
    pl = rc.get("payload", {})
    check("receipt.payload fields + totals add up",
          set(pl) == {"order_id", "customer_id", "items", "subtotal_minor", "discount_minor", "total_minor", "currency",
                      "paid_at"} and pl.get("total_minor") == pl.get("subtotal_minor", 0) - pl.get("discount_minor", 0)
          and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", str(pl.get("paid_at"))) is not None, short(pl))
    if ARGS.salt:
        check("receipt.signature = HMAC(salt, order_id | canonical(payload))", rc.get("signature") == sign("ord-1", pl),
              f"got {rc.get('signature')}")
    try:
        pdf = base64.b64decode(rc.get("pdf_base64", ""))
    except Exception:
        pdf = b""
    check("receipt.pdf_base64 decodes to a PDF (starts with %PDF)", pdf.startswith(b"%PDF"), f"first bytes {pdf[:10]!r}")
    if pdf:
        with open("receipt_check.pdf", "wb") as f:
            f.write(pdf)
        found = pdf_text_contains(pdf, ["ord-1", "PKR 9000.00"])
        check("PDF text contains order id and 'PKR 9000.00' (if FAIL: open receipt_check.pdf and look by eye)",
              all(found.values()), f"found: {found}")
    s2, body2, _ = checkout("ord-1", items)
    check("replay same order -> 200 identical body (no second purchase)", s2 == 200 and body2 == body, f"got {s2}")
    s, inv, _ = inventory("var-jersey-001-L")
    check("stock L = 3 after one purchase of 2 (replay did not buy again)", inv.get("stock") == 3, short(inv))
    expect("same order_id, different body -> 409 DUPLICATE_ORDER_ID",
           checkout("ord-1", [{"variant_id": "var-jersey-001-L", "quantity": 1}]), 409, "DUPLICATE_ORDER_ID")
    s, body, _ = checkout("ord-2", [{"variant_id": "var-jersey-001-L", "quantity": 1}], discount="WELCOME10")
    check("WELCOME10 -> discount 45000, total 405000", s == 201 and body.get("discount_minor") == 45000
          and body.get("total_minor") == 405000, f"got {s} {short(body)}")
    expect("unknown discount code -> 400 INVALID_DISCOUNT_CODE",
           checkout("ord-3", [{"variant_id": "var-jersey-001-L", "quantity": 1}], discount="FREE100"), 400,
           "INVALID_DISCOUNT_CODE")
    expect("unknown variant -> 404 VARIANT_NOT_FOUND", checkout("ord-4", [{"variant_id": "var-x", "quantity": 1}]), 404,
           "VARIANT_NOT_FOUND")
    expect("quantity 0 -> 400", checkout("ord-5", [{"variant_id": "var-jersey-001-L", "quantity": 0}]), 400,
           "VALIDATION_ERROR")
    expect("quantity 11 -> 400", checkout("ord-5", [{"variant_id": "var-jersey-001-L", "quantity": 11}]), 400,
           "VALIDATION_ERROR")
    expect("no items -> 400", checkout("ord-5", []), 400, "VALIDATION_ERROR")
    expect("same variant twice -> 400", checkout("ord-5", [{"variant_id": "var-jersey-001-L", "quantity": 1},
                                                           {"variant_id": "var-jersey-001-L", "quantity": 1}]), 400,
           "VALIDATION_ERROR")
    expect("tok_declined -> 402 PAYMENT_DECLINED", checkout("ord-6", [{"variant_id": "var-jersey-001-L", "quantity": 1}],
                                                            token="tok_declined"), 402, "PAYMENT_DECLINED")
    expect("tok_capture_fail -> 402 PAYMENT_CAPTURE_FAILED",
           checkout("ord-7", [{"variant_id": "var-jersey-001-L", "quantity": 1}], token="tok_capture_fail"), 402,
           "PAYMENT_CAPTURE_FAILED")
    s, inv, _ = inventory("var-jersey-001-L")
    check("failed payments released their stock (L stock 2, reserved 0)",
          inv.get("stock") == 2 and inv.get("reserved") == 0, short(inv))
    s, body, _ = checkout("ord-8", [{"variant_id": "var-jersey-001-L", "quantity": 3}])
    expect("asking for 3 when 2 left -> 409 OUT_OF_STOCK", (s, body, {}), 409, "OUT_OF_STOCK")
    check("OUT_OF_STOCK details.variant_id = var-jersey-001-L",
          isinstance(body, dict) and body.get("error", {}).get("details", {}).get("variant_id") == "var-jersey-001-L",
          short(body))
    weird = "cust-<script>alert(\"x\")</script>'"
    s, body, _ = checkout("ord-9", [{"variant_id": "var-jersey-001-L", "quantity": 1}], customer=weird)
    check("customer_id with quotes/<script> stored and returned as plain data (201, never 5xx)",
          s == 201 and body.get("receipt", {}).get("payload", {}).get("customer_id") == weird, f"got {s} {short(body)}")
    # the graded burst
    reset(stock={"var-jersey-001-M": 1, "var-jersey-001-L": 5})
    barrier = threading.Barrier(20)
    statuses = [None] * 20
    codes = [None] * 20

    def buyer(i):
        barrier.wait()
        st, bd, _ = checkout(f"burst-{i}", [{"variant_id": "var-jersey-001-M", "quantity": 1}], customer=f"c{i}")
        statuses[i] = st
        codes[i] = bd.get("error", {}).get("code") if isinstance(bd, dict) else None

    threads = [threading.Thread(target=buyer, args=(i,)) for i in range(20)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    took = time.time() - t0
    check("20 simultaneous buyers of the last unit: exactly one 201, nineteen 409 OUT_OF_STOCK",
          statuses.count(201) == 1 and statuses.count(409) == 19 and codes.count("OUT_OF_STOCK") == 19,
          f"statuses {statuses}")
    check("burst finished within 10 s", took < 10, f"took {took:.1f} s")
    s, inv, _ = inventory("var-jersey-001-M")
    check("after burst: stock 0, reserved 0 (never negative)", inv == {"variant_id": "var-jersey-001-M", "stock": 0,
                                                                         "reserved": 0}, short(inv))


# ---------------------------------------------------------------- rbac + security

MATRIX = {  # probe -> target -> roles allowed (spec §5.13)
    "P1": {None: ["super_admin"]},
    "P2": {"own": ["super_admin", "league_organizer"], "other": ["super_admin"], "foreign": ["super_admin"]},
    "P3": {"own": ["super_admin", "club_manager"], "other": ["super_admin"], "foreign": ["super_admin"]},
    "P4": {"own": ["super_admin", "club_manager"], "other": ["super_admin"], "foreign": ["super_admin"]},
    "P5": {"own": ["super_admin", "club_manager", "player"], "other": ["super_admin"], "foreign": ["super_admin"]},
    "P6": {"own": ["super_admin", "league_organizer", "club_manager", "player", "viewer"],
           "other": ["super_admin", "league_organizer", "club_manager", "player", "viewer"], "foreign": ["super_admin"]},
    "P7": {None: ["super_admin"]},
}
ROLES = ["super_admin", "league_organizer", "club_manager", "player", "viewer"]


def probe_request(probe, target, ctx):
    if probe == "P1":
        return "POST", "/audit/v1/rbac/tenants"
    if probe == "P7":
        return "GET", "/audit/v1/rbac/platform/config"
    if probe == "P2":
        return "POST", f"/audit/v1/rbac/leagues/{ctx[target + '_league_id']}/fixtures"
    if probe == "P3":
        return "POST", f"/audit/v1/rbac/clubs/{ctx[target + '_club_id']}/roster"
    if probe == "P4":
        return "POST", f"/audit/v1/rbac/clubs/{ctx[target + '_club_id']}/products"
    if probe == "P5":
        return "PATCH", f"/audit/v1/rbac/players/{ctx[target + '_player_id']}"
    return "GET", f"/audit/v1/rbac/clubs/{ctx[target + '_club_id']}"


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_rbac():
    section("rbac", "rbac-matrix, 85 probe checks, bad tokens, 413, rate limit")
    reset()
    s, m, _ = call("POST", "/audit/v1/rbac-matrix")
    ctx_expected = {"tenant_id": "tenant-alpha", "foreign_tenant_id": "tenant-beta", "own_league_id": "league-alpha-1",
                    "other_league_id": "league-alpha-2", "foreign_league_id": "league-beta-1",
                    "own_club_id": "club-alpha-1", "other_club_id": "club-alpha-2", "foreign_club_id": "club-beta-1",
                    "own_player_id": "player-alpha-1", "other_player_id": "player-alpha-2",
                    "foreign_player_id": "player-beta-1"}
    ok = s == 200 and isinstance(m, dict) and set(m.get("tokens", {})) == set(ROLES) and m.get("context") == ctx_expected
    if not check("POST /audit/v1/rbac-matrix -> 200 tokens for 5 roles + exact context", ok, f"got {s} {short(m)}"):
        return
    tokens, ctx = m["tokens"], m["context"]
    bad = []
    count = 0
    for probe, targets in MATRIX.items():
        for target, allowed in targets.items():
            method, path = probe_request(probe, target, ctx)
            for role in ROLES:
                body = {} if method in ("POST", "PATCH") else None
                st, bd, _ = call(method, path, body, token=tokens[role])
                count += 1
                if role in allowed:
                    good = st == 200 and bd == {"authorized": True}
                else:
                    good = st == 403 and isinstance(bd, dict) and bd.get("error", {}).get("code") == "FORBIDDEN"
                if not good:
                    bad.append(f"{probe} {target or ''} as {role}: got {st} {short(bd, 80)}")
    check(f"all {count} matrix probes match the spec table", not bad, "; ".join(bad[:8]))
    expect("P7 without token -> 401 UNAUTHENTICATED", call("GET", "/audit/v1/rbac/platform/config"), 401,
           "UNAUTHENTICATED")
    sa = tokens["super_admin"]
    head, payload, sig = sa.split(".")
    tampered = f"{head}.{payload}.{sig[:-2]}{'AA' if sig[-2:] != 'AA' else 'BB'}"
    expect("P7 with tampered signature -> 401", call("GET", "/audit/v1/rbac/platform/config", token=tampered), 401,
           "UNAUTHENTICATED")
    none_tok = f"{b64url(json.dumps({'alg': 'none', 'typ': 'JWT'}).encode())}.{payload}."
    expect("P7 with alg:none token -> 401", call("GET", "/audit/v1/rbac/platform/config", token=none_tok), 401,
           "UNAUTHENTICATED")
    expect("P7 with garbage token -> 401", call("GET", "/audit/v1/rbac/platform/config", token="abc.def"), 401,
           "UNAUTHENTICATED")
    big = json.dumps({"sport_id": "big", "pad": "x" * (1024 * 1024 + 10)}).encode()
    expect("body over 1 MB to /audit/v1/sports -> 413 PAYLOAD_TOO_LARGE", call("POST", "/audit/v1/sports", raw=big), 413,
           "PAYLOAD_TOO_LARGE")
    expect("body over 1 MB to /audit/v1/events -> 413", call("POST", "/audit/v1/events", raw=big), 413,
           "PAYLOAD_TOO_LARGE")
    # /audit/v1 + /health must not be rate limited
    sts = [call("GET", "/health")[0] for _ in range(150)]
    check("150 quick /health calls: none limited (all 200)", all(x == 200 for x in sts), f"non-200: {set(sts)}")
    # rate limit probe
    print("  ... sending 150 requests to /api/v1/ping (takes a few seconds), then waiting 11 s")
    time.sleep(11)  # empty the rolling window first
    results = []
    t0 = time.time()
    for _ in range(150):
        results.append(call("GET", "/api/v1/ping"))
    took = time.time() - t0
    first_ok = results[0][0] == 200 and results[0][1] == {"pong": True}
    limited = [r for r in results if r[0] == 429]
    retry_ok = all(r[2].get("Retry-After") for r in limited)
    code_ok = all(isinstance(r[1], dict) and r[1].get("error", {}).get("code") == "RATE_LIMITED" for r in limited)
    check("ping: first 200 {pong:true}; >= 40 of 150 are 429 RATE_LIMITED with Retry-After",
          first_ok and len(limited) >= 40 and retry_ok and code_ok,
          f"first {results[0][0]} {short(results[0][1])}, 429s {len(limited)}, Retry-After ok {retry_ok}, took {took:.1f}s")
    time.sleep(11)
    s, body, _ = call("GET", "/api/v1/ping")
    check("11 s later ping is 200 again", s == 200 and body == {"pong": True}, f"got {s} {short(body)}")


# ---------------------------------------------------------------- offline sync

def test_offline():
    section("offline", "offline-sync conflict table, ordering, duplicates")
    reset()
    post_event("os-0", "m-off", "match_init", {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2"})
    post_event("os-1", "m-off", "match_start", {})          # match version is now 2
    post_event("os-u", "m-up", "match_init", {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2"})
    roster_setup("lg-off", [("sa", "tenant-alpha"), ("sb", "tenant-alpha")],
                 [("op1", "gk", "sa", "captain"), ("op2", "df", "sa", "starter"), ("op3", "gk", "sb", "starter")])

    def se(action_id, queued, base, event_id, match_id="m-off", team="t1", etype="score"):
        payload = {"team_id": team, "event_type": "goal"} if etype == "score" else {}
        return {"action_id": action_id, "type": "score_event", "queued_at": queued, "base_version": base,
                "payload": ev(event_id, match_id, etype, payload)}

    transfer_body = {"request_id": "off-tr-1", "league_id": "lg-off", "player_id": "op2", "type": "transfer",
                     "from_squad_id": "sa", "to_squad_id": "sb", "effective_date": "2026-09-10", "loan_end_date": None,
                     "reason": "offline move", "requested_by": "manager"}
    bad_transfer = dict(transfer_body, request_id="off-tr-2", player_id="op3", from_squad_id="sa")
    actions = [
        se("a1", "2026-10-17T11:05:00Z", 2, "off-e1"),            # processed 2nd -> stale -> rebased_append
        se("a2", "2026-10-17T11:00:00Z", 2, "off-e2"),            # processed 1st -> appended
        se("a3", "2026-10-17T11:06:00Z", 99, "off-e3"),           # future base -> INVALID_BASE_VERSION
        se("a4", "2026-10-17T11:07:00Z", 0, "off-e4", match_id="m-none"),  # unknown match
        se("a5", "2026-10-17T11:08:00Z", 0, "off-e5", match_id="m-up"),    # upcoming -> MATCH_NOT_IN_PROGRESS
        se("a6", "2026-10-17T11:09:00Z", 4, "off-e2"),            # same event_id + same payload -> duplicate
        {"action_id": "a7", "type": "roster_transfer", "queued_at": "2026-10-17T11:10:00Z", "base_version": 0,
         "payload": transfer_body},
        {"action_id": "a8", "type": "roster_transfer", "queued_at": "2026-10-17T11:11:00Z", "base_version": 0,
         "payload": bad_transfer},
    ]
    s, body, _ = call("POST", "/audit/v1/offline-sync", {"device_id": "dev-1", "actions": actions})
    if not check("offline-sync -> 200 {device_id, results, summary}",
                 s == 200 and isinstance(body, dict) and set(body) == {"device_id", "results", "summary"},
                 f"got {s} {short(body)}"):
        return
    res = {r["action_id"]: r for r in body["results"]}
    check("results returned in REQUEST order", [r["action_id"] for r in body["results"]] == [a["action_id"] for a in actions])
    check("result fields action_id,status,resolution,error_code,processed_order,server_version,signature",
          all(set(r) == {"action_id", "status", "resolution", "error_code", "processed_order", "server_version",
                         "signature"} for r in body["results"]), short(body["results"][:1]))

    def is_(aid, status, resolution, code, version=None):
        r = res.get(aid, {})
        ok = r.get("status") == status and r.get("resolution") == resolution and r.get("error_code") == code
        if version is not None:
            ok = ok and r.get("server_version") == version
        return ok, short(r)

    ok, d = is_("a2", "applied", "appended", None, 3)
    check("a2 (earliest queued_at, base == version) -> applied/appended, server_version 3, processed first",
          ok and res["a2"]["processed_order"] == 1, d)
    if ARGS.salt:
        check("a2 signature = event signature", res["a2"].get("signature") == sign("off-e2", {"team_id": "t1",
                                                                                              "event_type": "goal"}))
    ok, d = is_("a1", "applied", "rebased_append", None, 4)
    check("a1 (stale base 2 < 3) -> applied/rebased_append, server_version 4, processed second",
          ok and res["a1"]["processed_order"] == 2, d)
    ok, d = is_("a3", "rejected", "server_wins", "INVALID_BASE_VERSION", 4)
    check("a3 base_version > current -> rejected/server_wins INVALID_BASE_VERSION, signature null",
          ok and res["a3"]["signature"] is None, d)
    check("a4 unknown match -> rejected MATCH_NOT_FOUND", is_("a4", "rejected", "server_wins", "MATCH_NOT_FOUND")[0],
          short(res.get("a4")))
    check("a5 upcoming match -> rejected MATCH_NOT_IN_PROGRESS",
          is_("a5", "rejected", "server_wins", "MATCH_NOT_IN_PROGRESS")[0], short(res.get("a5")))
    check("a6 same event_id + identical payload -> duplicate/skipped_duplicate",
          is_("a6", "duplicate", "skipped_duplicate", None)[0], short(res.get("a6")))
    check("a7 roster transfer -> applied/appended, server_version 1 (player audit entries)",
          is_("a7", "applied", "appended", None, 1)[0] and res["a7"]["signature"] is None, short(res.get("a7")))
    check("a8 roster rule failure -> rejected NOT_IN_SQUAD", is_("a8", "rejected", "server_wins", "NOT_IN_SQUAD")[0],
          short(res.get("a8")))
    check("summary counts applied 3, rejected 4, duplicate 1",
          body["summary"] == {"applied": 3, "rejected": 4, "duplicate": 1}, short(body["summary"]))
    s, sc, _ = score("m-off")
    check("match really has the 2 synced goals (version 4)", sc.get("version") == 4 and sc["home"]["score"] == 2,
          short(sc))
    s, body2, _ = call("POST", "/audit/v1/offline-sync", {"device_id": "dev-1", "actions": actions})
    check("re-sending the same request -> every action duplicate, nothing changes",
          s == 200 and all(r["status"] == "duplicate" for r in body2["results"])
          and body2["summary"] == {"applied": 0, "rejected": 0, "duplicate": 8}
          and score("m-off")[1].get("version") == 4, short(body2))
    expect("actions [] -> 400", call("POST", "/audit/v1/offline-sync", {"device_id": "d", "actions": []}), 400,
           "VALIDATION_ERROR")
    many = [se(f"x{i}", "2026-10-17T11:00:00Z", 0, f"xe{i}") for i in range(101)]
    expect("101 actions -> 400", call("POST", "/audit/v1/offline-sync", {"device_id": "d", "actions": many}), 400,
           "VALIDATION_ERROR")
    expect("missing device_id -> 400", call("POST", "/audit/v1/offline-sync", {"actions": actions[:1]}), 400,
           "VALIDATION_ERROR")


# ---------------------------------------------------------------- main

TESTS = {"scoring": test_scoring, "fixtures": test_fixtures, "standings": test_standings, "roster": test_roster,
         "store": test_store, "rbac": test_rbac, "offline": test_offline}


def main():
    global ARGS
    parser = argparse.ArgumentParser(description="Check a running NaSCon backend against the spec.")
    parser.add_argument("--base", default="http://localhost:8080", help="backend URL (default http://localhost:8080)")
    parser.add_argument("--salt", default="", help="the DAY1_SALT the backend was started with (to check signatures)")
    parser.add_argument("--only", default="", help="comma list of areas: " + ",".join(TESTS))
    ARGS = parser.parse_args()
    if not ARGS.salt:
        print("NOTE: no --salt given -> signature checks are SKIPPED. Pass the same salt you started docker with.")
    if not test_setup():
        sys.exit(2)
    wanted = [a for a in ARGS.only.split(",") if a] or list(TESTS)
    for area in wanted:
        try:
            TESTS[area]()
        except Exception as err:  # a crash in one area must not hide the others
            check(f"area '{area}' ran to the end without crashing", False, f"{type(err).__name__}: {err}")
    reset()  # leave the backend in its baseline state
    print("\n================ SUMMARY ================")
    total_fail = 0
    for area in AREAS:
        rows = [r for r in RESULTS if r[0] == area]
        if not rows:
            continue
        failed = [r for r in rows if not r[2]]
        total_fail += len(failed)
        print(f"  {area:10s} {len(rows) - len(failed):3d} / {len(rows):3d} passed")
    if total_fail:
        print(f"\n{total_fail} check(s) FAILED:")
        for area, name, ok, detail in RESULTS:
            if not ok:
                print(f"  [{area}] {name}\n        -> {detail}")
        sys.exit(1)
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
