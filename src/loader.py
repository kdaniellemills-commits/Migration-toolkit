"""Write pipeline output into a database, all-or-nothing.

Default target is a local SQLite file, so the toolkit runs with no setup.
Set the DATABASE_URL environment variable to point at another database
(for example Postgres; install its driver first).

Behavior worth knowing:
  - One transaction: if anything fails, nothing is written.
  - dry_run executes every insert inside the transaction so the database's own
    constraints are exercised, then rolls back. Empty tables may still be created.
  - v1 loads into an empty target. Re-running the same load violates the unique
    legacy_id constraint and fails safely without duplicating anything.
"""
import os
from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from models import Account, Base, Contact

DEFAULT_URL = "sqlite:///migration.db"


def get_engine(url=None):
    url = url or os.environ.get("DATABASE_URL") or DEFAULT_URL
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless asked; Postgres always enforces them.
        # Turning this on makes both databases behave the same way.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def _to_date(iso_text):
    return date.fromisoformat(iso_text) if iso_text else None


def load(result, engine, dry_run=False):
    """Insert loaded accounts, then contacts. Returns the counts written."""
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        try:
            by_legacy_id = {}
            for a in result["accounts"]["loaded"]:
                account = Account(
                    legacy_id=a["legacy_id"], name=a["name"], city=a["city"],
                    state=a["state"], phone=a["phone"], created=_to_date(a["created"]))
                session.add(account)
                by_legacy_id[a["legacy_id"]] = account
            session.flush()  # assigns each account its new primary key

            for c in result["contacts"]["loaded"]:
                session.add(Contact(
                    legacy_id=c["legacy_id"],
                    account_id=by_legacy_id[c["account_legacy_id"]].id,
                    first_name=c["first_name"], last_name=c["last_name"],
                    email=c["email"], phone=c["phone"], title=c["title"]))
            session.flush()

            counts = {"accounts": len(result["accounts"]["loaded"]),
                      "contacts": len(result["contacts"]["loaded"])}
            if dry_run:
                session.rollback()
            else:
                session.commit()
            return counts
        except Exception:
            session.rollback()
            raise
