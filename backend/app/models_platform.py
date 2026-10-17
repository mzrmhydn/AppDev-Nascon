# Platform tables: tenants, users, clubs, players, settings, store, idempotency, offline sync, showcase
# (FR-2.1, FR-2.3, FR-5.1, NFR-3, spec §5.5). Roster tables are added with plan 07.
from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# JSONB on Postgres; plain JSON elsewhere (lets tests run on SQLite).
JSONB_ = JSON().with_variant(JSONB, "postgresql")


def _now():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    primary_color: Mapped[str] = mapped_column(String(16))
    accent_color: Mapped[str] = mapped_column(String(16))


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(200))
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    league_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    club_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    player_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Club(Base):
    __tablename__ = "clubs"
    club_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    profile: Mapped[dict] = mapped_column(JSONB_, default=dict)  # venue, socials, staff, stats


class Player(Base):
    """One players table for RBAC baseline players and players created by /roster/setup."""
    __tablename__ = "players"
    player_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(32), nullable=True)
    club_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


# ---------- store (plan 06) ----------

class Product(Base):
    __tablename__ = "products"
    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    club_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Variant(Base):
    __tablename__ = "variants"
    # Second safety net for NFR-3: even a bug cannot store negative stock.
    __table_args__ = (CheckConstraint("stock >= 0", name="stock_not_negative"),
                      CheckConstraint("reserved >= 0", name="reserved_not_negative"))
    variant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64))
    size: Mapped[str | None] = mapped_column(String(16), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price_minor: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer)
    reserved: Mapped[int] = mapped_column(Integer, default=0)


class PriceChange(Base):
    __tablename__ = "price_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_id: Mapped[str] = mapped_column(String(64))
    price_minor: Mapped[int] = mapped_column(Integer)
    effective_at: Mapped[str] = mapped_column(String(32))  # ISO 8601 UTC


class DiscountCode(Base):
    __tablename__ = "discount_codes"
    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    percent: Mapped[int] = mapped_column(Integer)


class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    request: Mapped[dict | None] = mapped_column(JSONB_, nullable=True)  # raw body for replay comparison
    response: Mapped[dict | None] = mapped_column(JSONB_, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------- idempotency / offline / showcase ----------

class Idempotency(Base):
    __tablename__ = "idempotency"
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    request: Mapped[dict] = mapped_column(JSONB_)
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSONB_)


class OfflineAction(Base):
    __tablename__ = "offline_actions"
    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request: Mapped[dict] = mapped_column(JSONB_)
    result: Mapped[dict] = mapped_column(JSONB_)


class Showcase(Base):
    __tablename__ = "showcase"
    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64))
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------- roster (plan 07, FR-2.2, spec §5.11) ----------

class RosterLeague(Base):
    __tablename__ = "roster_leagues"
    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    sport_id: Mapped[str] = mapped_column(String(64))
    window_open: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD, inclusive
    window_close: Mapped[str] = mapped_column(String(10))
    max_squad_size: Mapped[int] = mapped_column(Integer)
    required_positions: Mapped[dict] = mapped_column(JSONB_, default=dict)


class Squad(Base):
    __tablename__ = "squads"
    squad_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    league_id: Mapped[str] = mapped_column(String(64), index=True)
    club_id: Mapped[str] = mapped_column(String(64))
    tenant_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))


class Registration(Base):
    """A player's membership of a squad for a date range [start_date, end_date). end_date NULL = open."""
    __tablename__ = "registrations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(String(64), index=True)
    league_id: Mapped[str] = mapped_column(String(64), index=True)
    squad_id: Mapped[str] = mapped_column(String(64))
    parent_squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registration_type: Mapped[str] = mapped_column(String(16))  # initial | transfer | loan
    start_date: Mapped[str] = mapped_column(String(10))
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # exclusive
    loan_end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    role: Mapped[str] = mapped_column(String(16))


class RosterAudit(Base):
    """Append-only roster history (who, when, why)."""
    __tablename__ = "roster_audit"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[str] = mapped_column(String(16), unique=True)
    player_id: Mapped[str] = mapped_column(String(64), index=True)
    league_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    from_squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_squad_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_date: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(32))
    who: Mapped[str] = mapped_column(String(200))
    when: Mapped[str] = mapped_column(String(20))
    why: Mapped[str] = mapped_column(String(1000))
    loan_registration_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # for loan_return dedupe


class LiveMatch(Base):
    """matches_in_progress from /roster/setup (edge case 6)."""
    __tablename__ = "matches_in_progress"
    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    home_squad_id: Mapped[str] = mapped_column(String(64))
    away_squad_id: Mapped[str] = mapped_column(String(64))
