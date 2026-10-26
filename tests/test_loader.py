import csv
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from generate_data import main as generate
from loader import DEFAULT_URL, get_engine, load
from models import Account, Base, Contact
from pipeline import run

ACCT_HEADER = ["ACCT_ID", "ACCT_NAME", "CITY", "STATE", "PHONE", "CREATED"]
CONTACT_HEADER = ["CONTACT_ID", "ACCT_ID", "FIRST", "LAST", "EMAIL", "PHONE", "TITLE"]


@pytest.fixture
def engine(tmp_path):
    eng = get_engine(f"sqlite:///{(tmp_path / 'target.db').as_posix()}")
    yield eng
    eng.dispose()


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def small_result(tmp_path):
    write_csv(tmp_path / "a.csv", ACCT_HEADER, [
        ["A1", "Acme LLC", "Houston", "TX", "713-555-0142", "2021-03-04"],
        ["A2", "Beta Inc", "Austin", "Texas", "512-555-0100", "03/05/2021"],
    ])
    write_csv(tmp_path / "c.csv", CONTACT_HEADER, [
        ["C1", "A2", "Ava", "Reyes", "ava@example.com", "", "Owner"],
        ["C2", "A1", "Leo", "Chen", "leo@example.com", "", "IT Lead"],
    ])
    return run(tmp_path / "a.csv", tmp_path / "c.csv")


def count(engine, model):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model))


def test_load_matches_ground_truth_counts(tmp_path, engine):
    generate(tmp_path)
    expected = json.loads((tmp_path / "expected.json").read_text())
    result = run(tmp_path / "legacy_accounts.csv", tmp_path / "legacy_contacts.csv")
    counts = load(result, engine)
    assert counts == {"accounts": expected["accounts"]["loaded"],
                      "contacts": expected["contacts"]["loaded"]}
    assert count(engine, Account) == expected["accounts"]["loaded"]
    assert count(engine, Contact) == expected["contacts"]["loaded"]


def test_contacts_point_at_the_right_account(tmp_path, engine):
    load(small_result(tmp_path), engine)
    with Session(engine) as session:
        rows = session.execute(
            select(Contact.email, Account.legacy_id)
            .join(Account, Contact.account_id == Account.id)
        ).all()
    assert dict(rows) == {"ava@example.com": "A2", "leo@example.com": "A1"}


def test_dry_run_reports_counts_but_keeps_no_rows(tmp_path, engine):
    counts = load(small_result(tmp_path), engine, dry_run=True)
    assert counts == {"accounts": 2, "contacts": 2}
    assert count(engine, Account) == 0
    assert count(engine, Contact) == 0


def test_rerun_fails_and_changes_nothing(tmp_path, engine):
    result = small_result(tmp_path)
    load(result, engine)
    with pytest.raises(IntegrityError):
        load(result, engine)
    assert count(engine, Account) == 2
    assert count(engine, Contact) == 2


def test_database_enforces_foreign_keys(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Contact(legacy_id="C9", account_id=999, email="x@example.com"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_default_url_is_sqlite_file(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert str(get_engine().url) == DEFAULT_URL


def test_database_url_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///elsewhere.db")
    assert str(get_engine().url) == "sqlite:///elsewhere.db"
