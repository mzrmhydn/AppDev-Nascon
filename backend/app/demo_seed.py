# Demo data for the judges' walkthrough (contract §2.13, plan 09). Runs at startup and via
# POST /api/v1/dev/demo-seed; NEVER from /audit/v1/reset. Idempotent: every block skips work already done.
# Events and roster go through the real services, so signatures and audit entries are genuine.
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Club, League, Match, Product, RosterLeague, Showcase, Variant
from app.services import events, roster

log = logging.getLogger("nascon")

ALPHA_CLUBS = ["club-alpha-1", "club-alpha-2", "demo-club-alpha-3", "demo-club-alpha-4"]

PROFILES = {
    "club-alpha-1": ("Alpha United", "AUN", "#0B5FFF", "Alpha Arena", "Islamabad", 33.6844, 73.0479,
                     [("Usman Tariq", "coach"), ("Sana Mir", "manager"), ("Dr. Faisal Iqbal", "physio")]),
    "club-alpha-2": ("Alpha Rovers", "ARO", "#FFB020", "Rovers Ground", "Rawalpindi", 33.5651, 73.0169,
                     [("Kamran Akmal", "coach"), ("Hina Baloch", "manager"), ("Dr. Ayesha Noor", "physio")]),
    "demo-club-alpha-3": ("Margalla FC", "MFC", "#16A34A", "Margalla Stadium", "Islamabad", 33.7380, 73.0844,
                          [("Imran Nazir", "coach"), ("Zainab Raza", "manager"), ("Dr. Bilal Shah", "physio")]),
    "demo-club-alpha-4": ("Rawal City", "RCY", "#DC2626", "Rawal Lake Park", "Islamabad", 33.7000, 73.1250,
                          [("Saeed Ajmal", "coach"), ("Mariam Khan", "manager"), ("Dr. Hamid Ali", "physio")]),
    "club-beta-1": ("Beta Strikers", "BST", "#0E9F6E", "Beta Dome", "Lahore", 31.5204, 74.3587,
                    [("Shahid Afridi", "coach"), ("Nida Dar", "manager"), ("Dr. Omar Javed", "physio")]),
}

FIRST = ["Ahmed", "Hamza", "Bilal", "Usman", "Zain", "Faisal", "Saad", "Danish", "Hassan", "Owais", "Talha",
         "Junaid", "Rizwan", "Waqas", "Shoaib", "Fahad"]
LAST = ["Khan", "Ahmed", "Malik", "Qureshi", "Butt", "Chaudhry", "Sheikh", "Mirza", "Raza", "Iqbal", "Abbasi",
        "Siddiqui"]
POSITIONS = ["gk", "gk", "df", "df", "df", "df", "mf", "mf", "mf", "fw", "fw", "fw"]
ROLES = ["captain", "substitute", "vice_captain", "starter", "starter", "starter", "starter", "starter",
         "starter", "starter", "starter", "substitute"]


def _profile(club_id):
    name, short, color, venue, city, lat, lng, staff = PROFILES[club_id]
    handle = "@" + name.lower().replace(" ", "")
    return {
        "home_venue": {"name": venue, "city": city, "lat": lat, "lng": lng},
        "socials": {"instagram": handle, "x": handle, "facebook": None},
        "staff": [{"name": n, "role": r} for n, r in staff],
        "stats": [{"season": "2025", "played": 18, "won": 10, "drawn": 4, "lost": 4, "trophies": 1},
                  {"season": "2024", "played": 18, "won": 8, "drawn": 5, "lost": 5, "trophies": 0}],
    }


def seed_clubs(db):
    for club_id, (name, short, color, *_rest) in PROFILES.items():
        club = db.get(Club, club_id)
        if club is None:
            tenant = "tenant-beta" if club_id == "club-beta-1" else "tenant-alpha"
            club = Club(club_id=club_id, tenant_id=tenant, name=name)
            db.add(club)
        club.short_name, club.primary_color, club.profile = short, color, _profile(club_id)
    db.commit()


def seed_leagues_and_fixtures(db):
    day = datetime.now(timezone.utc).date()
    lg = db.get(League, "league-alpha-1")
    lg.name, lg.season, lg.sport_id, lg.teams = "Alpha Premier League", "2026", "football", list(ALPHA_CLUBS)
    lg.points, lg.qualification_spots = {"win": 3, "draw": 1, "loss": 0}, 2
    c1, c2, c3, c4 = ALPHA_CLUBS
    pairs = [(c1, c2, 1), (c3, c4, 1), (c1, c3, 2), (c2, c4, 2), (c1, c4, 3), (c2, c3, 3)]
    for i, (home, away, rnd) in enumerate(pairs, start=1):
        if db.get(Match, f"demo-m{i}") is None:
            when = day + timedelta(days=0 if i <= 4 else 1)
            db.add(Match(match_id=f"demo-m{i}", league_id=lg.league_id, sport_id="football", home_team_id=home,
                         away_team_id=away, round=rnd, scheduled_at=f"{when.isoformat()}T{8 + i:02d}:00:00Z",
                         venue=PROFILES[home][3]))
    cup = db.get(League, "league-alpha-2")
    cup.name, cup.season, cup.sport_id, cup.teams = "Alpha Basketball Cup", "2026", "basketball", [c1, c2]
    cup.points, cup.qualification_spots = {"win": 2, "draw": 0, "loss": 0}, 1
    for i, (home, away) in enumerate([(c1, c2), (c2, c1)], start=1):
        if db.get(Match, f"demo-b{i}") is None:
            db.add(Match(match_id=f"demo-b{i}", league_id=cup.league_id, sport_id="basketball",
                         home_team_id=home, away_team_id=away, round=i,
                         scheduled_at=f"{(day + timedelta(days=i)).isoformat()}T18:00:00Z",
                         venue=PROFILES[home][3]))
    db.commit()


def seed_events(db):
    def ev(n, match, etype, payload):
        return {"event_id": f"demo-evt-{match}-{n}", "match_id": match, "type": etype, "payload": payload}

    def goal(team):
        return {"team_id": team, "event_type": "goal"}

    c1, c2, c3, c4 = ALPHA_CLUBS
    scripts = {
        "demo-m1": [("match_start", {}), ("score", goal(c1)), ("score", goal(c2)),
                    ("discipline", {"team_id": c2, "points": -1}), ("score", goal(c1)), ("match_end", {})],
        "demo-m2": [("match_start", {}), ("score", goal(c3)), ("score", goal(c4)), ("match_end", {})],
        "demo-m3": [("match_start", {}), ("score", goal(c1)), ("score", goal(c3)),
                    ("compensation", {"compensates": "demo-evt-demo-m3-3", "reason": "Offside on review"}),
                    ("match_end", {})],
        "demo-m4": [("match_start", {}), ("score", goal(c2)), ("score", goal(c4))],
    }
    for match_id, steps in scripts.items():
        if events.match_version(db, match_id) > 0:
            continue  # already played
        for n, (etype, payload) in enumerate(steps, start=1):
            events.append_event(db, ev(n, match_id, etype, payload))


def seed_roster(db):
    if db.get(RosterLeague, "league-alpha-1") is not None:
        return
    players = []
    k = 0
    for club_index, club_id in enumerate(ALPHA_CLUBS):
        for slot in range(12):
            if club_id == "club-alpha-1" and slot == 0:
                pid, name = "player-alpha-1", "Ali Khan"
            elif club_id == "club-alpha-2" and slot == 2:
                pid, name = "player-alpha-2", "Bilal Ahmed"
            else:
                pid = f"demo-p-{club_index + 1}-{slot + 1:02d}"
                name = f"{FIRST[k % len(FIRST)]} {LAST[(k * 7) % len(LAST)]}"
                k += 1
            players.append({"player_id": pid, "name": name, "position": POSITIONS[slot], "squad_id": club_id,
                            "role": ROLES[slot]})
    roster.setup(db, {
        "league": {"league_id": "league-alpha-1", "tenant_id": "tenant-alpha", "sport_id": "football",
                   "transfer_window": {"open": "2026-10-01", "close": "2026-10-31"},
                   "max_squad_size": 25, "required_positions": {"gk": 1}},
        "squads": [{"squad_id": c, "club_id": c, "tenant_id": "tenant-alpha", "name": PROFILES[c][0]}
                   for c in ALPHA_CLUBS],
        "players": players,
        "matches_in_progress": [],
    })


def seed_store(db):
    items = [
        ("demo-prod-scarf", "Alpha Supporters Scarf", "accessory", [("demo-var-scarf", None, "Blue", 150000, 20)]),
        ("demo-prod-cap", "Alpha Snapback Cap", "accessory", [("demo-var-cap-black", None, "Black", 120000, 10),
                                                              ("demo-var-cap-white", None, "White", 120000, 10)]),
        ("demo-prod-wallpaper", "Matchday Wallpaper Pack", "digital",
         [("demo-var-wallpaper", None, None, 30000, 999)]),
    ]
    for product_id, name, category, variants in items:
        if db.get(Product, product_id) is not None:
            continue
        db.add(Product(product_id=product_id, tenant_id="tenant-alpha", club_id="club-alpha-1", name=name,
                       category=category, description=f"Official {name.lower()}."))
        for variant_id, size, color, price, stock in variants:
            db.add(Variant(variant_id=variant_id, product_id=product_id, size=size, color=color,
                           price_minor=price, stock=stock, reserved=0))
    if db.get(Showcase, "demo-m4") is None:
        db.add(Showcase(match_id="demo-m4", product_id="prod-jersey-001", pinned_at=datetime.now(timezone.utc)))
    db.commit()


def seed_demo(db):
    """Each block is idempotent; the order matters (clubs -> leagues -> events -> roster -> store)."""
    seed_clubs(db)
    seed_leagues_and_fixtures(db)
    seed_events(db)
    seed_roster(db)
    seed_store(db)


def seed_demo_safely(session_factory):
    """Startup wrapper: a demo-data bug must never stop startup or /health."""
    try:
        with session_factory() as db:
            seed_demo(db)
        log.info("demo data seeded")
    except Exception:
        log.exception("demo seed failed (ignored)")
