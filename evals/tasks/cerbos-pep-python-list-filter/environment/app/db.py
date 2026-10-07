"""SQLAlchemy models and session for the expenses database.

DATABASE_URL selects the database (default: sqlite:///<this dir>/data/expenses.db).
"""

import os
from pathlib import Path

from sqlalchemy import Boolean, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DEFAULT_DB = Path(__file__).with_name("data") / "expenses.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    roles: Mapped[str] = mapped_column(String)  # comma-separated, e.g. "employee,finance"
    department: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String)
    review_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, index=True)
    department: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)  # draft, submitted, approved, rejected
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(String, default="")


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
