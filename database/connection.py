import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


@dataclass(frozen=True)
class DatabasePoolSettings:
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int


def _with_neon_defaults(database_url: str) -> str:
    url = database_url.strip()

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")

    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def get_database_pool_settings() -> DatabasePoolSettings:
    return DatabasePoolSettings(
        pool_size=_env_int("DB_POOL_SIZE", 2, minimum=1),
        max_overflow=_env_int("DB_MAX_OVERFLOW", 1, minimum=0),
        pool_timeout=_env_int("DB_POOL_TIMEOUT", 10, minimum=1),
        pool_recycle=_env_int("DB_POOL_RECYCLE", 300, minimum=1),
    )


@lru_cache
def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Add your Neon connection string to .env.")

    pool_settings = get_database_pool_settings()

    return create_engine(
        _with_neon_defaults(database_url),
        pool_pre_ping=True,
        pool_size=pool_settings.pool_size,
        max_overflow=pool_settings.max_overflow,
        pool_timeout=pool_settings.pool_timeout,
        pool_recycle=pool_settings.pool_recycle,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()
    return True


def _env_int(name: str, default: int, minimum: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    if parsed < minimum:
        return default

    return parsed
