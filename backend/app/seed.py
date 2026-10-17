# Baseline data for /audit/v1/reset and first startup (spec §5.5). Exact ids; repeatable: wipe then insert.
import logging

from sqlalchemy import text

from app.auth import hash_password
from app.db import Base
from app.domain.seed_sports import SEED_SPORTS
from app.models import (Club, DiscountCode, League, Player, Product, Setting, Sport, Tenant, User,
                        Variant)

log = logging.getLogger("nascon")

DEMO_PASSWORD = "Nascon@26"
SPORT_ORDER = ["football", "basketball", "cricket", "esports"]
TENANT_ORDER = ["tenant-alpha", "tenant-beta"]

# Hash once per process: PBKDF2 is deliberately slow and /reset must stay well under 10 s.
_password_hash = None


def _demo_hash():
    global _password_hash
    if _password_hash is None:
        _password_hash = hash_password(DEMO_PASSWORD)
    return _password_hash


def wipe_all(db):
    """Delete every row of every table (matches, events, leagues, rosters, orders, custom sports...)."""
    tables = [t.name for t in Base.metadata.sorted_tables]
    if db.bind.dialect.name == "postgresql":
        db.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
    else:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())


def insert_baseline(db, seed, stock):
    db.add_all([
        Tenant(tenant_id="tenant-alpha", name="Alpha Sports", primary_color="#0B5FFF", accent_color="#FFB020"),
        Tenant(tenant_id="tenant-beta", name="Beta Athletics", primary_color="#0E9F6E", accent_color="#F05252"),
    ])
    db.add_all([
        Club(club_id="club-alpha-1", tenant_id="tenant-alpha", name="Alpha United", short_name="ALU",
             primary_color="#0B5FFF", profile={}),
        Club(club_id="club-alpha-2", tenant_id="tenant-alpha", name="Alpha Rovers", short_name="ALR",
             primary_color="#FFB020", profile={}),
        Club(club_id="club-beta-1", tenant_id="tenant-beta", name="Beta Strikers", short_name="BST",
             primary_color="#0E9F6E", profile={}),
    ])
    db.add_all([
        Player(player_id="player-alpha-1", name="Ali Khan", position="gk", club_id="club-alpha-1",
               tenant_id="tenant-alpha"),
        Player(player_id="player-alpha-2", name="Bilal Ahmed", position="df", club_id="club-alpha-2",
               tenant_id="tenant-alpha"),
        Player(player_id="player-beta-1", name="Hamza Raza", position="fw", club_id="club-beta-1",
               tenant_id="tenant-beta"),
    ])
    db.add_all([
        League(league_id="league-alpha-1", tenant_id="tenant-alpha", name="Alpha Premier League", season="2026",
               teams=[], lots_seed=seed, created_via="seed"),
        League(league_id="league-alpha-2", tenant_id="tenant-alpha", name="Alpha Basketball Cup", season="2026",
               teams=[], lots_seed=seed, created_via="seed"),
        League(league_id="league-beta-1", tenant_id="tenant-beta", name="Beta League", season="2026",
               teams=[], lots_seed=seed, created_via="seed"),
    ])
    pw = _demo_hash()
    db.add_all([
        User(user_id="user-admin", email="admin@nascon.test", password_hash=pw, role="super_admin",
             display_name="Platform Admin"),
        User(user_id="user-organizer", email="organizer@nascon.test", password_hash=pw, role="league_organizer",
             display_name="League Organizer", tenant_id="tenant-alpha", league_id="league-alpha-1"),
        User(user_id="user-manager", email="manager@nascon.test", password_hash=pw, role="club_manager",
             display_name="Club Manager", tenant_id="tenant-alpha", club_id="club-alpha-1"),
        User(user_id="user-player", email="player@nascon.test", password_hash=pw, role="player",
             display_name="Ali Khan", tenant_id="tenant-alpha", club_id="club-alpha-1",
             player_id="player-alpha-1"),
        User(user_id="user-viewer", email="viewer@nascon.test", password_hash=pw, role="viewer",
             display_name="General Viewer", tenant_id="tenant-alpha"),
    ])
    db.add(Product(product_id="prod-jersey-001", tenant_id="tenant-alpha", club_id="club-alpha-1",
                   name="Home Jersey 2026", category="apparel", description="Official Alpha United home jersey"))
    db.add_all([
        Variant(variant_id="var-jersey-001-M", product_id="prod-jersey-001", size="M", color="Blue",
                price_minor=450000, stock=stock["var-jersey-001-M"], reserved=0),
        Variant(variant_id="var-jersey-001-L", product_id="prod-jersey-001", size="L", color="Blue",
                price_minor=450000, stock=stock["var-jersey-001-L"], reserved=0),
    ])
    db.add(DiscountCode(code="WELCOME10", percent=10))
    for sport_id in SPORT_ORDER:
        db.add(Sport(sport_id=sport_id, config=SEED_SPORTS[sport_id], is_seed=True))
    db.add(Setting(key="last_reset_seed", value=str(seed)))


def reset_baseline(db, seed, stock):
    """Wipe everything and re-create the baseline in ONE transaction."""
    wipe_all(db)
    insert_baseline(db, seed, stock)
    db.commit()


def is_seeded(db):
    return db.get(Tenant, "tenant-alpha") is not None


def last_reset_seed(db):
    row = db.get(Setting, "last_reset_seed")
    return int(row.value) if row else 42
