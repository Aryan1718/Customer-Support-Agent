import os
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


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


@lru_cache
def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Add your Neon connection string to .env.")

    return create_engine(_with_neon_defaults(database_url), pool_pre_ping=True)


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

