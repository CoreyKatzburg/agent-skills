"""Database connection, session handling, and a UTC-safe datetime column type."""

from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    # FastAPI runs sync routes on worker threads, so the connection must be usable from any thread.
    # The timeout makes a writer wait for another writer instead of failing straight away.
    connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {},
)

if is_sqlite:

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        # WAL lets readers keep reading while someone writes.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    with SessionLocal() as session:
        yield session


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Stores datetimes as UTC and always hands them back with the UTC timezone attached.

    SQLite drops timezones. Without this, the API would send times without a "Z" suffix,
    and browsers would wrongly read them as local time.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
