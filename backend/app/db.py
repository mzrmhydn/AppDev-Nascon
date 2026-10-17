# Database engine, session factory and the FastAPI get_db dependency (NFR-3, NFR-7).
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Default pool (5 + 10) would queue the 20 simultaneous checkout requests (NFR-3).
    engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=10, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
