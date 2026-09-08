"""
Database engine and session management.

Supabase PostgreSQL is the single source of truth for every scan record.
If Supabase is configured but unreachable the app fails fast with actionable
instructions rather than silently writing to a throwaway local SQLite file
(which is what previously caused "my scans aren't in Supabase").
"""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

SETUP_HELP = """
──────────────────────────────────────────────────────────────────────────────
 SUPABASE POSTGRES IS NOT CONFIGURED
──────────────────────────────────────────────────────────────────────────────
 Scans must persist to Supabase, so the API will not start on a local
 SQLite file. Add ONE of the following to backend/.env:

 Option A (recommended) — just the database password:
     SUPABASE_DB_PASSWORD=<your Supabase database password>

 Option B — the full connection string. Copy it from
 Supabase Dashboard -> Project Settings -> Database -> Connection string -> URI
 (use the "Connection pooling" / Session mode URI if your network blocks 5432):
     DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

 To intentionally develop offline against SQLite, set:
     REQUIRE_SUPABASE=false
──────────────────────────────────────────────────────────────────────────────
""".strip()


class SupabaseConnectionError(RuntimeError):
    """Raised when Supabase Postgres is required but not usable."""


def _build_engine():
    db_url = settings.resolved_database_url()
    is_postgres = db_url.startswith("postgresql")

    if not is_postgres:
        if settings.REQUIRE_SUPABASE:
            raise SupabaseConnectionError(SETUP_HELP)
        logger.warning(
            "REQUIRE_SUPABASE=false — falling back to local SQLite. "
            "Scan records will NOT appear in Supabase."
        )
        return create_engine(
            "sqlite:///./border_screening.db",
            connect_args={"check_same_thread": False},
        ), False

    # Supabase offers two connection routes and they need different settings.
    #
    #   Direct  (db.<ref>.supabase.co:5432)          — real Postgres session.
    #   Pooler  (aws-N-<region>.pooler.supabase.com) — Supavisor in front of it.
    #             :5432 session mode, :6543 transaction mode.
    #
    # In transaction mode a backend connection is only held for the duration of
    # a single transaction, so server-side prepared statements leak across
    # clients and blow up with "prepared statement _pg3_N already exists".
    # psycopg3 prepares automatically after 5 executions, so it must be disabled.
    is_pooler = ".pooler.supabase.com" in db_url
    is_transaction_mode = is_pooler and ":6543" in db_url

    connect_args: dict = {
        "connect_timeout": 15,
        "application_name": "border-screening-api",
    }

    if is_transaction_mode:
        # None disables psycopg3's automatic prepared statements entirely.
        connect_args["prepare_threshold"] = None
    else:
        # Direct sessions are long-lived and Supabase reaps idle ones, so keep
        # the socket warm. Supavisor manages this itself in pooled mode.
        connect_args.update(
            {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            }
        )

    engine_kwargs: dict = {"echo": False, "connect_args": connect_args}

    if is_transaction_mode:
        # Supavisor is already the pool. A second pool on top of it just holds
        # connections open against the tenant limit, so don't keep one.
        from sqlalchemy.pool import NullPool

        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs.update(
            {
                "pool_pre_ping": True,
                "pool_size": 5,
                "max_overflow": 10,
                "pool_recycle": 300,
            }
        )

    candidate = create_engine(db_url, **engine_kwargs)

    try:
        with candidate.connect() as conn:
            conn.exec_driver_sql("select 1")
    except Exception as exc:  # noqa: BLE001 - surface the real cause to the operator
        safe_target = db_url.split("@")[-1].split("?")[0] if "@" in db_url else "supabase"
        message = (
            f"Could not connect to Supabase Postgres at {safe_target}: "
            f"{type(exc).__name__}: {exc}"
        )
        if settings.REQUIRE_SUPABASE:
            raise SupabaseConnectionError(f"{message}\n\n{SETUP_HELP}") from exc
        logger.error("%s — falling back to SQLite.", message)
        return create_engine(
            "sqlite:///./border_screening.db",
            connect_args={"check_same_thread": False},
        ), False

    logger.info(
        "Connected to Supabase PostgreSQL (%s) via %s.",
        db_url.split("@")[-1].split("?")[0],
        "Supavisor transaction pooler" if is_transaction_mode
        else "Supavisor session pooler" if is_pooler
        else "direct connection",
    )
    return candidate, True


engine, USING_SUPABASE = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - dev-only path
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass
