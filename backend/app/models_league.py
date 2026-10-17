# Tables for sports, leagues, match streams and the append-only event log (FR-1.1, FR-1.4, spec §5.6–5.10).
# match_events is never UPDATEd or DELETEd (only /reset truncates it); scores are rebuilt from it.
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# JSONB on Postgres; plain JSON elsewhere (lets tests run on SQLite).
JSONB_ = JSON().with_variant(JSONB, "postgresql")


def _now():
    return datetime.now(timezone.utc)


class Sport(Base):
    __tablename__ = "sports"
    sport_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config: Mapped[dict] = mapped_column(JSONB_)  # normalised config, same format for seed + mystery sports
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)


class League(Base):
    __tablename__ = "leagues"
    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    season: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sport_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    teams: Mapped[list] = mapped_column(JSONB_, default=list)
    points: Mapped[dict] = mapped_column(JSONB_, default=lambda: {"win": 3, "draw": 1, "loss": 0})
    tie_break_order: Mapped[list | None] = mapped_column(JSONB_, nullable=True)  # None = sport's order
    qualification_spots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lots_seed: Mapped[int] = mapped_column(Integer, default=42)
    created_via: Mapped[str] = mapped_column(String(16), default="seed")  # "seed" or "audit"


class Match(Base):
    """A match stream: a league fixture or a stand-alone match created by match_init."""
    __tablename__ = "matches"
    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    league_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sport_id: Mapped[str] = mapped_column(String(64))
    home_team_id: Mapped[str] = mapped_column(String(64))
    away_team_id: Mapped[str] = mapped_column(String(64))
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(200), nullable=True)


class MatchEvent(Base):
    __tablename__ = "match_events"
    __table_args__ = (UniqueConstraint("match_id", "sequence"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(64), ForeignKey("matches.match_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)  # unique across ALL matches
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSONB_)
    signature: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSONB_)  # raw body, for idempotent replay comparison
    response: Mapped[dict] = mapped_column(JSONB_)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def as_dict(self):
        """Shape used by domain.scoring.project()."""
        return {
            "sequence": self.sequence, "event_id": self.event_id, "type": self.type,
            "payload": self.payload, "signature": self.signature, "match_id": self.match_id,
        }
